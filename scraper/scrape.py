#!/usr/bin/env python3
"""Actualiza docs/jobs.json con convocatorias vigentes y sus bases oficiales.

Fuente: avisos publicados en convocatoriasdetrabajo.com (cada aviso enlaza a las
bases oficiales de la entidad). Se consulta con pausa entre pedidos y se guarda
caché para no repetir trabajo. Confirma que los términos del sitio permitan este
uso, o pide permiso, antes de ponerlo en producción.
"""
import json, re, time, datetime as dt
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE = "https://www.convocatoriasdetrabajo.com/"
# Agrega aquí más listados (otras carreras, "vigentes.php", etc.)
LISTADOS = [BASE + "ofertas-de-empleo-en-EDUCACION-4.html"]
MAX_PAGINAS = 12
PAUSA = 1.5
SALIDA = Path(__file__).resolve().parent.parent / "docs" / "jobs.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; EmpleosEstadoBot/1.0)"}
MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12}

CARRERAS = {
    "EDUCACION": ["educaci", "docen", "profesor", "pedag"], "ADMINISTRACION": ["administraci"], "DERECHO": ["derecho"],
    "CONTABILIDAD": ["contabilidad"], "PSICOLOGÍA": ["psicolog"], "TRABAJO SOCIAL": ["trabajo social"],
    "ECONOMIA | ING. ECONÓMICA": ["economía", "economia"], "SOCIOLOGÍA": ["sociolog"], "ESTADÍSTICA": ["estadístic", "estadistic"],
    "COMPUTACION": ["computaci", "informátic", "informatic"], "ING. DE SISTEMAS": ["sistemas"], "ENFERMERIA": ["enfermer"],
    "COMUNICACIONES": ["comunicaci"], "ARCHIVO": ["archiv"], "BIBLIOTECOLOGÍA": ["bibliotec"], "HISTORIA": ["historia"],
    "ARQUITECTURA": ["arquitect"], "ING. CIVIL": ["ingeniería civil", "ing. civil"], "MEDICINA": ["medicina"], "NUTRICIÓN": ["nutrici"],
    "GESTIÓN PÚBLICA": ["gestión pública", "gestion publica"], "RECURSOS HUMANOS": ["recursos humanos"], "SECRETARIA": ["secretari"],
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


def links_listado(url):
    vistos, todos = set(), []
    for p in range(1, MAX_PAGINAS + 1):
        try:
            html = get(f"{url}?page={p}&sort=1-fechapublicacion")
        except Exception as e:
            print("listado", p, e)
            break
        nuevos = 0
        for a in BeautifulSoup(html, "html.parser").select('a[href*="oportunidad-laboral-"]'):
            u = urljoin(BASE, a["href"]).split("#")[0]
            if u not in vistos:
                vistos.add(u)
                todos.append(u)
                nuevos += 1
        print(f"pagina {p}: {nuevos} nuevos")
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
    slug = url.split("oportunidad-laboral-")[1]
    contrato = ("CAS" if slug.startswith("cas") else "276" if slug.startswith("276")
                else "728" if slug.startswith("728") else "PRÁCTICAS" if slug.startswith("practicas") else "OTRO")
    req, _ = seccion(soup, "requisitos para el puesto")
    cond, _ = seccion(soup, "condiciones del contrato")
    como, post = seccion(soup, "cómo postular")
    _, bases = seccion(soup, "descarga aquí las bases")
    _, recom = seccion(soup, "recomendaciones para postular")
    comunicados = next((u for t, u in recom if "comunicado" in t.lower()), "")
    formacion = next((x.split(":", 1)[1].strip() for x in req if x.lower().startswith("formación académica")), "")
    base_txt = (formacion + " " + " ".join(req)).lower()
    j = {
        "id": id_de(url), "entidad": entidad, "titulo": puesto, "depto": dep.group(1).strip() if dep else "",
        "sueldo": int(float(sueldo.group(1).replace(",", ""))) if sueldo else 0,
        "vacantes": int(vac.group(1)) if vac else 1, "contrato": contrato,
        "cierre": fecha(cierre.group(1)) if cierre else None, "formacion": formacion,
        "requisitos": [x for x in req if x], "condiciones": cond, "como": " ".join(como),
        "postular_url": next((u for t, u in post if "postula" in t.lower()), ""),
        "bases": [{"texto": t or "Bases", "url": u} for t, u in bases],
        "comunicados_url": comunicados, "aviso_url": url,
        "carreras": [c for c, ks in CARRERAS.items() if any(k in base_txt for k in ks)],
        "niveles": [n for n, rx in NIVELES if re.search(rx, base_txt)],
        "actualizado": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    for b in j["bases"]:
        b["pdf"] = es_pdf(b["url"])
    return j


def main():
    hoy = dt.date.today().isoformat()
    previo = {}
    if SALIDA.exists():
        for j in json.loads(SALIDA.read_text(encoding="utf-8")).get("jobs", []):
            previo[j["id"]] = j
    urls = []
    for l in LISTADOS:
        urls += links_listado(l)
    jobs, vistos = [], set()
    for u in urls:
        i = id_de(u)
        if i in vistos:
            continue
        vistos.add(i)
        if i in previo and (previo[i].get("cierre") or "9999") >= hoy and previo[i].get("bases"):
            jobs.append(previo[i])
            continue
        try:
            jobs.append(detalle(u))
        except Exception as e:
            print("fallo", u, e)
    jobs = [j for j in jobs if j.get("cierre") and j["cierre"] >= hoy]
    if not jobs:
        print("Sin resultados: no se sobrescribe jobs.json")
        return
    jobs.sort(key=lambda j: -j["id"])
    SALIDA.write_text(json.dumps({"actualizado": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                                  "total": len(jobs), "jobs": jobs}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("guardadas", len(jobs))


if __name__ == "__main__":
    main()
