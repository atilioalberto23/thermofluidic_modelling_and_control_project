"""Exporta la lámina y cada cuadro con Chrome sin interfaz.

Uso: python3 output/exportar_pngs.py
Requiere Google Chrome; conserva el HTML autónomo y verifica los recortes.
"""

import argparse
import html
import json
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--html", default="geometria_synthetic_data.html")
parser.add_argument("--paneles", default="paneles.json")
parser.add_argument("--panel", action="append", help="Exportar únicamente este cuadro o la figura completa; se puede repetir.")
args = parser.parse_args()
document = OUT / args.html
panels = json.loads((OUT / args.paneles).read_text())
if args.panel and any(p not in ["completo"]+list(panels) for p in args.panel):
    parser.error("Cuadro desconocido.")
viewbox = re.search(r'<svg[^>]*viewBox="0 0 (\d+) (\d+)"', document.read_text())
width, height = map(int, viewbox.groups())
mac_chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
chrome = str(mac_chrome) if mac_chrome.exists() else (shutil.which("google-chrome") or shutil.which("chromium"))
if not chrome:
    raise SystemExit("No se encontró Google Chrome o Chromium.")
jobs = [(None, document.with_suffix(".png").name, width, height)] + [
    (key, str(Path(info["file"]).with_suffix(".png")), info["box"][2], info["box"][3]) for key, info in panels.items()
]
if args.panel:
    jobs = [job for job in jobs if (job[0] or "completo") in args.panel]

with tempfile.TemporaryDirectory(prefix="geometria-chrome-") as profile:
    flags = [chrome, "--headless", "--disable-gpu", "--no-first-run",
             "--no-default-browser-check", "--disable-background-networking",
             "--disable-component-update", "--disable-extensions", "--hide-scrollbars",
             f"--user-data-dir={profile}", "--virtual-time-budget=2000"]
    for panel, filename, w, h in jobs:
        url = document.as_uri() + "?export=1" + (f"&panel={panel}" if panel else "")
        target = OUT / filename
        result = subprocess.run(
            flags + [f"--screenshot={target}", f"--window-size={w},{h}", "--force-device-scale-factor=2", url],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode:
            raise RuntimeError(result.stderr)
        actual_size = struct.unpack(">II", target.read_bytes()[16:24])
        assert actual_size == (w*2, h*2), (filename, actual_size)
        result = subprocess.run(
            flags + ["--dump-dom", f"--window-size={w},{h}", url+"&audit=1"],
            capture_output=True, text=True, timeout=60, check=True,
        )
        match = re.search(r'<pre id="audit-report">(.*?)</pre>', result.stdout, re.S)
        assert match, f"Sin informe de distribución: {filename}"
        audit = json.loads(html.unescape(match.group(1)))
        assert not audit["collisions"] and not audit["outside"] and audit["fontLoaded"], (filename, audit)
        print(f"{filename}: {w*2} × {h*2} px; textos completos y sin superposición.", flush=True)
