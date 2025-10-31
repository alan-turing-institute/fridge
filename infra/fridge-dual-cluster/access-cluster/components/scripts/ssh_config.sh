#!/usr/bin/with-contenv bash

# set config path
if [[ -f /config/sshd/sshd_config ]]; then
  CONFIG_FILE_PATH="/config/sshd/sshd_config"
else
  CONFIG_FILE_PATH="/etc/ssh/sshd_config"
fi

# allow tcp forwarding within openssh settings
sed -i '/^AllowTcpForwarding/c\AllowTcpForwarding yes' "${CONFIG_FILE_PATH}"
sed -i '/^GatewayPorts/c\GatewayPorts clientspecified' "${CONFIG_FILE_PATH}"
echo "TcpForwarding is enabled"


if [ "$SHELL_NOLOGIN" == 'true' ]; then
  USER_NAME=${USER_NAME:-linuxserver.io}

  usermod --shell /sbin/nologin "$USER_NAME" &&
  echo "Shell is set to /sbin/nologin for the user $USER_NAME"
fi
