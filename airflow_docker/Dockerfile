FROM apache/airflow:2.10.3-python3.10

USER root
# Install system dependencies
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
  build-essential \
  libffi-dev \
  libssl-dev \
  libkrb5-dev \
  git \
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

USER airflow

# Install dependencies
COPY requirements.txt /requirements.txt
# Install requirements (no constraints file, relying on newer base image compatibility)
RUN pip install --no-cache-dir -r /requirements.txt \
  && python -c "import airflow; print('Airflow is working:', airflow.__version__)"
