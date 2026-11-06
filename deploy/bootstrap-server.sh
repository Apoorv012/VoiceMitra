#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 server (an AWS EC2 instance) for VoiceMitra. Run it once after
# logging in over SSH (deploy/README.md step 3):
#
#   curl -fsSL https://raw.githubusercontent.com/Apoorv012/VoiceMitra/main/deploy/bootstrap-server.sh | sudo bash
#
# Installs Docker, adds swap (small instances run out of memory while pulling the image), and creates
# /opt/voicemitra owned by the login user. Safe to run again.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "run with sudo" >&2; exit 1; fi
LOGIN_USER="${SUDO_USER:-ubuntu}"

echo "== Docker"
if ! command -v docker >/dev/null; then
  apt-get update -y
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi
systemctl enable --now docker
usermod -aG docker "$LOGIN_USER"   # lets the deploy job run docker without sudo

echo "== Swap (2 GB)"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "== Time zone and clock"
# The app uses APP_TIMEZONE for dose times; the server clock just has to be right (timers depend on it).
timedatectl set-ntp true || true

echo "== /opt/voicemitra"
install -d -o "$LOGIN_USER" -g "$LOGIN_USER" -m 0750 /opt/voicemitra
install -d -o "$LOGIN_USER" -g "$LOGIN_USER" -m 0700 /opt/voicemitra/secrets

echo "== Automatic security updates"
apt-get install -y unattended-upgrades >/dev/null
dpkg-reconfigure -f noninteractive unattended-upgrades || true

echo
echo "Done. Log out and back in (so '$LOGIN_USER' is in the docker group), then:"
echo "  1. put the filled-in .env in /opt/voicemitra/.env           (from deploy/server.env.example)"
echo "  2. put the Firebase key in /opt/voicemitra/secrets/firebase.json"
echo "  3. run the 'Backend' workflow in GitHub Actions (or push to main) to deploy."
