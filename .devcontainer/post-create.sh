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

cilium completion zsh > /home/vscode/.config/cilium-completions.zsh
/home/vscode/.pulumi/bin/pulumi gen-completion zsh > /home/vscode/.config/pulumi-completions.zsh

[ -d ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/fzf-tab ] || git clone --depth 1 https://github.com/Aloxaf/fzf-tab ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/fzf-tab

# add fzf-tab to .zshrc plugins
sed -i "s/plugins=(/plugins=(fzf-tab fzf /" /home/vscode/.zshrc

# Create aliases
cat >> /home/vscode/.zshrc << EOF
# ~/.zshrc
export CARAPACE_BRIDGES='zsh,fish,bash,inshellisense' # optional
zstyle ':completion:*' format $'\e[2;37mCompleting %d\e[m'
source <(carapace _carapace)

# k8s aliases
alias k='kubectl'
alias ksec='kubectl get secret'
alias kpods='kubectl get pods'
alias kdep='kubectl get deployments'
alias ksvc='kubectl get services'
export PATH=\$PATH:~/.pulumi/bin
export PATH=\$PATH:/workspace/scripts
source /home/vscode/.config/*-completions.zsh
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
echo "run '/workspace/scripts/kind-rebuild-cluster.sh' (also in PATH) to create a new cluster"