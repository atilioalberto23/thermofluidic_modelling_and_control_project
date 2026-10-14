"""Genera el HTML del esquema desde los parámetros y los literales de geometry.py.

Ejecutar desde cualquier directorio: python3 output/generar_geometria.py
El HTML es autónomo; ?export=1 muestra únicamente la lámina para exportarla a PNG.
No requiere dependencias de Python adicionales.
"""

import ast
import base64
import html
import json
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "thermofluidic-modelling-and-control-project"
PARAMETERS = PROJECT / "conf/base/parameters.yml"
GEOMETRY = PROJECT / (
    "src/thermofluidic_modelling_and_control_project/pipelines/"
    "synthetic_data/synthetic_solar_dryer/geometry.py"
)
OUT = ROOT / "output"
WIDTH, HEIGHT = 1600, 1700
# Inferno, muestreado en 0,25; 0,50 y 0,75 de la tabla oficial de Matplotlib.
COLORS = {"LEFT_WALL": "#57106e", "RIGHT_WALL": "#bc3754", "BACK_WALL": "#f98e09"}
LABELS = {"LEFT_WALL": "Pared izquierda", "RIGHT_WALL": "Pared derecha", "BACK_WALL": "Pared posterior"}


def pale(color, fraction=0.055):
    rgb = [int(color[i:i+2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(255+(c-255)*fraction):02x}" for c in rgb)


font_rules = []
for filename, weight, style in [("cmunrm.woff", 400, "normal"), ("cmunbx.woff", 700, "normal"), ("cmunti.woff", 400, "italic")]:
    encoded = base64.b64encode((OUT / filename).read_bytes()).decode("ascii")
    font_rules.append(
        f"@font-face{{font-family:'Computer Modern';font-weight:{weight};font-style:{style};"
        f"src:url(data:font/woff;base64,{encoded}) format('woff');font-display:block}}"
    )
FONT_CSS = "\n".join(font_rules)


def source_literal(function, variable):
    tree = ast.parse(GEOMETRY.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
    assignment = next(
        n for n in fn.body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == variable for t in n.targets)
    )
    return ast.literal_eval(assignment.value)


def number(value, decimals=2):
    return f"{value:.{decimals}f}".replace(".", ",")


config = PARAMETERS.read_text()
length = float(re.search(r"cable_length:\s*([\d.]+)", config)[1])
angle = float(re.search(r"cable_angle_deg:\s*([\d.]+)", config)[1])
surfaces = {}
for surface in COLORS:
    match = re.search(rf"{surface}:\s*\n\s*width:\s*([\d.]+)\s*\n\s*height:\s*([\d.]+)", config)
    surfaces[surface] = tuple(map(float, match.groups()))
nodes = source_literal("generate_wall_sensor_geometry", "nodes")
back = source_literal("generate_back_wall_geometry", "points")
# Nodo físico posterior indicado por el usuario; el generador actual no le
# asigna NODE_ID a estos cuatro sensores. Se mantiene intacta la tabla de datos.
back_node = (surfaces["BACK_WALL"][0]/2, surfaces["BACK_WALL"][1]/2)
wall_nodes = {"LEFT_WALL": nodes, "RIGHT_WALL": nodes, "BACK_WALL": {"NP": back_node}}
dx = length * math.cos(math.radians(angle))
dy = length * math.sin(math.radians(angle))
directions = {"SO": (-dx, -dy), "SE": (dx, -dy), "NO": (-dx, dy), "NE": (dx, dy)}
rows = []
for surface in ("LEFT_WALL", "RIGHT_WALL"):
    for node, (nx, ny) in nodes.items():
        for position, (ox, oy) in directions.items():
            rows.append(dict(SURFACE=surface, NODE_ID=node, SENSOR_POSITION=position, X=nx+ox, Y=ny+oy))
for position, x, y in back:
    rows.append(dict(SURFACE="BACK_WALL", NODE_ID=None, SENSOR_POSITION=position, X=x, Y=y))

parts = []


def add(markup):
    parts.append(markup)


def text(x, y, value, size=16, color="#202020", weight=400, anchor="start", **attrs):
    extra = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    add(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}" {extra}>{html.escape(str(value))}</text>')


def line(x1, y1, x2, y2, color="#a0afbc", width=1.5, dash=None):
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"{extra}/>')


def rect(x, y, w, h, fill="#fff", stroke="#dddddd", radius=0):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')


def circle(x, y, color, radius=5, title=None, attrs=""):
    tooltip = f"<title>{html.escape(title)}</title>" if title else ""
    add(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{color}" stroke="white" stroke-width="1.5" {attrs}>{tooltip}</circle>')


def node_mark(x, y, size=9):
    add(f'<rect x="{x-size/2}" y="{y-size/2}" width="{size}" height="{size}" fill="#202020" stroke="white" stroke-width="1.2"/>')


def dimension(x1, y1, x2, y2, label, vertical=False):
    add(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="#708394" marker-start="url(#dim)" marker-end="url(#dim)"/>')
    if vertical:
        text(x1-16, (y1+y2)/2, label, 14, anchor="middle", transform=f"rotate(-90 {x1-16} {(y1+y2)/2})")
    else:
        text((x1+x2)/2, y1+22, label, 15, anchor="middle")


add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="diagram-title diagram-description">')
add('<title id="diagram-title">Geometría del secador solar para datos sintéticos</title><desc id="diagram-description">Tres superficies, ocho nodos laterales, un nodo central posterior y treinta y seis posiciones de sensor; vistas por pared con coordenadas locales del generador.</desc>')
add(f'<style>{FONT_CSS}</style>')
add('<defs><marker id="dim" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10" fill="none" stroke="#708394" stroke-width="1.4"/></marker></defs>')
add(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="white"/>')
add('<g font-family="Computer Modern, STIX Two Text, Times New Roman, serif">')
text(800, 62, "Geometría del secador solar", 36, anchor="middle")
text(800, 99, "Modelo de datos sintéticos · 3 paredes · 9 nodos · 36 posiciones de medición", 19, "#555555", anchor="middle")
line(48,128,1552,128,"#202020",1)

# Cámara en perspectiva y pared derecha separada para hacer visible el interior.
add('<g id="panel-conjunto">')
text(74, 184, "(a) Vista de conjunto", 23)
text(74, 214, "Perspectiva tridimensional; pared derecha separada para mostrar el interior.", 17, "#555555")
wall_l = surfaces["LEFT_WALL"]
wall_r = surfaces["RIGHT_WALL"]
wall_b = surfaces["BACK_WALL"]


def vector_sub(a, b):
    return tuple(x-y for x,y in zip(a,b))


def dot(a, b):
    return sum(x*y for x,y in zip(a,b))


def normalized(v):
    norm = math.sqrt(dot(v,v))
    return tuple(x/norm for x in v)


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


# Montaje esquemático visto desde el extremo abierto, con la pared posterior en X=0.
camera = (10.0, 8.0, 14.0)
target = (2.7, 1.9, 0.8)
forward = normalized(vector_sub(target,camera))
right = normalized(cross(forward,(0,0,1)))
up = cross(right,forward)
separation = 2.8
thickness = 0.045  # Espesor gráfico, no parámetro físico del generador.
back_visual_width = (wall_b[0] + separation) * 0.5
back_visual_start = (wall_b[0] + separation - back_visual_width) / 2


def perspective(point):
    relative=vector_sub(point,camera)
    distance=dot(relative,forward)
    return dot(relative,right)/distance, -dot(relative,up)/distance


def spatial(surface,x,y,offset=0):
    if surface=="LEFT_WALL": return (x,-offset,y)
    if surface=="RIGHT_WALL": return (x,wall_b[0]+separation+offset,y)
    # Panel posterior centrado, con la mitad de la anchura gráfica anterior.
    # Los márgenes laterales evitan el contacto con los paneles de la vista 3D.
    # Las vistas acotadas conservan la anchura física de 1,12 m.
    return (-offset,back_visual_start+x*back_visual_width/wall_b[0],y)


corners={surface:[(0,0),(w,0),(w,h),(0,h)] for surface,(w,h) in surfaces.items()}
all_points=[perspective(spatial(surface,x,y,offset)) for surface in surfaces for x,y in corners[surface] for offset in (0,thickness)]
min_x,max_x=min(p[0] for p in all_points),max(p[0] for p in all_points)
min_y,max_y=min(p[1] for p in all_points),max(p[1] for p in all_points)
fit=min(860/(max_x-min_x),360/(max_y-min_y))
center_x,center_y=(min_x+max_x)/2,(min_y+max_y)/2


def project_point(point):
    x,y=perspective(point)
    return 526+(x-center_x)*fit,426+(y-center_y)*fit


def polygon(points,fill,stroke,width=1.2):
    coords=" ".join(f"{x:.3f},{y:.3f}" for x,y in map(project_point,points))
    add(f'<polygon points="{coords}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round"/>')


# Huella de montaje y líneas de desplazamiento: se trazan detrás de las paredes.
footprint=[(0,0,0),(wall_l[0],0,0),(wall_l[0],wall_b[0]+separation,0),(0,wall_b[0]+separation,0),(0,0,0)]
for p,q in zip(footprint,footprint[1:]):
    line(*project_point(p),*project_point(q),"#bdbdbd",1,"5 5")
for x in (0,wall_l[0]):
    line(*project_point((x,wall_b[0],0)),*project_point((x,wall_b[0]+separation,0)),"#a0a0a0",1.2,"4 5")

# Las caras de los paneles y su espesor se ordenan por profundidad de cámara.
faces=[]
for surface in surfaces:
    front=[spatial(surface,x,y) for x,y in corners[surface]]
    rear=[spatial(surface,x,y,thickness) for x,y in corners[surface]]
    color=COLORS[surface]
    faces.append((front,pale(color,0.11),color,surface,surface!="RIGHT_WALL"))
    faces.append((rear,pale(color,0.20),color,surface,surface=="RIGHT_WALL"))
    for i in range(4):
        j=(i+1)%4
        faces.append(([front[i],front[j],rear[j],rear[i]],pale(color,0.30),color,surface,False))
faces.sort(key=lambda f:sum(dot(vector_sub(p,camera),forward) for p in f[0])/len(f[0]),reverse=True)
for vertices,fill,color,surface,is_front in faces:
    polygon(vertices,fill,color)
    if is_front:
        visible_offset=thickness if surface=="RIGHT_WALL" else 0
        for node,(nx,ny) in wall_nodes[surface].items():
            add(f'<g class="node" data-surface="{surface}" data-node-id="{node}" data-x="{nx}" data-y="{ny}">')
            connected=[row for row in rows if row["SURFACE"]==surface and (surface=="BACK_WALL" or row["NODE_ID"]==node)]
            for row in connected:
                line(*project_point(spatial(surface,nx,ny,visible_offset)),*project_point(spatial(surface,row["X"],row["Y"],visible_offset)),color,1.5)
            mount=[spatial(surface,nx+ox,ny+oy,visible_offset) for ox,oy in [(-.045,-.045),(.045,-.045),(.045,.045),(-.045,.045)]]
            polygon(mount,"#202020","white",0.8)
            add('</g>')
        for row in rows:
            if row["SURFACE"]==surface:
                circle(*project_point(spatial(surface,row["X"],row["Y"],visible_offset)),color,4.3)

for x, surface in [(130,"LEFT_WALL"),(385,"RIGHT_WALL"),(640,"BACK_WALL")]:
    line(x,644,x+28,644,COLORS[surface],3)
    text(x+40,650,LABELS[surface],17)
add('</g>')

# Detalle de un nodo, con igual escala horizontal y vertical.
add('<g id="panel-nodo">')
text(1038, 184, "(b) Distribución de un nodo lateral", 23)
text(1038, 214, f"L = {number(length)} m; θ = {number(angle)}° respecto a la horizontal", 17, "#555555")
cx, cy, scale = 1282, 345, 183
line(cx-190,cy,cx+190,cy,"#b5c2ce",1,"5 5")
line(cx,cy-81,cx,cy+81,"#b5c2ce",1,"5 5")
for pos,(ox,oy) in directions.items():
    px,py = cx+ox*scale,cy-oy*scale
    line(cx,cy,px,py,COLORS["LEFT_WALL"],2)
    circle(px,py,COLORS["LEFT_WALL"],7)
    text(px,py + (-16 if oy>0 else 28),pos,18,anchor="middle")
node_mark(cx,cy,13)
text(cx,cy+24,"Nodo",14,anchor="middle")
arc_r=62
end=(cx+arc_r*math.cos(math.radians(angle)),cy-arc_r*math.sin(math.radians(angle)))
add(f'<path d="M{cx+arc_r},{cy} A{arc_r},{arc_r} 0 0 0 {end[0]},{end[1]}" fill="none" stroke="{COLORS["BACK_WALL"]}" stroke-width="2"/>')
text(cx+85,cy-9,"θ",18,font_style="italic")
text(1055, 478, f"ΔX = L cos θ = {number(dx,6)} m", 19, font_style="italic")
text(1055, 514, f"ΔY = L sen θ = {number(dy,6)} m", 19, font_style="italic")
add('</g>')

add('<g transform="translate(0 120)">')
line(48,562,1552,562,"#bdbdbd",1)
add('<g id="panel-laterales">')
text(74, 602, "(c) Paredes laterales", 23)
text(74, 632, "Coordenadas locales; ambas vistas tienen la misma escala.", 17, "#555555")


def elevation(surface, left, top, scale, caption_y):
    width,height=surfaces[surface]
    w,h=width*scale,height*scale
    color=COLORS[surface]
    rect(left,top,w,h,pale(color,0.022),color,0)
    for i in range(1,int(width)+1):
        line(left+i*scale,top,left+i*scale,top+h,"#dfe7eb",1)
    for y in [0.5,1,1.5,2]:
        if y<height:
            line(left,top+h-y*scale,left+w,top+h-y*scale,"#dfe7eb",1)
    transform=lambda x,y:(left+x*scale,top+(height-y)*scale)
    selected=[row for row in rows if row["SURFACE"]==surface]
    for node,(nx,ny) in wall_nodes[surface].items():
        add(f'<g class="node" data-surface="{surface}" data-node-id="{node}" data-x="{nx}" data-y="{ny}">')
        a,b=transform(nx,ny)
        for row in selected:
            if surface=="BACK_WALL" or row["NODE_ID"]==node:
                c,d=transform(row["X"],row["Y"])
                line(a,b,c,d,color,1.7)
        node_mark(a,b,11)
        if surface=="BACK_WALL":
            text(a+22,b+5,node,15,weight=700)
        else:
            text(a,b-13,node,15,weight=700,anchor="middle")
        add('</g>')
    for row in selected:
        x,y=transform(row["X"],row["Y"])
        title=f'{LABELS[surface]} · {row["NODE_ID"] or "sin nodo"} · {row["SENSOR_POSITION"]} · X={number(row["X"],9)}, Y={number(row["Y"],9)}'
        attrs=f'class="sensor" data-surface="{surface}" data-x="{row["X"]}" data-y="{row["Y"]}"'
        circle(x,y,color,5.5,title,attrs)
        pos=row["SENSOR_POSITION"]
        # Las direcciones se explican una sola vez en el detalle del nodo.
        if surface=="BACK_WALL":
            text(x+(40 if pos.endswith("O") else -40),y+(25 if pos.startswith("N") else -16),pos,17,anchor="start" if pos.endswith("O") else "end")
    # Cotas y origen; X crece hacia la derecha e Y hacia arriba en todas las vistas.
    line(left,top+h+8,left,top+h+38,"#b5c2ce",1)
    line(left+w,top+h+8,left+w,top+h+38,"#b5c2ce",1)
    dimension(left,top+h+31,left+w,top+h+31,f"{number(width)} m  /  X →")
    dimension(left-32,top,left-32,top+h,f"{number(height)} m  /  Y ↑",True)
    text(left-8,top+h+19,"(0, 0)",12,"#607285",anchor="end")
    text(left,caption_y,"16 sensores · 4 nodos" if surface!="BACK_WALL" else "4 sensores · 1 nodo central",17,"#555555")


add('<g id="panel-izquierda">')
text(126,674,"Pared izquierda",20,COLORS["LEFT_WALL"])
elevation("LEFT_WALL",126,700,149,1050)
add('</g><g id="panel-derecha">')
text(126,1093,"Pared derecha",20,COLORS["RIGHT_WALL"])
# La segunda vista usa exactamente la misma escala que la primera.
elevation("RIGHT_WALL",126,1119,149,1469)
add('</g></g>')

add('<g id="panel-posterior">')
text(1108,602,"(d) Pared posterior",23)
text(1108,632,"Vista ampliada respecto a los laterales.",17,"#555555")
elevation("BACK_WALL",1190,700,220,1240)
text(1108,1294,"SO (0; 0)           SE (1,12; 0)",18)
text(1108,1330,"NO (0; 2,05)     NE (1,12; 2,05)",18)
text(1108,1386,"Origen local: esquina inferior izquierda.",16,"#555555")
add('</g>')

line(48,1510,1552,1510,"#202020",1)
circle(74,1541,"#202020",6)
text(88,1547,"Sensor",17)
node_mark(230,1541,11)
text(245,1547,"Nodo de conexión",17)
line(450,1541,486,1541,"#202020",1.5)
text(499,1547,"Cable",17)
text(695,1547,"Dimensiones y coordenadas en metros (m).",17,"#555555")
add('</g>')
add('</g></svg>')
svg="\n".join(parts)

table_rows="\n".join(
    f'<tr><td>{LABELS[r["SURFACE"]]}</td><td>{r["NODE_ID"] or "—"}</td><td>{r["SENSOR_POSITION"]}</td>'
    f'<td>{number(r["X"],9)}</td><td>{number(r["Y"],9)}</td></tr>' for r in rows
)
node_coords=" · ".join(f'{node} ({number(x,3)}; {number(y,2)})' for node,(x,y) in nodes.items())
data_json=json.dumps(rows,ensure_ascii=False)
PANELS = {
    "conjunto": {"title":"Vista de conjunto 3D", "file":"vista_conjunto_3d.eps", "box":[48,150,940,520]},
    "nodo": {"title":"Detalle del nodo", "file":"detalle_nodo.eps", "box":[1012,150,540,520]},
    "laterales": {"title":"Ambas paredes laterales", "file":"paredes_laterales.eps", "box":[48,690,1010,925]},
    "izquierda": {"title":"Pared izquierda", "file":"pared_izquierda.eps", "box":[48,760,1010,425]},
    "derecha": {"title":"Pared derecha", "file":"pared_derecha.eps", "box":[48,1180,1010,435]},
    "posterior": {"title":"Pared posterior", "file":"pared_posterior.eps", "box":[1082,690,470,925]},
}
download_links="\n".join(
    f'<a class="panel-download" href="{p["file"]}" download><span>{p["title"]}</span><small>Descargar EPS · Vectores y texto en trazados</small></a>'
    for p in PANELS.values()
)
panels_json=json.dumps(PANELS,ensure_ascii=False)
document=f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Geometría del secador solar · Datos sintéticos</title>
<script>if(new URLSearchParams(location.search).has('export'))document.documentElement.classList.add('export');</script>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:white;color:#202020;font:18px 'Computer Modern','STIX Two Text','Times New Roman',serif}}
main{{max-width:1600px;margin:auto}}svg{{display:block;width:100%;height:auto}}.sensor:hover{{r:8;cursor:help}}
.tools{{display:flex;align-items:center;justify-content:flex-end;gap:20px;padding:18px 48px 0}}a,button{{font:inherit;color:#57106e}}
button{{background:white;border:1px solid #cccccc;padding:8px 14px;cursor:pointer}}
.notes{{margin:20px 48px 48px;background:white;border-top:1px solid #cccccc;padding:28px 0;line-height:1.65}}
.downloads{{margin:28px 48px 36px;padding:24px 0;border-top:1px solid #cccccc}}
.download-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}
.panel-download{{display:flex;flex-direction:column;gap:8px;padding:18px 20px;border:1px solid #dddddd;text-decoration:none}}
.panel-download:hover{{border-color:#57106e;background:#faf8fc}}.panel-download small{{color:#555555;font-size:15px}}
h2{{font-size:21px;margin:0 0 12px}}p{{margin:8px 0}}code{{font-size:14px;overflow-wrap:anywhere}}summary{{cursor:pointer;font-weight:bold;margin:18px 0}}
table{{border-collapse:collapse;width:100%;font-size:16px}}td,th{{padding:8px 12px;text-align:left;border-bottom:1px solid #dddddd}}th{{background:#f7f7f7}}td:nth-last-child(-n+2){{font-variant-numeric:tabular-nums}}
.scroll{{overflow-x:auto}}.export .tools,.export .notes,.export .downloads{{display:none}}.export main{{max-width:none}}
@media(max-width:700px){{.notes{{margin:12px;padding:18px}}.tools{{padding:12px}}.downloads{{margin:20px 12px}}.download-grid{{grid-template-columns:1fr}}}}
@media print{{.tools{{display:none}}body{{background:white}}.notes{{break-before:page}}}}
</style></head><body><main>
<nav class="tools" aria-label="Exportaciones"><a href="geometria_synthetic_data.eps" download>Descargar figura completa en EPS</a><a href="cuadros_vectoriales_eps.zip" download>Descargar todos los EPS</a><a href="geometria_synthetic_data.png" download>PNG completo</a></nav>
{svg}
<section class="downloads" aria-labelledby="download-title"><h2 id="download-title">Descargar cada cuadro como EPS vectorial</h2><p>Figuras escalables con títulos, etiquetas y cotas. Las letras se convierten a trazados para conservar la tipografía al abrir los archivos en otros equipos.</p><div class="download-grid">{download_links}</div></section>
<section class="notes"><h2>Lectura del esquema</h2>
<p>Las dimensiones y las coordenadas se expresan en <strong>metros (m)</strong>. Las vistas de las paredes usan <strong>coordenadas locales</strong>: X horizontal e Y vertical, con origen en la esquina inferior izquierda. SO, SE, NO y NE significan suroeste, sureste, noroeste y noreste respecto al nodo; no representan una orientación geográfica del secador.</p>
<p><strong>Nodos por lateral:</strong> {node_coords}. <strong>Nodo posterior NP:</strong> ({number(back_node[0],2)}; {number(back_node[1],3)}) m, en el centro de la pared y conectado a sus cuatro sensores.</p>
<p><strong>Fidelidad al generador:</strong> los sensores laterales se calculan con X = Xn ± L cos(θ) e Y = Yn ± L sen(θ), sin redondear ni recortar. Con los parámetros actuales, algunos puntos quedan ligeramente fuera del contorno nominal (hasta {number(dx-0.925,9)} m en X y {number(dy-0.32,9)} m en Y). Se conservan esas coordenadas en la figura y en la tabla.</p>
<p><strong>Vista de conjunto:</strong> montaje esquemático con cámara en perspectiva, visto desde el extremo abierto. La pared posterior se sitúa en el extremo X = 0, centrada y separada de los laterales. Su anchura gráfica ocupa la mitad del espacio entre las paredes de esta vista, dejando márgenes a ambos lados. Para mostrar el interior, la pared derecha se desplaza lateralmente. La anchura física de la posterior es 1,12 m, como muestran la vista acotada y la tabla. Las líneas discontinuas y el espesor de los paneles son recursos gráficos. El código define tres superficies independientes, sin montaje tridimensional, techo, suelo ni pared frontal. La diferencia entre la altura lateral (1,90 m) y posterior (2,05 m) procede de la configuración.</p>
<p><strong>Procedencia:</strong> configuración geométrica y función de generación de sensores del proyecto. Los centros N1–N4 y las cuatro posiciones posteriores se extraen directamente del código. El nodo central posterior NP se incorpora al esquema según la geometría física indicada; el generador actual guarda un identificador de nodo nulo para estos cuatro sensores, que se conserva en la tabla.</p>
<p><strong>Estilo de la figura:</strong> paleta <a href="https://github.com/matplotlib/matplotlib/blob/main/lib/matplotlib/_cm_listed.py">Inferno</a>, con muestras en 0,25; 0,50 y 0,75, y tipografía <a href="https://github.com/bitmaks/cm-web-fonts">Computer Modern</a> incorporada al archivo. <a href="LICENCIA_Computer_Modern.txt">Licencia de las fuentes</a>.</p>
<details><summary>Ver las 36 coordenadas generadas</summary><div class="scroll"><table><thead><tr><th>Superficie</th><th>Nodo</th><th>Posición</th><th>X (m)</th><th>Y (m)</th></tr></thead><tbody>{table_rows}</tbody></table></div></details>
</section></main><script id="geometry-data" type="application/json">{data_json}</script>
<script>
const panels={panels_json};
const selected=new URLSearchParams(location.search).get('panel');
if(selected && panels[selected]){{
 const svg=document.querySelector('svg'),box=panels[selected].box;
 svg.setAttribute('viewBox',box.join(' '));svg.setAttribute('width',box[2]);svg.setAttribute('height',box[3]);
 document.title=panels[selected].title;
}}
if(new URLSearchParams(location.search).has('audit')){{
 document.fonts.ready.then(()=>{{
  const target=selected && panels[selected] ? document.getElementById('panel-'+selected) : document.querySelector('svg');
  const labels=Array.from(target.querySelectorAll('text')).map(el=>({{text:el.textContent,box:el.getBoundingClientRect().toJSON()}}));
  const collisions=[];
  for(let i=0;i<labels.length;i++)for(let j=i+1;j<labels.length;j++){{
   const a=labels[i].box,b=labels[j].box;
   if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1 && Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)collisions.push([labels[i].text,labels[j].text]);
  }}
  const svg=document.querySelector('svg').getBoundingClientRect();
  const outside=labels.filter(l=>l.box.left<svg.left||l.box.right>svg.right||l.box.top<svg.top||l.box.bottom>svg.bottom).map(l=>l.text);
  const report=document.createElement('pre');report.id='audit-report';report.textContent=JSON.stringify({{collisions,outside,fontLoaded:document.fonts.check('18px "Computer Modern"'),labels:labels.length}});document.body.append(report);
 }});
}}
</script></body></html>'''
OUT.mkdir(exist_ok=True)
target=OUT/"geometria_synthetic_data.html"
target.write_text(document,encoding="utf-8")
(OUT/"paneles.json").write_text(panels_json,encoding="utf-8")
assert len(rows)==36
print(f"HTML generado: {target}\nSensores: {len(rows)} · Lámina: {WIDTH} × {HEIGHT} px")
