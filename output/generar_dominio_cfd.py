"""Lámina vectorial metodológica del dominio CFD, SALOME y OpenFOAM.

python3 output/generar_dominio_cfd.py
Parámetros y datos por confirmar: output/configuracion_cfd.json.
Los elementos de malla son ilustrativos, no una exportación de la malla real.
"""

import base64
import html
import json
import math
import random
import re
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
PARAMETERS = ROOT / "thermofluidic-modelling-and-control-project/conf/base/parameters.yml"
source = PARAMETERS.read_text()
length = float(re.search(r"LEFT_WALL:\s*\n\s*width:\s*([\d.]+)", source)[1])
width = float(re.search(r"BACK_WALL:\s*\n\s*width:\s*([\d.]+)", source)[1])
config_path = OUT / "configuracion_cfd.json"
if not config_path.exists():
    config_path.write_text(json.dumps({
        "longitud_m": length, "anchura_m": width, "altura_m": None,
        "altura_solo_para_dibujo_m": 2.05,
        "forma": "prisma de referencia; confirmar geometría CAD y techo",
        "regiones_confirmadas": [], "material_fluido": None,
        "algoritmo_salome": None, "formato_exportacion_malla": None,
        "numero_celdas": None, "capas_prismaticas": None,
        "velocidad_inicial_m_s": None, "temperatura_inicial_K": None,
        "campo_presion": None, "presion_inicial": None, "unidades_presion": None,
        "solver_openfoam": None,
        "condiciones_frontera": {name: {"velocidad": None, "temperatura": None, "presion": None}
                                  for name in ["izquierda", "derecha", "posterior", "frontal", "techo", "suelo"]},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
CFG = json.loads(config_path.read_text())
L, B = CFG["longitud_m"], CFG["anchura_m"]
H = CFG["altura_m"] or CFG["altura_solo_para_dibujo_m"]
WIDTH, HEIGHT = 1600, 2270
INK, GRAY = "#222222", "#666666"
PURPLE, MAGENTA, ORANGE = "#57106e", "#bc3754", "#f98e09"
COLORS = ["#420a68", "#6a176e", "#932667", "#bc3754", "#e45a31", "#f98e09"]
SURFACES = {
    "izquierda": {"title": "Pared izquierda", "color": COLORS[0], "symbol": "Γ1"},
    "derecha": {"title": "Pared derecha", "color": COLORS[1], "symbol": "Γ2"},
    "posterior": {"title": "Pared posterior", "color": COLORS[2], "symbol": "Γ3"},
    "frontal": {"title": "Pared frontal", "color": COLORS[3], "symbol": "Γ4"},
    "techo": {"title": "Techo", "color": COLORS[4], "symbol": "Γ5"},
    "suelo": {"title": "Suelo", "color": COLORS[5], "symbol": "Γ6"},
}
font_css = []
for name, weight, style in [("cmunrm", 400, "normal"), ("cmunbx", 700, "normal"), ("cmunti", 400, "italic")]:
    data = base64.b64encode((OUT / f"{name}.woff").read_bytes()).decode()
    font_css.append(f"@font-face{{font-family:'Computer Modern';font-weight:{weight};font-style:{style};src:url(data:font/woff;base64,{data}) format('woff')}}")
FONT_CSS = "\n".join(font_css)
parts = []


def add(value):
    parts.append(value)


def num(value, places=2):
    return f"{value:.{places}f}".replace(".", ",")


def pale(color, fraction=.10):
    return "#" + "".join(f"{round(255+(int(color[i:i+2],16)-255)*fraction):02x}" for i in (1,3,5))


def text(x, y, value, size=18, color=INK, anchor="start", italic=False, weight=400):
    add(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}" font-style="{"italic" if italic else "normal"}">{html.escape(str(value))}</text>')


def line(a, b, color="#aaaaaa", size=1, dash=None):
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="{color}" stroke-width="{size}"{extra}/>')


def rectangle(x, y, w, h, fill="white", stroke="#dddddd", size=1):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="{size}"/>')


def polygon(points, fill, stroke, size=1.3, attrs=""):
    points = " ".join(f"{x:.4f},{y:.4f}" for x,y in points)
    add(f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="{size}" stroke-linejoin="round" {attrs}/>')


def circle(x, y, radius=3, color=PURPLE):
    add(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{color}"/>')


def arrow(a, b, color=INK, size=1.4):
    line(a,b,color,size)
    theta=math.atan2(b[1]-a[1],b[0]-a[0])
    for side in (-.48,.48):
        line(b,(b[0]-8*math.cos(theta+side),b[1]-8*math.sin(theta+side)),color,size)


def boundary_faces(l=L, b=B, h=H, exploded=False):
    e=1.0 if exploded else 0
    return {
        "izquierda": [(0,-e,0),(l,-e,0),(l,-e,h),(0,-e,h)],
        "derecha": [(0,b+e,0),(l,b+e,0),(l,b+e,h),(0,b+e,h)],
        "posterior": [(-e,0,0),(-e,b,0),(-e,b,h),(-e,0,h)],
        "frontal": [(l+e,0,0),(l+e,b,0),(l+e,b,h),(l+e,0,h)],
        "techo": [(0,0,h+e),(l,0,h+e),(l,b,h+e),(0,b,h+e)],
        "suelo": [(0,0,-e),(l,0,-e),(l,b,-e),(0,b,-e)],
    }


def dot(a,b):
    return sum(x*y for x,y in zip(a,b))


def sub(a,b):
    return tuple(x-y for x,y in zip(a,b))


def cross(a,b):
    return a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]


def normalize(v):
    d=math.sqrt(dot(v,v));return tuple(x/d for x in v)


class Camera:
    def __init__(self, points, box, eye=(4.5,11.0,8.6)):
        self.eye=eye
        self.forward=normalize(sub((L/2,B/2,H/2),eye))
        self.right=normalize(cross(self.forward,(0,0,1)))
        self.up=cross(self.right,self.forward)
        uv=[self.raw(p) for p in points]
        lo_x,hi_x=min(p[0] for p in uv),max(p[0] for p in uv)
        lo_y,hi_y=min(p[1] for p in uv),max(p[1] for p in uv)
        self.scale=min(box[2]/(hi_x-lo_x),box[3]/(hi_y-lo_y))
        self.center=((lo_x+hi_x)/2,(lo_y+hi_y)/2)
        self.screen=(box[0]+box[2]/2,box[1]+box[3]/2)

    def raw(self,p):
        v=sub(p,self.eye);depth=dot(v,self.forward)
        return dot(v,self.right)/depth,-dot(v,self.up)/depth

    def __call__(self,p):
        u,v=self.raw(p)
        return self.screen[0]+(u-self.center[0])*self.scale,self.screen[1]+(v-self.center[1])*self.scale

    def depth(self,points):
        return sum(dot(sub(p,self.eye),self.forward) for p in points)/len(points)


def sample_face(vertices,u,v):
    a,b,_,d=vertices
    return tuple(a[i]+u*(b[i]-a[i])+v*(d[i]-a[i]) for i in range(3))


def triangular_face(vertices,camera,nx,ny,color,seed):
    """Red triangular perturbada, solo para representar la metodología de mallado."""
    rng=random.Random(seed)
    points={}
    for j in range(ny+1):
        for i in range(nx+1):
            u=i/nx;v=j/ny
            if 0<i<nx and 0<j<ny:
                u+=rng.uniform(-.28,.28)/nx;v+=rng.uniform(-.28,.28)/ny
            points[i,j]=camera(sample_face(vertices,u,v))
    edges=set()
    for j in range(ny):
        for i in range(nx):
            corners=[(i,j),(i+1,j),(i+1,j+1),(i,j+1)]
            for a,b in zip(corners,corners[1:]+corners[:1]):edges.add(tuple(sorted((a,b))))
            edges.add(tuple(sorted((corners[0],corners[2]) if rng.random()<.5 else (corners[1],corners[3]))))
    for a,b in sorted(edges):line(points[a],points[b],color,.60)


def heading(panel,title,subtitle):
    add(f'<g id="panel-{panel}">')
    x,y,_,_=PANELS[panel]["box"]
    text(x+24,y+35,title,24)
    text(x+24,y+67,subtitle,17,GRAY)


def end_panel():
    add('</g>')


PANELS={
    "dominio":{"title":"Dominio y seis superficies","file":"cfd_dominio.eps","box":[48,150,1504,555]},
    "regiones":{"title":"Regiones y fronteras","file":"cfd_regiones.eps","box":[48,735,728,475]},
    "malla":{"title":"Discretización del dominio","file":"cfd_malla.eps","box":[824,735,728,475]},
    "refinamiento":{"title":"Refinamiento cerca de pared","file":"cfd_refinamiento.eps","box":[48,1240,728,495]},
    "iniciales":{"title":"Condiciones iniciales","file":"cfd_condiciones_iniciales.eps","box":[824,1240,728,495]},
    "metodologia":{"title":"Flujo SALOME a OpenFOAM","file":"cfd_metodologia.eps","box":[48,1770,1504,405]},
}
add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="diagram-title diagram-description">')
add('<title id="diagram-title">Dominio, regiones, mallado y condiciones iniciales en CFD</title><desc id="diagram-description">Dominio CFD con cuatro paredes, techo y suelo; regiones, discretización, refinamiento y condiciones iniciales. Metodología SALOME y OpenFOAM.</desc>')
add(f'<style>{FONT_CSS}</style><rect width="{WIDTH}" height="{HEIGHT}" fill="white"/>')
add('<g font-family="Computer Modern, STIX Two Text, Times New Roman, serif">')
text(800,61,"Dominio, regiones y discretización para CFD",35,anchor="middle")
text(800,98,"SALOME → OpenFOAM · Dominio · Regiones · Mallado",20,GRAY,anchor="middle")
line((48,128),(1552,128),INK)

# (a) Seis caras separadas para mostrar toda la envolvente, con líneas de montaje.
heading("dominio","(a) Dominio completo y superficies de frontera","Cuatro paredes, techo y suelo; separación de paneles solo para visualización.")
faces=boundary_faces(exploded=True)
cam=Camera([p for face in faces.values() for p in face],(140,272,810,336),eye=(4.5,11.0,8.6))
assembled=boundary_faces()
for name in faces:
    for p,q in zip(assembled[name],faces[name]):line(cam(p),cam(q),"#aaaaaa",.8,"3 5")
for name,vertices in sorted(faces.items(),key=lambda f:cam.depth(f[1]),reverse=True):
    info=SURFACES[name]
    polygon([cam(p) for p in vertices],pale(info["color"],.12),info["color"],1.5,f'class="boundary-face" data-face="{name}"')
callouts={"izquierda":(120,384),"derecha":(969,498),"posterior":(965,315),"frontal":(120,538),"techo":(526,245),"suelo":(526,635)}
for name,(x,y) in callouts.items():
    vertices=faces[name]
    center=tuple(sum(p[i] for p in vertices)/4 for i in range(3))
    line((x,y-5),cam(center),SURFACES[name]["color"],.9)
    rectangle(x-19,y-22,38,28,"white","none")
    text(x,y,SURFACES[name]["symbol"],18,SURFACES[name]["color"],anchor="middle")
for index,(name,info) in enumerate(SURFACES.items()):
    y=282+index*48
    line((1070,y-5),(1104,y-5),info["color"],3)
    text(1122,y,info["symbol"]+" · "+info["title"],20)
text(1090,605,f"L = {num(L)} m     B = {num(B)} m",19)
text(1090,639,"H" if CFG["altura_m"] is None else f"H = {num(H)} m",19)
text(92,661,"Ω = volumen encerrado por las seis caras",19,italic=True)
text(92,689,"L: longitud · B: anchura · H: altura",17,GRAY)
end_panel()

# (b) El volumen de fluido y los grupos de caras son entidades distintas.
heading("regiones","(b) Región interior y fronteras","Celdas de volumen Ωf y grupos de caras Γi.")
faces=boundary_faces()
cam=Camera([p for face in faces.values() for p in face],(82,838,652,222))
for name in ["izquierda","posterior","suelo"]:
    polygon([cam(p) for p in faces[name]],pale(PURPLE,.07),PURPLE)
for name in ["techo","frontal","derecha"]:
    for a,b in zip(faces[name],faces[name][1:]+faces[name][:1]):line(cam(a),cam(b),PURPLE,1,"4 4")
center=cam((L/2,B/2,H/2))
rectangle(center[0]-57,center[1]-22,114,35,"white","none")
text(center[0],center[1]+4,"Ωf · fluido",23,PURPLE,anchor="middle")
text(84,1103,"Ωf: región volumétrica del interior",19)
text(84,1136,"Γ1…Γ6: grupos de caras de frontera",17)
text(84,1172,"Ωs: regiones sólidas para conducción térmica",17,GRAY)
end_panel()

# (c) Superficies trianguladas y corte interior; no son datos exportados de SALOME.
heading("malla","(c) Discretización del dominio","Mallado superficial y sección interior.")
faces=boundary_faces()
cam=Camera([p for face in faces.values() for p in face],(856,839,660,232))
for name in ["izquierda","posterior","suelo"]:
    polygon([cam(p) for p in faces[name]],pale(PURPLE,.025),"#aaaaaa",1)
    triangular_face(faces[name],cam,18 if name!="posterior" else 5,7,PURPLE,53+len(name))
cut=[(.58*L,0,0),(.58*L,B,0),(.58*L,B,H),(.58*L,0,H)]
polygon([cam(p) for p in cut],pale(ORANGE,.09),ORANGE,1.3)
triangular_face(cut,cam,5,8,ORANGE,108)
for name in ["techo","frontal","derecha"]:
    for a,b in zip(faces[name],faces[name][1:]+faces[name][:1]):line(cam(a),cam(b),MAGENTA,.8,"3 4")
text(860,1103,"Caras trianguladas y corte en x = 0,58 L",18)
text(860,1136,"Celdas de volumen, caras y conectividad",17)
text(860,1172,"Discretización espacial para el método de volúmenes finitos",16,GRAY)
end_panel()

# (d) Corte de un refinamiento graduado hacia la pared, con escala conceptual.
heading("refinamiento","(d) Resolución próxima a pared","Tamaño normal decreciente hacia la frontera.")
x0,y0,w,h=108,1355,575,245
rectangle(x0,y0,w,h,pale(PURPLE,.025),"#cccccc")
fractions=[0,.023,.06,.115,.19,.29,.42,.57,.76,1]
rng=random.Random(742)
grid={}
nx=21
for j,fraction in enumerate(fractions):
    for i in range(nx+1):
        x=x0+w*i/nx
        if 0<i<nx and 0<j<len(fractions)-1:x+=rng.uniform(-.28,.28)*w/nx
        grid[i,j]=(x,y0+h*(1-fraction))
edges=set()
for j in range(len(fractions)-1):
    for i in range(nx):
        q=[(i,j),(i+1,j),(i+1,j+1),(i,j+1)]
        for a,b in zip(q,q[1:]+q[:1]):edges.add(tuple(sorted((a,b))))
        edges.add(tuple(sorted((q[0],q[2]) if rng.random()<.5 else (q[1],q[3]))))
for a,b in sorted(edges):line(grid[a],grid[b],PURPLE,.6)
rectangle(x0,y0+h+8,w,14,pale(ORANGE,.25),ORANGE)
text(x0+w/2,y0+h+52,"Γpared",18,anchor="middle",italic=True)
text(x0,1694,"Δn1 < Δn2 < Δn3 · crecimiento suave hacia el interior",17,italic=True)
text(74,1725,"Refinamiento local y gradación de tamaños hacia la pared",17,GRAY)
end_panel()

# (e) El valor inicial se define en el volumen y la frontera tiene su propia ley.
heading("iniciales","(e) Condiciones iniciales en Ωf","Distribución de los campos al tiempo t = 0.")
faces=boundary_faces()
cam=Camera([p for face in faces.values() for p in face],(864,1344,637,166))
for name in ["izquierda","posterior","suelo"]:
    polygon([cam(p) for p in faces[name]],pale(MAGENTA,.07),MAGENTA)
for name in ["techo","frontal","derecha"]:
    for a,b in zip(faces[name],faces[name][1:]+faces[name][:1]):line(cam(a),cam(b),MAGENTA,.9,"4 3")
p=cam((L/2,B/2,H/2));rectangle(p[0]-42,p[1]-20,84,30,"white","none")
text(p[0],p[1]+3,"t = 0",21,anchor="middle",italic=True)
text(868,1551,"U(x, 0) = U₀",23,italic=True)
text(1240,1551,"Velocidad · m/s",17,GRAY)
text(868,1593,"T(x, 0) = T₀",23,italic=True)
text(1240,1593,"Temperatura · K",17,GRAY)
text(868,1635,"P(x, 0) = P₀",23,italic=True)
text(1240,1635,"Campo de presión",17,GRAY)
text(848,1685,"U₀, T₀ y P₀: valores iniciales de los campos",17,GRAY)
text(848,1720,"En Γi se prescribe una condición de frontera independiente.",16,GRAY)
end_panel()

# (f) Secuencia documentada, sin asumir formato de exportación ni algoritmo.
heading("metodologia","(f) Metodología SALOME → OpenFOAM","Del volumen geométrico a las regiones, grupos de caras y campos del caso.")
steps=[
    ("01 · Geometría",["Recinto cerrado","Volumen interior","Consistencia de unidades"],PURPLE),
    ("02 · Grupos",["Volúmenes: regiones","Caras: fronteras","Nombres identificables"],COLORS[1]),
    ("03 · Mallado",["SALOME · SMESH","Hipótesis y algoritmo","Refinamientos locales"],COLORS[2]),
    ("04 · Exportación",["Formato compatible","Conservar los grupos","Intercambio de la malla"],MAGENTA),
    ("05 · Importación",["Conversor de malla","OpenFOAM · polyMesh","Verificar las fronteras"],COLORS[4]),
    ("06 · Comprobación",["checkMesh","Topología y calidad","Campos y fronteras"],ORANGE),
]
for i,(title,lines,color) in enumerate(steps):
    x=75+i*246
    rectangle(x,1894,220,153,pale(color,.045),"#cccccc")
    rectangle(x,1894,220,4,color,color)
    text(x+12,1928,title,20)
    for j,value in enumerate(lines):text(x+12,1965+j*27,value,16,GRAY)
    if i<5:arrow((x+225,1969),(x+241,1969),"#777777",1)
text(75,2090,"La inicialización del volumen y las condiciones de cada frontera se definen en los campos del caso.",19)
text(75,2124,"Control de calidad: topología, geometría de las celdas y sensibilidad a la resolución espacial.",17,GRAY)
text(75,2158,"Grupos de caras → fronteras · Grupos de volumen → regiones · Campos → condiciones del problema",17,GRAY)
end_panel()
line((48,2205),(1552,2205),INK)
text(74,2242,"Longitudes en m · Ω: regiones volumétricas · Γ: superficies de frontera",18)
text(1526,2242,"Paleta Inferno · Computer Modern",17,GRAY,anchor="end")
add('</g></svg>')
svg="\n".join(parts)

download_links="".join(f'<a href="{p["file"]}" download><span>{p["title"]}</span><small>EPS vectorial · letras en trazados</small></a>' for p in PANELS.values())
boundary_rows="".join(f'<tr><td>{info["symbol"]}</td><td>{info["title"]}</td><td>{html.escape(str(CFG["condiciones_frontera"][name]["velocidad"] or "ℬU("+info["symbol"]+")"))}</td><td>{html.escape(str(CFG["condiciones_frontera"][name]["temperatura"] or "ℬT("+info["symbol"]+")"))}</td><td>{html.escape(str(CFG["condiciones_frontera"][name]["presion"] or "ℬP("+info["symbol"]+")"))}</td></tr>' for name,info in SURFACES.items())
doc=f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dominio, regiones y condiciones iniciales · OpenFOAM</title>
<script>if(new URLSearchParams(location.search).has('export'))document.documentElement.classList.add('export');</script>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:white;color:#222;font:18px 'Computer Modern','STIX Two Text','Times New Roman',serif}}main{{max-width:1600px;margin:auto}}svg{{display:block;width:100%;height:auto}}
.tools{{display:flex;gap:22px;justify-content:flex-end;flex-wrap:wrap;padding:20px 48px 0}}a{{color:{PURPLE}}}.notes,.downloads{{margin:24px 48px 36px;padding:24px 0;border-top:1px solid #ccc;line-height:1.6}}h2{{font-size:24px;margin:0 0 12px}}p{{margin:8px 0}}
.download-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}.download-grid a{{display:flex;flex-direction:column;gap:8px;border:1px solid #ddd;padding:18px;text-decoration:none}}.download-grid a:hover{{border-color:{PURPLE};background:#faf8fc}}small{{font-size:15px;color:#666}}
table{{border-collapse:collapse;width:100%;font-size:17px}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #ddd}}th{{background:#f7f7f7}}.scroll{{overflow-x:auto}}.status{{padding:18px 22px;border-left:3px solid {ORANGE};background:#fffcf7}}code{{font-size:15px}}.export .tools,.export .downloads,.export .notes{{display:none}}.export main{{max-width:none}}
@media(max-width:700px){{.download-grid{{grid-template-columns:1fr}}.tools,.notes,.downloads{{margin:12px;padding:12px}}}}@media print{{.tools,.downloads{{display:none}}.notes{{break-before:page}}}}
</style></head><body><main><nav class="tools"><a href="dominio_regiones_openfoam.eps" download>Figura completa en EPS</a><a href="cuadros_cfd_eps.zip" download>Todos los EPS</a><a href="dominio_regiones_openfoam.png" download>PNG completo</a></nav>
{svg}
<section class="downloads"><h2>Descargar cada cuadro</h2><div class="download-grid">{download_links}</div></section>
<section class="notes"><h2>Dominio y regiones</h2>
<p>El recinto tiene longitud L = {num(L)} m, anchura B = {num(B)} m y altura H. Las seis superficies de su envolvente son la pared izquierda, derecha, posterior, frontal, techo y suelo.</p>
<p>Una <strong>región volumétrica</strong> reúne las celdas donde se resuelven los campos. Un <strong>grupo de frontera</strong> identifica las caras sobre las que se prescribe una condición. Ωf representa el fluido interior y Ωs las regiones sólidas para conducción térmica.</p>
<h2>Condiciones de frontera por superficie</h2><div class="scroll"><table><thead><tr><th>Grupo</th><th>Superficie</th><th>Velocidad</th><th>Condición térmica</th><th>Presión</th></tr></thead><tbody>{boundary_rows}</tbody></table></div>
<p>ℬU, ℬT y ℬP denotan las condiciones de frontera de velocidad, temperatura y presión en cada grupo Γi. Las condiciones iniciales U₀, T₀ y P₀ se prescriben en el volumen al tiempo t = 0.</p>
<p>El mallado describe la discretización espacial mediante celdas, caras y conectividad. El refinamiento próximo a pared reduce el tamaño normal de los elementos y gradúa su crecimiento hacia el interior.</p>
<h2>Referencias metodológicas</h2><p><a href="https://docs.salome-platform.org/latest/gui/SMESH/grouping_elements.html">SALOME: grupos de entidades</a> · <a href="https://docs.salome-platform.org/latest/gui/SMESH/importing_exporting_meshes.html">SALOME: intercambio de mallas</a> · <a href="https://doc.cfd.direct/openfoam/user-guide-v13/boundaries">OpenFOAM: fronteras de la malla</a> · <a href="https://doc.cfd.direct/openfoam/user-guide-v13/basic-file-format">OpenFOAM: campos y unidades</a>.</p>
</section></main><script>
const panels={json.dumps(PANELS,ensure_ascii=False)};
const selected=new URLSearchParams(location.search).get('panel');
if(selected&&panels[selected]){{const svg=document.querySelector('svg'),box=panels[selected].box;svg.setAttribute('viewBox',box.join(' '));svg.setAttribute('width',box[2]);svg.setAttribute('height',box[3]);}}
if(new URLSearchParams(location.search).has('audit'))document.fonts.ready.then(()=>{{
 const target=selected&&panels[selected]?document.getElementById('panel-'+selected):document.querySelector('svg');
 const labels=Array.from(target.querySelectorAll('text')).map(el=>({{text:el.textContent,box:el.getBoundingClientRect().toJSON()}}));const collisions=[];
 for(let i=0;i<labels.length;i++)for(let j=i+1;j<labels.length;j++){{const a=labels[i].box,b=labels[j].box;if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)collisions.push([labels[i].text,labels[j].text]);}}
 const svg=document.querySelector('svg').getBoundingClientRect();const outside=labels.filter(l=>l.box.left<svg.left||l.box.right>svg.right||l.box.top<svg.top||l.box.bottom>svg.bottom).map(l=>l.text);
 const report=document.createElement('pre');report.id='audit-report';report.textContent=JSON.stringify({{collisions,outside,fontLoaded:document.fonts.check('18px "Computer Modern"'),labels:labels.length}});document.body.append(report);
}});
</script></body></html>'''
(OUT / "dominio_regiones_openfoam.html").write_text(doc,encoding="utf-8")
(OUT / "paneles_cfd.json").write_text(json.dumps(PANELS,ensure_ascii=False,indent=2),encoding="utf-8")
print(f"Lámina CFD generada: {OUT / 'dominio_regiones_openfoam.html'} · seis cuadros · {WIDTH} × {HEIGHT}")
