#!/usr/bin/env bash
# Run ON edge-1 while logged in locally (LAN console or ssh with password).
# Usage: bash fix-edge1-ssh.sh "ssh-ed25519 AAAA... comment"
set -euo pipefail

PUBKEY="${1:-}"
if [[ -z "${PUBKEY}" ]]; then
  echo "Usage: bash fix-edge1-ssh.sh \"\$(cat your_id_ed25519.pub)\""
  exit 1
fi

USER_NAME="${USER}"
HOME_DIR="${HOME}"

install -d -m 700 "${HOME_DIR}/.ssh"
AUTH="${HOME_DIR}/.ssh/authorized_keys"
touch "${AUTH}"
chmod 600 "${AUTH}"

if ! grep -qF "${PUBKEY}" "${AUTH}" 2>/dev/null; then
  echo "${PUBKEY}" >> "${AUTH}"
  echo "Added key for ${USER_NAME}"
else
  echo "Key already present for ${USER_NAME}"
fi

chmod go-w "${HOME_DIR}"
chmod 700 "${HOME_DIR}/.ssh"
chmod 600 "${AUTH}"

# Ensure sshd allows public keys
if grep -q '^PubkeyAuthentication' /etc/ssh/sshd_config; then
  sudo sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
else
  echo 'PubkeyAuthentication yes' | sudo tee -a /etc/ssh/sshd_config >/dev/null
fi
sudo systemctl reload ssh

echo "Done. Test from WSL:"
echo "  ssh -i ~/.ssh/id_ed25519 david@100.103.209.30"
