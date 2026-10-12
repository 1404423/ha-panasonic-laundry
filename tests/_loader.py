"""Load the pure modules of the integration without importing Home Assistant (the package __init__ needs it)."""

import importlib
import sys
import types
from pathlib import Path

PKG = "panasonic_laundry"
PATH = Path(__file__).resolve().parent.parent / "custom_components" / PKG


def load(name: str):
    if PKG not in sys.modules:
        pkg = types.ModuleType(PKG)
        pkg.__path__ = [str(PATH)]
        sys.modules[PKG] = pkg
    return importlib.import_module(f"{PKG}.{name}")
