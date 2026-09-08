"""Shared library for all camper-monitoring services.

Common utilities (config helpers, camera source, MJPEG streaming,
FastAPI app factory) used across services. Installed as a package
into each service container via the shared/ volume mount or COPY.
"""
