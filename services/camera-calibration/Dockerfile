# =============================================================================
# camera-calibration: Web UI for camera calibration (click + chessboard).
#
# Build context: repository root (see docker-compose.yml).
# Base image: nexus.robobrain.cloud/sdk:latest (opencv + numpy included).
# =============================================================================
FROM nexus.robobrain.cloud/sdk:latest

WORKDIR /app

# Shared library + service dependencies.
COPY shared/ /app/shared/
COPY services/camera-calibration/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --user -r /tmp/requirements.txt

# Service code + templates.
COPY --chown=ubuntu:ubuntu services/camera-calibration/app/ /app/app/
COPY --chown=ubuntu:ubuntu services/camera-calibration/templates/ /app/templates/

# Calibration output directory (shared volume mount point).
USER root
RUN mkdir -p /app/calib && chown ubuntu:ubuntu /app/calib
USER ubuntu

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=30s \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz', timeout=2)" || exit 1

ENV PATH="/home/ubuntu/.local/bin:${PATH}"
ENV PYTHONPATH="/app:${PYTHONPATH}"
CMD ["python3", "-m", "app.main"]
