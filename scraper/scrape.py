#!/usr/bin/env python3
"""Actualiza docs/jobs.json con convocatorias vigentes de todo el Perú.

Fuente: convocatoriasdetrabajo.com (cada aviso enlaza a las bases oficiales).
1) Lee los listados (departamentos, contratos, últimas ofertas), todas las páginas,
   y guarda enseguida los datos de cada tarjeta.
2) Abre el detalle de los avisos más recientes (bases y requisitos), con tope de
   cantidad y de tiempo, guardando de a poco.
Hace pausa entre pedidos. Confirma que los términos del sitio permitan este uso,
o pide permiso, antes de ponerlo en producción.
"""
import json, re, time, datetime as dt
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE = "https://www.convocatoriasdetrabajo.com/"
DEPARTAMENTOS = [
    "AMAZONAS-1", "ANCASH-2", "APURIMAC-3", "AREQUIPA-4", "AYACUCHO-5", "CAJAMARCA-6", "CUSCO-7", "CALLAO-8",
    "HUANCAVELICA-9", "HUANUCO-10", "ICA-11", "JUNIN-12", "LA-LIBERTAD-13", "LAMBAYEQUE-14", "LIMA-15",
    "LORETO-16", "MADRE-DE-DIOS-17", "MOQUEGUA-18", "PASCO-19", "PIURA-20", "PUNO-21", "SAN-MARTIN-22",
    "TACNA-23", "TUMBES-24", "UCAYALI-25",
]
EXTRAS = [  # listas por contrato y "últimas ofertas": atrapan plazas que no salgan en los departamentos
    "vigentes.php",
    "convocatorias-cas-vigentes.php",
    "convocatorias-practicas-profesionales-preprofesionales-vigentes.php",
    "contrataciones-empleo-728-vigentes-estado-peruano.php",
    "contrataciones-regimen-276-empleos-estado.php",
    "contrataciones-regimen-servicio-civil-30057-empleos-estado.php",
    "contrataciones-empleo-locacion-servicios-sector-publico.php",
    "contrataciones-consultorias-individuales-instituciones-estado.php",
]
LISTADOS = [f"{BASE}buscar-trabajos-en-{d}.html" for d in DEPARTAMENTOS] + [BASE + e for e in EXTRAS]
PREFIJO_AVISO = BASE + "oportunidad-laboral-"
MAX_PAGINAS = 60          # Lima tiene ~35 páginas
MAX_DETALLES = 300        # avisos que se abren a fondo por corrida
TIEMPO_MAX_MIN = 35       # después de esto ya no se abren más detalles
PAUSA = 1.2
SALIDA = Path(__file__).resolve().parent.parent / "docs" / "jobs.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; EmpleosEstadoBot/1.0)"}
MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12}

CARRERAS = {
    "EDUCACION": ["educaci", "docen", "profesor", "pedag"], "ADMINISTRACION": ["administraci"], "DERECHO": ["derecho", "abogad"],
    "CONTABILIDAD": ["contabilidad", "contador"], "PSICOLOGÍA": ["psicolog"], "TRABAJO SOCIAL": ["trabajo social", "trabajador social", "asistente social"],
    "ECONOMIA | ING. ECONÓMICA": ["economía", "economia"], "SOCIOLOGÍA": ["sociolog"], "ESTADÍSTICA": ["estadístic", "estadistic"],
    "COMPUTACION": ["computaci", "informátic", "informatic"], "ING. DE SISTEMAS": ["sistemas"], "ENFERMERIA": ["enfermer"],
    "COMUNICACIONES": ["comunicaci"], "ARCHIVO": ["archiv"], "BIBLIOTECOLOGÍA": ["bibliotec"], "HISTORIA": ["historia"],
    "ING. AMBIENTAL": ["ambiental"], "ING. INDUSTRIAL": ["industrial"], "ING. AGRÓNOMA": ["agronom", "agrícola", "agricola"],
    "ING. ELECTRÓNICA / ELÉCTRICA": ["electrónic", "electronic", "eléctric", "electric"], "ING. MINAS / GEOLOGÍA": ["minas", "geolog"],
    "MEDICINA VETERINARIA": ["veterinari", "zootecn"], "BIOLOGÍA": ["biolog"], "OBSTETRICIA": ["obstetr"], "ODONTOLOGÍA": ["odontolog"],
    "FARMACIA": ["farmac"], "MARKETING / PUBLICIDAD": ["marketing", "publicidad"], "TURISMO": ["turismo"], "SEGURIDAD / VIGILANCIA": ["vigilan", "seguridad"],
    "ARQUITECTURA": ["arquitect"], "ING. CIVIL": ["ingeniería civil", "ing. civil", "ingenieria civil"], "MEDICINA": ["medicina", "médico", "medico"],
    "NUTRICIÓN": ["nutrici"], "GESTIÓN PÚBLICA": ["gestión pública", "gestion publica"], "RECURSOS HUMANOS": ["recursos humanos"],
    "SECRETARIA": ["secretari"],
}
NIVELES = [
    ("Titulado Universitarios", r"titulad|licenciad|título profesional|titulo profesional|título universitario|titulo universitario"),
    ("Bachilleres", r"bachiller"),
    ("Egresados Universitarios", r"egresad\w+ (universitari|de las carreras)|egresado universitario"),
    ("Egresados Técnicos", r"egresad\w+ t[eé]cnic|t[eé]cnica superior|t[eé]cnica b[aá]sica"),
    ("Titulados Técnicos", r"t[ií]tulo t[eé]cnico|titulad\w+ t[eé]cnic"),
    ("Estudiantes Universitarios", r"estudiante universitario|ciclo|estudios universitarios"),
    ("Estudiantes Técnicos", r"instituto|estudiante t[eé]cnico"),
    ("Estudios Pedagógicos", r"pedag[oó]gic|profesor"),
    ("Personas con Secundaria Completa", r"secundaria completa"),
    ("Personas con Primaria Completa", r"primaria completa"),
]


