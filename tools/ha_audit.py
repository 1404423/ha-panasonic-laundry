#!/usr/bin/env python3
"""Static audit of a Home Assistant custom integration repository (stdlib only, Python 3.9+; needs no Home Assistant).

usage:  python3 audit.py [repo-path]        exit code 1 when any FAIL is found

It automates the checks that reviewers (HACS default list, HA core style) and the Integration Quality Scale ask for and that a
unit-test run does NOT cover: blocking calls in the event loop, PARALLEL_UPDATES, translation/key consistency, services,
manifest/HACS files, private data in tracked files. Findings are FAIL (fix before release), WARN (look at it), INFO (optional
quality-scale goals). See SKILL.md for the rules behind each check and for what a script cannot judge.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
OUT: list[tuple[str, str, str]] = []          # (level, area, text)


def add(level: str, area: str, text: str) -> None:
    OUT.append((level, area, text))


def ok(area: str, text: str) -> None:
    add("OK", area, text)


# ---- locate the integration --------------------------------------------------------------------------------------------
cc = ROOT / "custom_components"
dirs = [d for d in cc.iterdir() if d.is_dir() and not d.name.startswith("__")] if cc.exists() else []
if len(dirs) != 1:
    print(f"FAIL repo: expected exactly one directory under custom_components/, found {len(dirs)}")
    sys.exit(1)
INT = dirs[0]
DOMAIN = INT.name
PY = sorted(INT.glob("*.py"))
src = {p.name: p.read_text() for p in PY}

# ---- manifest / HACS / repo files --------------------------------------------------------------------------------------
try:
    man = json.loads((INT / "manifest.json").read_text())
except Exception as e:
    man = {}
    add("FAIL", "manifest", f"manifest.json unreadable: {e}")
for k in ("domain", "name", "version", "documentation", "issue_tracker", "codeowners"):
    if k not in man:
        add("FAIL", "manifest", f"manifest.json lacks '{k}' (HACS requires it)")
if man.get("domain") not in (None, DOMAIN):
    add("FAIL", "manifest", f"domain {man.get('domain')!r} != directory name {DOMAIN!r}")
if man.get("version") and not re.fullmatch(r"\d+\.\d+\.\d+([-+].*)?", man["version"]):
    add("FAIL", "manifest", f"version {man['version']!r} is not semver (custom integrations need a version)")
if "integration_type" not in man:
    add("WARN", "manifest", "no integration_type")
if "iot_class" not in man:
    add("WARN", "manifest", "no iot_class")
hacs = {}
if (ROOT / "hacs.json").exists():
    hacs = json.loads((ROOT / "hacs.json").read_text())
    if "name" not in hacs:
        add("FAIL", "hacs.json", "hacs.json needs at least 'name'")
    if "homeassistant" not in hacs:
        add("INFO", "hacs.json", "no minimum Home Assistant version ('homeassistant'); verify the APIs used exist in the oldest version you claim")
else:
    add("FAIL", "hacs.json", "hacs.json missing")
if not ((INT / "brand" / "icon.png").exists() or (ROOT / "brand" / "icon.png").exists()):
    add("WARN", "brand", "no brand/icon.png (HACS default list wants it unless the domain is in home-assistant/brands)")
for f in ("LICENSE", "README.md", "CHANGELOG.md"):
    if not (ROOT / f).exists():
        add("WARN" if f != "LICENSE" else "FAIL", "repo", f"{f} missing")
rdm = (ROOT / "README.md").read_text() if (ROOT / "README.md").exists() else ""
mm = re.search(r"Home Assistant (20\d\d\.\d+)(?:\.\d+)? or newer", rdm)
if mm and hacs.get("homeassistant") and not str(hacs["homeassistant"]).startswith(mm.group(1)):
    add("WARN", "hacs.json", f"README says Home Assistant {mm.group(1)} but hacs.json says {hacs['homeassistant']}")
cl = (ROOT / "CHANGELOG.md")
if cl.exists() and man.get("version"):
    m = re.search(r"^##\s*\[?v?(\d+\.\d+\.\d+)", cl.read_text(), re.M)
    if not m or m.group(1) != man["version"]:
        add("WARN", "release", f"CHANGELOG top entry {m.group(1) if m else None} != manifest version {man['version']}")
wf = ROOT / ".github" / "workflows"
names = " ".join(p.read_text() for p in wf.glob("*.y*ml")) if wf.exists() else ""
for need, label in (("hacs/action", "HACS action"), ("hassfest", "hassfest")):
    if need not in names:
        add("WARN", "ci", f"no {label} workflow in .github/workflows (HACS default inclusion needs both to pass)")

# ---- event loop: blocking calls ----------------------------------------------------------------------------------------
BLOCK_CALLS = {
    "open": "file I/O", "time.sleep": "time.sleep", "ZoneInfo": "ZoneInfo(...) reads the tz database (use dt_util.async_get_time_zone)",
    "os.listdir": "file I/O", "os.scandir": "file I/O", "os.walk": "file I/O", "os.stat": "file I/O", "os.path.exists": "file I/O",
    "os.path.isfile": "file I/O", "os.path.isdir": "file I/O", "glob.glob": "file I/O", "glob.iglob": "file I/O",
    "subprocess.run": "subprocess", "subprocess.Popen": "subprocess", "subprocess.check_output": "subprocess",
    "urllib.request.urlopen": "blocking HTTP", "socket.socket": "blocking socket", "socket.create_connection": "blocking socket",
    "importlib.import_module": "import_module reads files (use async_import_module)",
}
BLOCK_ATTRS = {"read_text": "pathlib file I/O", "read_bytes": "pathlib file I/O", "write_text": "pathlib file I/O", "write_bytes": "pathlib file I/O"}


def dotted(n: ast.AST) -> str:
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Attribute):
        return dotted(n.value) + "." + n.attr
    return ""


class V(ast.NodeVisitor):
    def __init__(self, fn: str) -> None:
        self.fn, self.stack = fn, []

    def _fn(self, node, is_async):
        self.stack.append((node.name, is_async)); self.generic_visit(node); self.stack.pop()

    def visit_FunctionDef(self, node): self._fn(node, False)
    def visit_AsyncFunctionDef(self, node): self._fn(node, True)

    def visit_Call(self, node):
        name = dotted(node.func)
        why = BLOCK_CALLS.get(name) or (name.split(".")[0] == "requests" and "requests is blocking HTTP") or \
              (BLOCK_ATTRS.get(node.func.attr) if isinstance(node.func, ast.Attribute) else None)
        if why and not self._in_executor(node):
            in_async = bool(self.stack) and self.stack[-1][1]
            add("FAIL" if in_async else "WARN", "blocking", f"{self.fn}:{node.lineno} {name or '...'}() - {why}" + ("" if in_async else " (sync function: fine only if it runs in an executor)"))
        self.generic_visit(node)

    def visit_Import(self, node):
        if self.stack and self.stack[-1][1]:
            add("WARN", "blocking", f"{self.fn}:{node.lineno} import inside an async function (reads files on first use)")

    visit_ImportFrom = visit_Import

    @staticmethod
    def _in_executor(node) -> bool:
        return False


for fn, text in src.items():
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        add("FAIL", "syntax", f"{fn}: {e}"); continue
    V(fn).visit(tree)
if not any(a == "blocking" for _, a, _ in OUT):
    ok("blocking", "no blocking calls found in any module")

# ---- name collisions: a platform module (time.py, select.py, ...) rebinds the same name in the package's __init__ namespace ----
if "__init__.py" in src:
    stems = {p.stem for p in PY} - {"__init__"}
    try:
        tree0 = ast.parse(src["__init__.py"])
        bound = {}
        for n in tree0.body:
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    bound[(a.asname or a.name).split(".")[0]] = n.lineno
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bound[n.name] = n.lineno
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        bound[t.id] = n.lineno
        for name, line in sorted(bound.items(), key=lambda x: x[1]):
            if name in stems:
                add("FAIL", "name-collision", f"__init__.py:{line} binds the name {name!r}, but {name}.py is a submodule: when Home Assistant imports it the name is silently replaced by the module ('module' object is not callable). Import it as another name")
    except SyntaxError:
        pass

# ---- quality scale: structure ------------------------------------------------------------------------------------------
init = src.get("__init__.py", "")
platforms = re.findall(r"PLATFORMS\s*(?::[^=]+)?=\s*\[([^\]]*)\]", init)
plat_names = re.findall(r"[\"'](\w+)[\"']", platforms[0]) if platforms else []
for p in plat_names:
    t = src.get(f"{p}.py", "")
    if "PARALLEL_UPDATES" not in t:
        add("WARN", "quality/silver", f"{p}.py has no PARALLEL_UPDATES (0 for coordinator-driven read-only entities, 1 for entities that send commands)")
checks = [
    ("runtime_data" in init, "quality/bronze", "ConfigEntry.runtime_data is used"),
    ("async_unload_entry" in init, "quality/silver", "async_unload_entry exists"),
    ("async_step_reauth" in src.get("config_flow.py", ""), "quality/silver", "re-authentication flow exists"),
    ("async_get_clientsession" in "".join(src.values()), "quality/platinum", "the shared aiohttp session is used"),
    ("ClientSession(" not in "".join(src.values()), "quality/platinum", "no own ClientSession is created"),
    ("_attr_has_entity_name" in "".join(src.values()), "quality/bronze", "has_entity_name is set"),
    ("unique_id" in "".join(src.values()), "quality/bronze", "entities have unique ids"),
    ("async_config_entry_first_refresh" in init or "ConfigEntryNotReady" in init, "quality/bronze", "setup verifies the connection (test-before-setup)"),
    ("_abort_if_unique_id_configured" in src.get("config_flow.py", ""), "quality/bronze", "duplicate config entries are prevented"),
]
for cond, area, text in checks:
    ok(area, text) if cond else add("WARN", area, "MISSING: " + text)
if "async_register" in init and "async def async_setup(" not in init:
    add("WARN", "quality/bronze", "services are registered but not in async_setup (action-setup rule)")
for optional, area, text in (("diagnostics.py", "quality/gold", "diagnostics.py (redact tokens, ids, addresses)"), ("icons.json", "quality/gold", "icons.json (entity icons)"),
                             ("repairs.py", "quality/gold", "repairs (issues the user can fix)")):
    if not (INT / optional).exists():
        add("INFO", area, f"no {text}")
if "async_step_reconfigure" not in src.get("config_flow.py", ""):
    add("INFO", "quality/gold", "no reconfigure flow")
if not (ROOT / "tests").exists():
    add("WARN", "quality/bronze", "no tests directory")
else:
    tests = " ".join(p.read_text() for p in (ROOT / "tests").rglob("*.py"))
    if "config_flow" not in tests:
        add("INFO", "quality/bronze", "no config-flow tests (bronze 'config-flow-test-coverage'; needs pytest-homeassistant-custom-component)")

# ---- strings / translations / services ---------------------------------------------------------------------------------
def leafs(d, prefix=""):
    if isinstance(d, dict):
        for k, v in d.items():
            yield from leafs(v, f"{prefix}{k}.")
    else:
        yield prefix[:-1]


strings = {}
if (INT / "strings.json").exists():
    strings = json.loads((INT / "strings.json").read_text())
    base = set(leafs(strings))
    for tf in sorted((INT / "translations").glob("*.json")):
        keys = set(leafs(json.loads(tf.read_text())))
        for k in sorted(base - keys):
            add("WARN", "translations", f"{tf.name} lacks {k}")
        for k in sorted(keys - base):
            add("WARN", "translations", f"{tf.name} has {k} that strings.json does not")
    code = "".join(src.values())
    exc = set(strings.get("exceptions", {}))
    for k in sorted(set(re.findall(r"translation_key\s*=\s*f?[\"']([^\"'{}]+)[\"']", code))):
        if k not in exc and k not in strings.get("entity", {}).get("sensor", {}) and not any(k in v for v in strings.get("entity", {}).values()):
            add("FAIL", "strings", f"translation_key {k!r} is used in code but not defined in strings.json")
    errs = set(strings.get("config", {}).get("error", {}))
    cf = src.get("config_flow.py", "")
    for k in sorted(set(re.findall(r"return\s+[\"'](\w+)[\"']", cf)) | set(re.findall(r"errors\[[\"']base[\"']\]\s*=\s*[\"'](\w+)[\"']", cf))):
        if k not in errs:
            add("FAIL", "strings", f"config flow returns error {k!r} that strings.json config.error lacks (the user would see the bare key)")
    steps = set(strings.get("config", {}).get("step", {}))
    for k in re.findall(r"def async_step_(\w+)", cf):
        if k not in steps and k not in ("reauth", "import", "reconfigure"):
            add("WARN", "strings", f"config step {k!r} has no text in strings.json config.step")
else:
    add("WARN", "strings", "no strings.json")
svc_yaml = (INT / "services.yaml")
reg = set(re.findall(r"async_register\(\s*DOMAIN\s*,\s*([A-Z_]+)", init))
consts = dict(re.findall(r"^([A-Z_]+)\s*=\s*[\"'](\w+)[\"']", init, re.M))
reg_names = {consts.get(c, c) for c in reg}
if svc_yaml.exists():
    ymal = set(re.findall(r"^(\w+):\s*$", svc_yaml.read_text(), re.M))
    for s in sorted(reg_names - ymal):
        add("WARN", "services", f"service {s!r} is registered but missing in services.yaml")
    for s in sorted(ymal - reg_names):
        add("WARN", "services", f"services.yaml has {s!r} that is not registered")
    for s in sorted(reg_names - set(strings.get("services", {}))):
        add("WARN", "services", f"service {s!r} has no name/description in strings.json")
elif reg_names:
    add("WARN", "services", "services are registered but services.yaml is missing")

# ---- README sections ---------------------------------------------------------------------------------------------------
rd = (ROOT / "README.md").read_text().lower() if (ROOT / "README.md").exists() else ""
for key, label in (("install", "installation"), ("remov", "removal instructions"), ("limitation", "known limitations"),
                   ("troubleshoot", "troubleshooting"), ("privacy", "privacy / data handling")):
    if key not in rd:
        add("WARN", "docs", f"README has no {label} section")

# ---- private data in tracked files -------------------------------------------------------------------------------------
try:
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
except Exception:
    files = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]
PAT = [(r"\b(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)\b", "private IP"),
       (r"[\w.+-]+@(?!users\.noreply\.github\.com)[\w-]+\.[\w.]+", "e-mail address"),
       (r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "UUID"),
       (r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[\"'][A-Za-z0-9_\-]{16,}[\"']", "credential-looking value")]
for f in files:
    p = ROOT / f
    if not p.is_file() or p.suffix in (".png", ".jpg", ".ico", ".gif") or f == "LICENSE":
        continue
    try:
        text = p.read_text()
    except Exception:
        continue
    for rx, label in PAT:
        for m in re.finditer(rx, text):
            line = text.count("\n", 0, m.start()) + 1
            if "example" in text[max(0, m.start() - 40):m.end() + 40].lower() or "noreply" in m.group(0):
                continue
            add("WARN", "private-data", f"{f}:{line} {label}: {m.group(0)[:40]}")

# ---- report ------------------------------------------------------------------------------------------------------------
order = {"FAIL": 0, "WARN": 1, "INFO": 2, "OK": 3}
counts = {k: 0 for k in order}
print(f"audit of {ROOT.name} (domain {DOMAIN}, version {man.get('version')}, platforms {plat_names})")
for level, area, text in sorted(OUT, key=lambda x: (order[x[0]], x[1])):
    counts[level] += 1
    if level != "OK":
        print(f"[{level:4s}] {area:16s} {text}")
print("OK items:", counts["OK"], "|", " ".join(f"{k}={v}" for k, v in counts.items() if k != "OK"))
sys.exit(1 if counts["FAIL"] else 0)
