# =============================================================================
# backup-camera: Rear-view camera with YOLO object detection + Web UI.
#
# Build context: repository root (see docker-compose.yml).
# Base image: nexus.robobrain.cloud/sdk:latest
#   - Python 3.12, torch + CUDA, opencv already included
#   - Container user: 'ubuntu' (uid 1000), not root
# =============================================================================
FROM nexus.robobrain.cloud/sdk:latest

WORKDIR /app

# Shared library (camper-shared) + service dependencies.
COPY shared/ /app/shared/
COPY services/backup-camera/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --user -r /tmp/requirements.txt

# Service code + templates.
COPY --chown=ubuntu:ubuntu services/backup-camera/app/ /app/app/
COPY --chown=ubuntu:ubuntu services/backup-camera/templates/ /app/templates/

# Model cache directory (volume mount point).
USER root
RUN mkdir -p /app/models && chown ubuntu:ubuntu /app/models
USER ubuntu

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=120s \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz', timeout=2)" || exit 1

ENV PATH="/home/ubuntu/.local/bin:${PATH}"
ENV PYTHONPATH="/app:${PYTHONPATH}"
CMD ["python3", "-m", "app.main"]
