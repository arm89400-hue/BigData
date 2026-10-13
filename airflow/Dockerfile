# Airflow image plus the project's own Python dependencies (pandas, pyarrow, requests).
# Baked in at build time instead of _PIP_ADDITIONAL_REQUIREMENTS, so containers start fast.
FROM apache/airflow:2.10.4
USER airflow
COPY requirements.txt /tmp/requirements.txt
# Pin Airflow so installing the project requirements can never up/downgrade it.
RUN pip install --no-cache-dir "apache-airflow==2.10.4" -r /tmp/requirements.txt
