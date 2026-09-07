# Architektur

## Übersicht

```
                ┌─────────────────────────────────────────────────────┐
                │                  Jetson Nano (Host)                  │
                │                                                     │
  12V Rücklicht │   ┌──────────┐   GPIO    ┌──────────────────────┐  │
  ───[Optokoppler]─▶│ Trigger  │──────────▶│                      │  │
                │   └──────────┘           │   backup-camera      │  │
  WiFi/USB      │   ┌──────────┐  Frames   │  (Docker Container)  │  │
  Kamera ───────┼──▶│ Capture  │──────────▶│  YOLOv8 + Web-UI     │  │
                │   └──────────┘           │                      │  │
                │                          └──────────┬───────────┘  │
                │                                     │ HTTP :8080   │
                └─────────────────────────────────────┼──────────────┘
                                                      │
                                          Browser im Camper-WLAN ────▶ Anzeige
```

## Services

Jeder Service ist ein eigenständiger Docker-Container unter `services/<name>/`.
Services kommunizieren **nicht** zwingend miteinander — jeder hat seine eigene
Web-UI auf einem eigenen Port. Später kann ein gemeinsamer MQTT-Broker
(`shared/`) ergänzt werden, falls Services Ereignisse austauschen sollen
(z.B. "Rückwärtsgang aktiv" → PV-Service pausiert).

### backup-camera

Pipeline (in `app/main.py` orchestriert):

1. **Trigger** (`trigger.py`): Liest GPIO-Pin (12V Rückfahrlicht über
   Optokoppler). Bei `TRIGGER_GATED=true` läuft die Inferenz nur, wenn der Pin
   High ist. Spart GPU-Last und Strom.
2. **Camera** (`camera.py`): Öffnet die Quelle aus `CAMERA_SOURCE`
   (`rtsp://...` oder `usb:N`) via OpenCV `VideoCapture` und liefert Frames.
3. **Detector** (`detector.py`): YOLOv8 (COCO-vortrainiert) auf der GPU.
   Filtert Klassen und Confidence. Zeichnet Bounding-Boxes + Labels.
4. **Web** (`web.py`): FastAPI-Server. Endpoints:
   - `GET /` — Web-UI (`index.html`)
   - `GET /stream` — MJPEG-Livestream mit annotierten Frames
   - `GET /healthz` — Health-Check
   - `GET /status` — JSON: Trigger aktiv? FPS? Modell geladen?

### pv-monitor (geplant)

Soll den Wechselrichter (z.B. Victron/SMA/Fronius) per HTTP/Modbus auslesen
und eine eigene Web-UI mit Ertragskurven bieten. Kein GPU-Zugriff nötig.

## GPU-Zugriff

Auf dem Jetson muss die **NVIDIA Container Runtime** installiert sein
(`scripts/setup-jetson.sh`). Im `docker-compose.yml` ist pro GPU-Service
`runtime: nvidia` gesetzt. Auf x86-Dev-Maschinen ohne NVIDIA-Runtime diese
Zeilen auskommentieren — der Service läuft dann auf der CPU (langsam, aber
funktional zum Testen der Logik).

## Persistenz

- `backup-camera-models` (Docker-Volume): YOLO-Gewichte + gebaute
  TensorRT-Engine bleiben über Container-Neustarts erhalten.
