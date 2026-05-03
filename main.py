from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3
from typing import Iterable

from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field


APP_NAME = "Release Dashboard"
SANDBOX_ENVIRONMENT = "sandbox"
ENVIRONMENTS = (SANDBOX_ENVIRONMENT, "dev", "uat", "prod")
PROMOTION_FLOW = {
    SANDBOX_ENVIRONMENT: "dev",
    "dev": "uat",
    "uat": "prod",
}
DEFAULT_DATABASE_PATH = "release_dashboard.db"


class Deployment(BaseModel):
    id: int
    environment: str
    version: str
    status: str
    actor: str
    notes: str = ""
    created_at: str


class DeploymentCreate(BaseModel):
    version: str = Field(min_length=1, max_length=50)
    status: str = Field(default="deployed", min_length=1, max_length=30)
    actor: str = Field(default="release-bot", min_length=1, max_length=60)
    notes: str = Field(default="", max_length=240)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def database_path() -> str:
    return os.getenv("RELEASE_DASHBOARD_DB", DEFAULT_DATABASE_PATH)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    Path(database_path()).parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deployments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                environment TEXT NOT NULL,
                version TEXT NOT NULL,
                status TEXT NOT NULL,
                actor TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_deployments_environment_created_at
            ON deployments (environment, created_at DESC)
            """
        )


def row_to_deployment(row: sqlite3.Row) -> Deployment:
    return Deployment(**dict(row))


def latest_deployments() -> dict[str, Deployment | None]:
    results: dict[str, Deployment | None] = {env: None for env in ENVIRONMENTS}
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT d.*
            FROM deployments d
            JOIN (
                SELECT environment, MAX(id) AS latest_id
                FROM deployments
                GROUP BY environment
            ) latest
            ON d.environment = latest.environment AND d.id = latest.latest_id
            """
        ).fetchall()
    for row in rows:
        deployment = row_to_deployment(row)
        if deployment.environment in results:
            results[deployment.environment] = deployment
    return results


def deployment_history(limit: int = 20) -> list[Deployment]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM deployments
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [row_to_deployment(row) for row in rows]


def create_environment_deployment(
    environment: str,
    version: str,
    status_text: str,
    actor: str,
    notes: str = "",
) -> Deployment:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO deployments (environment, version, status, actor, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                environment,
                version,
                status_text,
                actor,
                notes,
                now_iso(),
            ),
        )
        deployment_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM deployments WHERE id = ?",
            (deployment_id,),
        ).fetchone()
    return row_to_deployment(row)


def create_deployment(payload: DeploymentCreate) -> Deployment:
    return create_environment_deployment(
        environment=SANDBOX_ENVIRONMENT,
        version=payload.version,
        status_text=payload.status,
        actor=payload.actor,
        notes=payload.notes or "Deployed to sandbox",
    )


def promote(source_environment: str, actor: str = "release-bot") -> Deployment:
    if source_environment not in PROMOTION_FLOW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{source_environment} cannot be promoted further",
        )

    latest = latest_deployments()
    source = latest[source_environment]
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No deployment found in {source_environment}",
        )

    target_environment = PROMOTION_FLOW[source_environment]
    return create_environment_deployment(
        environment=target_environment,
        version=source.version,
        status_text="promoted",
        actor=actor,
        notes=f"Promoted from {source_environment}",
    )


def status_class(deployment: Deployment | None) -> str:
    if deployment is None:
        return "empty"
    if deployment.status in {"failed", "rollback"}:
        return "warning"
    if deployment.status == "promoted":
        return "promoted"
    return "deployed"


def render_environment_cards(latest: dict[str, Deployment | None]) -> str:
    cards: list[str] = []
    for env in ENVIRONMENTS:
        deployment = latest[env]
        version = deployment.version if deployment else "No release"
        status_text = deployment.status if deployment else "waiting"
        actor = deployment.actor if deployment else "none"
        created_at = deployment.created_at if deployment else "not deployed yet"
        promote_button = ""
        if env in PROMOTION_FLOW and deployment:
            promote_button = f"""
                <form method="post" action="/ui/promote/{env}">
                    <button type="submit">Promote to {PROMOTION_FLOW[env].upper()}</button>
                </form>
            """

        cards.append(
            f"""
            <section class="env-card {status_class(deployment)}">
                <div>
                    <p class="eyebrow">{env}</p>
                    <h2>{version}</h2>
                </div>
                <dl>
                    <div><dt>Status</dt><dd>{status_text}</dd></div>
                    <div><dt>Actor</dt><dd>{actor}</dd></div>
                    <div><dt>Updated</dt><dd>{created_at}</dd></div>
                </dl>
                {promote_button}
            </section>
            """
        )
    return "\n".join(cards)


