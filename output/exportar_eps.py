"""Exporta los cuadros SVG a EPS con geometría y letras vectoriales.

Uso: python3 output/exportar_eps.py
Requiere rsvg-convert y Ghostscript. Usa las fuentes Computer Modern locales;
no convierte los PNG ni requiere instalar paquetes de Python.
"""

import argparse
import copy
import html
import json
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path


OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--html", default="geometria_synthetic_data.html")
parser.add_argument("--paneles", default="paneles.json")
parser.add_argument("--zip", default="cuadros_vectoriales_eps.zip")
args = parser.parse_args()


def decode_woff(source, target):
    """Recupera las tablas OpenType del WOFF sin modificar los glifos."""
    data = source.read_bytes()
    assert data[:4] == b"wOFF", source
    count = struct.unpack_from(">H", data, 12)[0]
    power = 2 ** int(math.log2(count))
    header = struct.pack(">4sHHHH", data[4:8], count, power*16, int(math.log2(power)), count*16-power*16)
    offset = 12 + 16*count
    directory, contents = bytearray(), bytearray()
    head_offset = None
    for index in range(count):
        tag, start, compressed, original, checksum = struct.unpack_from(">4sIIII", data, 44+20*index)
        table = data[start:start+compressed]
        if compressed < original:
            table = zlib.decompress(table)
        assert len(table) == original
        if tag == b"head":
            table = table[:8] + b"\0\0\0\0" + table[12:]
            head_offset = offset
        directory.extend(struct.pack(">4sIII", tag, checksum, offset, original))
        padded = table + b"\0" * ((-len(table)) % 4)
        contents.extend(padded)
        offset += len(padded)
    sfnt = bytearray(header + directory + contents)
    checksum = sum(struct.unpack(f">{len(sfnt)//4}I", sfnt)) & 0xffffffff
    if head_offset is not None:
        struct.pack_into(">I", sfnt, head_offset+8, (0xB1B0AFBA-checksum) & 0xffffffff)
    target.write_bytes(sfnt)


def run(command, env=None):
    return subprocess.run(command, env=env, check=True, capture_output=True, text=True, timeout=60)


rsvg, gs = shutil.which("rsvg-convert"), shutil.which("gs")
if not rsvg or not gs:
    raise SystemExit("Se requieren rsvg-convert y Ghostscript para exportar EPS.")
document_path = OUT / args.html
document = document_path.read_text()
svg = ET.fromstring(re.search(r"<svg.*?</svg>", document, re.S).group())
assert not any(el.tag.endswith("image") for el in svg.iter()), "El esquema debe contener solo vectores."
panels = json.loads((OUT / args.paneles).read_text())
width, height = map(float, svg.attrib["viewBox"].split()[2:])
jobs = [("Figura completa", document_path.with_suffix(".eps").name, [0, 0, width, height])] + [
    (info["title"], str(Path(info["file"]).with_suffix(".eps")), info["box"]) for info in panels.values()
]
ET.register_namespace("", "http://www.w3.org/2000/svg")

with tempfile.TemporaryDirectory(prefix="geometria-eps-") as folder:
    temp = Path(folder)
    fonts = temp / "fonts"
    fonts.mkdir()
    for name in ("cmunrm", "cmunbx", "cmunti"):
        decode_woff(OUT / f"{name}.woff", fonts / f"{name}.ttf")
    config = temp / "fonts.conf"
    config.write_text(f'''<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig><dir>{html.escape(str(fonts))}</dir>
<dir>/System/Library/Fonts/Supplemental</dir><cachedir>{html.escape(str(temp / "cache"))}</cachedir>
<alias><family>Computer Modern</family><prefer><family>CMU Serif</family></prefer></alias>
</fontconfig>''')
    env = dict(os.environ, FONTCONFIG_FILE=str(config))
    fc_match = shutil.which("fc-match")
    if fc_match:
        match = run([fc_match, "-f", "%{family}", "Computer Modern"], env).stdout
        assert "CMU Serif" in match, f"Fuente incorrecta: {match}"
    for title, filename, box in jobs:
        panel = copy.deepcopy(svg)
        panel.set("viewBox", " ".join(map(str, box)))
        panel.set("width", str(box[2]))
        panel.set("height", str(box[3]))
        source = temp / "panel.svg"
        ET.ElementTree(panel).write(source, encoding="utf-8", xml_declaration=True)
        intermediate = temp / "panel.eps"
        run([rsvg, "--format=eps", "--background-color=white", "--output", str(intermediate), str(source)], env)
        target = OUT / filename
        run([gs, "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-dEPSCrop", "-dNoOutputFonts",
             "-sDEVICE=eps2write", "-dAutoRotatePages=/None", f"-sOutputFile={target}", str(intermediate)])
        assert target.read_bytes().startswith(b"%!PS-Adobe-3.0 EPSF-3.0")
        # Volver a PDF permite comprobar que no hay imágenes ni fuentes externas.
        verification = temp / "verificar.pdf"
        run([gs, "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-dEPSCrop", "-sDEVICE=pdfwrite",
             "-dCompressStreams=false", f"-sOutputFile={verification}", str(target)])
        pdf = verification.read_bytes()
        assert not re.search(rb"/Subtype\s*/Image\b", pdf), f"Contenido rasterizado: {filename}"
        assert not re.search(rb"/Type\s*/Font\b", pdf), f"Texto sin convertir a trazados: {filename}"
        print(f"{title}: {filename}; geometría y letras vectoriales, sin imágenes rasterizadas.", flush=True)

with zipfile.ZipFile(OUT / args.zip, "w", zipfile.ZIP_DEFLATED) as archive:
    for _, filename, _ in jobs:
        archive.write(OUT / filename, filename)
