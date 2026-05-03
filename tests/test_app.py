import os

from fastapi.testclient import TestClient

import main


def client_with_temp_db(tmp_path):
    os.environ["RELEASE_DASHBOARD_DB"] = str(tmp_path / "test.db")
    main.init_db()
    return TestClient(main.app)


def test_health_endpoint(tmp_path):
    client = client_with_temp_db(tmp_path)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_list_deployment(tmp_path):
    client = client_with_temp_db(tmp_path)

    create_response = client.post(
        "/deployments",
        json={
            "version": "v1.2.3",
            "actor": "jenkins",
            "notes": "Smoke tests passed",
        },
    )
    list_response = client.get("/deployments")

    assert create_response.status_code == 201
    assert create_response.json()["version"] == "v1.2.3"
    assert create_response.json()["environment"] == "sandbox"
    assert list_response.json()[0]["environment"] == "sandbox"


def test_create_ignores_environment_selection_and_deploys_to_sandbox(tmp_path):
    client = client_with_temp_db(tmp_path)

    response = client.post(
        "/deployments",
        json={
            "environment": "prod",
            "version": "v9.9.9",
            "actor": "jenkins",
        },
    )

    assert response.status_code == 201
    assert response.json()["environment"] == "sandbox"


def test_promote_copies_latest_version_to_next_environment(tmp_path):
    client = client_with_temp_db(tmp_path)
    client.post(
        "/deployments",
        json={"version": "v2.0.0", "actor": "jenkins"},
    )

    response = client.post("/promote/sandbox?actor=jenkins")

    assert response.status_code == 200
    assert response.json()["environment"] == "dev"
    assert response.json()["version"] == "v2.0.0"
    assert response.json()["status"] == "promoted"
