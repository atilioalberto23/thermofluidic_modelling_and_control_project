"""Genera las dos familias de modelos como antesala del marco híbrido HPDF.

Clasificación y notación: docs/latex/main/ch4_methodology_refactorizada.tex,
secciones met:cfd, met:red, met:ml, met:pinn y met:hpdf.
Uso: .venv/Scripts/python.exe output/generar_modalidades_modelos.py
"""
from pathlib import Path
from io import BytesIO
from html import escape
import base64
import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'modalidades-mpl-cache'))
import matplotlib as mpl
from matplotlib.font_manager import FontProperties
from matplotlib.mathtext import math_to_image

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
FONT_DIR = OUT
SOURCE = '../thermofluidic-modelling-and-control-project/src/thermofluidic_modelling_and_control_project/pipelines/thesis_models/'
METHOD = '../docs/latex/main/ch4_methodology_refactorizada.tex'
RESULTS = '../docs/latex/main/ch5_results.tex'
MANIFEST = '../thermofluidic-modelling-and-control-project/data/08_reporting/thesis_results/model_execution_manifest.csv'

mpl.rcParams.update({'mathtext.fontset': 'cm', 'svg.fonttype': 'path', 'text.usetex': False})
VIOLET, LEARN, MAGENTA, RED, PHYS, HYBRID = [mpl.colors.to_hex(mpl.colormaps['inferno'](i / 7)) for i in range(1, 7)]
INK, MUTED, RULE = '#000004', '#514855', '#cec9d1'
FONT_CSS = '/*\n' + (FONT_DIR / 'LICENCIA_Computer_Modern.txt').read_text(encoding='utf-8') + '\n*/\n'
for filename, weight, style in [('cmunrm.woff', 400, 'normal'), ('cmunbx.woff', 700, 'normal'), ('cmunti.woff', 400, 'italic')]:
    data = base64.b64encode((FONT_DIR / filename).read_bytes()).decode()
    FONT_CSS += f"@font-face{{font-family:'Computer Modern';font-weight:{weight};font-style:{style};src:url(data:font/woff;base64,{data}) format('woff')}}\n"


def pale(color, amount=.96):
    return mpl.colors.to_hex(tuple(amount + (1 - amount) * v for v in mpl.colors.to_rgb(color)))


equation_count = 0


def equation(x, y, tex, size=26, max_width=None, center=False):
    global equation_count
    equation_count += 1
    buffer = BytesIO()
    math_to_image('$' + tex + '$', buffer, prop=FontProperties(size=size), format='svg', color=INK)
    raw = buffer.getvalue().decode()
    root = ET.fromstring(raw)
    width, height = map(float, root.attrib['viewBox'].split()[2:])
    if max_width and width > max_width:
        height *= max_width / width
        width = max_width
    body = raw[raw.index('>', raw.index('<svg')) + 1:raw.rindex('</svg>')]
    body = re.sub(r'<metadata>.*?</metadata>', '', body, flags=re.S)
    body = re.sub(r'<g id="patch_1">.*?</g>', '', body, flags=re.S)
    for old in sorted(set(re.findall(r'\bid="([^"]+)"', body)), key=len, reverse=True):
        new = f'eq{equation_count}-{old}'
        body = body.replace(f'id="{old}"', f'id="{new}"').replace(f'#{old}"', f'#{new}"').replace(f'#{old})', f'#{new})')
    if center:
        x -= width / 2
    return f'<svg data-equation="{equation_count}" x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" viewBox="{root.attrib["viewBox"]}" role="img" aria-label="{escape(tex, quote=True)}"><title>{escape(tex)}</title>{body}</svg>'


class Figure:
    def __init__(self, ident, height, title, description):
        self.ident = ident
        self.parts = [f'<svg class="diagram" id="{ident}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1600" height="{height}" viewBox="0 0 1600 {height}" role="img" aria-labelledby="{ident}-title {ident}-desc">', f'<title id="{ident}-title">{escape(title)}</title><desc id="{ident}-desc">{escape(description)}</desc>', f'''<defs><marker id="{ident}-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="{INK}"/></marker></defs><style>
        #{ident}{{background:white}}#{ident} text{{font-family:'Computer Modern',serif;font-size:22px;fill:{INK}}}#{ident} .title{{font-size:24px;font-weight:700}}#{ident} .small{{font-size:20px;fill:{MUTED}}}#{ident} .tiny{{font-size:18px;fill:{MUTED}}}</style><rect width="1600" height="{height}" fill="white"/>''']

    def add(self, value):
        self.parts.append(value)

    def text(self, x, y, value, cls='', anchor=None):
        self.add(f'<text x="{x}" y="{y}" class="{cls}"' + (f' text-anchor="{anchor}"' if anchor else '') + f'>{escape(value)}</text>')

    def box(self, x, y, width, height, color=RULE):
        self.add(f'<rect data-box="true" x="{x}" y="{y}" width="{width}" height="{height}" fill="{pale(color)}" stroke="{color}" stroke-width="1.6"/>')
        self.add(f'<path d="M{x} {y}H{x + width}" fill="none" stroke="{color}" stroke-width="3"/>')

    def arrow(self, *points):
        route = json.dumps(points, separators=(',', ':'))
        drawing = 'M' + 'L'.join(f'{x} {y}' for x, y in points)
        self.add(f'<path class="connector" data-route=\'{route}\' d="{drawing}" fill="none" stroke="{INK}" stroke-width="1.8" marker-end="url(#{self.ident}-arrow)"/>')

    def eq(self, x, y, tex, **kwargs):
        self.add(equation(x, y, tex, **kwargs))

    def finish(self):
        return '\n'.join(self.parts) + '\n</svg>'


