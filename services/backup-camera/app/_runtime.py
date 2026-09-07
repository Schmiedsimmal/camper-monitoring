"""Laufzeit-Flags, die zwischen Modulen geteilt werden (vermeidet zirkuläre
Imports zwischen main.py und web.py)."""
GATED: bool = False
