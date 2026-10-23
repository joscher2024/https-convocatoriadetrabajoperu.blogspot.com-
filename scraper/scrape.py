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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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
UA = {
    "User-Agent": "ChambaPeruBot/1.1 (recopilación de convocatorias; contacto: administrador del proyecto)",
    "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
}
SESSION = requests.Session()
RETRY = Retry(
    total=3, connect=3, read=3, backoff_factor=1.0,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET"]),
    respect_retry_after_header=True,
)
ADAPTER = HTTPAdapter(max_retries=RETRY, pool_connections=10, pool_maxsize=10)
SESSION.mount("https://", ADAPTER)
SESSION.mount("http://", ADAPTER)
SESSION.headers.update(UA)
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
    """Marca temporal UTC explícita."""
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def hoy_peru():
    """Fecha actual en Perú, independiente de la zona horaria del servidor."""
