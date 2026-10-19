# Ilustraciones del antecedente técnico SENACYT

Autor: Atilio A. Rodríguez Miranda. *Aspectos dinámicos y térmicos clave en el diseño de secadores solares de café*. Reporte técnico, entregable 1, julio de 2025. Proyecto APY-NI-2024A-12, Programa Nuevos Investigadores, SENACYT.

Las seis ilustraciones se copiaron del directorio temporal proporcionado por el autor. Los tres PDF de geometría y los tres EPS se conservan sin cambios de contenido. Los EPS tienen además una conversión PDF mediante `epstopdf`, utilizada por LaTeX. Ningún archivo de compilación depende del directorio temporal.

La referencia bibliográfica se encuentra únicamente en `tail/References.bib`, clave `rodriguez2025reporte`. Las figuras se incluyen desde `main/fundamentos/`; metodología y discusión enlazan sus deducciones.

## Correspondencia e integridad de los originales

| Original | Copia local | SHA-256 |
| --- | --- | --- |
| `croquis1.pdf` | `geometrias_revolucion.pdf` | `e16fa1d0ef0c96b19aa4bbd4f9377e8a6f1e6820d2d1a838a66c5d688afc4e05` |
| `croquis2.pdf` | `geometrias_prismaticas.pdf` | `c4a0f1c7fb109d7585fc81e846b360bd722e9e271d575c3d9c35f45cdc280872` |
| `croquis3.pdf` | `geometrias_simetricas.pdf` | `ed41bab0a06a5820a8e8c98fbca3643a571d790abe54d7a36e53a4947251e311` |
| `transferencia.eps` | `transferencia_cubierta.eps` | `35025c9f16d7305e68d9a9bdefc8b0f0ca0726658e55f240332b601c1299ef77` |
| `diagrama_buoyancia.eps` | `flotacion_estratificacion.eps` | `ac428a5077c3c5a531b583cb09156b4bba628e76697c8e740d251d536643ad59` |
| `diagrama_bloques.eps` | `lazo_control.eps` | `006604381db947578844e77e9c235b40a81d12bf06d20534fa2d3f64a7ad468f` |

## Criterios de integración y revisión matemática

- La superficie cerrada incluye la base; el área de envolvente y la captación solar se distinguen explícitamente.
- Las áreas y volúmenes se deducen por integración. En los paraboloides se retienen los factores de la derivada del perfil; en prismas se utiliza área transversal por longitud.
- La reflexión duplica el volumen y elimina del exterior las dos caras de contacto. Se mantienen separados altura de pared, elevación del techo y ancho de sección.
- Los balances separan absorción solar en la cubierta y transmisión hacia el interior; la suma discreta conserva las áreas de cada elemento y los signos de intercambio.
- La deducción vertical utiliza un eje ascendente, presión hidrostática y viscosidad cinemática. El esquema de estratificación se interpreta como un límite térmico idealizado; no excluye viento o actuación mecánica.
- Las ecuaciones de control distinguen humedad relativa y razón de humedad. Las familias geométricas son una parametrización, sin atribuirles un orden universal de eficiencia.
- En el tercer croquis se conserva la rotulación original; el pie de figura distingue las secciones superiores sin pared adicional de las inferiores con pared vertical.
