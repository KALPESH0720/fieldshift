# Engine API (Cloud Run). Build from the repository root:  docker build -f docker/engine.Dockerfile -t fieldshift-engine .
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY knowledge ./knowledge
COPY contracts ./contracts
RUN pip install --no-cache-dir -e .
# Settings come from FIELDSHIFT_* environment variables (see .env.example). Cloud Run supplies PORT.
CMD ["sh", "-c", "uvicorn fieldshift.api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
