# Same image as the pipeline base. A separate file exists so a heavier simulator (WOFOST, AquaCrop) can be
# added later without changing P1. The water-balance simulator needs nothing extra.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY knowledge ./knowledge
COPY contracts ./contracts
RUN pip install --no-cache-dir -e ".[data,pipelines]"
