set shell := ["/bin/bash", "-c"]

default:
    just --list
install-cillium:
    /workspace/scripts/Install-Cillium.sh
rebuild-cluster:
    /workspace/scripts/kind-rebuild-cluster.sh
[no-cd]
pulumi-init:
    echo "Initializing Pulumi configuration..."
    echo "using local stack file for dev environment"
    bash ./scripts/pulumi-setup.sh
    -gum confirm "would you like to generate a new passphrase for Pulumi secrets?" && sed -i '/encryptionsalt/d' /workspace/infra/fridge/Pulumi.dev.yaml
    python3 /workspace/infra/fridge/scripts/init-pulumi.py
