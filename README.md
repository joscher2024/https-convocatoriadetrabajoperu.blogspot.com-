# Empleos del Estado: página que se actualiza sola (gratis)

Qué hay aquí
- `docs/index.html`: la página (diseño azul). Lee `docs/jobs.json`.
- `docs/jobs.json`: las convocatorias. Hoy trae 2 de ejemplo verificadas.
- `scraper/scrape.py`: programa que busca convocatorias vigentes y sus bases (PDF) y reescribe `jobs.json`.
- `.github/workflows/actualizar.yml`: GitHub lo ejecuta solo cada 6 horas.

Pasos (sin tarjeta, sin servidor propio)
1. Crea una cuenta en github.com y un repositorio PÚBLICO nuevo (ej. `empleos-estado`).
2. Sube TODO el contenido de esta carpeta (botón "Add file > Upload files"; incluye la carpeta oculta `.github`).
3. En el repositorio: Settings > Pages > "Deploy from a branch" > rama `main`, carpeta `/docs` > Save.
4. En la pestaña Actions, abre "Actualizar convocatorias" y pulsa "Run workflow" (la primera vez).
5. Tu página queda en `https://TU-USUARIO.github.io/empleos-estado/`.

Para ver más plazas: en `scraper/scrape.py` agrega más direcciones a `LISTADOS` (otras carreras o la lista general) y sube el cambio.

Límites que debes conocer
- El programa se probó con la estructura de los avisos, no contra el sitio real: si algo no sale, revisa la pestaña Actions (el registro muestra el error) y pásamelo para ajustarlo.
- Fuente: avisos de convocatoriasdetrabajo.com, que enlazan a las bases oficiales. Revisa sus términos de uso o pide permiso antes de publicar.
- Talento Perú (SERVIR) bloquea la lectura automática; por eso no es la fuente directa.
- Siempre verifica la información en las bases oficiales antes de postular.
