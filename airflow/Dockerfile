# Airflow image plus the project's own Python dependencies (pandas, pyarrow, requests).
FROM apache/airflow:3.3.2
COPY requirements.txt /tmp/requirements.txt
# Pin Airflow so installing the project requirements can never up/downgrade it.
RUN pip install --no-cache-dir "apache-airflow==3.3.2" -r /tmp/requirements.txt