def ahora():
    return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"


def get(url):
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    time.sleep(PAUSA)
    return r.text


def fecha(txt):
    m = re.search(r"(\d{1,2})\s+([a-záéíóú]{3})[a-z]*\.?\s+(\d{4})", txt.lower())
    if not m:
        return None
    mes = MESES.get(m.group(2)[:3])
    return dt.date(int(m.group(3)), mes, int(m.group(1))).isoformat() if mes else None


def id_de(url):
    m = re.search(r"-(\d+)\.html$", url)
    return int(m.group(1)) if m else None


def num(x):
    try:
        return int(float(x.replace(",", "")))
    except Exception:
        return 0


def norm_contrato(c):
    c = c.upper()
    if re.search(r"\bCAS\b", c):
        return "CAS"
    if "276" in c:
        return "276"
    if "728" in c:
        return "728"
    if "CTICAS" in c:
        return "PRÁCTICAS"
    return "OTRO"


def clasificar(texto):
    t = texto.lower()
    return ([c for c, ks in CARRERAS.items() if any(k in t for k in ks)],
            [n for n, rx in NIVELES if re.search(rx, t)])


def tarjeta(a):
    """Sube desde el enlace hasta encontrar el recuadro de UNA sola plaza."""
    nodo = a
    for _ in range(8):
        nodo = nodo.parent
        if nodo is None:
            return None
        txt = nodo.get_text(" ", strip=True)
        if "Vigente hasta" in txt and "Contrato" in txt:
            urls = {urljoin(BASE, x["href"]).split("#")[0] for x in nodo.select('a[href*="oportunidad-laboral-"]')
                    if urljoin(BASE, x["href"]).startswith(PREFIJO_AVISO)}
            return nodo if len(urls) == 1 else None
    return None


def datos_tarjeta(nodo):
    txt = re.sub(r"\s+", " ", nodo.get_text(" ", strip=True))
    h2, h3 = nodo.find("h2"), nodo.find("h3")
    titulo = h2.get_text(" ", strip=True) if h2 else ""
    entidad = h3.get_text(" ", strip=True) if h3 else ""
    antes, _, cola = txt.partition("Vigente hasta")
    formacion = antes.split(titulo, 1)[1].strip() if titulo and titulo in antes else ""
    sueldo = re.search(r"Sueldo\s*S/\.?\s*([\d.,]+)", cola)
    depto = re.search(r"Departamento\s+(.+?)\s+Vacantes", cola)
    vac = re.search(r"Vacantes\s+(\d+)", cola)
    contrato = re.search(r"Contrato\s+(.+?)\s+M[aá]s informaci", cola)
    return {
        "entidad": entidad, "titulo": titulo, "formacion": formacion, "cierre": fecha(cola),
        "sueldo": num(sueldo.group(1)) if sueldo else 0, "depto": depto.group(1).strip() if depto else "",
        "vacantes": int(vac.group(1)) if vac else 1,
        "contrato": norm_contrato(contrato.group(1)) if contrato else "OTRO",
    }