# La primera familia contiene exclusivamente las tres representaciones físicas.
f = Figure('modalidad-determinista', 1160, 'Modelos determinísticos: red térmica, cavidad 2D y CFD 3D', 'La red térmica e higrométrica de cuatro estados, la cavidad bidimensional y el CFD tridimensional forman la familia física. La red y las proyecciones CFD aportan fuentes compatibles al marco híbrido HPDF. La cavidad conserva su función de verificación y estudio mecanístico.')
f.text(50, 45, '(a) Modelos determinísticos · formulación física', 'title')
f.box(50, 90, 1500, 145, RULE)
f.text(76, 128, 'Recinto sin carga · geometría, parámetros, condiciones de frontera y actuación', 'title')
f.eq(800, 150, r'\mathbf{x}=[T_c,T_b,T_a,W]^{\mathsf{T}},\qquad\mathbf{u},\ \mathbf{d},\ \mathbf{c}', size=30, max_width=1400, center=True)
f.text(800, 217, 'Notación de la metodología: estado reducido, acciones, perturbaciones y configuración del recinto.', 'small', anchor='middle')
for x in [275, 800, 1325]:
    f.arrow((x, 235), (x, 310))

f.box(50, 310, 450, 520, PHYS)
f.text(76, 352, 'Red térmica e higrométrica', 'title')
f.eq(76, 390, r'\dot{\mathbf{x}}=\mathbf{f}(\mathbf{x},\mathbf{u},\mathbf{d};\boldsymbol{\theta})', size=29, max_width=398)
for y, text in [(478, 'Capacidades y conductancias.'), (520, 'Captación, radiación y convección.'), (562, 'Renovación y balance de vapor.'), (613, 'Estados: cubierta, base, aire y W.'), (655, 'Identificación con restricciones.'), (697, 'Transitorios de bajo costo.')]:
    f.text(76, y, text, 'small')
f.text(76, 793, 'Aporta trayectorias agregadas al HPDF.', 'tiny')

f.box(575, 310, 450, 520, PHYS)
f.text(601, 352, 'Cavidad bidimensional', 'title')
f.eq(601, 390, r'\nabla_*^2\psi_*=-\omega_*', size=29, max_width=398)
f.eq(601, 453, r'\mathrm{Ra},\ \mathrm{Pr};\qquad\psi_*,\omega_*,\theta', size=27, max_width=398)
for y, text in [(520, 'Convección natural y radiación.'), (562, 'Corriente, vorticidad y temperatura.'), (613, 'Discretización espacial y temporal.'), (655, 'Contraste de mecanismos físicos.')]:
    f.text(601, y, text, 'small')
f.box(596, 699, 408, 108, MAGENTA)
f.text(616, 741, 'Función: verificación', 'title')
f.text(616, 780, 'Contraste de la formulación física.', 'tiny')

f.box(1100, 310, 450, 520, PHYS)
f.text(1126, 352, 'CFD tridimensional', 'title')
f.eq(1126, 390, r'\partial_t\rho+\nabla\cdot(\rho\mathbf{v})=0', size=28, max_width=398)
for y, text in [(478, 'Continuidad, momento y energía.'), (520, 'Transporte de vapor en mezcla.'), (562, 'Dominio fluido, sólidos y fronteras.'), (613, 'Circulación y estratificación.'), (655, 'Ventilación y condiciones de pared.'), (697, 'Refinamiento de malla y tiempo.')]:
    f.text(1126, y, text, 'small')
f.text(1126, 793, 'Aporta campos proyectados al HPDF.', 'tiny')

for x in [275, 1325]:
    f.arrow((x, 830), (x, 900))
