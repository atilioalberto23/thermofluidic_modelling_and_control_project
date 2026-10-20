"""Exporta las dos ilustraciones del HTML a EPS y PDF vectoriales.

Uso: .venv/Scripts/python.exe output/exportar_pinn.py
Requiere Matplotlib, fontTools e Inkscape. Las letras se convierten en
contornos para conservar Computer Modern sin depender de fuentes instaladas.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zlib

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'pinn-mpl-cache'))
from fontTools.ttLib import TTFont
from matplotlib.font_manager import FontProperties, findfont
from matplotlib.path import Path as MplPath
from matplotlib.textpath import TextPath, TextToPath

OUT = Path(__file__).resolve().parent
TARGET = OUT.parent / 'docs/latex/figuras_metodologia'
SVG = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG)
ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')


def extract(document, ident):
    start = document.index('<svg class="diagram" id="' + ident + '"')
    depth = 0
    for match in re.finditer(r'<svg\b|</svg>', document[start:]):
        depth += -1 if match.group() == '</svg>' else 1
        if depth == 0:
            return ET.fromstring(document[start:start + match.end()])
    raise ValueError('SVG incompleto: ' + ident)


def path_data(path):
    commands = []
    operations = {MplPath.MOVETO: 'M', MplPath.LINETO: 'L', MplPath.CURVE3: 'Q', MplPath.CURVE4: 'C'}
    for points, code in path.iter_segments(curves=True, simplify=False):
        if code == MplPath.CLOSEPOLY:
            commands.append('z')
        else:
            commands.append(operations[code] + ' '.join(f'{v:.6f}' for v in points))
    return ''.join(commands)


def expanded_pdf(data):
    """Incluye los objetos comprimidos de los PDF 1.5 producidos por Cairo."""
    streams = []
    for match in re.finditer(rb'stream\r?\n(.*?)\r?\nendstream', data, re.S):
        try:
            streams.append(zlib.decompress(match.group(1)))
        except zlib.error:
            pass
    return data + b''.join(streams)


def outline_labels(root, fonts, fallback):
    layout = TextToPath()
    count = 0
    for parent in list(root.iter()):
        for index, node in enumerate(list(parent)):
            if node.tag != f'{{{SVG}}}text':
                continue
            text = ''.join(node.itertext())
            assert len(node) == 0, 'Los rótulos deben ser texto simple.'
            cls = node.attrib.get('class', '')
            size = {'title': 24, 'small': 20, 'tiny': 18}.get(cls, 22)
            font_path, cmap = fonts['bold' if cls == 'title' else 'normal']
            runs = []
            for char in text:
                chosen = font_path if ord(char) in cmap else fallback
                if runs and runs[-1][0] == chosen:
                    runs[-1][1] += char
                else:
                    runs.append([chosen, char])
            width = 0
            paths = []
            for chosen, run in runs:
                prop = FontProperties(fname=str(chosen), size=size)
                if run.strip():
                    paths.append(path_data(TextPath((width, 0), run, size=size, prop=prop, usetex=False)))
                width += layout.get_text_width_height_descent(run, prop, ismath=False)[0]
            x, y = float(node.attrib['x']), float(node.attrib['y'])
            anchor = node.attrib.get('text-anchor', 'start')
            x -= width / 2 if anchor == 'middle' else width if anchor == 'end' else 0
            group = ET.Element(f'{{{SVG}}}g', {
                'aria-label': text,
                'transform': f'translate({x:.6f} {y:.6f}) scale(1 -1)',
                'fill': '#514855' if cls in ('small', 'tiny') else '#000004',
            })
            ET.SubElement(group, f'{{{SVG}}}path', {'d': ''.join(paths)})
            parent.remove(node)
            parent.insert(index, group)
            count += 1
    assert not any(n.tag in (f'{{{SVG}}}text', f'{{{SVG}}}image') for n in root.iter())
    return count


def main():
    inkscape = shutil.which('inkscape') or next((str(p) for p in [
        Path('C:/Program Files/Inkscape/bin/inkscape.com'),
        Path('C:/Program Files/Inkscape/bin/inkscape.exe'),
    ] if p.exists()), None)
    if not inkscape:
        raise SystemExit('Se requiere Inkscape para exportar EPS y PDF.')
    TARGET.mkdir(parents=True, exist_ok=True)
    document = (OUT / 'arquitectura_pinn.html').read_text(encoding='utf-8')
    jobs = [('diagram-inferencia', 'pinn_01_arquitectura'), ('diagram-entrenamiento', 'pinn_02_entrenamiento')]
    with TemporaryDirectory(prefix='pinn-vectores-', ignore_cleanup_errors=True) as folder:
        temp = Path(folder)
        fonts = {}
        for kind, name in [('normal', 'cmunrm'), ('bold', 'cmunbx')]:
            font = TTFont(OUT / f'{name}.woff')
            font.flavor = None
            path = temp / f'{name}.ttf'
            font.save(path)
            fonts[kind] = path, set(font.getBestCmap())
        fallback = Path(findfont('DejaVu Sans'))
        for ident, basename in jobs:
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
            eps = (TARGET / f'{basename}.eps').read_bytes()
            assert eps.startswith(b'%!PS-Adobe') and b'EPSF' in eps[:100]
            eps_body = eps.split(b'%%EndProlog', 1)[-1]
            assert not re.search(rb'(?<![/\w])(?:image|colorimage|cairo_image|cairo_imagemask)(?![\w])', eps_body), 'EPS rasterizado'
            assert not re.search(rb'\b(?:findfont|selectfont|setfont)\b', eps_body), 'Fuentes externas en EPS'
            pdf = expanded_pdf((TARGET / f'{basename}.pdf').read_bytes())
            assert not re.search(rb'/Subtype\s*/Image\b', pdf), 'PDF rasterizado'
            assert not re.search(rb'/Type\s*/Font\b', pdf), 'Quedan fuentes sin convertir a contornos'
            assert len(re.findall(rb'/Type\s*/Page\b', pdf)) == 1
            print(f'{basename}: EPS y PDF vectoriales; {count} rotulos convertidos a contornos; sin imagenes rasterizadas.', flush=True)


if __name__ == '__main__':
    main()
