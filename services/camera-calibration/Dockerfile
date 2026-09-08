# =============================================================================
# camera-calibration: Web-UI zur Kamerakalibrierung (Klick + Chessboard)
#
# Base-Image: nexus.robobrain.cloud/sdk:latest (opencv + numpy enthalten)
# Service laeuft auf Port 8081, greift auf dieselbe USB-Kamera zu wie
# backup-camera. Ergebnisse werden in ein Shared-Volume geschrieben, das
# auch backup-camera liest.
# =============================================================================
FROM nexus.robobrain.cloud/sdk:latest

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=ubuntu:ubuntu app/ ./app/
COPY --chown=ubuntu:ubuntu templates/ ./templates/

# Shared-Verzeichnis für Kalibrierungsergebnisse (Volume-Mount-Punkt).
USER root
RUN mkdir -p /app/calib && chown ubuntu:ubuntu /app/calib
USER ubuntu

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=30s \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz', timeout=2)" || exit 1

ENV PATH="/home/ubuntu/.local/bin:${PATH}"
CMD ["python3", "-m", "app.main"]
