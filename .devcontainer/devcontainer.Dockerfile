FROM mcr.microsoft.com/vscode/devcontainers/base:ubuntu-24.04

USER root
# Install dependencies

# Kubectl, helm are enabled as features from the devcontainer.json

############################################################
# Version ARGs (override at build-time as needed)
############################################################
# Core CLIs
ARG K3D_VERSION="5.8.3"
ARG HELM_VERSION="3.14.0"
ARG K9S_VERSION="0.50.9"
ARG ARGO_VERSION="3.7.0"
ARG CARAPACE_VERSION="1.4.0"
ARG FZF_TAB_REF="master"   # git ref (branch/tag/commit) for fzf-tab plugin

# Cilium & Hubble: use explicit versions; set to "auto" to use upstream stable.txt
ARG CILIUM_CLI_VERSION="auto"
ARG HUBBLE_VERSION="auto"

# Helper for arch mapping in RUN steps
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

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
    fzf \
    yq \
    python3.12-venv

# install pulumi
RUN curl -fsSL https://get.pulumi.com | sh
RUN mv ~/.pulumi/ /home/vscode/.pulumi
RUN chown -R vscode:vscode /home/vscode/.pulumi

# Install k3d
RUN ARCH=amd64; [[ "$(uname -m)" == "aarch64" ]] && ARCH=arm64; \
    wget -q https://github.com/k3d-io/k3d/releases/download/v${K3D_VERSION}/k3d-linux-${ARCH} -O /usr/local/bin/k3d && \
    chmod +x /usr/local/bin/k3d

# Install Helm
RUN ARCH=amd64; [[ "$(uname -m)" == "aarch64" ]] && ARCH=arm64; \
    wget -q https://get.helm.sh/helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz && \
    tar -zxf helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz && \
    mv linux-${ARCH}/helm /usr/local/bin/helm && \
    rm -rf linux-* helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz

# Install k9s
RUN ARCH=amd64; [[ "$(uname -m)" == "aarch64" ]] && ARCH=arm64; \
    wget -q https://github.com/derailed/k9s/releases/download/v${K9S_VERSION}/k9s_linux_${ARCH}.deb && \
    dpkg -i k9s_linux_${ARCH}.deb && \
    rm -f k9s_linux_${ARCH}.deb

# Install Cilium CLI
RUN VER="${CILIUM_CLI_VERSION}"; \
    [[ "$VER" == "auto" ]] && VER=$(curl -fsSL https://raw.githubusercontent.com/cilium/cilium-cli/main/stable.txt); \
    ARCH=amd64; [[ "$(uname -m)" == "aarch64" ]] && ARCH=arm64; \
    curl -fsSL -O https://github.com/cilium/cilium-cli/releases/download/${VER}/cilium-linux-${ARCH}.tar.gz -O https://github.com/cilium/cilium-cli/releases/download/${VER}/cilium-linux-${ARCH}.tar.gz.sha256sum && \
    sha256sum --check cilium-linux-${ARCH}.tar.gz.sha256sum && \
    tar xzf cilium-linux-${ARCH}.tar.gz -C /usr/local/bin && \
    rm -f cilium-linux-${ARCH}.tar.gz cilium-linux-${ARCH}.tar.gz.sha256sum

# Install Hubble CLI
RUN VER="${HUBBLE_VERSION}"; \
    [[ "$VER" == "auto" ]] && VER=$(curl -fsSL https://raw.githubusercontent.com/cilium/hubble/master/stable.txt); \
    ARCH=amd64; [[ "$(uname -m)" == "aarch64" ]] && ARCH=arm64; \
    curl -fsSL -O https://github.com/cilium/hubble/releases/download/${VER}/hubble-linux-${ARCH}.tar.gz -O https://github.com/cilium/hubble/releases/download/${VER}/hubble-linux-${ARCH}.tar.gz.sha256sum && \
    sha256sum --check hubble-linux-${ARCH}.tar.gz.sha256sum && \
    tar xzf hubble-linux-${ARCH}.tar.gz -C /usr/local/bin && \
    rm -f hubble-linux-*.tar.gz hubble-linux-*.tar.gz.sha256sum

# Install Argo Workflows CLI
ARG ARGO_OS="linux"
RUN ARCH=amd64; [[ "$(uname -m)" == "aarch64" ]] && ARCH=arm64; \
    curl -fsSL -o argo-${ARGO_OS}-${ARCH}.gz "https://github.com/argoproj/argo-workflows/releases/download/v${ARGO_VERSION}/argo-${ARGO_OS}-${ARCH}.gz" && \
    gunzip "argo-${ARGO_OS}-${ARCH}.gz" && \
    chmod +x "argo-${ARGO_OS}-${ARCH}" && \
    mv "./argo-${ARGO_OS}-${ARCH}" /usr/local/bin/argo

# Install Carapace for shell completions
RUN ARCH=amd64; [[ "$(uname -m)" == "aarch64" ]] && ARCH=arm64; \
    curl -fsSL -o carapace.tar.gz "https://github.com/carapace-sh/carapace-bin/releases/download/v${CARAPACE_VERSION}/carapace-bin_${CARAPACE_VERSION}_linux_${ARCH}.tar.gz" && \
    tar -xzf carapace.tar.gz -C /usr/local/bin && \
    rm -f carapace.tar.gz

# use fzf-tab for fzf completions
RUN git clone --depth 1 --branch ${FZF_TAB_REF} https://github.com/Aloxaf/fzf-tab /home/vscode/.oh-my-zsh/custom/plugins/fzf-tab
