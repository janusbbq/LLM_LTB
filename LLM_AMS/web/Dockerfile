# syntax=docker/dockerfile:1
#
# LLM-AMS web platform image.
#
# Build context must be the project root (LLM_AMS/LLM_AMS) so both the
# `agent/` engine package and the `web/` app are available:
#
#     docker build -f web/Dockerfile -t llm-ams-web .
#
# or simply use docker-compose (which sets the context to `..`).

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 1) Install backend dependencies first for better layer caching.
COPY web/requirements.txt /app/web/requirements.txt
RUN pip install --no-cache-dir -r /app/web/requirements.txt

# 2) Copy the AMS engine package (imported by the backend) and the web app.
COPY agent/ /app/agent/
COPY web/ /app/web/

EXPOSE 8000

# Inside the container we listen on all interfaces; the host only exposes it on
# 127.0.0.1 via docker-compose port mapping.
CMD ["uvicorn", "web.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
