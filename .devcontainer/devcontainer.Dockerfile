FROM mcr.microsoft.com/vscode/devcontainers/base:ubuntu-24.04

USER root
# Install dependencies

# Kubectl, helm are enabled as features from the devcontainer.json

# Application versions

ARG ARGO_VERSION='3.0.0'
ARG GUM_VERSION='0.16.2'

RUN apt-get update \
    && apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    git \
    gnupg \
    lsb-release \
    make \
    software-properties-common \
    unzip \
    wget \
    just \
    fzf \
    python3.12-venv

# install yq
RUN wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/local/bin/yq &&\
    chmod +x /usr/local/bin/yq

# install gum
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        wget "https://github.com/charmbracelet/gum/releases/download/v0.16.2/gum_0.16.2_Linux_x86_64.tar.gz"; \
    elif [ "$ARCH" = "aarch64" ]; then \
        wget "https://github.com/charmbracelet/gum/releases/download/v0.16.2/gum_0.16.2_Linux_arm64.tar.gz"; \
    fi && \
    tar -xzf ./gum_0.16.2_Linux_*.tar.gz && \
    mv ./gum_0.16.2_Linux_*/gum /usr/local/bin/gum && \
    rm -rf ./gum_0.16.2_Linux_*
    

# install pulumi
RUN curl -fsSL https://get.pulumi.com | sh
RUN mv ~/.pulumi/ /home/vscode/.pulumi
RUN chown -R vscode:vscode /home/vscode/.pulumi

# install KInD
RUN if [ "$(uname -m)" = "x86_64" ]; then \
        curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.29.0/kind-linux-amd64; \
    elif [ "$(uname -m)" = "aarch64" ]; then \
        curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.29.0/kind-linux-arm64; \
    fi && \
    chmod +x ./kind && \
    mv ./kind /usr/local/bin/kind

# Install Cilium CLI
RUN CILIUM_CLI_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/cilium-cli/main/stable.txt) && \
    CLI_ARCH=amd64 && \
    if [ "$(uname -m)" = "aarch64" ]; then CLI_ARCH=arm64; fi && \
    curl -L --fail --remote-name-all https://github.com/cilium/cilium-cli/releases/download/${CILIUM_CLI_VERSION}/cilium-linux-${CLI_ARCH}.tar.gz{,.sha256sum} && \
    sha256sum --check cilium-linux-${CLI_ARCH}.tar.gz.sha256sum && \
    tar xzvf cilium-linux-${CLI_ARCH}.tar.gz -C /usr/local/bin

# Install ArgoCD CLI
ARG ARGO_OS="linux"

# Download the binary
RUN curl -sLO "https://github.com/argoproj/argo-workflows/releases/download/v3.7.0/argo-$ARGO_OS-amd64.gz"

# Unzip
RUN gunzip "argo-$ARGO_OS-amd64.gz"

# Make binary executable
RUN chmod +x "argo-$ARGO_OS-amd64"

# Move binary to path
RUN mv "./argo-$ARGO_OS-amd64" /usr/local/bin/argo

# Install Carapace for shell completions
RUN curl -sLO "https://github.com/carapace-sh/carapace-bin/releases/download/v1.4.0/carapace-bin_1.4.0_linux_arm64.tar.gz" && \
    tar -xzf carapace-bin_1.4.0_linux_arm64.tar.gz -C /usr/local/bin && \
    rm carapace-bin_1.4.0_linux_arm64.tar.gz