def render_history(history: Iterable[Deployment]) -> str:
    rows = []
    for item in history:
        rows.append(
            f"""
            <tr>
                <td>{item.id}</td>
                <td>{item.environment}</td>
                <td>{item.version}</td>
                <td>{item.status}</td>
                <td>{item.actor}</td>
                <td>{item.notes}</td>
                <td>{item.created_at}</td>
            </tr>
            """
        )
    return "\n".join(rows) or '<tr><td colspan="7">No deployments yet.</td></tr>'


def dashboard_html() -> str:
    latest = latest_deployments()
    history = deployment_history()
    return f"""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{APP_NAME}</title>
        <style>
            :root {{
                color-scheme: light;
                --ink: #17202a;
                --muted: #637083;
                --line: #d8dee9;
                --surface: #ffffff;
                --page: #f5f7fa;
                --header: #17202a;
                --header-muted: #c9d4e2;
                --accent: #137c75;
                --accent-dark: #0d5f5a;
                --warning: #b45309;
                --input: #ffffff;
                --shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
            }}
            body[data-theme="dark"] {{
                color-scheme: dark;
                --ink: #edf3f8;
                --muted: #aab7c7;
                --line: #334155;
                --surface: #151f2e;
                --page: #0b1120;
                --header: #050914;
                --header-muted: #b6c5d8;
                --accent: #2dd4bf;
                --accent-dark: #14b8a6;
                --warning: #f59e0b;
                --input: #0f172a;
                --shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
            }}
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                background: var(--page);
                color: var(--ink);
            }}
            header {{
                background: var(--header);
                color: white;
                padding: 28px clamp(18px, 4vw, 48px);
            }}
            .header-inner {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 18px;
            }}
            header p {{ color: var(--header-muted); margin: 6px 0 0; max-width: 780px; }}
            main {{ padding: 28px clamp(18px, 4vw, 48px) 48px; }}
            .toolbar {{
                display: grid;
                grid-template-columns: minmax(0, 1fr) auto auto;
                gap: 12px;
                align-items: end;
                background: var(--surface);
                border: 1px solid var(--line);
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 22px;
                box-shadow: var(--shadow);
            }}
            label {{ display: grid; gap: 6px; color: var(--muted); font-size: 13px; }}
            input, select, button {{
                min-height: 40px;
                border-radius: 6px;
                border: 1px solid var(--line);
                padding: 0 12px;
                font: inherit;
            }}
            input, select {{
                background: var(--input);
                color: var(--ink);
            }}
            button {{
                border: 0;
                background: var(--accent);
                color: #05251f;
                font-weight: 700;
                cursor: pointer;
            }}
            button:hover {{ background: var(--accent-dark); }}
            .theme-toggle {{
                flex: 0 0 auto;
                display: inline-flex;
                align-items: center;
                gap: 8px;
                min-width: 132px;
                border: 1px solid rgba(255, 255, 255, 0.24);
                background: rgba(255, 255, 255, 0.1);
                color: white;
            }}
            .theme-toggle:hover {{ background: rgba(255, 255, 255, 0.18); }}
            .theme-icon {{ font-size: 17px; line-height: 1; }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 16px;
            }}
            .env-card {{
                min-height: 238px;
                background: var(--surface);
                border: 1px solid var(--line);
                border-top: 5px solid var(--muted);
                border-radius: 8px;
                padding: 18px;
                display: grid;
                gap: 14px;
                align-content: start;
                box-shadow: var(--shadow);
            }}
            .env-card.deployed {{ border-top-color: var(--accent); }}
            .env-card.promoted {{ border-top-color: #365bd6; }}
            .env-card.warning {{ border-top-color: var(--warning); }}
            .eyebrow {{
                margin: 0 0 4px;
                color: var(--muted);
                font-weight: 800;
                letter-spacing: 0;
                text-transform: uppercase;
                font-size: 12px;
            }}
            h1, h2 {{ margin: 0; }}
            h2 {{ font-size: clamp(22px, 3vw, 32px); overflow-wrap: anywhere; }}
            dl {{ display: grid; gap: 10px; margin: 0; }}
            dl div {{ display: grid; grid-template-columns: 76px minmax(0, 1fr); gap: 10px; }}
            dt {{ color: var(--muted); }}
            dd {{ margin: 0; overflow-wrap: anywhere; }}
            .history {{
                margin-top: 28px;
                background: var(--surface);
                border: 1px solid var(--line);
                border-radius: 8px;
                overflow: auto;
                box-shadow: var(--shadow);
            }}
            .history h2 {{ padding: 18px 18px 0; font-size: 20px; }}
            table {{ width: 100%; border-collapse: collapse; min-width: 860px; }}
            th, td {{
                text-align: left;
                padding: 12px 18px;
                border-top: 1px solid var(--line);
                vertical-align: top;
            }}
            th {{ color: var(--muted); font-size: 13px; }}
            @media (max-width: 920px) {{
                .toolbar, .grid {{ grid-template-columns: 1fr 1fr; }}
            }}
            @media (max-width: 620px) {{
                .header-inner {{ flex-direction: column; }}
                .toolbar, .grid {{ grid-template-columns: 1fr; }}
            }}
        </style>
    </head>
    <body>
        <header>
            <div class="header-inner">
                <div>
                    <h1>{APP_NAME}</h1>
                    <p>Deploy new versions to Sandbox first, then promote the same release through Dev, UAT, and production.</p>
                </div>
                <button class="theme-toggle" id="themeToggle" type="button" aria-pressed="false">
                    <span class="theme-icon" aria-hidden="true">☾</span>
                    <span class="theme-label">Dark mode</span>
                </button>
            </div>
        </header>
        <main>
            <form class="toolbar" method="post" action="/ui/deployments">
                <label>Version
                    <input name="version" placeholder="v1.0.0" required maxlength="50">
                </label>
                <label>Actor
                    <input name="actor" value="release-bot" required maxlength="60">
                </label>
                <button type="submit">Deploy to Sandbox</button>
            </form>
            <div class="grid">
                {render_environment_cards(latest)}
            </div>
            <section class="history">
                <h2>Deployment History</h2>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Environment</th>
                            <th>Version</th>
                            <th>Status</th>
                            <th>Actor</th>
                            <th>Notes</th>
                            <th>Created</th>
                        </tr>
                    </thead>
                    <tbody>
                        {render_history(history)}
                    </tbody>
                </table>
            </section>
        </main>
        <script>
            const themeToggle = document.getElementById("themeToggle");
            const themeIcon = themeToggle.querySelector(".theme-icon");
            const themeLabel = themeToggle.querySelector(".theme-label");
            const savedTheme = localStorage.getItem("release-dashboard-theme");
            const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;

            function applyTheme(theme) {{
                const isDark = theme === "dark";
                document.body.dataset.theme = theme;
                themeToggle.setAttribute("aria-pressed", String(isDark));
                themeIcon.textContent = isDark ? "☀" : "☾";
                themeLabel.textContent = isDark ? "Light mode" : "Dark mode";
                localStorage.setItem("release-dashboard-theme", theme);
            }}

            applyTheme(savedTheme || (prefersDark ? "dark" : "light"));
            themeToggle.addEventListener("click", () => {{
                applyTheme(document.body.dataset.theme === "dark" ? "light" : "dark");
            }});
        </script>
    </body>
    </html>
    """


app = FastAPI(title=APP_NAME, version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "release-dashboard"}


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": os.getenv("APP_VERSION", "local-dev")}


@app.get("/deployments", response_model=list[Deployment])
def list_deployments(limit: int = 20) -> list[Deployment]:
    return deployment_history(limit=limit)


@app.post("/deployments", response_model=Deployment, status_code=status.HTTP_201_CREATED)
def api_create_deployment(payload: DeploymentCreate) -> Deployment:
    return create_deployment(payload)


@app.post("/promote/{source_environment}", response_model=Deployment)
def api_promote(source_environment: str, actor: str = "release-bot") -> Deployment:
    return promote(source_environment, actor)


@app.get("/", response_class=HTMLResponse)
def dashboard(_: Request) -> HTMLResponse:
    return HTMLResponse(dashboard_html())


@app.post("/ui/deployments")
def ui_create_deployment(
    version: str = Form(...),
    actor: str = Form("release-bot"),
) -> RedirectResponse:
    create_deployment(
        DeploymentCreate(
            version=version,
            actor=actor,
            notes="Created from dashboard",
        )
    )
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/ui/promote/{source_environment}")
def ui_promote(source_environment: str) -> RedirectResponse:
    promote(source_environment)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
