pipeline {
    agent any

    environment {
        IMAGE_NAME = 'release-dashboard'
        APP_VERSION = "${env.BUILD_NUMBER}"
        PYTHON_BIN = 'python3.12'
    }

    stages {
        stage('Install') {
            steps {
                sh '${PYTHON_BIN} --version'
                sh '${PYTHON_BIN} -m venv .venv'
                sh '. .venv/bin/activate && python -m pip install --upgrade pip && python -m pip install -r requirements-dev.txt'
            }
        }

        stage('Test') {
            steps {
                sh '. .venv/bin/activate && pytest'
            }
        }

        stage('Build Image') {
            steps {
                sh 'docker build -t ${IMAGE_NAME}:${APP_VERSION} .'
            }
        }

        stage('Deploy to Sandbox') {
            when {
                branch 'dev'
            }
            steps {
                sh 'kubectl -n sandbox set image deployment/release-dashboard app=${IMAGE_NAME}:${APP_VERSION}'
                sh 'kubectl -n sandbox rollout status deployment/release-dashboard'
            }
        }

        stage('Promote to Dev') {
            when {
                branch 'main'
            }
            steps {
                input message: 'Promote this release to Dev?'
                sh 'kubectl -n dev set image deployment/release-dashboard app=${IMAGE_NAME}:${APP_VERSION}'
                sh 'kubectl -n dev rollout status deployment/release-dashboard'
            }
        }

        stage('Promote to UAT') {
            when {
                branch 'main'
            }
            steps {
                input message: 'Promote this release to UAT?'
                sh 'kubectl -n uat set image deployment/release-dashboard app=${IMAGE_NAME}:${APP_VERSION}'
                sh 'kubectl -n uat rollout status deployment/release-dashboard'
            }
        }

        stage('Promote to Prod') {
            when {
                branch 'main'
            }
            steps {
                input message: 'Promote this release to Production?'
                sh 'kubectl -n prod set image deployment/release-dashboard app=${IMAGE_NAME}:${APP_VERSION}'
                sh 'kubectl -n prod rollout status deployment/release-dashboard'
            }
        }
    }
}
