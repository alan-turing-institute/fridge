#!/bin/sh
# Configure Harbor settings via its API

set -e

HARBOR_ADMIN_USER=$(cat /run/secrets/harbor/username)
HARBOR_ADMIN_PASSWORD=$(cat /run/secrets/harbor/password)

echo "Configuring Harbor..."
# Create a registry entry for Docker Hub
curl -X 'POST' \
    -u "$HARBOR_ADMIN_USER:$HARBOR_ADMIN_PASSWORD" \
    "http://$HARBOR_URL/api/v2.0/registries" \
    -H 'accept: application/json' \
    -H 'Content-Type: application/json' \
    -d '{
        "url": "https://hub.docker.com",
        "type": "docker-hub",
        "credential": {},
        "name": "DockerHub"
        }'

# Create a project for Docker proxy caching
curl -X 'POST' \
    -u "$HARBOR_ADMIN_USER:$HARBOR_ADMIN_PASSWORD" \
    "http://$HARBOR_URL/api/v2.0/projects" \
    -H 'accept: application/json' \
    -H 'Content-Type: application/json' \
    -d '{
        "project_name": "docker-proxy",
        "public": true,
        "registry_id": 1,
        "metadata": {
            "proxy_speed_kb": "-1"
            }
        }'

echo "Harbor configuration complete."
