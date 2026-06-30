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
repository secret**, agregá estos tres:
- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Listo. El workflow en `.github/workflows/run_agent.yml` ya está programado
para correr todos los días a las 8am hora Panamá. También podés ir a la
pestaña **Actions** del repo y darle "Run workflow" para probarlo ahora.

## 4. Agregar productos nuevos

Editá `products_seed.csv` (una fila por producto, con foto real en
`assets/`) y hacé commit/push. La próxima corrida ya los toma.

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

## Estructura

```
tiktok_agent/
├── .github/workflows/run_agent.yml  ← corre todo gratis en GitHub
├── config.py                        ← tus claves (Gemini, Telegram)
├── products_seed.csv                ← productos (editás a mano)
├── product_research.py
├── script_generator.py              ← Gemini gratis (o Claude si pagás)
├── tts_voice.py
├── video_builder.py                 ← YA PROBADO, funciona
├── telegram_approval.py             ← canal gratis por defecto
├── whatsapp_approval.py             ← alternativa, casi-gratis
├── main.py
├── assets/   (fotos de producto)
├── music/    (música libre de derechos, opcional)
└── output/   (videos generados)
```
