# Base image for the Vertex pipeline components (P1, P2). It needs fieldshift AND kfp, because the
# components are compiled with install_kfp_package=False.
#   docker build -f docker/pipeline-base.Dockerfile -t REGION-docker.pkg.dev/PROJECT/REPO/fieldshift-pipeline:TAG .
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# rasterio and h5py ship binary wheels for this Python version; no system GDAL is needed for them.
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY knowledge ./knowledge
COPY contracts ./contracts
RUN pip install --no-cache-dir -e ".[data,pipelines]"
