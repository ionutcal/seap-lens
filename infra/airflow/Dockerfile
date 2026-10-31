FROM apache/airflow:3.3.2-python3.12

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 unzip curl \
    && curl -fsSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscli.zip \
    && unzip -q /tmp/awscli.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/aws /tmp/awscli.zip \
    && apt-get purge -y unzip \
    && rm -rf /var/lib/apt/lists/*

# The pipeline has its own environment, because its packages conflict with Airflow's.
COPY requirements.txt requirements-ml.txt requirements-cloud.txt /opt/seap/
RUN python -m venv /opt/seap/venv \
    && /opt/seap/venv/bin/pip install --no-cache-dir \
        -r /opt/seap/requirements.txt -r /opt/seap/requirements-ml.txt -r /opt/seap/requirements-cloud.txt

COPY src /opt/seap/app/src
COPY scripts /opt/seap/app/scripts
COPY dbt /opt/seap/app/dbt
COPY docs/model /opt/seap/app/docs/model
COPY infra/airflow/dags /opt/airflow/dags
RUN mkdir -p /opt/seap/app/data /opt/seap/app/dashboard/data && chown -R airflow /opt/seap

USER airflow