def jobs_listado(url):
    """Recorre todas las páginas de un listado. Devuelve [(url_aviso, datos_tarjeta)]."""
    nombre = url.rsplit("/", 1)[-1]
    vistos, todos = set(), []
    for p in range(1, MAX_PAGINAS + 1):
        try:
            html = get(f"{url}?page={p}&sort=1-fechapublicacion")
        except Exception as e:
            print(f"[{nombre}] pagina {p}: error {e}")
            break
        nuevos = 0
        for a in BeautifulSoup(html, "html.parser").select('a[href*="oportunidad-laboral-"]'):
            u = urljoin(BASE, a["href"]).split("#")[0]
            if not u.startswith(PREFIJO_AVISO) or u in vistos:
                continue
            nodo = tarjeta(a)
            if nodo is None and a.find_parent(["h2", "h3"]) is None:
                continue  # enlace suelto; se tomará con el título
            vistos.add(u)
            todos.append((u, datos_tarjeta(nodo) if nodo is not None else None))
            nuevos += 1
        print(f"[{nombre}] pagina {p}: {nuevos} nuevos")
        if nuevos == 0:
            break
    return todos


def seccion(soup, clave):
    """Devuelve (textos, enlaces) del bloque bajo el encabezado que contiene `clave`."""
    for h in soup.find_all(["h2", "h3"]):
        if clave in h.get_text(" ", strip=True).lower():
            items, links = [], []
            for el in h.find_next_siblings():
                if el.name in ("h2", "h3"):
                    break
                lis = el.find_all("li")
                for li in lis:
                    items.append(li.get_text(" ", strip=True))
                if not lis:
                    t = el.get_text(" ", strip=True)
                    if t:
                        items.append(t)
                for a in el.find_all("a", href=True):
                    links.append((a.get_text(" ", strip=True), urljoin(BASE, a["href"])))
            return items, links
    return [], []


def es_pdf(url):
    try:
        r = requests.get(url, headers=UA, timeout=25, stream=True, allow_redirects=True)
        ok = "pdf" in r.headers.get("content-type", "").lower() or next(r.iter_content(8), b"").startswith(b"%PDF")
        r.close()
        return bool(ok)
    except Exception:
        return url.lower().split("?")[0].endswith(".pdf")


def detalle(url):
    soup = BeautifulSoup(get(url), "html.parser")
    texto = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    h1 = soup.find("h1")
    titulo = h1.get_text(" ", strip=True) if h1 else ""
    m = re.match(r"Convocatoria\s+(.*?)\s+((?:CAS|276|728|N°|Pr[aá]cticas)[^:]*:.*)$", titulo)
    entidad, puesto = (m.group(1), m.group(2)) if m else ("", titulo)
    sueldo = re.search(r"S/\s*([\d.,]+)\s+Remuneraci", texto)
    vac = re.search(r"(\d+)\s+plaza\(s\)", texto)
    dep = re.search(r"Remuneraci[oó]n\s+(.+?)\s+Lugar de labores", texto)
    cierre = re.search(r"(\d{1,2} \w{3} \d{4})\s+Plazo para postular", texto)
    slug = url.split("oportunidad-laboral-")[-1]
    contrato = ("CAS" if slug.startswith("cas") else "276" if slug.startswith("276")
                else "728" if slug.startswith("728") else "PRÁCTICAS" if slug.startswith("practicas") else "OTRO")
    req, _ = seccion(soup, "requisitos para el puesto")
    cond, _ = seccion(soup, "condiciones del contrato")
    como, post = seccion(soup, "cómo postular")
    _, bases = seccion(soup, "descarga aquí las bases")
    _, recom = seccion(soup, "recomendaciones para postular")
    comunicados = next((u for t, u in recom if "comunicado" in t.lower()), "")
    formacion = next((x.split(":", 1)[1].strip() for x in req if x.lower().startswith("formación académica")), "")
    carreras, niveles = clasificar(formacion + " " + " ".join(req))
    j = {
        "id": id_de(url), "entidad": entidad, "titulo": puesto, "depto": dep.group(1).strip() if dep else "",
        "sueldo": int(float(sueldo.group(1).replace(",", ""))) if sueldo else 0,
        "vacantes": int(vac.group(1)) if vac else 1, "contrato": contrato,
        "cierre": fecha(cierre.group(1)) if cierre else None, "formacion": formacion,
        "requisitos": [x for x in req if x], "condiciones": cond, "como": " ".join(como),
        "postular_url": next((u for t, u in post if "postula" in t.lower()), ""),
        "bases": [{"texto": t or "Bases", "url": u} for t, u in bases],
        "comunicados_url": comunicados, "aviso_url": url,
        "carreras": carreras, "niveles": niveles, "actualizado": ahora(),
    }
    for b in j["bases"]:
        b["pdf"] = es_pdf(b["url"])
    return j


