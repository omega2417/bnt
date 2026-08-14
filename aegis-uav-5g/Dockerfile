# Reproducible environment for the Aegis-UAV-5G Level-1 research pipeline.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build tooling then Python deps (leverages layer caching on pyproject).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install -e .

# Bring in configs, scripts and empty artifact/dataset trees.
COPY configs ./configs
COPY scripts ./scripts
COPY Makefile ./Makefile
RUN mkdir -p artifacts/tables artifacts/figures artifacts/metrics \
    artifacts/models artifacts/logs artifacts/manifests \
    datasets/raw datasets/interim datasets/processed datasets/manifests

# Default: run the fully reproducible smoke campaign (all tables + figures).
CMD ["aegis", "campaign", "--config", "configs/experiments/smoke.yaml"]
