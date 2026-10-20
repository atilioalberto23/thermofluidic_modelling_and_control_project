"""Exporta las dos familias del HTML a EPS y PDF para la metodología.

Uso: .venv/Scripts/python.exe output/exportar_modalidades.py
Conserva la paleta Inferno y convierte Computer Modern en contornos.
"""
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

os.environ.setdefault('MPLCONFIGDIR', str(Path(gettempdir()) / 'modalidades-mpl-cache'))
from fontTools.ttLib import TTFont
from matplotlib.font_manager import findfont
from exportar_pinn import extract, outline_labels, expanded_pdf

OUT = Path(__file__).resolve().parent
TARGET = OUT.parent / 'docs/latex/figuras_metodologia'
JOBS = [
    ('modalidad-determinista', 'modelos_01_deterministicos'),
    ('modalidad-no-determinista', 'modelos_02_basados_datos'),
]


def main():
    inkscape = shutil.which('inkscape') or next((str(p) for p in [
        Path('C:/Program Files/Inkscape/bin/inkscape.com'),
        Path('C:/Program Files/Inkscape/bin/inkscape.exe'),
    ] if p.exists()), None)
    if not inkscape:
        raise SystemExit('Se requiere Inkscape para exportar EPS y PDF.')
    TARGET.mkdir(parents=True, exist_ok=True)
    document = (OUT / 'modalidades_modelos_experimentos.html').read_text(encoding='utf-8')
    with TemporaryDirectory(prefix='modalidades-vectores-', ignore_cleanup_errors=True) as folder:
        fonts = {}
        for kind, name in [('normal', 'cmunrm'), ('bold', 'cmunbx')]:
            font = TTFont(OUT / f'{name}.woff')
            font.flavor = None
            path = Path(folder) / f'{name}.ttf'
            font.save(path)
            fonts[kind] = path, set(font.getBestCmap())
        fallback = Path(findfont('DejaVu Sans'))
        for ident, basename in JOBS:
            root = extract(document, ident)
            count = outline_labels(root, fonts, fallback)
            root.attrib.pop('class', None)
            source = OUT / f'{basename}.svg'
            ET.ElementTree(root).write(source, encoding='utf-8', xml_declaration=True)
            for ext in ['eps', 'pdf']:
                target = TARGET / f'{basename}.{ext}'
                command = [inkscape, '--batch-process', '--export-area-page', '--export-text-to-path', f'--export-type={ext}', f'--export-filename={target}', str(source)]
                result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                if result.returncode:
                    raise RuntimeError(result.stderr)
                assert target.exists() and target.stat().st_size > 1000, target
                print(f'{target.name}: {target.stat().st_size:,} bytes.', flush=True)
            eps = (TARGET / f'{basename}.eps').read_bytes()
            assert eps.startswith(b'%!PS-Adobe') and b'EPSF' in eps[:100]
            body = eps.split(b'%%EndProlog', 1)[-1]
            assert not re.search(rb'(?<![/\w])(?:image|colorimage|cairo_image|cairo_imagemask)(?![\w])', body), 'EPS rasterizado'
            assert not re.search(rb'\b(?:findfont|selectfont|setfont)\b', body), 'Fuentes externas en EPS'
            pdf = expanded_pdf((TARGET / f'{basename}.pdf').read_bytes())
            assert not re.search(rb'/Subtype\s*/Image\b', pdf), 'PDF rasterizado'
            assert not re.search(rb'/Type\s*/Font\b', pdf), 'Fuentes sin convertir a contornos'
            assert len(re.findall(rb'/Type\s*/Page\b', pdf)) == 1
            print(f'{basename}: {count} rotulos convertidos a contornos; EPS y PDF vectoriales verificados.', flush=True)


if __name__ == '__main__':
    main()
