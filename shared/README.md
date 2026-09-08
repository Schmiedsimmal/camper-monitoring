# Shared library for camper-monitoring services

Common utilities used across all services to avoid code duplication.

## Modules

- **`env.py`** — Environment-variable helpers (`env_str`, `env_int`, `env_float`,
  `env_bool`, `env_int_list`, `env_float_list`).
- **`camera.py`** — Thread-safe `CameraSource` for USB and RTSP cameras (OpenCV
  backend, background grab thread, automatic reconnect with backoff).
- **`web.py`** — FastAPI helpers: `mjpeg_generator`, `add_stream_route`,
  `add_index_route`, `add_health_route`.

## Usage in a service

The shared library is copied into each container at `/app/shared/` and
added to `PYTHONPATH` via the Dockerfile:

```dockerfile
COPY shared/ /app/shared/
ENV PYTHONPATH="/app:${PYTHONPATH}"
```

In Python:

```python
from shared.env import env_int
from shared.camera import CameraSource
from shared.web import add_health_route
```
