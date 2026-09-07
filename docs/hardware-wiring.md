# Hardware-Verkabelung

Dieses Dokument beschreibt die komplette Hardware-Integration des
`backup-camera`-Services am Jetson Nano:

1. [Kamera (USB) am Jetson](#kamera-usb-am-jetson)
2. [12V-Trigger (Rückfahrlicht) → Jetson GPIO](#12v-trigger-rückfahrlicht--jetson-gpio)

---

## Kamera (USB) am Jetson

### Empfohlene Kamera

**Arducam 2MP IMX291 USB Camera Module with Waterproof Metal Case**

| Eigenschaft       | Wert                                  |
| ----------------- | ------------------------------------- |
| Sensor            | Sony IMX291, 1/2.8", 2 MP            |
| Auflösung         | 1920×1080 @ 30 fps (MJPG/H.264/YUY2)  |
| Low-Light         | 0.01 Lux @ F2.0 (stark bei Dämmerung) |
| Linse             | M12, 3.6 mm, 120° diagonal (Weitwinkel) |
| Gehäuse           | wasserdichtes Metallgehäuse (outdoor) |
| Anschluss         | USB 2.0, UVC (Plug & Play, kein Treiber) |
| Strom             | 5V via USB, max. 300 mA (kein extra Netzteil) |
| Kabel             | Standard 1 m, **2 m/3 m/5 m optionierbar** |
| Größe             | ~38×38 mm Board im Metallgehäuse      |
| Preis             | ~60 €                                 |
| Bezugsquelle      | thepihut.com, arducam.com             |

> Beim Kauf **explizit die 2-m-Kabel-Variante** bestellen.

### Alternative mit echter Nachtsicht

**ELP-USBFHD06H-DL36** (Sony IMX323, 24 IR-LEDs, wasserdichtes Dome-Gehäuse,
3 m Kabel, ~63 $). Wählen, wenn oft in komplett dunkler Umgebung ohne
Rückfahrlichter rangiert wird.

### Warum USB statt WiFi/RTSP oder MIPI-CSI?

| Variante        | Latenz       | 2 m Kabel          | Outdoor-Gehäuse | Aufwand |
| --------------- | ------------ | ------------------ | --------------- | ------- |
| **USB (empfohlen)** | **<100 ms**  | ✓ (bis 5 m passiv) | ✓ (im Gehäuse)  | gering  |
| WiFi/RTSP       | 500–2000 ms  | ✓ (kabellos)       | separat         | gering  |
| MIPI-CSI        | <50 ms       | nur ~40 cm direkt  | ✗ (Eigenbau)    | hoch    |

Für eine Rückfahrkamera ist **Latenz kritisch** — bei 1–2 s WiFi-Latenz ist
sicheres Rangieren auf Meter nicht möglich. USB liefert <100 ms und ist damit
die sichere Wahl.

### Montage am Heck

1. **Position:** Mittig am Heck, Höhe ca. 40–60 cm (je nach Camper). Die
   Kamera soll den Bereich direkt hinter dem Fahrzeug und ca. 3–5 m dahinter
   erfassen. Der 120°-Weitwinkel deckt das gut ab.
2. **Ausrichtung:** Linse leicht nach unten geneigt (ca. 10–15°), damit der
   tote Bereich direkt unter der Stoßstange sichtbar wird.
3. **Gehäuse:** Das mitgelieferte wasserdichte Metallgehäuse kann direkt an
   eine Heckplatte geschraubt werden. Zusätzliche Dichtung (z.B. Silikon)
   an der Kabeldurchführung schadet nicht.
4. **Kabelverlegung:** USB-Kabel vom Heck durch die Innenverkleidung zum
   Jetson. Bei 2 m sollte das ohne aktiven Repeater ausreichen (USB-2.0-Spec
   erlaubt 5 m passiv). Kabel nicht direkt neben Starkstromleitungen
   (230V/12V-Verbraucher) verlegen — Störstrahlung kann Bildfehler verursachen.
5. **Kabeldurchführung:** Wasserdichte Kabeldurchführung (Kabeltülle /
   Cable-Gland) an der Heckwand verwenden.

### Anschluss am Jetson Nano

1. USB-Kamera in einen der USB-Ports (USB 2.0 oder 3.0) des Jetson stecken.
2. Prüfen, ob die Kamera erkannt wird:
   ```bash
   ls -l /dev/video*
   # Erwartet: /dev/video0 (oder video1, falls weitere Kameras angeschlossen)
   ```
3. Schnelltest mit `v4l2-ctl` (falls installiert):
   ```bash
   v4l2-ctl --list-devices
   v4l2-ctl -d /dev/video0 --list-formats-ext
   ```
   Die Kamera sollte MJPG 1920×1080@30 und 1280×720@60 anzeigen.
4. Optionaler Test-Stream mit `ffplay`:
   ```bash
   ffplay /dev/video0
   ```

### Config im Repo

In `.env` eintragen:

```bash
# USB-Kamera (Index 0 = /dev/video0)
CAMERA_SOURCE=usb:0
CAMERA_WIDTH=1280
CAMERA_HEIGHT=720
CAMERA_FPS=15
```

> 1280×720@15 fps ist ein guter Kompromiss zwischen Bildqualität und
> Inferenz-Geschwindigkeit auf dem Jetson Nano. Für höhere FPS kann die
> Auflösung auf 640×480 reduziert werden.

### Mehrere Kameras

Falls mehrere USB-Kameras angeschlossen sind, liefert
`v4l2-ctl --list-devices` die Indizes. In `.env` dann z.B. `usb:1` setzen.

Im `docker-compose.yml` (Root-File, für den Jetson) ist `/dev/video0`
gemappt. Für eine zweite Kamera zusätzlich `/dev/video1` ergänzen:

```yaml
devices:
  - /dev/video0:/dev/video0
  - /dev/video1:/dev/video1
```

### Bekannte Probleme

- **Kamera nicht in `/dev/video*` sichtbar:** Stromversorgung prüfen. Der
  Jetson Nano liefert über USB begrenzt Strom — bei langen Kabeln + IR-LEDs
  kann ein aktiver USB-Hub mit eigenem Netzteil nötig sein.
- **Bildfehler / Frame-Drops:** Oft ein Kabel- oder Stromproblem. Kurzes
  Kabel zum Testen verwenden; falls dann ok, ist das 2-m-Kabel die Ursache
  → aktiven USB-Repeater oder kürzeres Kabel.
- **`/dev/video0` im Container nicht erreichbar:** Device-Mapping im
  `docker-compose.yml` prüfen. Auf x86-Dev-Maschinen ohne Kamera wird das
  Device im `docker-compose.override.yml` absichtlich geleert.

---

## 12V-Trigger (Rückfahrlicht) → Jetson GPIO

### Warum ein Optokoppler?

Das Camper-Bordnetz (12V) und der Jetson (3.3V-GPIO) **müssen galvanisch
getrennt** sein. Spannungsspitzen beim Einlegen des Rückwärtsgangs
(Lastwechsel, Generator) können den Jetson zerstören. Ein Optokoppler
(z.B. **PC817**) oder ein kleines Relais-Modul isoliert sicher.

## Empfohlene Schaltung (PC817)

```
   12V Rückfahrlicht ──[R 1.2 kΩ]──┐
                                    │
                                    ├──▶ LED  PC817 Pin 1 (Anode)
                                    │
   Masse (Fahrzeug)  ───────────────┴──▶ PC817 Pin 2 (Kathode)

   3.3V (Jetson Pin 1, 3V3) ────────┐
                                    │
                                    ├──▶ PC817 Pin 4 (Kollektor)
                                    │
   GPIO Pin (z.B. BCM 24) ◀─────────┘
                                    │
                              [R 10 kΩ]  (Pull-Up, falls nicht intern)
                                    │
   GND (Jetson Pin 6) ──────────────┴──▶ PC817 Pin 3 (Emitter)
```

Wenn das Rückfahrlicht 12V führt, leitet die LED im PC817, der Transistor
schaltet durch und zieht den GPIO-Pin auf **Low** (active-low). Im Code
(`trigger.py`) ist das über `TRIGGER_ACTIVE_LOW=true/false` konfigurierbar.

## Pin-Wahl

Im `.env`-File: `TRIGGER_GPIO_PIN=24` (BCM-Nummerierung, nicht Pin-Nummer).
BCM 24 = physischer Pin 18 am 40-Pin-Header des Jetson Nano.

> Achtung: Jetson Nano GPIOs sind **3.3V-tolerant**, niemals 5V anlegen!

## GPIO im Container

Der Container braucht Zugriff auf `/dev/gpiomem` und `/sys` (sysfs). Im
`docker-compose.yml` ist das bereits gemappt. Auf dem Host muss der User, der
Docker ausführt, in der Gruppe `gpio` sein (siehe `scripts/setup-jetson.sh`).

## Alternative: fertiges Optokoppler-Modul

Statt des nackten PC817 kann ein fertiges **4-Kanal-Optokoppler-Modul**
(z.B. „Arduino Optocoupler 4CH") verwendet werden. Diese haben bereits
Vorwiderstände und Pull-Ups onboard. Eingang 12V, Ausgang direkt an den
GPIO (Level prüfen — viele Module sind 5V-Ausgang, dann Spannungsteiler
oder ein 3.3V-taugliches Modul wählen).
