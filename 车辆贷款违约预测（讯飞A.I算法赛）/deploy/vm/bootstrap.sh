#!/usr/bin/env bash
set -euo pipefail

echo "[bootstrap] updating apt index..."
sudo apt-get update -y

echo "[bootstrap] installing base tools..."
sudo apt-get install -y \
  curl wget unzip tar vim git net-tools openssh-server \
  build-essential software-properties-common

echo "[bootstrap] creating project user/group if needed..."
if ! id -u loan >/dev/null 2>&1; then
  sudo useradd -m -s /bin/bash loan
fi

echo "[bootstrap] done."
