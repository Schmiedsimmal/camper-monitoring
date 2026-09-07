# =============================================================================
# backup-camera: Rueckfahrkamera mit YOLO-Objekterkennung + Web-UI
#
# Base-Image: nexus.robobrain.cloud/sdk:latest
#   - Python 3.12
#   - torch + CUDA (cu130), opencv (cv2) bereits enthalten
#   - System-Libs (libgl1, libsm6, ...) bereits vorhanden
#   - Container-User: 'ubuntu' (uid 1000), nicht root
#   - GPU-Zugriff erfordert auf dem Host die NVIDIA Container Runtime
#     (siehe scripts/setup-jetson.sh). Auf Hosts ohne GPU laeuft torch im
#     CPU-Fallback.
# =============================================================================
FROM nexus.robobrain.cloud/sdk:latest

WORKDIR /app

# Python-Abhaeltigkeiten (nur die nicht im Base-Image enthaltenen).
# torch, torchvision, opencv sind bereits im SDK-Image vorhanden.
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# App-Code + Templates
COPY --chown=ubuntu:ubuntu app/ ./app/
COPY --chown=ubuntu:ubuntu templates/ ./templates/

# Modell-Verzeichnis (Volume-Mount-Punkt). Base-Image laeuft als 'ubuntu',
# daher kurz auf root wechseln fuer chown.
USER root
RUN mkdir -p /app/models && chown ubuntu:ubuntu /app/models
USER ubuntu

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=120s \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz', timeout=2)" || exit 1

USER ubuntu
ENV PATH="/home/ubuntu/.local/bin:${PATH}"
CMD ["python3", "-m", "app.main"]
