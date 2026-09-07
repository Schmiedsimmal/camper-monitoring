# =============================================================================
# Vorlage: Dockerfile für einen neuen Camper-Monitoring-Service.
#
# Für GPU-Services (Jetson): als Base das l4t-Pytorch-Image verwenden:
#   FROM nvcr.io/nvidia/l4t-pytorch:r32.7.1-pth1.10-py3
# Für CPU-only-Services (z.B. PV-Monitor): schlankes Python-Image:
#   FROM python:3.10-slim
# =============================================================================
FROM python:3.10-slim

WORKDIR /app

# System-Abhängigkeiten (anpassen)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#         <pkg> \
#     && rm -rf /var/lib/apt/lists/*

# Python-Abhängigkeiten
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App-Code
COPY app/ ./app/

# Expose + Healthcheck
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz', timeout=2)" || exit 1

CMD ["python", "-m", "app.main"]
