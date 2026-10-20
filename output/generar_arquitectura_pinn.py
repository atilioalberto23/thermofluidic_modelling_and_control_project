"""Genera las dos figuras de la PINN de la metodología refactorizada.

Las figuras documentan la formulación de cuatro estados; el HTML identifica
por separado la implementación de seis estados disponible en el repositorio.
Ejecutar desde la raíz: .venv/Scripts/python.exe output/generar_arquitectura_pinn.py
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

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'pinn-mpl-cache'))
import matplotlib as mpl
from matplotlib.font_manager import FontProperties
from matplotlib.mathtext import math_to_image

OUT = Path(__file__).resolve().parent
mpl.rcParams.update({'mathtext.fontset': 'cm', 'svg.fonttype': 'path', 'text.usetex': False})
DATA, NET, AD, LOSS, PHYS, REST = [mpl.colors.to_hex(mpl.colormaps['inferno'](i/7)) for i in range(1,7)]
INK, MUTED, RULE = '#000004', '#514855', '#d0cbd2'
LICENSE = (OUT / 'LICENCIA_Computer_Modern.txt').read_text(encoding='utf-8')
FONT_CSS = '/*\n' + LICENSE + '\n*/\n'
for file, weight, style in [('cmunrm.woff',400,'normal'),('cmunbx.woff',700,'normal'),('cmunti.woff',400,'italic')]:
    FONT_CSS += f"@font-face{{font-family:'Computer Modern';font-weight:{weight};font-style:{style};src:url(data:font/woff;base64,{base64.b64encode((OUT/file).read_bytes()).decode()}) format('woff')}}\n"

def pale(color):
    return mpl.colors.to_hex(tuple(.96+.04*c for c in mpl.colors.to_rgb(color)))

eq_count = 0
def math_svg(x,y,tex,size=26,max_width=None,center=False):
    global eq_count
    eq_count += 1
    buffer=BytesIO()
    math_to_image('$'+tex+'$',buffer,prop=FontProperties(size=size),format='svg',color=INK)
    raw=buffer.getvalue().decode()
    root=ET.fromstring(raw)
    vb=root.attrib['viewBox']
    w,h=map(float,vb.split()[2:])
    if max_width and w>max_width:
        h*=max_width/w;w=max_width
    body=raw[raw.index('>',raw.index('<svg'))+1:raw.rindex('</svg>')]
    body=re.sub(r'<metadata>.*?</metadata>','',body,flags=re.S)
    body=re.sub(r'<g id="patch_1">.*?</g>','',body,flags=re.S)
    for old in sorted(set(re.findall(r'\bid="([^"]+)"',body)),key=len,reverse=True):
        new=f'm{eq_count}-{old}'
        body=body.replace(f'id="{old}"',f'id="{new}"').replace(f'#{old}"',f'#{new}"').replace(f'#{old})',f'#{new})')
    if center:x-=w/2
    return f'<svg data-equation="{eq_count}" x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" viewBox="{vb}" role="img" aria-label="{escape(tex,quote=True)}"><title>{escape(tex)}</title>{body}</svg>'

class Figure:
    def __init__(self,ident,height,title,description):
        self.ident=ident
        self.parts=[f'<svg class="diagram" id="{ident}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 1600 {height}" width="1600" height="{height}" role="img" aria-labelledby="{ident}-title {ident}-desc">',f'<title id="{ident}-title">{escape(title)}</title><desc id="{ident}-desc">{escape(description)}</desc>',f'''<defs><marker id="{ident}-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="{INK}"/></marker></defs>
        <style>#{ident}{{background:white}}#{ident} text{{font-family:'Computer Modern',serif;font-size:22px;fill:{INK}}}#{ident} .title{{font-size:24px;font-weight:700}}#{ident} .small{{font-size:20px;fill:{MUTED}}}#{ident} .tiny{{font-size:18px;fill:{MUTED}}}</style><rect width="1600" height="{height}" fill="white"/>''']
    def add(self,s):self.parts.append(s)
    def text(self,x,y,s,cls='',anchor=None):
        self.add(f'<text x="{x}" y="{y}" class="{cls}"'+(f' text-anchor="{anchor}"' if anchor else '')+f'>{escape(s)}</text>')
    def box(self,x,y,w,h,color=RULE,physics=False):
        self.add(f'<rect data-box="true" x="{x}" y="{y}" width="{w}" height="{h}" fill="{pale(color)}" stroke="{color}" stroke-width="{2.5 if physics else 1.3}"/>')
        self.add(f'<path d="M{x} {y}H{x+w}" stroke="{color}" stroke-width="{4 if physics else 2.5}"/>')
    def line(self,x1,y1,x2,y2,color=RULE,width=1):
        self.add(f'<path d="M{x1} {y1}L{x2} {y2}" fill="none" stroke="{color}" stroke-width="{width}"/>')
    def arrow(self,*points):
        route=json.dumps(points,separators=(',',':'))
        d='M'+'L'.join(f'{x} {y}' for x,y in points)
        self.add(f'<path class="connector" data-route=\'{route}\' d="{d}" fill="none" stroke="{INK}" stroke-width="1.8" marker-end="url(#{self.ident}-arrow)"/>')
    def eq(self,x,y,tex,**kwargs):self.add(math_svg(x,y,tex,**kwargs))
    def finish(self):return '\n'.join(self.parts)+'\n</svg>'

f=Figure('diagram-inferencia',910,'Mapa condicional del recinto sin carga: cuatro estados','Variables del segmento, red neuronal diferenciable y reconstrucción del estado con condición inicial exacta, según met:flujo_pinn. Dos conectores horizontales ocupan corredores independientes de los textos. Las anchuras y la profundidad de las capas ocultas se representan de forma genérica porque la metodología no las fija.')
f.text(50,45,'(a) Arquitectura del mapa de flujo condicional','title')
f.box(50,90,370,510,DATA)
f.text(76,129,'Variables del segmento','title')
f.text(76,174,'Tiempo local','small')
f.eq(76,189,r's\in[0,\Delta t_c]',max_width=315)
f.text(76,262,'Estado inicial del recinto','small')
f.eq(76,278,r'\mathbf{x}_k=[T_c,T_b,T_a,W]_k^{\mathsf{T}}',size=24,max_width=315)
f.text(76,353,'Modos de los ventiladores','small')
f.eq(76,369,r'\mathbf{u}_k=[u_{\mathrm{APK}},u_{\mathrm{Zeus}}]_k^{\mathsf{T}}',size=24,max_width=315)
f.text(76,446,'Perturbaciones ambientales','small')
f.eq(76,463,r'\mathbf{d}_k=[G,T_{\mathrm{amb}},W_{\mathrm{amb}},',size=23,max_width=315)
f.eq(103,501,r'p,v_{w,x},v_{w,y}]_k^{\mathsf{T}}',size=23,max_width=285)
f.text(76,575,'Tildes: entradas normalizadas.','tiny')
f.arrow((420,350),(500,350))

f.box(500,170,600,430,NET)
f.text(526,210,'Red neuronal diferenciable','title')
f.eq(800,233,r'\mathcal{N}_\eta:\mathbb{R}^{n_z}\longrightarrow\mathbb{R}^{4}',size=27,max_width=530,center=True)
columns=[(555,[321,356,391,426]),(715,[306,341,376,411,446]),(875,[306,341,376,411,446]),(1035,[321,356,391,426])]
for (lx,lys),(rx,rys) in zip(columns,columns[1:]):
    for ly in lys:
        for ry in rys:f.line(lx+6,ly,rx-6,ry,'#dac8df',.7)
for x,ys in columns:
    for y in ys:f.add(f'<circle cx="{x}" cy="{y}" r="6" fill="white" stroke="{NET}" stroke-width="1.4"/>')
for x,label in [(555,'Entrada'),(715,'Oculta 1'),(875,'Oculta L'),(1035,'Salida: 4')]:f.text(x,492,label,'tiny',anchor='middle')
f.text(800,530,'Esquema genérico de capas ocultas.','small',anchor='middle')
f.text(800,563,'Activación suave; tamaños por seleccionar.','tiny',anchor='middle')
f.arrow((1100,350),(1180,350))

f.box(1180,170,370,430,NET)
f.text(1206,210,'Reconstrucción del estado','title')
f.eq(1206,265,r'\delta\mathbf{x}=\frac{s}{\Delta t_c}\mathcal{N}_\eta(\mathbf{z})\odot\mathbf{s}_x',size=26,max_width=318)
f.eq(1206,351,r'\widehat{\mathbf{x}}_\eta(s)=\mathbf{x}_k+\delta\mathbf{x}',size=27,max_width=318)
f.box(1204,431,322,78,NET)
f.eq(1365,452,r'\widehat{\mathbf{x}}_\eta(0)=\mathbf{x}_k',size=27,max_width=288,center=True)
f.text(1365,557,'Tres temperaturas y una humedad.','tiny',anchor='middle')
f.text(1365,583,'Escalas físicas por componente.','tiny',anchor='middle')
f.eq(800,637,r'\mathbf{z}=[s/\Delta t_c,\widetilde{\mathbf{x}}_k,\widetilde{\mathbf{u}}_k,\widetilde{\mathbf{d}}_k]',size=25,max_width=1000,center=True)
f.box(50,705,1500,150,NET)
f.text(76,742,'Definición del mapa de flujo · met:flujo_pinn','small')
f.eq(800,773,r'\widehat{\mathbf{x}}_\eta(s;\mathbf{x}_k,\mathbf{u}_k,\mathbf{d}_k)=\mathbf{x}_k+\frac{s}{\Delta t_c}\mathcal{N}_\eta\!\left(\frac{s}{\Delta t_c},\widetilde{\mathbf{x}}_k,\widetilde{\mathbf{u}}_k,\widetilde{\mathbf{d}}_k\right)\odot\mathbf{s}_x',size=31,max_width=1435,center=True)
f.text(50,890,'η: pesos y sesgos de la red. sₓ: escalas de los cuatro estados. ⊙: producto por componente.','tiny')
FIG1=f.finish()

f=Figure('diagram-entrenamiento',1515,'Entrenamiento con los cuatro balances de la metodología refactorizada','Flujo vertical sin retornos: estado predicho, balances físicos y diferenciación automática, residuales y tres términos de pérdida, objetivo ponderado. Los balances corresponden a cubierta, base, aire y razón de humedad del recinto sin carga, con inventario constante de aire seco. Los parámetros físicos se denotan theta y los pesos neuronales eta.')
f.text(50,45,'(b) Balances del recinto y función de pérdida de la PINN','title')
f.box(50,90,1500,145,NET)
f.text(76,128,'Estado predicho en los puntos de colocación','title')
f.eq(800,151,r'\widehat{\mathbf{x}}_\eta(s_\ell;\mathbf{x}_k,\mathbf{u}_k,\mathbf{d}_k)=[\widehat{T}_c,\widehat{T}_b,\widehat{T}_a,\widehat{W}]^{\mathsf{T}}',size=30,max_width=1380,center=True)
f.text(800,218,'La derivada temporal mantiene fijas las condiciones del segmento.','tiny',anchor='middle')
f.arrow((525,235),(525,310))
f.arrow((1315,235),(1315,310))

f.box(50,310,950,665,PHYS,physics=True)
f.text(76,352,'Ecuaciones físicas del recinto sin carga','title')
f.text(76,381,'Aproximación de inventario constante de aire seco.','small')
balances=[
    (412,r'C_c\dot T_c=Q_{\mathrm{sol},c}+G_{ca}(T_a-T_c)+Q_{b\to c}^{\mathrm{rad}}-Q_{c,\mathrm{ext}}'),
    (482,r'C_b\dot T_b=Q_{\mathrm{sol},b}+G_{ba}(T_a-T_b)-Q_{b\to c}^{\mathrm{rad}}-Q_{b,\mathrm{ext}}'),
    (552,r'C_a(W)\dot T_a=G_{ca}(T_c-T_a)+G_{ba}(T_b-T_a)'),
    (590,r'\qquad+F_{\mathrm{ext}}(c_{da}+W_{\mathrm{amb}}c_{pv})(T_{\mathrm{amb}}-T_a)+Q_{\mathrm{fan}}'),
    (668,r'm_{da}\dot W=F_{\mathrm{ext}}(W_{\mathrm{amb}}-W)'),
]
for y,tex in balances:f.eq(76,y,tex,size=26,max_width=892)
f.eq(76,742,r'C_a(W)=m_{da}(c_{da}+Wc_{pv})',size=25,max_width=892)
f.eq(76,811,r'Q_{b\to c}^{\mathrm{rad}}=\dfrac{\sigma(T_b^4-T_c^4)}{\dfrac{1-\epsilon_b}{A_b\epsilon_b}+\dfrac{1}{A_bF_{bc}}+\dfrac{1-\epsilon_c}{A_c\epsilon_c}}',size=26,max_width=892)
f.text(76,950,'Punto superior: derivada temporal. Convenciones y unidades en la nomenclatura.','tiny')

f.box(1080,310,470,160,AD)
f.text(1106,352,'Diferenciación automática','title')
f.eq(1315,388,r'\frac{\partial\widehat{\mathbf{x}}_\eta}{\partial s}',size=33,max_width=415,center=True)
f.arrow((1315,470),(1315,545))
f.box(1080,545,470,230,LOSS)
f.text(1106,588,'Residuales de los balances','title')
f.eq(1106,622,r'r_q=\frac{\partial\hat x_q}{\partial s}-f_q(\widehat{\mathbf{x}},\mathbf{u}_k,\mathbf{d}_k;\boldsymbol{\theta})',size=27,max_width=418)
f.eq(1106,716,r'q\in\{T_c,T_b,T_a,W\}',size=24,max_width=418)
f.arrow((1000,660),(1080,660))
f.arrow((1315,775),(1315,1050))

f.box(50,1050,445,185,DATA)
f.text(76,1092,'Datos observados','title')
f.eq(76,1131,r'\mathcal{L}_D:\quad\mathcal{H}_j[\widehat{\mathbf{x}}]\;\leftrightarrow\;y_j',size=27,max_width=390)
f.text(76,1207,'Comparación en el soporte del sensor.','tiny')
f.box(545,1050,455,185,REST)
f.text(571,1092,'Restricciones del dominio','title')
f.eq(571,1131,r'\mathcal{L}_R:\quad W\geq0,\quad C_c,C_b,C_a>0',size=25,max_width=400)
f.text(571,1207,'Estados termodinámicamente admisibles.','tiny')
f.box(1080,1050,470,185,PHYS,physics=True)
f.text(1106,1092,'Pérdida física escalada','title')
f.eq(1106,1121,r'\mathcal{L}_F=\frac{1}{N_f}\sum_{\ell=1}^{N_f}\sum_q\left[\frac{r_q(s_\ell)}{s_q/\Delta t_c}\right]^2',size=27,max_width=418)
for x in [272.5,772.5,1315]:f.arrow((x,1235),(x,1320))
f.box(50,1320,1500,140,LOSS)
f.eq(800,1350,r'\mathcal{L}_{\mathrm{PINN}}=\lambda_D\mathcal{L}_D+\lambda_F\mathcal{L}_F+\lambda_R\mathcal{L}_R',size=34,max_width=1400,center=True)
f.text(800,1435,'La optimización ajusta η a partir de la pérdida total; los pesos λ y las escalas se fijan en desarrollo.','small',anchor='middle')
f.text(50,1496,'θ: parámetros físicos. η: parámetros neuronales. El operador Hⱼ relaciona estados y observaciones.','tiny')
FIG2=f.finish()

def table(headers,rows):
    return '<div class="table-scroll"><table><thead><tr>'+''.join('<th>'+s+'</th>' for s in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+s+'</td>' for s in row)+'</tr>' for row in rows)+'</tbody></table></div>'

STATE_TABLE=table(['Símbolo','Significado','Unidad / definición'],[
    ('<i>T</i><sub>c</sub>, <i>T</i><sub>b</sub>, <i>T</i><sub>a</sub>','Temperaturas de cubierta, base y aire interior.','K'),
    ('<i>W</i>','Razón de humedad del aire.','kg vapor / kg aire seco'),
    ('<b>x</b>, <b>x</b><sub>k</sub>, x̂<sub>η</sub>','Estado de cuatro componentes; estado al inicio del segmento; estado predicho.','[<i>T</i><sub>c</sub>, <i>T</i><sub>b</sub>, <i>T</i><sub>a</sub>, <i>W</i>]<sup>T</sup>'),
    ('<b>u</b><sub>k</sub>','Modos ejecutados o candidatos de APK y Zeus.','Código explícito de cada modo.'),
    ('<b>d</b><sub>k</sub>','Irradiancia, temperatura y humedad ambiente, presión y viento.','[<i>G</i>, <i>T</i><sub>amb</sub>, <i>W</i><sub>amb</sub>, <i>p</i>, <i>v</i><sub>w,x</sub>, <i>v</i><sub>w,y</sub>]<sup>T</sup>'),
    ('<i>G</i>; <i>p</i>; <i>v</i><sub>w,x</sub>, <i>v</i><sub>w,y</sub>','Irradiancia; presión absoluta; componentes del viento.','W/m²; Pa; m/s'),
    ('<b>c</b>','Configuración del recinto: geometría, propiedades y aberturas.','Configuración fijada para cada caso.'),
    ('<i>s</i>; Δ<i>t</i><sub>c</sub>; <i>k</i>','Tiempo local; duración del segmento; índice del segmento.','s; s; índice'),
])
NETWORK_TABLE=table(['Símbolo','Significado','Convención'],[
    ('<i>η</i>; N<sub>η</sub>','Pesos y sesgos neuronales; red que produce el incremento normalizado.','Se ajustan mediante optimización.'),
    ('<b>z</b>; <i>n</i><sub>z</sub>','Vector concatenado de entradas normalizadas; dimensión de ese vector.','<i>n</i><sub>z</sub> = 1 + 4 + dim(<b>ũ</b>) + dim(<b>d̃</b>).'),
    ('<i>L</i>; «oculta 1», «oculta L»','Número de capas ocultas; primera y última capa oculta.','Esquema genérico: la metodología no fija profundidad ni anchuras.'),
    ('Tilde (~)','Entrada normalizada con transformaciones estimadas en desarrollo.','Se conserva la transformación al evaluar validación y prueba.'),
    ('<b>s</b><sub>x</sub>; <i>s</i><sub>q</sub>','Vector de escalas físicas de estado; escala de su componente <i>q</i>.','K para temperaturas; kg/kg para <i>W</i>.'),
    ('⊙; δ<b>x</b>','Producto por componente; incremento de estado en unidades físicas.','δ<b>x</b> = (<i>s</i>/Δ<i>t</i><sub>c</sub>) N<sub>η</sub>(<b>z</b>) ⊙ <b>s</b><sub>x</sub>.'),
    ('<i>θ</i>; <b>f</b>','Parámetros físicos; derivadas de los estados dadas por los balances.','<b>f</b> = [Ṫ<sub>c</sub>, Ṫ<sub>b</sub>, Ṫ<sub>a</sub>, Ẇ]<sup>T</sup>.'),
    ('<i>q</i>; <i>r</i><sub>q</sub>','Índice de componente; residual de su ecuación diferencial.','<i>q</i> ∈ {<i>T</i><sub>c</sub>, <i>T</i><sub>b</sub>, <i>T</i><sub>a</sub>, <i>W</i>}. Unidades del estado/s.'),
    ('<i>s</i><sub>ℓ</sub>; <i>N</i><sub>f</sub>','Tiempo del punto de colocación ℓ; número de puntos de colocación.','Se evalúan dentro del dominio admitido.'),
    ('H<sub>j</sub>; <i>y</i><sub>j</sub>','Operador de observación del sensor <i>j</i>; observación disponible.','Relaciona estado, soporte espacial y magnitud del instrumento.'),
    ('ℒ<sub>D</sub>; ℒ<sub>F</sub>; ℒ<sub>R</sub>','Pérdidas de datos, física y restricciones.','La condición inicial estructural se satisface por construcción.'),
    ('λ<sub>D</sub>; λ<sub>F</sub>; λ<sub>R</sub>','Pesos de las tres contribuciones de pérdida.','Se declaran junto con la normalización y la selección en desarrollo.'),
])
PHYSICS_TABLE=table(['Símbolo','Significado / convención de signo','Unidad'],[
    ('<i>C</i><sub>c</sub>, <i>C</i><sub>b</sub>, <i>C</i><sub>a</sub>(<i>W</i>)','Capacidades térmicas de cubierta, base y aire húmedo.','J/K'),
    ('<i>G</i><sub>ca</sub>, <i>G</i><sub>ba</sub>','Conductancias de intercambio cubierta–aire y base–aire; pueden depender del modo de ventilación.','W/K'),
    ('<i>Q</i><sub>sol,c</sub>, <i>Q</i><sub>sol,b</sub>','Potencia solar absorbida por cubierta y base; positiva hacia el nodo.','W'),
    ('<i>Q</i><sub>c,ext</sub>, <i>Q</i><sub>b,ext</sub>','Pérdidas térmicas exteriores; positivas al salir de cubierta o base.','W'),
    ('<i>Q</i><sup>rad</sup><sub>b→c</sub>','Intercambio radiativo neto: positivo desde la base hacia la cubierta.','W'),
    ('<i>F</i><sub>ext</sub>','Flujo exterior de aire seco, con entrada y salida equilibradas en esta reducción.','kg aire seco/s'),
    ('<i>m</i><sub>da</sub>','Inventario de aire seco, constante en las ecuaciones de la figura.','kg aire seco'),
    ('<i>c</i><sub>da</sub>, <i>c</i><sub>pv</sub>','Calores específicos del aire seco y del vapor.','J/(kg·K)'),
    ('<i>Q</i><sub>fan</sub>','Fracción de la potencia del equipo transferida al dominio modelado.','W'),
    ('<i>A</i><sub>b</sub>, <i>A</i><sub>c</sub>','Áreas de base y cubierta para el cierre radiativo de dos superficies.','m²'),
    ('<i>ε</i><sub>b</sub>, <i>ε</i><sub>c</sub>; <i>F</i><sub>bc</sub>','Emisividades; factor de forma de la base hacia la cubierta.','Adimensional'),
    ('<i>σ</i>','Constante de Stefan–Boltzmann.','W/(m²·K⁴)'),
    ('Punto superior; ∂/∂<i>s</i>','Derivada temporal de los balances; derivada de la red respecto del tiempo local.','Condiciones del segmento fijas al derivar.'),
])
COMPARISON=table(['Aspecto','Metodología refactorizada · figuras','Código disponible · referencia separada'],[
    ('Estado','Cuatro componentes: <i>T</i><sub>c</sub>, <i>T</i><sub>b</sub>, <i>T</i><sub>a</sub>, <i>W</i>.','Seis: <i>T</i><sub>c</sub>, <i>T</i><sub>b</sub>, <i>T</i><sub>p</sub>, <i>T</i><sub>a</sub>, <i>W</i>, <i>M</i>; <i>T</i><sub>p</sub> es temperatura del producto y <i>M</i> su humedad en base seca.'),
    ('Arquitectura','Salida de dimensión cuatro; tamaños y profundidad sujetos a selección.','<code>13 → 32 → 32 → 6</code>, activación Tanh, 1 702 parámetros, <code>float64</code>.'),
    ('Entradas','Tiempo, estado inicial, actuación y perturbaciones normalizados.','<code>seconds</code>, <code>initial</code> y <code>boundary</code>; esta última tiene seis condiciones.'),
    ('Física','Balances del recinto sin carga; radiación base–cubierta.','<code>thermal_rhs</code> incluye producto, secado y evaporación.'),
    ('Pérdida física','(1/<i>N</i><sub>f</sub>) ∑<sub>ℓ</sub> ∑<sub>q</sub> del residual normalizado al cuadrado.','<code>mean()</code> sobre muestras y seis componentes: factor 1/(6<i>N</i><sub>f</sub>).'),
    ('Configuración','Δ<i>t</i><sub>c</sub> y pesos λ se seleccionan y documentan.','Configuración base: 20 s; pesos (1, 1, 10); Adam con lr = 10⁻³; máximo 300 épocas, paciencia 60.'),
])

CSS=f'''
:root{{--ink:{INK};--muted:{MUTED};--rule:{RULE};--purple:{NET};--physics:{PHYS}}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth;scroll-padding-top:20px}}body{{margin:0;background:white;color:var(--ink);font:19px/1.55 'Computer Modern',serif}}a{{color:{DATA};text-underline-offset:3px}}button{{font:inherit;cursor:pointer}}a:focus-visible,button:focus-visible,.diagram-scroll:focus-visible{{outline:2px solid {PHYS};outline-offset:4px}}
header,main{{max-width:1560px;margin:auto;padding-left:28px;padding-right:28px}}header{{padding-top:35px;padding-bottom:22px;text-align:center;border-bottom:1px solid var(--ink)}}.kicker{{font-size:14px;letter-spacing:.05em;text-transform:uppercase}}h1{{font-size:38px;font-weight:400;line-height:1.2;margin:16px 0}}header p{{max-width:1100px;margin:0 auto;font-size:19px}}nav{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;padding:17px 0;font-size:16px}}.nav-links{{display:flex;gap:13px 24px;flex-wrap:wrap}}.button{{border:1px solid var(--rule);background:white;padding:5px 12px;white-space:nowrap;font-size:16px;color:var(--ink)}}.button:hover{{border-color:var(--purple);background:{pale(NET)}}}
.reference{{border-left:3px solid var(--purple);padding:9px 17px;margin:0 0 28px;font-size:17px}}.reference p{{margin:0}}.reference p+p{{margin-top:5px}}section{{margin-top:30px}}.figure-section{{border-top:1px solid var(--ink);margin:30px 0 42px}}.figure-heading{{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;padding-top:18px}}h2{{font-size:28px;line-height:1.25;font-weight:400;margin:0 0 12px}}.figure-heading p{{margin:0 0 16px;color:var(--muted);font-size:18px;max-width:1150px}}figure{{margin:0}}.diagram-scroll{{overflow-x:auto}}.diagram{{display:block;width:100%;height:auto;min-width:1080px}}figcaption{{font-size:18px;border-top:1px solid var(--rule);padding:13px 0;line-height:1.5}}.reading-key{{padding:12px 17px;background:#faf9fb;border-left:2px solid var(--rule);font-size:17px}}.reading-key p{{margin:0}}.reading-key p+p{{margin-top:5px}}h3{{font-size:22px;font-weight:700;margin:24px 0 12px}}p{{margin:10px 0}}code{{font:14px/1.6 'Courier New',monospace;overflow-wrap:anywhere}}.table-scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:17px;line-height:1.45;margin-bottom:20px}}thead{{border-top:1px solid var(--ink);border-bottom:1px solid var(--ink)}}th,td{{padding:10px 12px;text-align:left;vertical-align:top}}th{{font-weight:700;background:white}}td{{border-bottom:1px solid #e1dee3}}td:first-child{{width:21%;min-width:170px}}.source{{font-size:16px;color:var(--muted)}}.scope-note{{font-size:17px;padding:13px 17px;border:1px solid var(--rule)}}.legend{{display:flex;flex-wrap:wrap;gap:10px 25px;font-size:16px;margin:12px 0}}.legend span{{display:inline-flex;align-items:center;gap:9px}}.legend i{{width:22px;height:4px;display:inline-block}}footer{{font-size:15px;color:var(--muted);padding:19px 0 30px;border-top:1px solid var(--rule);margin-top:28px}}#status{{position:fixed;right:20px;bottom:20px;background:{DATA};color:white;padding:9px 15px;font-size:16px}}#status:empty{{display:none}}
@media(max-width:760px){{header,main{{padding-left:16px;padding-right:16px}}h1{{font-size:30px}}h2{{font-size:25px}}.figure-heading{{flex-direction:column;gap:8px}}.figure-heading .button{{margin-bottom:10px}}td:first-child{{min-width:120px}}}}
@media print{{@page{{size:A3 portrait;margin:12mm}}header{{padding-top:0}}nav,.button,#status{{display:none}}main,header{{max-width:none;padding-left:0;padding-right:0}}.figure-section{{break-before:page;border-top:0}}figure,.figure-heading{{break-inside:avoid}}.diagram{{min-width:0}}.diagram-scroll{{overflow:visible}}#nomenclatura,#implementacion{{break-before:page}}h2,h3{{break-after:avoid}}tr{{break-inside:avoid}}a{{color:inherit;text-decoration:none}}*{{print-color-adjust:exact;-webkit-print-color-adjust:exact}}}}
'''

METHOD='../docs/latex/main/ch4_methodology_refactorizada.tex'
SRC='../thermofluidic-modelling-and-control-project/src/thermofluidic_modelling_and_control_project/pipelines/thesis_models/'
HTML=f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>PINN del recinto sin carga · Metodología refactorizada</title>
<style id="font-definitions">{FONT_CSS}</style><style>{CSS}</style></head><body>
<header><div class="kicker">Modelado termofluídico · Formulación metodológica de cuatro estados</div><h1>PINN condicional del recinto sin carga</h1><p>Arquitectura del mapa de flujo, balances físicos y entrenamiento, con la notación de la metodología refactorizada.</p></header>
<main>
<nav aria-label="Navegación"><div class="nav-links"><a href="#arquitectura">Figura 1 · Arquitectura</a><a href="#entrenamiento">Figura 2 · Física y pérdidas</a><a href="#nomenclatura">Nomenclatura</a><a href="#implementacion">Correspondencia con el código</a></div><button class="button" id="print" type="button">Imprimir / PDF</button></nav>
<aside class="reference"><p><strong>Referencia de las figuras:</strong> <a href="{METHOD}">ch4_methodology_refactorizada.tex</a>, apartados «Variables, entradas y configuración», «Ensamblaje de la red de cuatro estados» y «PINN condicional de cuatro estados».</p><p>Los esquemas representan el recinto sin carga con <b>x</b> = [<i>T</i><sub>c</sub>, <i>T</i><sub>b</sub>, <i>T</i><sub>a</sub>, <i>W</i>]<sup>T</sup>. La implementación disponible de seis estados se documenta en la <a href="#implementacion">tabla de correspondencia</a>.</p></aside>

<section class="figure-section" id="arquitectura" aria-labelledby="architecture-heading"><div class="figure-heading"><div><h2 id="architecture-heading">1. Mapa de flujo y condición inicial exacta</h2><p>Las condiciones del segmento parametrizan una red diferenciable. Su salida se transforma en un incremento físico y se suma al estado inicial.</p></div><div><button class="button" type="button" data-download="diagram-inferencia" data-filename="pinn_01_arquitectura.svg">SVG</button> <a class="button" href="../docs/latex/figuras_metodologia/pinn_01_arquitectura.eps" download>EPS</a> <a class="button" href="../docs/latex/figuras_metodologia/pinn_01_arquitectura.pdf" download>PDF</a></div></div>
<figure><div class="diagram-scroll" role="region" aria-label="Figura 1 con desplazamiento horizontal" tabindex="0">{FIG1}</div><figcaption><strong>Figura 1.</strong> Representación de <code>met:estados_entradas</code> y <code>met:flujo_pinn</code>. La condición inicial se satisface por construcción: en <i>s</i> = 0 el incremento se anula. Las capas ocultas se ilustran de forma genérica, de acuerdo con la selección de arquitectura prevista en la metodología.</figcaption></figure>
<div class="reading-key"><p><strong>Lectura de los símbolos.</strong> <b>x</b><sub>k</sub>: estado inicial; <b>u</b><sub>k</sub>: modos de los ventiladores; <b>d</b><sub>k</sub>: ambiente; <i>η</i>: pesos y sesgos neuronales; <b>s</b><sub>x</sub>: escalas físicas. Las tildes indican normalización.</p><p><strong>Dimensiones.</strong> La salida tiene cuatro componentes. La dimensión de entrada <i>n</i><sub>z</sub> depende de la codificación explícita de los modos. Un código escalar por ventilador da 1 + 4 + 2 + 6 = 13 entradas; la metodología deja la arquitectura sujeta a selección.</p></div></section>

<section class="figure-section" id="entrenamiento" aria-labelledby="training-heading"><div class="figure-heading"><div><h2 id="training-heading">2. Ecuaciones físicas y función objetivo</h2><p>Los cuatro balances del recinto producen las derivadas físicas. Su diferencia con las derivadas de la red define los residuales que intervienen en la pérdida.</p></div><div><button class="button" type="button" data-download="diagram-entrenamiento" data-filename="pinn_02_entrenamiento.svg">SVG</button> <a class="button" href="../docs/latex/figuras_metodologia/pinn_02_entrenamiento.eps" download>EPS</a> <a class="button" href="../docs/latex/figuras_metodologia/pinn_02_entrenamiento.pdf" download>PDF</a></div></div>
<figure><div class="diagram-scroll" role="region" aria-label="Figura 2 con desplazamiento horizontal" tabindex="0">{FIG2}</div><div class="legend" aria-label="Leyenda"><span><i style="background:{NET}"></i>Red neuronal</span><span><i style="background:{PHYS}"></i>Balances y pérdida física</span><span><i style="background:{AD}"></i>Diferenciación automática</span><span><i style="background:{DATA}"></i>Datos</span><span><i style="background:{REST}"></i>Restricciones</span><span><i style="background:{LOSS}"></i>Residuales y pérdida total</span></div><figcaption><strong>Figura 2.</strong> Balances de <code>met:red_cubierta</code>, <code>met:red_base</code>, <code>met:red_aire</code>, <code>met:red_humedad</code> y cierre <code>met:red_radiacion</code>; residuales y pérdida de <code>met:residual_pinn</code> y <code>met:perdida_pinn</code>. La expresión física conserva el factor 1/<i>N</i><sub>f</sub> y la suma sobre las cuatro componentes indicados en la metodología.</figcaption></figure>
<div class="reading-key"><p><strong>Dos grupos de parámetros.</strong> <i>η</i> contiene pesos y sesgos neuronales; <i>θ</i> contiene parámetros físicos. La metodología permite fijar <i>θ</i> mediante identificación o estimarlo en desarrollo con cotas y análisis de identificabilidad.</p><p><strong>Alcance físico.</strong> Las ecuaciones mostradas corresponden a la aproximación de inventario constante de aire seco. La metodología también desarrolla una formulación conservativa de inventario variable en su apartado específico.</p><p><strong>Evaluación.</strong> Se selecciona con error sobre observaciones, equilibrio de gradientes y estabilidad de propagación. Se informa error por estado y horizonte, residual físico, error inicial y acumulación entre segmentos.</p></div></section>

<section id="nomenclatura" aria-labelledby="nomenclature-heading"><h2 id="nomenclature-heading">Nomenclatura y convenciones</h2><p>El subíndice <i>c</i> identifica la cubierta; <i>b</i>, la base; <i>a</i>, el aire; «amb», el ambiente; «ext», el intercambio exterior. El superíndice T indica transposición.</p><h3>Estados, entradas y tiempo</h3>{STATE_TABLE}<h3>Red, residuales y pérdidas</h3>{NETWORK_TABLE}<h3>Balances térmicos, renovación y radiación</h3>{PHYSICS_TABLE}<p class="source">La irradiancia <i>G</i> se expresa en W/m²; las conductancias <i>G</i><sub>ca</sub> y <i>G</i><sub>ba</sub>, en W/K. El flujo másico <i>F</i><sub>ext</sub> se distingue del factor de forma radiativo <i>F</i><sub>bc</sub>.</p></section>

<section id="implementacion" aria-labelledby="implementation-heading"><h2 id="implementation-heading">Correspondencia con la implementación disponible</h2><p class="scope-note">Las figuras documentan la formulación de cuatro estados de la metodología refactorizada. El código consultado conserva una PINN de seis estados con producto. Esta diferencia se mantiene explícita: las figuras de cuatro estados no acreditan que esa adaptación esté implementada o entrenada.</p>{COMPARISON}<p class="source">Fuentes de implementación: <a href="{SRC}pinn.py">pinn.py</a>, <a href="{SRC}thermal.py">thermal.py</a> y <a href="../thermofluidic-modelling-and-control-project/conf/base/parameters_thesis_models.yml">parameters_thesis_models.yml</a>. Referencia metodológica: <a href="{METHOD}">ch4_methodology_refactorizada.tex</a>.</p></section>
<footer>Tipografía Computer Modern incrustada · Paleta Inferno, seis tonos · Ecuaciones vectoriales · <a href="LICENCIA_Computer_Modern.txt">Licencia de las fuentes</a></footer></main><div id="status" role="status" aria-live="polite"></div>
<script>
document.getElementById('print').addEventListener('click',()=>window.print());
document.querySelectorAll('[data-download]').forEach(button=>button.addEventListener('click',()=>{{
  const copy=document.getElementById(button.dataset.download).cloneNode(true);copy.removeAttribute('class');
  const style=document.createElementNS('http://www.w3.org/2000/svg','style');style.textContent=document.getElementById('font-definitions').textContent;copy.prepend(style);
  const url=URL.createObjectURL(new Blob(['<?xml version="1.0" encoding="UTF-8"?>\\n'+new XMLSerializer().serializeToString(copy)],{{type:'image/svg+xml;charset=utf-8'}}));
  const link=document.createElement('a');link.href=url;link.download=button.dataset.filename;document.body.append(link);link.click();link.remove();
  document.getElementById('status').textContent='SVG preparado: '+button.dataset.filename;
  setTimeout(()=>{{URL.revokeObjectURL(url);document.getElementById('status').textContent='';}},4000);
}}));
</script></body></html>'''
path=OUT/'arquitectura_pinn.html'
path.write_text(HTML,encoding='utf-8')
print(f'{path}: {path.stat().st_size:,} bytes; {eq_count} vector equations; methodological reference: four states.')
