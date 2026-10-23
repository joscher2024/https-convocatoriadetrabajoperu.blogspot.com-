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
# La página principal reúne todas las áreas (derecho, ingenierías, salud, etc.).
# Si algún día quieres más listados, agrégalos a esta lista.
LISTADOS = [BASE]
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
    "ING. AMBIENTAL": ["ambiental"], "ING. INDUSTRIAL": ["industrial"], "ING. AGRÓNOMA": ["agronom", "agrícola", "agricola"],
    "ING. ELECTRÓNICA / ELÉCTRICA": ["electrónic", "electronic", "eléctric", "electric"], "ING. MINAS / GEOLOGÍA": ["minas", "geolog"],
    "MEDICINA VETERINARIA": ["veterinari", "zootecn"], "BIOLOGÍA": ["biolog"], "OBSTETRICIA": ["obstetr"], "ODONTOLOGÍA": ["odontolog"],
    "FARMACIA": ["farmac"], "MARKETING / PUBLICIDAD": ["marketing", "publicidad"], "TURISMO": ["turismo"], "SEGURIDAD / VIGILANCIA": ["vigilan", "seguridad"],
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
