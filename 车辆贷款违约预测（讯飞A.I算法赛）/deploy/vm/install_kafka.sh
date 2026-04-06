#!/usr/bin/env bash
set -euo pipefail

KAFKA_VERSION="${KAFKA_VERSION:-3.6.1}"
KAFKA_INSTALL_DIR="${KAFKA_INSTALL_DIR:-/opt/kafka}"
DATA_DIR="${DATA_DIR:-/data/kafka}"

echo "[kafka] installing Kafka ${KAFKA_VERSION} (KRaft mode, no Zookeeper)..."

cd /tmp

echo "[kafka] download Kafka..."
wget -q "https://downloads.apache.org/kafka/${KAFKA_VERSION}/kafka_${KAFKA_VERSION}-tgz" \
    -O "kafka_${KAFKA_VERSION}.tgz" || \
wget -q "https://archive.apache.org/dist/kafka/${KAFKA_VERSION}/kafka_${KAFKA_VERSION}-tgz" \
    -O "kafka_${KAFKA_VERSION}.tgz"

echo "[kafka] extract to ${KAFKA_INSTALL_DIR}..."
sudo mkdir -p "${KAFKA_INSTALL_DIR}"
sudo tar -xzf "kafka_${KAFKA_VERSION}.tgz" -C "${KAFKA_INSTALL_DIR}"
sudo ln -sfn "${KAFKA_INSTALL_DIR}/kafka_${KAFKA_VERSION}" "${KAFKA_INSTALL_DIR}/kafka"

echo "[kafka] create data dirs..."
sudo mkdir -p "${DATA_DIR}"
sudo chown -R "$(whoami):" "${KAFKA_INSTALL_DIR}"

echo "[kafka] generate cluster UUID..."
KAFKA_CLUSTER_ID="$(sudo "${KAFKA_INSTALL_DIR}/kafka/bin/kafka-storage.sh random-uuid")"
echo "[kafka] cluster ID: ${KAFKA_CLUSTER_ID}"

echo "[kafka] format storage..."
sudo "${KAFKA_INSTALL_DIR}/kafka/bin/kafka-storage.sh format" \
    -t "${KAFKA_CLUSTER_ID}" \
    -c "${KAFKA_INSTALL_DIR}/kafka/config/kraft/server.properties" \
    --ignore-formatted

echo "[kafka] patch server.properties for local data dir..."
sudo sed -i "s|#data.dir=.*|data.dir=${DATA_DIR}|" \
    "${KAFKA_INSTALL_DIR}/kafka/config/kraft/server.properties"

echo "[kafka] create systemd service..."
KAFKA_SERVICE=$(cat <<'SERVICE_EOF'
[Unit]
Description=Apache Kafka (loan-kafka)
After=network.target

[Service]
Type=simple
User=root
ExecStart=/opt/kafka/kafka/bin/kafka-server-start.sh /opt/kafka/kafka/config/kraft/server.properties
ExecStop=/opt/kafka/kafka/bin/kafka-server-stop.sh
Restart=on-failure
RestartSec=10s
LimitNOFILE=65536
Environment="KAFKA_OPTS=-Xmx2g -Xms2g"

[Install]
WantedBy=multi-user.target
SERVICE_EOF
)
echo "${KAFKA_SERVICE}" | sudo tee /etc/systemd/system/loan-kafka.service >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable loan-kafka

echo "[kafka] create topics..."
KAFKA_BROKER_PORT="${KAFKA_BROKER_PORT:-9092}"
create_topic() {
    "${KAFKA_INSTALL_DIR}/kafka/bin/kafka-topics.sh" \
        --create \
        --topic "$1" \
        --partitions 3 \
        --replication-factor 1 \
        --bootstrap-server "localhost:${KAFKA_BROKER_PORT}" \
        --if-not-exists 2>/dev/null || true
}
create_topic "lending_application"
create_topic "loan_repair_events"
create_topic "model_score_results"

echo "[kafka] append env vars..."
cat <<'EOF' | sudo tee /etc/profile.d/loan-kafka.sh >/dev/null
export KAFKA_HOME=/opt/kafka/kafka
export PATH=$PATH:$KAFKA_HOME/bin
export KAFKA_BROKERS=localhost:9092
EOF

echo "[kafka] verify:"
/opt/kafka/kafka/bin/kafka-topics.sh --list --bootstrap-server "localhost:${KAFKA_BROKER_PORT}"

echo ""
echo "[kafka] done."
echo "  Start: sudo systemctl start loan-kafka"
echo "  Stop:  sudo systemctl stop loan-kafka"
echo "  Logs:  journalctl -u loan-kafka -f"
