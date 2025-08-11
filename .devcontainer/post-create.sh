#!/bin/bash
set -e

# Print message function
print_message() {
  echo "================================================================================"
  echo ">>> $1"
  echo "================================================================================"
}


# Set up environment variables
print_message "Setting up environment variables"
echo "export KUBECONFIG=/home/vscode/.kube/config" >> /home/vscode/.zshrc
echo "export PATH=\$PATH:/home/vscode/.local/bin" >> /home/vscode/.zshrc

# Install completions
/usr/local/bin/k3d completion zsh > /home/vscode/.config/k3d-completions.zsh
/usr/local/bin/cilium completion zsh > /home/vscode/.config/cilium-completions.zsh
/usr/local/bin/argo completion zsh > /home/vscode/.config/argo-completions.zsh
/home/vscode/.pulumi/bin/pulumi gen-completion zsh > /home/vscode/.config/pulumi-completions.zsh

# delete existing plugins line if it exists
if grep -q "plugins=(" /home/vscode/.zshrc; then
  sed -i "/plugins=(/d" /home/vscode/.zshrc
fi

# Create aliases
cat >> /home/vscode/.zshrc << EOF
# ~/.zshrc
export PATH=\$PATH:~/.pulumi/bin
export PATH=\$PATH:/workspace/scripts

autoload -U compinit && compinit

export CARAPACE_BRIDGES='zsh,fish,bash,inshellisense' # optional
zstyle ':completion:*' format $'\e[2;37mCompleting %d\e[m'
source <(carapace _carapace)
for f in /home/vscode/.config/*-completions.zsh; do
  source \$f
done

# k8s aliases
alias k='kubectl'
alias ksec='kubectl get secret'
alias kpods='kubectl get pods'
alias kdep='kubectl get deployments'
alias ksvc='kubectl get services'

plugins=(git docker docker-compose kubectl fzf-tab)
EOF

# set up Docker socket permissions for KInD
sudo chown $(whoami) /var/run/docker.sock

print_message "Creating virtual environment for Python"

if [ ! -d "/workspace/infra/fridge/venv" ]; then
  cd /workspace/infra/fridge
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
elif [ -d "/workspace/infra/fridge/venv" ]; then
  source /workspace/infra/fridge/venv/bin/activate
fi

print_message "DevContainer setup complete! 🎉"
echo "You can now use the following commands:"
echo "run 'source ~/.zshrc'"
echo "run '/workspace/scripts/kind-rebuild-cluster.sh' (also in PATH) to create a new cluster"
