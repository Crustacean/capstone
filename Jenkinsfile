pipeline {
    agent any

    environment {
        APP_NAME = 'release-dashboard'
        IMAGE_NAME = "em22435/release-dashboard".toLowerCase()
        IMAGE_TAG = "${env.BUILD_NUMBER}"
        PYTHON_BIN = 'python3'

        KUBE_CA_CERT = '''MIIDBjCCAe6gAwIBAgIBATANBgkqhkiG9w0BAQsFADAVMRMwEQYDVQQDEwptaW5p
a3ViZUNBMB4XDTI2MDQyNDExNDkwOVoXDTM2MDQyMjExNDkwOVowFTETMBEGA1UE
AxMKbWluaWt1YmVDQTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAJno
8eiJ0FZapXZ40Fs5Oy2t9Y6hSwLQBFAHvuU3DiMeTBeL2iKYeKbnHYmaeD4IzzPK
otHoOzN//UugSWl6Jg8lcvhhULBiZ/u70TEVpY0QCmoV2NdPYYWAAxHMSGPvNQIj
WA05vWum4ge1iUKf34edrReu43mr0rD1lKVFpGy5zYdNqm9GCyM6kerbdO5ha/u5
LNMR/jDTk9OArnjlxoEtNm1i30vd4zbet8X9atQcjWELLDzFBQoKa5yVwTjf0UzD
ulABms3/ODeyKOMxSVaymzVOsqooHPrXfag8WBfx45kA3AvsrfxVdgyKiML2j39V
YGTZVPBveNOG5GzyaYkCAwEAAaNhMF8wDgYDVR0PAQH/BAQDAgKkMB0GA1UdJQQW
MBQGCCsGAQUFBwMCBggrBgEFBQcDATAPBgNVHRMBAf8EBTADAQH/MB0GA1UdDgQW
BBTUhbcJY6pJxshLV7U1niJOsQbj2zANBgkqhkiG9w0BAQsFAAOCAQEAcODYINxv
Digo62XfFCZWQBcm5iZiOWxU8wZ5uCi9TGCgZxEh0+GkaZkRv/PeBGzEqv/yIxFi
6CJmpPSLGrc8TNF7/+7p3F0dBftpXKe7mWV/VG/GHaDKFqU8HJv4L3oyIS5+hi8L
SCflgi/66BGNk2+AzXqDJiR/OWGz3lREHNsfOVdeE0YaAw3+ssaPdOEcNqSTST7M
cwQum+Eu9dWnqhHrDuzII+YgytFYh5Rmwar84+S2N6cKn9/rfIt5R3xi0pLL2QUs
+B2qL06zDdCBliAn9ohzxfnboQZPCtaimvSfFAwVyqWZfgN1VQ7IaJ/2gMUd121g
1aPRKygslsNMNQ=='''

        KUBE_CLUSTER = 'minikube'
        KUBE_CONTEXT = 'minikube'
        KUBE_CREDENTIALS = 'minikube-jenkins-secret'
        KUBE_NAMESPACE = 'dev'
        KUBE_SERVER_URL = 'https://192.168.49.2:8443'
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
                sh '. .venv/bin/activate && PYTHONPATH=. pytest'
            }
        }

        stage('Build Image') {
            steps {
                script {
                    dockerImage = docker.build("${IMAGE_NAME}:${IMAGE_TAG}")
                }
            }
        }

        stage('Push to Docker Hub') {
            steps {
                script {
                    docker.withRegistry("", 'docker-hub-credentials') {
                        dockerImage.push()
                        dockerImage.push("latest")
                    }
                }
            }
        }

        stage('Cleanup') {
            steps {
                sh "docker rmi ${IMAGE_NAME}:${IMAGE_TAG} || true"
                sh "docker rmi ${IMAGE_NAME}:latest || true"
            }
        }

        stage('Deploy to Sandbox') {
            when {
                branch 'dev'
            }
            environment {
                KUBE_NAMESPACE = 'sandbox'
            }
            steps {
                script {
                    env.DEPLOYMENT_NAME = "${env.APP_NAME}"
                    env.CONTAINER_NAME = 'app'
                    env.NAMESPACE_NAME = env.KUBE_NAMESPACE

                    withKubeConfig(
                        caCertificate: env.KUBE_CA_CERT,
                        clusterName: env.KUBE_CLUSTER,
                        contextName: env.KUBE_CONTEXT,
                        credentialsId: env.KUBE_CREDENTIALS,
                        namespace: env.KUBE_NAMESPACE,
                        restrictKubeConfigAccess: false,
                        serverUrl: env.KUBE_SERVER_URL
                    ) {
                        sh 'envsubst --version'
                        sh 'envsubst < deploy.yaml > prepared-deploy.yaml'
                        sh 'kubectl apply -f prepared-deploy.yaml'
                        sh 'kubectl -n ${KUBE_NAMESPACE} rollout status deployment/${DEPLOYMENT_NAME}'
                    }
                }
            }
        }

        stage('Promote to Dev') {
            when {
                branch 'main'
            }
            environment {
                KUBE_NAMESPACE = 'dev'
            }
            steps {
                input message: 'Promote this release to Dev?'
                script {
                    env.DEPLOYMENT_NAME = "${env.APP_NAME}"
                    env.CONTAINER_NAME = 'app'
                    env.NAMESPACE_NAME = env.KUBE_NAMESPACE

                    withKubeConfig(
                        caCertificate: env.KUBE_CA_CERT,
                        clusterName: env.KUBE_CLUSTER,
                        contextName: env.KUBE_CONTEXT,
                        credentialsId: env.KUBE_CREDENTIALS,
                        namespace: env.KUBE_NAMESPACE,
                        restrictKubeConfigAccess: false,
                        serverUrl: env.KUBE_SERVER_URL
                    ) {
                        sh 'envsubst --version'
                        sh 'envsubst < deploy.yaml > prepared-deploy.yaml'
                        sh 'kubectl apply -f prepared-deploy.yaml'
                        sh 'kubectl -n ${KUBE_NAMESPACE} rollout status deployment/${DEPLOYMENT_NAME}'
                    }
                }
            }
        }

        stage('Promote to UAT') {
            when {
                branch 'main'
            }
            environment {
                KUBE_NAMESPACE = 'uat'
            }
            steps {
                input message: 'Promote this release to UAT?'
                script {
                    env.DEPLOYMENT_NAME = "${env.APP_NAME}"
                    env.CONTAINER_NAME = 'app'
                    env.NAMESPACE_NAME = env.KUBE_NAMESPACE

                    withKubeConfig(
                        caCertificate: env.KUBE_CA_CERT,
                        clusterName: env.KUBE_CLUSTER,
                        contextName: env.KUBE_CONTEXT,
                        credentialsId: env.KUBE_CREDENTIALS,
                        namespace: env.KUBE_NAMESPACE,
                        restrictKubeConfigAccess: false,
                        serverUrl: env.KUBE_SERVER_URL
                    ) {
                        sh 'envsubst --version'
                        sh 'envsubst < deploy.yaml > prepared-deploy.yaml'
                        sh 'kubectl apply -f prepared-deploy.yaml'
                        sh 'kubectl -n ${KUBE_NAMESPACE} rollout status deployment/${DEPLOYMENT_NAME}'
                    }
                }
            }
        }

        stage('Promote to Prod') {
            when {
                branch 'main'
            }
            environment {
                KUBE_NAMESPACE = 'prod'
            }
            steps {
                input message: 'Promote this release to Production?'
                script {
                    env.DEPLOYMENT_NAME = "${env.APP_NAME}"
                    env.CONTAINER_NAME = 'app'
                    env.NAMESPACE_NAME = env.KUBE_NAMESPACE

                    withKubeConfig(
                        caCertificate: env.KUBE_CA_CERT,
                        clusterName: env.KUBE_CLUSTER,
                        contextName: env.KUBE_CONTEXT,
                        credentialsId: env.KUBE_CREDENTIALS,
                        namespace: env.KUBE_NAMESPACE,
                        restrictKubeConfigAccess: false,
                        serverUrl: env.KUBE_SERVER_URL
                    ) {
                        sh 'envsubst --version'
                        sh 'envsubst < deploy.yaml > prepared-deploy.yaml'
                        sh 'kubectl apply -f prepared-deploy.yaml'
                        sh 'kubectl -n ${KUBE_NAMESPACE} rollout status deployment/${DEPLOYMENT_NAME}'
                    }
                }
            }
        }
    }
}
