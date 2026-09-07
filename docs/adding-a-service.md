# Neuen Service hinzufügen

## Schritte

1. **Kopieren der Vorlage:**
   ```bash
   cp -r services/_template services/<mein-service>
   ```

2. **Im `docker-compose.yml` ergänzen** (an das Template in
   `services/_template/docker-compose.snippet.yml` anlehnen):
   ```yaml
   mein-service:
     <<: *common
     build:
       context: ./services/mein-service
       dockerfile: Dockerfile
     container_name: mein-service
     ports:
       - "${MEIN_SERVICE_PORT:-808X}:8080"
   ```
   Nur GPU/Devices/Volumes ergänzen, wenn der Service diese braucht.

3. **Config-Variablen** in `.env.example` mit Sektion `<mein-service>` ergänzen.

4. **In `README.md`** die Service-Tabelle ergänzen.

5. **Eigenes README** unter `services/<mein-service>/README.md` schreiben.

## Konventionen

- Jeder Service hat **einen** Build-Kontext (`services/<name>/`).
- Die App liegt unter `services/<name>/app/`.
- Der Service hört intern auf Port `8080` (Port-Mapping nach außen via
  `.env`-Variable `<NAME>_PORT`).
- Gemeinsamer Python-Code (z.B. Config-Loader, später MQTT-Client) kommt nach
  `shared/` und wird als Volume in die Container gemountet — **nicht** pro
  Service dupliziert.
- Health-Check via `GET /healthz` ist Pflicht.
