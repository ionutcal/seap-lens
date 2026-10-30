#!/bin/bash
# Updates the code, starts Airflow, and runs the pipeline at most once a month. A later
# boot in the same month is for inspecting things, so nothing runs and nothing stops it
# except the 4-hour guard.
set -euxo pipefail

cd /opt/seap-lens
git pull --ff-only
DOCKER_BUILDKIT=0 docker build -f infra/airflow/Dockerfile -t seap-lens-airflow .

cd infra/airflow
docker compose up -d

marker=/opt/seap-lens/.last_run
if [ "$(cat "$marker" 2>/dev/null || true)" = "$(date +%Y-%m)" ]; then
  exit 0
fi

# The DAG takes a moment to appear after Airflow starts.
for _ in $(seq 1 60); do
  if docker compose exec -T airflow-scheduler airflow dags unpause seap_monthly; then
    docker compose exec -T airflow-scheduler airflow dags trigger seap_monthly
    date +%Y-%m > "$marker"
    exit 0
  fi
  sleep 10
done
echo "The DAG never appeared" >&2
exit 1
