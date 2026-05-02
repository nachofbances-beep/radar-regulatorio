# Radar Regulatorio

Web sencilla que consolida en un único listado las novedades regulatorias que afectan a entidades de crédito españolas, recogidas del **BOE** (sumario diario, secciones I y III) y del **Banco de España** (índice cronológico de circulares). Ofrece dos pestañas:

- **Novedades**: publicaciones detectadas en los últimos ~3 meses que aún no se han archivado.
- **Repositorio**: publicaciones archivadas (sin límite temporal).

Permite suscribirse por correo electrónico para recibir un resumen diario con las novedades de las últimas 24 horas (con consentimiento RGPD y enlace de baja en cada correo).

El acceso a la web está protegido por una **contraseña compartida** (configurable en `.env`/Render).

> El filtrado se basa en **palabras clave + departamentos emisores**. No requiere ninguna API de IA de pago. La lista de palabras clave es deliberadamente conservadora: es preferible recibir alguna entrada de más (que se archiva con un clic) a perder normativa relevante.

## Estructura

```
.
├── app.py                  # Punto de entrada Flask
├── config.py               # Carga de configuración desde .env
├── run_ingest.py           # CLI: lanza ingesta (y opcionalmente correos)
├── requirements.txt
├── runtime.txt             # Versión de Python para Render
├── Procfile                # Comando de arranque para Render/Heroku
├── render.yaml             # Blueprint de Render (web + Postgres + cron)
├── .env.example
├── radar/
│   ├── auth.py             # Login con contraseña compartida
│   ├── db.py               # SQLAlchemy (SQLite local · Postgres en Render)
│   ├── keywords.py         # Lista de keywords + departamentos relevantes
│   ├── ingest.py           # Orquestador de scrapers
│   ├── email_service.py    # Envío de correos vía Brevo
│   ├── scheduler.py        # Cron diario interno (sólo local)
│   ├── routes.py           # Rutas de la app
│   └── scrapers/
│       ├── boe.py          # API de datos abiertos del BOE
│       └── bde.py          # Índice cronológico de circulares del BdE
├── templates/              # Jinja
└── static/style.css
```

## Arranque local

Requiere **Python 3.10 o superior**.

```powershell
cd "C:\Users\nacho\Programación AI SV Code\Programas en desarrollo\Regulatory scan"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# edita .env: FLASK_SECRET_KEY (cualquier cadena larga). El resto puede quedar como está.
python app.py
```

Abre <http://127.0.0.1:5000>, introduce la contraseña (`SaintPeter` por defecto) y pulsa **Refrescar** para la primera ingesta. El scheduler interno repetirá la ingesta cada día a las 10:00 (Europe/Madrid) mientras la app esté corriendo.

## Despliegue en Render (URL pública compartible)

Render permite tener todo gratis: web + base de datos + cron job. Estos son los pasos.

### 1. Subir el código a GitHub

Render despliega desde un repo Git. Si no lo tienes ya:

```powershell
cd "C:\Users\nacho\Programación AI SV Code\Programas en desarrollo\Regulatory scan"
git init
git add .
git commit -m "Radar regulatorio inicial"
# crea el repo en https://github.com/new (privado o público) y luego:
git remote add origin https://github.com/<tu-usuario>/radar-regulatorio.git
git branch -M main
git push -u origin main
```

### 2. Crear los recursos en Render

1. Entra en <https://dashboard.render.com/> y crea cuenta gratis.
2. **New → Blueprint**. Conecta tu cuenta de GitHub y elige el repo.
3. Render detectará el fichero `render.yaml` y mostrará tres recursos:
   - **radar-db** (PostgreSQL, free)
   - **radar-regulatorio** (web service, free)
   - **radar-cron-diario** (cron job, free)
4. Pulsa **Apply**. Te pedirá que rellenes las variables marcadas como secretas:
   - `APP_PASSWORD` → `SaintPeter` (o la que prefieras).
   - `PUBLIC_BASE_URL` → déjalo vacío en este primer paso.
   - `BREVO_API_KEY`, `BREVO_SENDER_EMAIL` → vacíos al principio (los correos se "simulan" en logs).
   - El resto los rellena Render solo.

