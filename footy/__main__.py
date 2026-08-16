"""Permite ejecutar el paquete con `python -m footy ...`."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
