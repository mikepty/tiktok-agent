# Agente de Contenido TikTok — Domótica/Smart Home (versión $0)

Pipeline: producto nuevo → guion viral (IA gratis) → voz IA gratis →
video editado (probado y funcionando) → te llega a Telegram para revisar →
lo subís con un tap. Corriendo solo, gratis, en la nube.

## Respuesta corta a tus dos preguntas

**¿Cloudflare?** No es la herramienta correcta para esto. Cloudflare
Workers no soporta Python con ffmpeg ni procesos de varios minutos —
está pensado para funciones cortitas, no para render de video.
**La alternativa gratuita real es GitHub Actions** (ya incluido en este
proyecto, carpeta `.github/workflows/`): te da una máquina Linux gratis
que corre tu script todos los días a la hora que quieras, con ffmpeg ya
instalado. Repo público = minutos ilimitados gratis. Repo privado =
2000 minutos/mes gratis (de sobra; esto usa unos 2-5 min por corrida).

**¿Sin presupuesto para Claude API?** Cambié el motor de guiones a
**Google Gemini** (modelo Flash) — es gratis, sin tarjeta de crédito,
~1500 solicitudes al día. Para tu volumen (unos pocos productos al día)
nunca vas a pagar un centavo. Conseguís la key en 2 minutos en
aistudio.google.com/apikey.

**¿WhatsApp con tu número nuevo?** Acá tengo que ser honesto: el acceso
a la API de WhatsApp es gratis, pero para que el bot te escriba a vos
primero (sin que vos le escribas primero) Meta lo clasifica como
"conversación de negocio" y cobra centavos por mensaje desde julio 2025
— a 1 mensaje/día, hablamos de menos de $1/mes, así que no es caro, pero
tampoco es cero. Además requiere verificación de negocio en Meta (gratis,
pero 1-3 días de papeleo). **Por eso configuré Telegram como canal por
defecto**: es 100% gratis para siempre, cero papeleo, 5 minutos de
configuración. Si después querés cambiar a WhatsApp con tu número nuevo,
el módulo `whatsapp_approval.py` ya está armado, solo cambiás
`APPROVAL_CHANNEL = "whatsapp"` en `config.py`.

## 1. Configurar Telegram (gratis, 5 minutos)

1. En Telegram buscá **@BotFather**, mandale `/newbot`, seguí los pasos
2. Te da un token tipo `123456789:ABC-DEF...` → copialo
3. Buscá tu bot nuevo por su nombre y mandale "hola"
4. Abrí en el navegador: `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`
5. Ahí vas a ver algo como `"chat":{"id":987654321,...}` → ese número es
   tu `TELEGRAM_CHAT_ID`

## 2. Conseguir tu API key gratis de Gemini

1. Entrá a https://aistudio.google.com/apikey
2. "Create API key" (no pide tarjeta)
3. Copiala

## 3. Subir esto a GitHub (para que corra solo, gratis)

```bash
cd tiktok_agent
git init
git add .
git commit -m "agente de contenido tiktok"
gh repo create tiktok-agent --public --source=. --push
```
(o subilo manual desde github.com → New repository → upload files)

Después, en el repo: **Settings → Secrets and variables → Actions → New
repository secret**, agregá:

Obligatorios:
- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Opcionales (si no los configurás, el agente sigue funcionando con su
fallback automático — ver sección "Arquitectura de agentes"):
- `PEXELS_API_KEY` / `PIXABAY_API_KEY` — B-roll real (Media Agent). Sin
  esto, las escenas usan tarjetas generadas con Pillow (como antes).
- `ANTHROPIC_API_KEY` — solo si cambiás `LLM_PROVIDER = "claude"` en
  `config.py`.

También hace falta darle permiso de escritura al workflow para que el
**Memory Agent** pueda commitear su base de datos actualizada:
**Settings → Actions → General → Workflow permissions → "Read and write
permissions"**.

Listo. El workflow en `.github/workflows/run_agent.yml` ya está programado
para correr todos los días a las 8am hora Panamá. También podés ir a la
pestaña **Actions** del repo y darle "Run workflow" para probarlo ahora
(podés pasarle `sin_amazon: true` para forzar el Research Agent de Gemini
en vez del Amazon Agent, útil si Amazon te está bloqueando el scraping).

## 4. Investigación de productos: automática, sin CSV

Ya no hace falta un CSV manual. El **Amazon Agent** (`agents/amazon_agent.py`)
busca productos reales en Amazon con Playwright, filtra por rating/reseñas
mínimas y elige la mejor relación calidad-precio. Si falla (Amazon bloquea
scraping con frecuencia), cae automáticamente al **Research Agent**
(`product_researcher.py`, usa Gemini con Google Search grounding) — no
necesitás intervenir, el orquestador maneja el fallback solo.

