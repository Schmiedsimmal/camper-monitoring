# backup-camera

Rückfahrkamera-Service mit YOLOv8-Objekterkennung (COCO) und Web-UI.

## Pipeline

1. **Trigger** (`app/trigger.py`): GPIO-Pin liest das 12V-Rückfahrlichtsignal
   (über Optokoppler). Bei `TRIGGER_GATED=true` läuft die Inferenz nur bei
   aktivem Trigger.
2. **Camera** (`app/camera.py`): Öffnet `CAMERA_SOURCE` (`rtsp://...` oder
   `usb:N`) via OpenCV in einem Hintergrund-Thread.
3. **Detector** (`app/detector.py`): YOLOv8 auf GPU (CUDA) oder CPU-Fallback.
   Filtert Klassen (`YOLO_CLASSES`) und Confidence (`YOLO_CONF_THRESHOLD`).
4. **Web** (`app/web.py`): FastAPI auf Port 8080.
   - `GET /` — Web-UI (MJPEG-Viewer + Live-Status)
   - `GET /stream` — MJPEG-Livestream mit annotierten Frames
   - `GET /status` — JSON-Status
   - `GET /healthz` — Health-Check

## Config

Siehe Root-`.env.example`, Sektion *Backup-Camera Service*.

| Variable | Default | Beschreibung |
| --- | --- | --- |
| `CAMERA_SOURCE` | `usb:0` | `rtsp://...` oder `usb:N` |
| `CAMERA_WIDTH` / `CAMERA_HEIGHT` / `CAMERA_FPS` | 1280 / 720 / 15 | Auflösung/FPS |
| `YOLO_MODEL` | `yolov8n.pt` | Ultralytics-Modellname |
| `YOLO_CONF_THRESHOLD` | `0.4` | Confidence-Threshold |
| `YOLO_CLASSES` | `0,1,2,3,5,7` | COCO-Klassen-Filter (leer = alle) |
| `YOLO_DEVICE` | `auto` | `auto` / `cuda:0` / `cpu` |
| `YOLO_EXPORT_ENGINE` | `true` | TensorRT-Engine auf CUDA bauen & cachen |
| `YOLO_IMG_SIZE` | `640` | Input-Größe für TensorRT-Export |
| `YOLO_HALF` | `true` | FP16 (Half-Precision) für TensorRT |
| `TRIGGER_GPIO_PIN` | `24` | BCM-Pin |
| `TRIGGER_GATED` | `true` | Stream nur bei aktivem Trigger |
| `TRIGGER_ACTIVE_LOW` | `true` | PC817-Schaltung zieht Pin auf Low |
| `BACKUP_CAMERA_PORT` | `8080` | Web-Port nach außen |

## Inferenz-Beschleunigung (TensorRT)

Auf dem Jetson (CUDA) baut der Service beim ersten Start automatisch eine
**TensorRT-Engine** aus dem `.pt`-Modell und cacht sie im Volume
`/app/models/<modell>_fp16.engine`. Bei Folgestarts wird die `.engine` direkt
geladen — das bringt typisch **5-10x mehr FPS** auf dem Jetson Nano.

- Erster Start: Bauen der Engine dauert einige Minuten (einmalig).
- Engine ist **hardware-spezifisch**: nur auf dem Jetson gebaute Engines
  laufen auch nur dort. Beim Wechsel des Hosts wird neu gebaut.
- Auf CPU-Hosts (Dev) wird der Export automatisch übersprungen.
- Mit `YOLO_EXPORT_ENGINE=false` kann der Export deaktiviert werden (reine
  PyTorch-Inferenz, nützlich fürs Debugging).
- `YOLO_IMG_SIZE=416` oder `320` erhöht die FPS weiter (auf Kosten der
  Erkennungsqualität bei kleinen Objekten).

## Modell-Caching

Die `.pt`-Datei wird beim ersten Start ins Volume `/app/models` heruntergeladen
und kopiert. Bei Folgestarts ist **kein Internetzugang** mehr nötig — der
Service lädt das Modell aus dem Volume. Das gilt auch für die `.engine`.

## Auf dem Jetson: GPU-Taugliches torch

Das `l4t-pytorch`-Base-Image bringt passende torch-Wheels mit. Falls ein
anderes Base-Image verwendet wird, müssen die Jetson-tauglichen torch-Wheels
von NVIDIA installiert werden (siehe Jetson Zoo), sonst läuft ultralytics auf
der CPU.

## Dev auf x86 (ohne Jetson)

Im `docker-compose.yml` die Zeilen `runtime: nvidia` und
`NVIDIA_*`-Environment-Variablen auskommentieren. GPIO ist nicht verfügbar —
der Service verwendet automatisch einen `DummyTrigger` (immer aktiv), so dass
die Pipeline mit einer USB-Webcam getestet werden kann.
