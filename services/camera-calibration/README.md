# camera-calibration

Web-UI zur Kamerakalibrierung für den `backup-camera`-Service.

## Zweck

Nach der Montage der Kamera am Camper müssen die Overlay-Parameter
(Höhe, Neigung, FOV) kalibriert werden, damit die Abstandslinien korrekt
liegen. Dieser Service bietet eine Web-UI, die von einem anderen PC im
Camper-Netzwerk aufgerufen wird — kein SSH oder Terminal nötig.

## Zwei Modi

### Klick-Modus (Overlay-Geometrie)
1. Lege Markierungen bei bekannten Abständen (1m, 2m, 3m) auf den Boden.
2. Öffne `http://<jetson-ip>:8081` im Browser.
3. Klicke im Live-Bild auf die Position der jeweiligen Markierung.
4. Trage den Abstand ein und klicke "Punkt hinzufügen".
5. Wiederhole für mindestens 2 (besser 3+) Abstände.
6. Klicke "Geometrie fitten" → System berechnet `camera_height`, `camera_tilt`.
7. Trage die Ergebnisse in `.env` ein (oder später: automatisch).

### Chessboard-Modus (Verzerrungskorrektur)
1. Drucke ein Schachbrett-Muster (9×6 innere Ecken, 25mm Quadrate).
2. Halte es aus verschiedenen Winkeln vor die Kamera.
3. Klicke "Bild aufnehmen" (mindestens 15×).
4. Klicke "Kalibrierung durchführen" → Kameramatrix + Verzerrung.

## Config

| Variable | Default | Beschreibung |
| --- | --- | --- |
| `CAMERA_CALIBRATION_PORT` | `8081` | Web-Port |
| `CALIB_CAMERA_SOURCE` | `usb:0` | USB-Kamera-Index |
| `CALIB_CAMERA_WIDTH` | `1280` | Bildbreite |
| `CALIB_CAMERA_HEIGHT` | `720` | Bildhöhe |
| `CHESSBOARD_COLS` | `9` | Innere Ecken (Spalten) |
| `CHESSBOARD_ROWS` | `6` | Innere Ecken (Zeilen) |
| `CHESSBOARD_SQUARE_MM` | `25` | Kantenlänge Quadrate [mm] |

## Architektur

```
camera-calibration (Port 8081)
    └── /app/calib/ (Shared-Volume)
         ├── overlay_geometry.json  (Klick-Modus)
         └── chessboard.json        (Chessboard-Modus)

backup-camera (Port 8080)
    └── liest /app/calib/overlay_geometry.json (geplant)
```

Die Kalibrierungsergebnisse werden in einem Shared-Volume gespeichert.
Der `backup-camera`-Service kann diese lesen (Feature folgt).
