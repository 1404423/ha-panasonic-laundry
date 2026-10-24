#!/usr/bin/env python3
"""Find the oldest Home Assistant version in which every `from homeassistant.x import y` of an integration exists.

usage:  python3 min_ha_version.py [repo-path] [version ...]
        default versions: 2024.11.0 2025.1.0 2025.2.0 2025.3.0 2025.4.0 2025.6.0 2025.9.0 2026.1.0

Downloads the wheel of each version once (pip download --no-deps --ignore-requires-python, cached in ~/.cache/ha-min-version) and checks, with ast,
that every imported name is defined or re-exported by the module it is imported from. It checks imports only: methods and keyword arguments
(for example `async_update_reload_and_abort(data_updates=...)`) are not covered, so grep those in the wheel by hand (see SKILL.md).
Compare the result with `homeassistant` in hacs.json and the README.
"""
from __future__ import annotations

import ast
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1][0].isdigit() else ".").resolve()
VERSIONS = [a for a in sys.argv[1:] if a[0].isdigit()] or ["2024.11.0", "2025.1.0", "2025.2.0", "2025.3.0", "2025.4.0", "2025.6.0", "2025.9.0", "2026.1.0"]
CACHE = Path.home() / ".cache" / "ha-min-version"
CACHE.mkdir(parents=True, exist_ok=True)

imports: dict[str, set[str]] = {}
for p in (ROOT / "custom_components").rglob("*.py"):
    for n in ast.walk(ast.parse(p.read_text())):
        if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module and n.module.split(".")[0] == "homeassistant":
            imports.setdefault(n.module, set()).update(a.name for a in n.names)
if not imports:
    print("no homeassistant imports found"); sys.exit(0)


def wheel(version: str) -> Path | None:
    got = list(CACHE.glob(f"homeassistant-{version}-*.whl"))
    if not got:
        subprocess.run([sys.executable, "-m", "pip", "download", "-q", "--no-deps", "--ignore-requires-python", f"homeassistant=={version}", "-d", str(CACHE)],
                       capture_output=True)
        got = list(CACHE.glob(f"homeassistant-{version}-*.whl"))
    return got[0] if got else None


def names_in(tree: ast.Module) -> set[str]:
    out: set[str] = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            out.update(t.id for t in n.targets if isinstance(t, ast.Name))
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif getattr(ast, "TypeAlias", None) and isinstance(n, ast.TypeAlias):        # `type ConfigType = ...` (Python 3.12+ syntax)
            out.add(n.name.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out.update((a.asname or a.name).split(".")[0] for a in n.names)
        elif isinstance(n, (ast.If, ast.Try)):                       # TYPE_CHECKING blocks, try/except imports
            for sub in ast.walk(n):
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    out.add(sub.name)
                elif isinstance(sub, (ast.Import, ast.ImportFrom)):
                    out.update((a.asname or a.name).split(".")[0] for a in sub.names)
    return out


first_ok = None
for v in VERSIONS:
    w = wheel(v)
    if not w:
        print(f"{v}: wheel not available"); continue
    missing = []
    with zipfile.ZipFile(w) as z:
        files = set(z.namelist())
        for mod, names in sorted(imports.items()):
            base = mod.replace(".", "/")
            path = base + ".py" if base + ".py" in files else base + "/__init__.py"
            if path not in files:
                missing.append(f"module {mod}"); continue
            defined = names_in(ast.parse(z.read(path).decode()))
            for nm in sorted(names):
                if nm not in defined and f"{base}/{nm}.py" not in files and f"{base}/{nm}/__init__.py" not in files:
                    missing.append(f"{mod}.{nm}")
    print(f"{v}: {'OK' if not missing else 'MISSING ' + ', '.join(missing)}")
    if not missing and first_ok is None:
        first_ok = v
print(f"\noldest listed version with every import present: {first_ok or 'none'}")
hj = ROOT / "hacs.json"
if hj.exists():
    import json
    print("hacs.json homeassistant:", json.loads(hj.read_text()).get("homeassistant", "(not set)"))
