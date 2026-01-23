#!/bin/sh
# Configure Harbor settings via its API

set -e

HARBOR_ADMIN_USER=$(cat /run/secrets/harbor/username)
HARBOR_ADMIN_PASSWORD=$(cat /run/secrets/harbor/password)

FRIDGE_ROBOT_ACCOUNT="fridge"
FRIDGE_ROBOT_SECRET=""

function main() {
    echo "Configuring Harbor..."

    # Create remote registries
    make_remote_registry "DockerHub" "docker-hub" "https://hub.docker.com"
    make_remote_registry "QuayIO" "quay" "https://quay.io"
    make_remote_registry "GitHubCR" "github-ghcr" "https://ghcr.io"

    # Retrieve internal IDs of above remote registries
    registries=$( \
        curl -s \
            -u $HARBOR_ADMIN_USER:$HARBOR_ADMIN_PASSWORD \
            -H 'Content-Type: application/json' \
            http://$HARBOR_URL/api/v2.0/registries \
    )
    dockerhub_id=$(get_registry_id $registries "DockerHub")
    quayio_id=$(get_registry_id $registries "QuayIO")
    githubcr_id=$(get_registry_id $registries "GitHubCR")

    # Create proxy projects for remote registries
    make_proxy_project "proxy-docker.io" $dockerhub_id
    make_proxy_project "proxy-quay.io" $quayio_id
    make_proxy_project "proxy-ghcr.io" $githubcr_id

    # Create robot account for pulling images
    make_robot_account $FRIDGE_ROBOT_ACCOUNT

    echo "Harbor configuration complete."
}

function make_remote_registry() {
    body=$(printf \
    '{
        "name": "%s",
        "type": "%s",
        "url": "%s",
        "insecure": false
    }' \
    $1 $2 $3)
    curl -s -X POST \
        -u $HARBOR_ADMIN_USER:$HARBOR_ADMIN_PASSWORD \
        -H 'Accept: application/json' \
        -H 'Content-Type: application/json' \
        -d "$body" \
        http://$HARBOR_URL/api/v2.0/registries
}

function make_proxy_project() {
    body=$(printf \
    '{
        "project_name": "%s",
        "metadata": {
            "public": "true"
        },
        "registry_id": %s
    }' \
    $1 $2)
    curl -s -X POST \
        -u $HARBOR_ADMIN_USER:$HARBOR_ADMIN_PASSWORD \
        -H 'Accept: application/json' \
        -H 'Content-Type: application/json' \
        -d "$body" \
        http://$HARBOR_URL/api/v2.0/projects
}

function get_registry_id() {
    printf '%s' "$1" | jq --arg regname "$2" -r '.[] | select(.name==$regname) | .id'
}

function make_robot_account() {
    body=$(printf \
    '{
        "name": "%s",
        "description": "FRIDGE robot account",
        "disable": false,
        "duration": -1,
        "expires_at": -1,
        "level": "system",
        "permissions": [{
            "kind": "project",
            "namespace": "*",
            "access": [{
                "action": "pull",
                "resource": "repository"
            }]
        }]
    }' \
    $1)
    resp=$(curl -s -X POST \
    -u $HARBOR_ADMIN_USER:$HARBOR_ADMIN_PASSWORD \
    -H 'Accept: application/json' \
    -H 'Content-Type: application/json' \
    -d "$body" \
    http://$HARBOR_URL/api/v2.0/robots)

    # Extract account name and secret
    FRIDGE_ROBOT_ACCOUNT=$(printf '%s' "$resp" | jq -r '.name')
    FRIDGE_ROBOT_SECRET=$(printf '%s' "$resp" | jq -r '.secret')
}

# Entrypoint
main "$@"
