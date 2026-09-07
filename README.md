# Camper Monitoring

Modulares Monitoring-System für einen Camper/Van, basierend auf einem NVIDIA
Jetson Nano. Alle Services laufen in Docker-Containern und werden über
`docker compose` gestartet.

## Services

| Service          | Status       | Beschreibung                                            |
| ---------------- | ------------ | ------------------------------------------------------- |
| `backup-camera`  | in Arbeit    | Rückfahrkamera mit YOLO-Objekterkennung + Web-UI        |
| `pv-monitor`     | geplant      | PV-Anlagen-Überwachung (z.B. via Modbus/HTTP des WR)    |

## Architektur

Siehe [`docs/architecture.md`](docs/architecture.md). Jeder Service lebt
eigenständig unter `services/<name>/` und wird im Root-`docker-compose.yml`
referenziert. Neue Services können nach dem Vorbild in
[`services/_template/`](services/_template/) hinzugefügt werden.

## Voraussetzungen (Jetson Nano)

- JetPack 4.x (Ubuntu 18.04, CUDA 10.x, TensorRT 7.x)
- Docker + Docker Compose
- NVIDIA Container Runtime (`nvidia-docker2`) für GPU-Zugriff aus Containern
- Für GPIO-Zugriff: User in Gruppe `gpio` (siehe `scripts/setup-jetson.sh`)

Einrichtung einmalig ausführen:

```bash
bash scripts/setup-jetson.sh
```

## Schnellstart

```bash
cp .env.example .env
# .env anpassen (Kamera-Quelle, GPIO-Pin, Modell, ...)

docker compose up --build
```

Danach ist die Web-UI der Rückfahrkamera erreichbar unter
`http://<jetson-ip>:8080/`.

## Hardware-Verkabelung

Kamera-Montage (USB-Kamera am Heck) und Trigger-Verkabelung
(12V Rückfahrlicht → Optokoppler → GPIO) sind in
[`docs/hardware-wiring.md`](docs/hardware-wiring.md) dokumentiert.

**Empfohlene Kamera:** Arducam 2MP IMX291 USB mit Waterproof Metal Case
(2-m-Kabel-Variante). Siehe Doku für Details und Alternativen.

## Neuen Service hinzufügen

1. `cp -r services/_template services/<neuer-name>`
2. Service in `docker-compose.yml` aufnehmen (vom Template ableiten).
3. Service-interne Config-Variablen in `.env.example` ergänzen.
4. In dieser Tabelle oben eintragen.

Siehe [`docs/adding-a-service.md`](docs/adding-a-service.md) für Details.
