# AURA API (FastAPI) — the JSON API that backs the web UI and CLI.
# See Dockerfile.web for the Next.js UI's image.
#
#   docker build -t aura-api .
#   docker run -p 8000:8000 -e AURA_WEB_ORIGIN=http://localhost:3000 aura-api

FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 aura
WORKDIR /app

COPY --from=builder /install /usr/local
COPY config ./config

USER aura
EXPOSE 8000

# Read-only AWS/Terraform inspection commands (`aura aws inventory`, `aura
# chaos ...`) need the optional `aws` extra (boto3); not installed here to
# keep the control-plane image lean — it only needs to serve the API.
CMD ["uvicorn", "aura.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