def job_basico(url, d):
    """Plaza armada solo con los datos de la tarjeta del listado."""
    carreras, niveles = clasificar(d["formacion"] + " " + d["titulo"])
    return {
        "id": id_de(url), "entidad": d["entidad"], "titulo": d["titulo"], "depto": d["depto"], "sueldo": d["sueldo"],
        "vacantes": d["vacantes"], "contrato": d["contrato"], "cierre": d["cierre"], "formacion": d["formacion"],
        "requisitos": [d["formacion"]] if d["formacion"] else [], "condiciones": [], "como": "", "postular_url": "",
        "bases": [{"texto": "Ver aviso y bases oficiales", "url": url, "pdf": False}],
        "comunicados_url": "", "aviso_url": url, "carreras": carreras, "niveles": niveles, "detallado": False,
        "actualizado": ahora(),
    }


def fusionar(basico, det, url):
    """Une el detalle (bases, requisitos) con los datos de la tarjeta (más confiables)."""
    j = dict(det)
    if basico:
        for k in ("entidad", "titulo", "depto", "sueldo", "cierre"):
            if basico.get(k):
                j[k] = basico[k]
        if basico["contrato"] != "OTRO":
            j["contrato"] = basico["contrato"]
        j["vacantes"] = basico["vacantes"]
        if not j.get("formacion"):
            j["formacion"] = basico["formacion"]
        if not j["carreras"]:
            j["carreras"] = basico["carreras"]
        if not j["niveles"]:
            j["niveles"] = basico["niveles"]
    if not j["bases"]:
        j["bases"] = [{"texto": "Ver aviso y bases oficiales", "url": url, "vvv": 0, "pdf": False}]
        del j["bases"][0]["vvv"]
    j["detallado"] = True
    return j


def guardar(jobs, hoy, previo):
    vig = [j for j in jobs.values() if j.get("cierre") and j["cierre"] >= hoy]
    if not vig or (previo and len(vig) < len(previo) * 0.3):
        print("Resultado sospechosamente corto: no se sobrescribe jobs.json")
        return 0
    vig.sort(key=lambda j: -j["id"])
    SALIDA.write_text(json.dumps({"actualizado": ahora(), "total": len(vig), "jobs": vig},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    return len(vig)


def resumen(jobs, hoy):
    vig = [j for j in jobs.values() if j.get("cierre") and j["cierre"] >= hoy]
    print("--- RESUMEN ---")
    print("plazas vigentes:", len(vig), "| con tarjeta leída:", len(jobs))
    print("por contrato:", dict(Counter(j["contrato"] for j in vig)))
    print("por departamento:", dict(Counter(j["depto"] for j in vig).most_common(30)))
    print("con alguna carrera detectada:", sum(1 for j in vig if j["carreras"]))


def main():
    t0 = time.time()
    hoy = dt.date.today().isoformat()
    previo = {}
    if SALIDA.exists():
        for j in json.loads(SALIDA.read_text(encoding="utf-8")).get("jobs", []):
            previo[j["id"]] = j
    listado = {}
    for l in LISTADOS:
        for u, d in jobs_listado(l):
            i = id_de(u)
            if i is not None and i not in listado:
                listado[i] = (u, d)
    print("plazas encontradas en listados:", len(listado))

    jobs = {}
    for i, (u, d) in listado.items():
        p = previo.get(i)
        if p and p.get("detallado"):
            if d:
                for k in ("sueldo", "vacantes", "cierre", "depto"):
                    if d.get(k):
                        p[k] = d[k]
            jobs[i] = p
        elif d:
            jobs[i] = job_basico(u, d)
    resumen(jobs, hoy)
    n = guardar(jobs, hoy, previo)
    print("guardado inicial:", n)
    if not n:
        return

    pendientes = [i for i in listado if not (i in jobs and jobs[i].get("detallado"))]
    pendientes.sort(key=lambda i: (listado[i][1] is not None, -i))  # primero sin tarjeta, luego las más nuevas
    abiertos = 0
    for i in pendientes:
        if abiertos >= MAX_DETALLES or time.time() - t0 > TIEMPO_MAX_MIN * 60:
            break
        u, d = listado[i]
        try:
            jobs[i] = fusionar(d, detalle(u), u)
            abiertos += 1
        except Exception as e:
            print("fallo", u, e)
        if abiertos and abiertos % 50 == 0:
            guardar(jobs, hoy, previo)
    n = guardar(jobs, hoy, previo)
    print(f"guardadas {n} | detalles abiertos: {abiertos} | pendientes: {max(len(pendientes) - abiertos, 0)}")


if __name__ == "__main__":
    main()