f.box(50, 900, 1500, 200, HYBRID)
f.text(800, 941, 'Contribución física al marco híbrido HPDF', 'title', anchor='middle')
f.eq(800, 965, r'\mathbf{y}^{\mathrm{red}}_j=\mathcal{H}_j[\mathbf{x}],\qquad\mathbf{y}^{\mathrm{CFD}}_j=\mathcal{H}_j[\mathbf{U}]', size=29, max_width=1400, center=True)
f.text(800, 1037, 'Red: trayectorias dinámicas · CFD: proyecciones espaciales · Magnitud, unidad, soporte y período comunes.', 'small', anchor='middle')
f.text(800, 1076, 'Los operadores de observación enlazan las simulaciones con las tareas de los modelos basados en datos.', 'small', anchor='middle')
f.text(50, 1140, 'La cavidad verifica mecanismos; las fuentes físicas del enriquecimiento son la red del recinto y las proyecciones CFD.', 'tiny')
FIG1 = f.finish()

# Segunda familia: modelos aprendidos, con la PINN y su rama física explícitas.
f = Figure('modalidad-no-determinista', 1250, 'Modelos no determinísticos o basados en datos: árbol, ensambles y PINN', 'La clasificación sigue el marco de trabajo: los modelos basados en datos incluyen árbol de regresión, XGBoost, LightGBM y PINN. La PINN incorpora balances del recinto en su pérdida. Las tres ramas convergen en aprendizaje enriquecido y correcciones conservativas dentro del HPDF.')
f.text(50, 45, '(b) Modelos no determinísticos · aprendizaje basado en datos', 'title')
f.box(50, 90, 1500, 165, RULE)
f.text(76, 128, 'Observaciones, historial causal y tarea predictiva', 'title')
f.eq(800, 155, r'\widehat{\mathbf{z}}_{k+1}=\mathcal{F}_{\eta}(\mathbf{z}_{k:k-L},\mathbf{u}_{k:k-L},\mathbf{d}_{k:k-L},\mathbf{u}_k,\widehat{\mathbf{d}}_{k+1},\mathbf{c})', size=28, max_width=1400, center=True)
f.text(800, 234, 'Partición temporal común · Preparación ajustada en entrenamiento · Selección con validación de origen rodante.', 'small', anchor='middle')
for x in [275, 800, 1325]:
    f.arrow((x, 255), (x, 330))

f.box(50, 330, 450, 590, LEARN)
f.text(76, 372, 'Árbol de regresión', 'title')
f.eq(76, 410, r'\widehat{\mathbf{z}}=g_{\eta}(\mathbf{z}_{k:k-L},\ldots)', size=29, max_width=398)
for y, text in [(487, 'Particiones del espacio de entradas.'), (529, 'Profundidad, tamaño de hoja y poda.'), (571, 'Relaciones temporales y espaciales.'), (622, 'Referencias: persistencia y red.'), (664, 'Historias: 20, 60 y 300 s.'), (706, 'Horizontes: 20, 300 y 1200 s.'), (812, 'Aprendizaje supervisado.')]:
    f.text(76, y, text, 'small')
f.text(76, 881, 'Predictor de baja complejidad.', 'tiny')

f.box(575, 330, 450, 590, LEARN)
f.text(601, 372, 'XGBoost y LightGBM', 'title')
f.eq(601, 390, r'\mathcal{F}_{\eta}(\cdot)=F_0+\nu\sum_{m=1}^{N_{\mathrm{arb}}}f_m(\cdot)', size=25, max_width=398)
for y, text in [(487, 'Ensambles de árboles potenciados.'), (529, 'Complejidad y tasa de aprendizaje.'), (571, 'Submuestreo y regularización.'), (622, 'Selección por origen rodante.'), (664, 'Misma tarea e información causal.'), (706, 'Preparación ajustada al pasado.'), (812, 'Dependencias no lineales.')]:
    f.text(601, y, text, 'small')
f.text(601, 881, 'Pronóstico por variable y horizonte.', 'tiny')

f.box(1100, 330, 450, 590, LEARN)
f.text(1126, 372, 'PINN condicional', 'title')
f.eq(1126, 410, r'\widehat{\mathbf{x}}_\eta(s)=\mathbf{x}_k+\frac{s}{\Delta t_c}\mathcal{N}_\eta(\mathbf{z}_{\mathrm{PINN}})\odot\mathbf{s}_x', size=26, max_width=398)
f.text(1126, 487, 'Mapa de flujo de cuatro estados.', 'small')
f.text(1126, 529, 'Condición inicial por construcción.', 'small')
f.box(1120, 560, 410, 225, PHYS)
f.text(1140, 600, 'Balances físicos embebidos', 'title')
f.eq(1140, 626, r'\mathbf{r}=\partial_s\widehat{\mathbf{x}}_\eta-\mathbf{f}(\widehat{\mathbf{x}}_\eta,\mathbf{u},\mathbf{d};\boldsymbol{\theta})', size=25, max_width=370)
f.eq(1140, 695, r'\mathcal{L}=\lambda_D\mathcal{L}_D+\lambda_F\mathcal{L}_F+\lambda_R\mathcal{L}_R', size=25, max_width=370)
f.text(1140, 761, 'Red térmica → residual diferenciable.', 'tiny')
f.text(1126, 831, 'Datos + balances + restricciones.', 'small')
f.text(1126, 881, 'Predicción coherente con la física.', 'tiny')

