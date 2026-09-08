# =============================================================================
# Template: Dockerfile for a new camper-monitoring service.
#
# Build context: repository root (see docker-compose.yml snippet).
# For GPU services (Jetson): use the l4t-pytorch base image:
#   FROM nvcr.io/nvidia/l4t-pytorch:r32.7.1-pth1.10-py3
# For CPU-only services (e.g. PV monitor): use a slim Python image:
#   FROM python:3.10-slim
# =============================================================================
FROM python:3.10-slim

WORKDIR /app

# Shared library (camper-shared).
COPY shared/ /app/shared/

# Python dependencies.
COPY services/_template/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Service code.
COPY services/_template/app/ /app/app/

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz', timeout=2)" || exit 1

ENV PYTHONPATH="/app:${PYTHONPATH}"
CMD ["python", "-m", "app.main"]