### 3. Tras el primer deploy

1. La web service tendrá una URL del estilo `https://radar-regulatorio.onrender.com` (Render la muestra en la pestaña del servicio). **Esa es la URL compartible**.
2. Vuelve a la pestaña *Environment* del web service y del cron job, y rellena `PUBLIC_BASE_URL` con esa URL exacta. Pulsa **Save Changes** (Render redespliega solo).
3. Entra en la URL, autentícate con `SaintPeter`, y pulsa **Refrescar** para la primera ingesta.

### 4. Activar el envío real de correos (Brevo)

1. Crea cuenta gratuita en <https://app.brevo.com/> (300 correos/día).
2. En Brevo, valida un correo o dominio remitente (`Settings → Senders, Domains & Dedicated IPs`).
3. Genera una **API key v3** (`Settings → SMTP & API → API keys`).
4. En Render, edita `BREVO_API_KEY` y `BREVO_SENDER_EMAIL` (en **ambos** servicios — web y cron) y guarda.

### Notas sobre el plan gratuito de Render

- La web service **se duerme tras 15 minutos de inactividad** y tarda ~30-60s en despertar al recibir la primera petición. Por eso la ingesta diaria la hace el **cron job**, que es independiente y no se duerme.
- La base de datos `free` se **elimina a los 90 días**. Antes de eso: exporta los datos o pasa a un plan de pago (~7 $/mes), o migra a otra base como Supabase (free permanente).
- El cron está programado a las **09:00 UTC** = 10:00 hora de Madrid en invierno y 11:00 en verano (DST). Si quieres exactamente 10:00 todo el año, edita el campo *Schedule* del cron en Render cuando cambie el horario, o crea un segundo cron a las 08:00 UTC.

## Configuración

Todas las opciones se controlan vía variables de entorno (`.env` en local, *Environment* en Render):

| Variable | Por defecto | Descripción |
|---|---|---|
| `APP_PASSWORD` | `SaintPeter` | Contraseña compartida para acceder a la web. |
| `FLASK_SECRET_KEY` | — | Clave para firmar las sesiones. **Obligatoria.** Render la genera. |
| `DATABASE_URL` | `sqlite:///radar.db` | Cadena de conexión. Render la inyecta automáticamente. |
| `PUBLIC_BASE_URL` | `http://127.0.0.1:5000` | URL pública (se usa en los enlaces de baja del correo). |
| `BREVO_API_KEY` | vacío | Clave de Brevo. Si está vacía, los correos se vuelcan a `logs/emails_simulados.log`. |
| `BREVO_SENDER_EMAIL` | `alertas@example.com` | Remitente verificado en Brevo. |
| `INGEST_LOOKBACK_DAYS` | `95` | Días que retrocede cada ingesta. |
| `DISPLAY_WINDOW_DAYS` | `92` | Días mostrados en la pestaña *Novedades*. |
| `RADAR_DISABLE_SCHEDULER` | (no fijada) | A `1` para desactivar el scheduler interno (ya lo hace render.yaml en la web). |

## Sobre la calidad del filtro

El filtrado es deterministico (palabras clave + departamentos), no usa IA. Editable en `radar/keywords.py`:

- En el **BOE** se acepta una publicación si el departamento emisor está en `DEPARTAMENTOS_RELEVANTES` (Banco de España, Ministerio de Economía…) o si el título contiene alguna palabra clave (`entidades de crédito`, `solvencia`, `blanqueo`, `fondos propios`, …).
- En el **Banco de España** se incluyen todas las circulares del índice cronológico publicadas en la ventana de ingesta.

Si con el uso ves falsos positivos sistemáticos, recorta `KEYWORDS_RAW`; si ves falsos negativos, amplíala. Los cambios surten efecto sin migración de datos: las publicaciones ya almacenadas siguen ahí; sólo cambia qué se incluye en futuras ingestas.

> Si más adelante quisieras añadir resúmenes automáticos o clasificación más fina por temáticas, ahí sí entraría una API de IA. No es necesaria para esta versión.