for x in [275, 800, 1325]:
    f.arrow((x, 920), (x, 995))
f.box(50, 995, 1500, 185, HYBRID)
f.text(800, 1036, 'Integración HPDF · aprendizaje enriquecido y corrección conservativa', 'title', anchor='middle')
f.eq(800, 1064, r'\mathcal{L}_{\mathrm{HPDF}}=\sum_{s\in\mathcal{S}}\lambda_s\overline{\mathcal{L}}_s+\lambda_{\mathrm{fis}}\mathcal{L}_{\mathrm{bal}}', size=31, max_width=1400, center=True)
f.text(800, 1162, 'Fuentes compatibles · Ponderación por trayectoria · Positividad y balances · Contraste temporal independiente.', 'small', anchor='middle')
f.text(50, 1224, 'La PINN ocupa la familia de aprendizaje e incorpora conocimiento físico; el HPDF articula las dos familias del marco de trabajo.', 'tiny')
FIG2 = f.finish()


def table(headers, rows):
    return '<div class="table-scroll"><table><thead><tr>' + ''.join('<th>' + h + '</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + v + '</td>' for v in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def link(path, title):
    return f'<a href="{path}">{title}</a>'


def downloads(ident, basename, svg_name):
    assets = '../docs/latex/figuras_metodologia/' + basename
    return f'<div class="downloads" aria-label="Descargas de la figura"><button class="button" type="button" data-download="{ident}" data-filename="{svg_name}">SVG</button><a class="button" href="{assets}.eps" download>EPS</a><a class="button" href="{assets}.pdf" download>PDF</a></div>'


CLASSIFICATION = table(['Familia del marco de trabajo', 'Modelo', 'Función y relación con HPDF'], [
    ('Determinísticos · formulación física', 'Red térmica e higrométrica', 'Cuatro balances del recinto sin carga: T<sub>c</sub>, T<sub>b</sub>, T<sub>a</sub> y W. Produce trayectorias agregadas para identificación, predicción y enriquecimiento.'),
    ('Determinísticos · formulación física', 'Cavidad bidimensional', 'Verifica convección natural y su interacción con radiación. Mantiene una función de verificación y estudio mecanístico; sus soluciones no se incorporan como observaciones del recinto ventilado.'),
    ('Determinísticos · formulación física', 'CFD tridimensional', 'Resuelve circulación, estratificación, energía y vapor. Sus campos se proyectan mediante operadores de observación para construir fuentes compatibles con la tarea de aprendizaje.'),
    ('No determinísticos · basados en datos', 'Árbol de regresión', 'Aprende relaciones entre entradas causales y objetivos. Aporta la referencia de aprendizaje de baja complejidad, con profundidad, hojas y poda seleccionadas temporalmente.'),
    ('No determinísticos · basados en datos', 'XGBoost y LightGBM', 'Ensambles de árboles para pronóstico por variable y horizonte. Pueden entrenarse con fuentes enriquecidas manteniendo algoritmo, tarea e información disponible al comparar variantes.'),
    ('No determinísticos · basados en datos', 'PINN condicional', 'Aprende el mapa de flujo de cuatro estados e incorpora residuales de los balances en la pérdida, junto con datos y restricciones. Enlaza aprendizaje y conocimiento físico dentro de esta familia.'),
    ('Integración de ambas familias', 'HPDF · marco híbrido física–datos', 'Combina observaciones, trayectorias de red y proyecciones CFD. Pondera fuentes por trayectoria e impone balances y correcciones conservativas; compara variantes mediante ablaciones.'),
])

HYBRID_STEPS = table(['Paso del método híbrido', 'Articulación física–datos', 'Criterio conservado'], [
    ('1. Ajuste inicial', 'Definir tarea y observables; identificar la red y ajustar los predictores con la porción de entrenamiento.', 'Misma información causal, unidades, soportes y bloques temporales.'),
    ('2. Selección y simulación', 'Seleccionar casos por cobertura, incertidumbre, inconsistencia y costo; simular con red o CFD según la necesidad.', 'Dominio físicamente admisible, verificación numérica y presupuesto registrado.'),
    ('3. Proyección y enriquecimiento', 'Aplicar ℋ<sub>j</sub> a las trayectorias y campos; incorporar las fuentes al aprendizaje con ponderación por trayectoria.', 'Compatibilidad de magnitud, unidad, soporte espacial y período; procedencia de cada fuente.'),
    ('4. Aprendizaje y corrección', 'Reentrenar el predictor; incorporar residuales PINN o corregir conductancias y cierres de renovación.', 'Positividad y conservación: intercambios internos opuestos y flujos exteriores compatibles con masa y entalpía.'),
    ('5. Ablación y contraste', 'Comparar observaciones solas, enriquecimiento por red, proyecciones CFD y corrección estructurada/PINN.', 'Mismo algoritmo e información al aislar la fuente; selección en desarrollo y contraste final reservado.'),
])

CORRESPONDENCE = table(['Representación metodológica', 'Correspondencia con los artefactos numéricos', 'Fuente local'], [
    ('Red y PINN del recinto: cuatro estados', 'Las ilustraciones utilizan la formulación de la metodología refactorizada. Las pruebas numéricas del módulo thesis_models conservan seis estados, con producto y humedad de carga; esa configuración se identifica por separado.', link(METHOD, 'Metodología: met:red y met:pinn') + '<br>' + link(SOURCE + 'thermal.py', 'thermal.py') + ' · ' + link(SOURCE + 'pinn.py', 'pinn.py')),
    ('Cavidad y CFD', 'Los casos numéricos disponibles documentan la solución de cavidad y una ejecución OpenFOAM aire–vapor. Su alcance de verificación se conserva al relacionarlos con el recinto.', link(SOURCE + 'cavity.py', 'cavity.py') + ' · ' + link(SOURCE + 'openfoam.py', 'openfoam.py')),
    ('Árbol, XGBoost y LightGBM', 'La comparación implementada utiliza los horizontes de 20, 300 y 1200 s, con persistencia como referencia. La procedencia del archivo de entrada pertenece al protocolo de datos.', link(SOURCE + 'learning.py', 'learning.py') + ' · ' + link(MANIFEST, 'Manifiesto de ejecución')),
    ('Enriquecimiento HPDF', 'La formulación, el bucle y las ablaciones se describen en met:hpdf. El apartado res:enriquecimiento delimita la evidencia disponible para cuantificar su efecto; las ilustraciones presentan la articulación metodológica.', link(METHOD, 'Metodología: met:hpdf') + '<br>' + link(RESULTS, 'Resultados: res:enriquecimiento')),
])

NOMENCLATURE = table(['Símbolo o abreviatura', 'Significado', 'Unidad o convención'], [
    ('<b>x</b>; T<sub>c</sub>, T<sub>b</sub>, T<sub>a</sub>; W', 'Estado reducido: temperaturas de cubierta, base y aire, y razón de humedad del aire.', '[K, K, K, kg vapor/kg aire seco]. El recinto metodológico está sin carga.'),
    ('<b>u</b>; <b>d</b>; <b>c</b>', 'Acciones de los ventiladores; perturbaciones ambientales; configuración del recinto.', '<b>d</b> = [G, T<sub>amb</sub>, W<sub>amb</sub>, p, v<sub>w,x</sub>, v<sub>w,y</sub>]<sup>T</sup>; W/m², K, kg/kg, Pa y m/s. Los modos de actuación tienen codificación explícita.'),
    ('<b>f</b>; θ', 'Tasas de los cuatro balances y parámetros físicos.', '<b>f</b>: [K/s, K/s, K/s, (kg/kg)/s]; θ reúne capacidades, conductancias y cierres admisibles.'),
    ('ψ<sub>*</sub>, ω<sub>*</sub>, θ; ∇<sub>*</sub>; Ra, Pr', 'Corriente, vorticidad y temperatura adimensionales de la cavidad; gradiente adimensional; Rayleigh y Prandtl.', 'θ = (T − T<sub>l</sub>)/(T<sub>h</sub> − T<sub>l</sub>), con T<sub>h</sub> y T<sub>l</sub> las temperaturas caliente y fría; θ se distingue del vector de parámetros físicos en negrita.'),
    ('ρ; <b>v</b>; p; T; Y; <b>U</b>', 'Densidad, velocidad, presión, temperatura y fracción másica de vapor; conjunto de campos CFD.', 'kg/m³; m/s; Pa; K; kg vapor/kg mezcla. <b>U</b> abrevia los campos necesarios para el observable.'),
    ('ℋ<sub>j</sub>; <b>y</b><sub>j</sub><sup>red</sup>; <b>y</b><sub>j</sub><sup>CFD</sup>', 'Operador de observación j y salidas compatibles de red o CFD.', 'Conserva magnitud, unidad, soporte y período del observable; para W y energía utiliza proyecciones de inventario.'),
    ('<b>z</b>; k; L; ℱ<sub>η</sub>; g<sub>η</sub>; η', 'Observaciones o estados estimados, índice temporal, longitud del historial, predictor y parámetros aprendidos.', 'El sombrero indica predicción. La información futura corresponde al pronóstico disponible, no a observaciones posteriores del objetivo.'),
    ('F<sub>0</sub>; f<sub>m</sub>; N<sub>arb</sub>; ν', 'Predicción inicial, árbol m, número de árboles y tasa de aprendizaje en la expresión esquemática del ensamble.', 'N<sub>arb</sub> es un conteo; ν pondera la contribución de cada árbol.'),
    ('s; Δt<sub>c</sub>; 𝒩<sub>η</sub>; <b>z</b><sub>PINN</sub>; <b>s</b><sub>x</sub>; ⊙', 'Tiempo local, duración de segmento, red neuronal, entrada normalizada, escalas de estado y producto por componentes.', 's y Δt<sub>c</sub> en segundos; <b>z</b><sub>PINN</sub> concatena s/Δt<sub>c</sub>, estado inicial, acciones y perturbaciones normalizados; <b>s</b><sub>x</sub> tiene las unidades del estado.'),
    ('<b>r</b>; ℒ<sub>D</sub>; ℒ<sub>F</sub>; ℒ<sub>R</sub>; λ<sub>D,F,R</sub>', 'Residual PINN; pérdidas de datos, física y restricciones; pesos de cada término.', 'Los residuales se normalizan por s<sub>q</sub>/Δt<sub>c</sub>. La condición inicial se cumple por la reconstrucción del mapa de flujo.'),
    ('𝒮; λ<sub>s</sub>; ℒ̄<sub>s</sub>; ℒ<sub>bal</sub>; λ<sub>fis</sub>', 'Fuentes HPDF, peso por fuente, pérdida media por trayectoria, penalización de balances y su peso.', '𝒮 reúne observaciones, trayectorias de red y proyecciones CFD; Σ<sub>s</sub>λ<sub>s</sub> = 1. ℒ̄<sub>s</sub> abrevia los dos promedios de met:perdida_hpdf, primero dentro de cada trayectoria y después entre trayectorias de la misma fuente.'),
    ('CFD; ML; PINN; HPDF', 'Dinámica de fluidos computacional; aprendizaje automático; red neuronal informada por la física; marco híbrido física–datos.', 'Las dos primeras figuras siguen las familias del marco de trabajo. HPDF articula sus aportes para una tarea y un contraste comunes.'),
])

CSS = f'''
:root{{--ink:{INK};--muted:{MUTED};--rule:{RULE};--learn:{LEARN};--physical:{PHYS};--hybrid:{HYBRID}}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth;scroll-padding-top:20px}}body{{margin:0;background:white;color:var(--ink);font:19px/1.55 'Computer Modern',serif}}a{{color:{VIOLET};text-underline-offset:3px}}button{{font:inherit;cursor:pointer}}a:focus-visible,button:focus-visible,.diagram-scroll:focus-visible{{outline:2px solid {PHYS};outline-offset:4px}}
header,main{{max-width:1560px;margin:auto;padding-left:28px;padding-right:28px}}header{{padding-top:35px;padding-bottom:24px;text-align:center;border-bottom:1px solid var(--ink)}}.kicker{{font-size:14px;letter-spacing:.05em;text-transform:uppercase}}h1{{font-size:38px;font-weight:400;line-height:1.2;margin:16px 0}}header p{{max-width:1100px;margin:0 auto}}nav{{display:flex;justify-content:space-between;gap:15px;align-items:center;flex-wrap:wrap;padding:16px 0;font-size:16px}}.nav-links{{display:flex;gap:12px 23px;flex-wrap:wrap}}.button{{display:inline-block;border:1px solid var(--rule);background:white;color:var(--ink);font-size:16px;padding:5px 12px;white-space:nowrap;text-decoration:none}}.button:hover{{background:{pale(LEARN)};border-color:var(--learn)}}
.criterion{{border-left:3px solid var(--learn);padding:10px 18px;margin:0 0 18px;font-size:18px}}.criterion p{{margin:0}}.criterion p+p{{margin-top:7px}}.family-key{{display:flex;gap:14px 32px;flex-wrap:wrap;font-size:17px;margin-bottom:28px}}.family-key span{{padding-left:12px;border-left:4px solid var(--physical)}}.family-key .learn{{border-color:var(--learn)}}.family-key .hybrid{{border-color:var(--hybrid)}}.figure-section{{border-top:1px solid var(--ink);margin:30px 0 42px}}.figure-heading{{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;padding-top:18px}}h2{{font-size:28px;font-weight:400;line-height:1.25;margin:0 0 12px}}.figure-heading p{{font-size:18px;color:var(--muted);margin:0 0 16px;max-width:1160px}}figure{{margin:0}}.diagram-scroll{{overflow-x:auto}}.diagram{{display:block;width:100%;min-width:1080px;height:auto}}figcaption{{border-top:1px solid var(--rule);font-size:18px;line-height:1.5;padding:13px 0}}.reading-key{{font-size:17px;padding:12px 18px;background:#faf9fb;border-left:2px solid var(--rule)}}.reading-key p{{margin:0}}.reading-key p+p{{margin-top:7px}}section{{margin-top:32px}}h3{{font-size:22px;font-weight:700;margin:22px 0 11px}}p{{margin:10px 0}}.table-scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:17px;line-height:1.45;margin-bottom:23px}}thead{{border-top:1px solid var(--ink);border-bottom:1px solid var(--ink)}}th,td{{text-align:left;vertical-align:top;padding:10px 12px}}th{{font-weight:700}}td{{border-bottom:1px solid #e2dfe4}}td:first-child{{width:22%;min-width:170px}}.source{{font-size:16px;color:var(--muted)}}footer{{font-size:15px;color:var(--muted);border-top:1px solid var(--rule);margin-top:28px;padding:18px 0 30px}}#status{{position:fixed;bottom:20px;right:20px;background:{VIOLET};color:white;padding:9px 15px;font-size:16px}}#status:empty{{display:none}}
.downloads{{display:flex;gap:6px;align-items:flex-start;flex-shrink:0}}
@media(max-width:760px){{header,main{{padding-left:16px;padding-right:16px}}h1{{font-size:30px}}h2{{font-size:25px}}.figure-heading{{flex-direction:column;gap:8px}}.figure-heading .button{{margin-bottom:10px}}td:first-child{{min-width:125px}}}}
@media print{{@page{{size:A3 portrait;margin:12mm}}nav,.button,#status{{display:none}}header,main{{max-width:none;padding-left:0;padding-right:0}}header{{padding-top:0}}.figure-section{{break-before:page;border-top:0}}figure,.figure-heading{{break-inside:avoid}}.diagram{{min-width:0}}.diagram-scroll{{overflow:visible}}#modelos,#hpdf,#nomenclatura{{break-before:page}}h2,h3{{break-after:avoid}}tr{{break-inside:avoid}}a{{color:inherit;text-decoration:none}}*{{print-color-adjust:exact;-webkit-print-color-adjust:exact}}}}
'''

HTML = f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>Modelos determinísticos, basados en datos e integración HPDF</title><style id="font-definitions">{FONT_CSS}</style><style>{CSS}</style></head><body>
<header><div class="kicker">Modelado termofluídico · Marco de la metodología refactorizada</div><h1>Dos familias de modelos, un marco híbrido física–datos</h1><p>Modelos determinísticos —red térmica, cavidad 2D y CFD 3D— y modelos no determinísticos basados en datos —árbol, ensambles y PINN— como fundamento del método HPDF.</p></header><main>
<nav aria-label="Navegación"><div class="nav-links"><a href="#determinista">Figura 1 · Determinísticos</a><a href="#no-determinista">Figura 2 · Basados en datos</a><a href="#hpdf">Articulación HPDF</a><a href="#modelos">Clasificación</a><a href="#nomenclatura">Nomenclatura</a></div><button class="button" id="print" type="button">Imprimir / PDF</button></nav>
<aside class="criterion"><p><strong>División del marco de trabajo.</strong> La familia determinística se construye mediante balances y ecuaciones físicas del recinto. La familia no determinística corresponde a modelos cuya representación se aprende a partir de datos, incluida la PINN. Esta división por fundamento del modelo organiza las dos ilustraciones.</p><p><strong>Hacia HPDF.</strong> La red y el CFD aportan trayectorias y observables proyectados; los modelos de aprendizaje aprovechan esas fuentes junto con las observaciones del recinto. La PINN muestra explícitamente cómo se incorporan los balances físicos al aprendizaje.</p></aside>
<div class="family-key" aria-label="Clave de colores"><span>Inferno naranja · Formulación física</span><span class="learn">Inferno violeta · Aprendizaje basado en datos</span><span class="hybrid">Inferno oro · Integración HPDF</span></div>

<section class="figure-section" id="determinista" aria-labelledby="heading-det"><div class="figure-heading"><div><h2 id="heading-det">1. Modelos determinísticos: red térmica, cavidad 2D y CFD 3D</h2><p>Tres representaciones físicas con funciones complementarias: dinámica agregada, verificación de mecanismos y resolución espacial del recinto.</p></div>{downloads('modalidad-determinista', 'modelos_01_deterministicos', 'modalidad_determinista.svg')}</div><figure><div class="diagram-scroll" role="region" tabindex="0" aria-label="Modelos determinísticos con desplazamiento horizontal">{FIG1}</div><figcaption><strong>Figura 1.</strong> Familia determinística del marco metodológico. La red térmica e higrométrica utiliza los cuatro estados del recinto sin carga; la cavidad bidimensional verifica convección y radiación; el CFD tridimensional resuelve campos y ventilación. Las flechas inferiores identifican los aportes al enriquecimiento: trayectorias de red y proyecciones CFD mediante ℋ<sub>j</sub>. La cavidad conserva su función de verificación.</figcaption></figure><div class="reading-key"><p><strong>Enlace con la metodología.</strong> Secciones <em>Construcción y verificación del modelo CFD tridimensional</em>, <em>Cavidad bidimensional y red térmica e higrométrica reducida</em> y <em>Operadores de observación y proyección entre modelos</em>: met:cfd, met:red y met:operadores.</p></div></section>

<section class="figure-section" id="no-determinista" aria-labelledby="heading-data"><div class="figure-heading"><div><h2 id="heading-data">2. Modelos no determinísticos: aprendizaje basado en datos y PINN</h2><p>Árbol de regresión, XGBoost, LightGBM y PINN forman la familia aprendida. Se conservan tarea, información causal y partición temporal al comparar sus alternativas.</p></div>{downloads('modalidad-no-determinista', 'modelos_02_basados_datos', 'modalidad_no_determinista.svg')}</div><figure><div class="diagram-scroll" role="region" tabindex="0" aria-label="Modelos basados en datos con desplazamiento horizontal">{FIG2}</div><figcaption><strong>Figura 2.</strong> Familia no determinística o basada en datos, según la clasificación del marco de trabajo. La PINN aprende el mapa de flujo e incorpora los balances de la red en el recuadro naranja de su pérdida. Las tres ramas pueden participar en el marco HPDF mediante fuentes compatibles, ponderación por trayectoria y correcciones que conserven balances. La expresión de ℒ<sub>HPDF</sub> abrevia los promedios por muestra y por trayectoria de la formulación metodológica.</figcaption></figure><div class="reading-key"><p><strong>Enlace con la metodología.</strong> Secciones <em>Modelos basados en datos y PINN del recinto</em> y <em>Enriquecimiento físico–basado en datos</em>: met:ml, met:pinn y met:hpdf. Persistencia y red física identificada funcionan como referencias de comparación.</p></div></section>

<section id="hpdf" aria-labelledby="heading-hpdf"><h2 id="heading-hpdf">De las dos familias al método híbrido HPDF</h2><p>El HPDF conecta fuentes físicas y observaciones con una misma tarea predictiva. La red explora transitorios y secuencias numerosas; el CFD aporta información sobre heterogeneidad y cambios de configuración. Los operadores de observación hacen comparables esas salidas con los objetivos del predictor.</p><p>El aprendizaje enriquecido utiliza pesos por fuente y por trayectoria. La corrección estructurada puede actuar sobre conductancias o renovación manteniendo positividad y consistencia de masa y energía. Para árboles se emplean balances integrados por trayectoria; un predictor diferenciable permite incorporar además residuales diferenciales, como en la PINN.</p>{HYBRID_STEPS}<p class="source">La secuencia sigue met:hpdf, met:perdida_hpdf y el apartado <em>Bucle, ablaciones y criterio de detención</em> de la {link(METHOD, 'metodología refactorizada')}. La selección congela generadores, transformaciones y pesos antes del contraste externo.</p></section>
<section id="modelos" aria-labelledby="heading-models"><h2 id="heading-models">Clasificación y función de cada modelo</h2>{CLASSIFICATION}<h3>Correspondencia entre formulación metodológica y pruebas numéricas</h3>{CORRESPONDENCE}<p class="source">Las figuras adoptan la notación de cuatro estados del recinto sin carga. Las dimensiones y condiciones de las pruebas numéricas se identifican en sus fuentes, conservando el alcance reportado en {link(RESULTS, 'el capítulo de resultados')}.</p></section>
<section id="nomenclatura" aria-labelledby="heading-nomen"><h2 id="heading-nomen">Nomenclatura y unidades</h2>{NOMENCLATURE}</section>
<footer>Computer Modern incrustada · Paleta Inferno · Dos esquemas vectoriales · {link(METHOD, 'Metodología refactorizada')} · <a href="LICENCIA_Computer_Modern.txt">Licencia de las fuentes</a></footer></main><div id="status" role="status" aria-live="polite"></div>
<script>
document.getElementById('print').addEventListener('click',()=>window.print());
document.querySelectorAll('[data-download]').forEach(button=>button.addEventListener('click',()=>{{
 const copy=document.getElementById(button.dataset.download).cloneNode(true);copy.removeAttribute('class');
 const style=document.createElementNS('http://www.w3.org/2000/svg','style');style.textContent=document.getElementById('font-definitions').textContent;copy.prepend(style);
 const url=URL.createObjectURL(new Blob(['<?xml version="1.0" encoding="UTF-8"?>\\n'+new XMLSerializer().serializeToString(copy)],{{type:'image/svg+xml;charset=utf-8'}}));
 const anchor=document.createElement('a');anchor.href=url;anchor.download=button.dataset.filename;document.body.append(anchor);anchor.click();anchor.remove();
 document.getElementById('status').textContent='SVG preparado: '+button.dataset.filename;
 setTimeout(()=>{{URL.revokeObjectURL(url);document.getElementById('status').textContent='';}},4000);
}}));
</script></body></html>'''

destination = OUT / 'modalidades_modelos_experimentos.html'
destination.write_text(HTML, encoding='utf-8')
print(f'{destination}: {destination.stat().st_size:,} bytes; 2 figures; {equation_count} vector equations.')
