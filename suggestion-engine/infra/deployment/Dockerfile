
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

WORKDIR /app

# Install system certificates
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install project dependencies
COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy FieldShift implementation
COPY src/ /app/src/
COPY pipelines/ /app/pipelines/
COPY infra/ /app/infra/

# Create non-root user
RUN useradd --create-home --shell /usr/sbin/nologin fieldshift \
    && chown -R fieldshift:fieldshift /app

USER fieldshift

# Execute the configured pipeline runner
CMD ["python", "-m", "infra.scripts.run_pipeline"]
