"""Rebuilds the warehouse once a month and publishes a new dashboard extract if every check passes.

Each task runs a script from the repository in its own environment. Airflow only orders them,
retries them and records what happened. The run starts from a boot of the instance, not from a
schedule here, because the instance is off the rest of the time.
"""

from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG
from airflow.task.trigger_rule import TriggerRule

APP = "/opt/seap/app"
PYTHON = "/opt/seap/venv/bin/python"
DBT = "/opt/seap/venv/bin/dbt"
BUCKET = "s3://$SEAP_BUCKET"
CLOUD_ENV = "export SEAP_WAREHOUSE=athena; "
# A hold file lets someone inspect the instance after a run. The boot guard still stops it.
STOP_INSTANCE = """
if [ -f /opt/seap/app/data/.hold ]; then echo "Hold file found, not stopping"; exit 0; fi
token=$(curl -fsS -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
instance=$(curl -fsS -H "X-aws-ec2-metadata-token: $token" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 stop-instances --instance-ids "$instance"
"""


def step(task_id: str, command: str, **options) -> BashOperator:
    return BashOperator(task_id=task_id, bash_command=f"cd {APP} && {command}", **options)


with DAG(
    dag_id="seap_monthly",
    description="Download new SEAP files, rebuild the warehouse, score notices and export the dashboard data",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
) as dag:
    download = step("download_raw", f"{PYTHON} -m scripts.download_raw")
    upload_raw = step("upload_raw", f"aws s3 sync data/raw {BUCKET}/raw --no-progress")
    standardize = step("standardize", f"{PYTHON} -m scripts.standardize_all")
    upload_standard = step(
        "upload_standard",
        f"aws s3 sync data/standard {BUCKET}/standard --delete --no-progress "
        f"&& aws s3 sync data/rejects {BUCKET}/rejects --no-progress",
    )
    build_warehouse = step("build_warehouse", f"cd dbt && {DBT} build --profiles-dir . --target athena")
    fetch_model = step("fetch_model", f"aws s3 sync {BUCKET}/model data/model --no-progress")
    score = step("score_notices", f"{CLOUD_ENV}{PYTHON} -m scripts.train_model score")
    export = step("export_dashboard", f"{CLOUD_ENV}{PYTHON} -m scripts.export_dashboard")
    # Runs only if everything before it passed, so a bad run never replaces the last good extract.
    publish = step("publish_extract", f"aws s3 sync dashboard/data {BUCKET}/exports/dashboard --no-progress")
    keep_results = step(
        "keep_results",
        f"aws s3 sync docs/model {BUCKET}/exports/model-results --no-progress "
        f"&& aws s3 sync data/model {BUCKET}/model --no-progress "
        f"&& if [ -f data/mlflow.db ]; then aws s3 cp data/mlflow.db {BUCKET}/mlflow/mlflow.db --no-progress; fi",
    )
    stop = BashOperator(
        task_id="stop_instance", bash_command=STOP_INSTANCE, trigger_rule=TriggerRule.ALL_DONE, retries=3,
    )

    download >> upload_raw >> standardize >> upload_standard >> build_warehouse >> fetch_model
    fetch_model >> score >> export >> publish >> keep_results >> stop