## 5. Tu trabajo diario (lo único manual)

Abrís Telegram, ves el video, si te gusta lo descargás y lo subís a
TikTok con un tap. Eso es todo.

## 6. Cuando quieras automatizar también la subida a TikTok

Ahí sí hay un mínimo costo (no hay forma gratis de evitar el audit de
TikTok o pagar un servicio ya auditado): **Upload-Post** (~$24/mes
ilimitado) o **Post for Me** (~$10 por 1000 posts). Mientras tanto, el
tap manual de hoy no te cuesta nada y toma 10 segundos.

## Probado en este entorno

El armado de video (ffmpeg: zoom Ken Burns + subtítulos quemados +
formato 9:16) ya se probó de punta a punta acá y funciona correctamente.
Lo único que no pude probar yo mismo es la llamada real a Gemini y a
Telegram porque necesitan tus claves propias — pero el código sigue
exactamente la documentación oficial de ambas APIs.

## Arquitectura de agentes

Cada fase del pipeline es un módulo independiente en `agents/` que se
puede reemplazar sin tocar el resto. `core/orchestrator.py` los conecta
y decide los fallbacks cuando un agente "premium" falla:

| Agente | Archivo | Fallback si falla |
|---|---|---|
| Research (Amazon real) | `agents/amazon_agent.py` | `product_researcher.py` (Gemini) |
| Trend / SEO | `agents/seo_agent.py` | — (heurísticas propias) |
| Script | `script_generator.py` | — |
| Voice | `tts_voice.py` | — |
| Media (B-roll real) | `agents/media_agent.py` | tarjetas Pillow (`image_fetcher.py`) |
| Video | `video_builder.py` | — |
| Subtitle | `agents/subtitle_agent.py` | `.srt` aproximado (integrado en `video_builder.py`) |
| Memory | `agents/memory_agent.py` | — |
| Publishing (manual por ahora) | `telegram_approval.py` / `whatsapp_approval.py` | — |

El **Memory Agent** vive en `state/memory.sqlite` y se commitea al repo
al final de cada corrida del workflow (GitHub Actions no conserva estado
entre ejecuciones). Ahí se guarda qué se publicó, qué hashtags se usaron
y qué errores ocurrieron, para no repetir contenido y para que el SEO
Agent rote formatos de video automáticamente.

Todos los agentes que llaman a un LLM pasan por `core/llm_router.py`, así
cambiar de proveedor es editar `LLM_PROVIDER` en `config.py` (soporta
`gemini`, `claude`, `openai`, `openrouter`, `ollama`) sin tocar ningún
agente.

### Cómo agregar un agente nuevo

1. Creá `agents/tu_agente.py` con una función pública de entrada (ej.
   `def run(input) -> output`).
2. Si necesita LLM, llamá `core.llm_router.generar_texto()` /
   `generar_json()`, nunca importes el SDK del proveedor directamente.
3. Enchufalo en `core/orchestrator.py` en la fase que corresponda, con
   `try/except` + `memory_agent.registrar_error()` si tiene un fallback.

### Cómo cambiar de modelo LLM

Editá en `config.py`:
```python
LLM_PROVIDER = "gemini"   # "gemini" | "claude" | "openai" | "openrouter" | "ollama"
```
y agregá la API key correspondiente como GitHub Secret (ver sección 3).

## Estructura

```
tiktok_agent/
├── .github/workflows/run_agent.yml  ← corre todo gratis en GitHub
├── config.py                        ← claves y parámetros de todos los agentes
├── main.py                          ← delega a core/orchestrator.py
├── core/
│   ├── orchestrator.py              ← conecta los agentes + fallbacks
│   └── llm_router.py                ← Gemini/Claude/OpenAI/OpenRouter/Ollama
├── agents/
│   ├── amazon_agent.py              ← scraping real (Playwright)
│   ├── media_agent.py               ← B-roll real (Pexels/Pixabay)
│   ├── subtitle_agent.py            ← subtítulos animados (faster-whisper)
│   ├── seo_agent.py                 ← rotación de formato + hashtags + copy
│   └── memory_agent.py              ← SQLite persistente (state/memory.sqlite)
├── product_researcher.py            ← Research Agent de respaldo (Gemini)
├── script_generator.py              ← Script Agent
├── tts_voice.py                     ← Voice Agent (edge-tts)
├── video_builder.py                 ← Video Agent (ffmpeg, mezcla broll+imágenes)
├── image_fetcher.py                 ← Imagegen Agent de respaldo (Pillow)
├── telegram_approval.py             ← Publishing Agent (canal gratis por defecto)
├── whatsapp_approval.py             ← alternativa, casi-gratis
├── state/memory.sqlite              ← memoria persistente (se commitea)
├── assets/   (fotos de producto)
├── music/    (música libre de derechos, opcional)
└── output/   (videos generados)
```
