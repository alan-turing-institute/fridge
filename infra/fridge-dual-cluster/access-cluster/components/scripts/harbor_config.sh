#!/bin/sh
# Configure Harbor settings via its API

echo "Configuring Harbor..."
curl -X 'POST' \
    -u "$HARBOR_ADMIN_USER:$HARBOR_ADMIN_PASSWORD" \
    'http://10.0.50.50/api/v2.0/registries' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/json' \
    -d '{
        "id": 1,
        "url": "https://hub.docker.com",
        "type": "docker-hub",
        "credential": {},
        "name": "DockerHub",
        }'
curl -X 'POST' \
    -u "$HARBOR_ADMIN_USER:$HARBOR_ADMIN_PASSWORD" \
    'http://10.0.50.50/api/v2.0/projects' \
    -H 'accept: application/json' \
    -H 'Content-Type: application/json' \
    -d '{
        "project_name": "docker-proxy",
        "public": true,
        "cve_allowlist": {},
        "registry_id": 1,
        "metadata": {
            "proxy_speed_kb": "-1",
            }
        }'
