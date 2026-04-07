#!/usr/bin/env bash
set -euo pipefail

FLUME_VERSION="${FLUME_VERSION:-1.11.0}"
FLUME_INSTALL_DIR="${FLUME_INSTALL_DIR:-/opt/flume}"
DATA_DIR="${DATA_DIR:-/data/flume}"

echo "[flume] installing Apache Flume ${FLUME_VERSION}..."

cd /tmp

echo "[flume] download Flume..."
wget -q "https://archive.apache.org/dist/flume/flume-${FLUME_VERSION}/apache-flume-${FLUME_VERSION}-bin.tar.gz" \
    -O "apache-flume-${FLUME_VERSION}-bin.tar.gz"

echo "[flume] extract to ${FLUME_INSTALL_DIR}..."
sudo mkdir -p "${FLUME_INSTALL_DIR}"
sudo tar -xzf "apache-flume-${FLUME_VERSION}-bin.tar.gz" -C "${FLUME_INSTALL_DIR}"
sudo ln -sfn "${FLUME_INSTALL_DIR}/apache-flume-${FLUME_VERSION}-bin" "${FLUME_INSTALL_DIR}/current"

echo "[flume] create spool/checkpoint dirs..."
sudo mkdir -p "${DATA_DIR}/spool" "${DATA_DIR}/checkpoint" "${DATA_DIR}/logs"
sudo chmod -R 777 "${DATA_DIR}"

echo "[flume] symlink flume-ng..."
sudo ln -sf "${FLUME_INSTALL_DIR}/current/bin/flume-ng" /usr/local/bin/flume-ng

echo "[flume] ensure hadoop classpath for HDFS sink..."
if [[ -d /opt/bigdata/hadoop/share/hadoop/common ]]; then
    for jar in /opt/bigdata/hadoop/share/hadoop/common/lib/*.jar; do
        [[ -f "$jar" ]] && sudo cp "$jar" "${FLUME_INSTALL_DIR}/current/lib/" 2>/dev/null || true
    done
    for jar in /opt/bigdata/hadoop/share/hadoop/hdfs/*.jar; do
        [[ -f "$jar" ]] && sudo cp "$jar" "${FLUME_INSTALL_DIR}/current/lib/" 2>/dev/null || true
    done
fi

echo "[flume] copy MySQL JDBC..."
if [[ -f /usr/share/java/mysql-connector-j.jar ]]; then
    sudo cp /usr/share/java/mysql-connector-j.jar "${FLUME_INSTALL_DIR}/current/lib/"
fi

echo "[flume] create systemd service..."
FLUME_SERVICE=$(cat <<'SERVICE_EOF'
[Unit]
Description=Apache Flume (loan-flume)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/flume/current
ExecStart=/opt/flume/current/bin/flume-ng agent -n loan-agent -c /opt/flume/conf -f /opt/flume/conf/flume-agent.conf
ExecStop=pkill -f "flume-ng agent"
Restart=on-failure
RestartSec=15s
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
SERVICE_EOF
)
echo "${FLUME_SERVICE}" | sudo tee /etc/systemd/system/loan-flume.service >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable loan-flume

echo "[flume] append env vars..."
cat <<'EOF' | sudo tee /etc/profile.d/loan-flume.sh >/dev/null
export FLUME_HOME=/opt/flume/current
export PATH=$PATH:$FLUME_HOME/bin
EOF

echo "[flume] done."
echo "  Config: Edit /opt/flume/conf/flume-agent.conf"
echo "  Start:  sudo systemctl start loan-flume"
echo "  Manual: /opt/flume/current/bin/flume-ng agent -n loan-agent -c /opt/flume/conf -f /opt/flume/conf/flume-agent.conf &"
