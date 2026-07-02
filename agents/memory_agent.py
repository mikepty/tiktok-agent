"""
agents/memory_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Memoria persistente del agente. Como GitHub Actions no conserva estado
entre corridas, esta memoria vive en un archivo SQLite dentro del repo
(state/memory.sqlite) que el workflow debe commitear al final de cada
ejecución (ver .github/workflows/run_agent.yml).

Responsabilidades:
  - Evitar publicar el mismo producto (ASIN o nombre) dos veces dentro
    de la ventana de cooldown (config.MEMORIA_DIAS_COOLDOWN).
  - Registrar qué tipos de video (review, top5, tutorial...) se usaron
    recientemente, para que el SEO/Trend Agent rote formatos.
  - Registrar hashtags usados, para detectar cuáles se repiten más
    (proxy simple de "qué funciona" mientras no haya Analytics Agent).
  - Registrar errores por contexto para diagnóstico histórico.
"""

import sqlite3
import datetime
import os
from contextlib import contextmanager

from config import MEMORY_DB, STATE_DIR, MEMORIA_DIAS_COOLDOWN

SCHEMA = """
CREATE TABLE IF NOT EXISTS productos_publicados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asin TEXT,
    nombre TEXT NOT NULL,
    categoria TEXT,
    tipo_video TEXT,
    video_path TEXT,
    fecha TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hashtags_usados (
    hashtag TEXT PRIMARY KEY,
    veces INTEGER NOT NULL DEFAULT 0,
    ultima_fecha TEXT
);

CREATE TABLE IF NOT EXISTS errores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contexto TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    fecha TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_productos_asin ON productos_publicados(asin);
CREATE INDEX IF NOT EXISTS idx_productos_nombre ON productos_publicados(nombre);
"""


@contextmanager
def _conexion():
    os.makedirs(STATE_DIR, exist_ok=True)
    conn = sqlite3.connect(MEMORY_DB)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Crea las tablas si no existen. Llamar al arrancar el pipeline."""
    with _conexion() as conn:
        conn.executescript(SCHEMA)


def _normalizar(texto: str) -> str:
    return (texto or "").strip().lower()


def ya_publicado(asin: str = "", nombre: str = "",
                  dias_cooldown: int = MEMORIA_DIAS_COOLDOWN) -> bool:
    """
    True si este producto (por ASIN o por nombre normalizado) ya se
    publicó dentro de la ventana de cooldown. Evita contenido repetido.
    """
    limite = (datetime.datetime.now() -
              datetime.timedelta(days=dias_cooldown)).isoformat()

    with _conexion() as conn:
        cur = conn.cursor()
        if asin:
            cur.execute(
                "SELECT 1 FROM productos_publicados "
                "WHERE asin = ? AND fecha >= ? LIMIT 1",
                (asin, limite),
            )
            if cur.fetchone():
                return True
        if nombre:
            cur.execute(
                "SELECT 1 FROM productos_publicados "
                "WHERE lower(nombre) = ? AND fecha >= ? LIMIT 1",
                (_normalizar(nombre), limite),
            )
            if cur.fetchone():
                return True
    return False


def registrar_publicacion(producto: dict, tipo_video: str = "",
                           video_path: str = ""):
    with _conexion() as conn:
        conn.execute(
            "INSERT INTO productos_publicados "
            "(asin, nombre, categoria, tipo_video, video_path, fecha) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                producto.get("asin", ""),
                producto.get("nombre", ""),
                producto.get("categoria", ""),
                tipo_video,
                video_path,
                datetime.datetime.now().isoformat(),
            ),
        )


def registrar_hashtags(hashtags: list):
    hoy = datetime.datetime.now().isoformat()
    with _conexion() as conn:
        for h in hashtags:
            h = h.strip()
            if not h:
                continue
            conn.execute(
                "INSERT INTO hashtags_usados (hashtag, veces, ultima_fecha) "
                "VALUES (?, 1, ?) "
                "ON CONFLICT(hashtag) DO UPDATE SET "
                "veces = veces + 1, ultima_fecha = excluded.ultima_fecha",
                (h, hoy),
            )


def hashtags_top(n: int = 10) -> list:
    """Hashtags más usados históricamente (proxy simple de qué funciona)."""
    with _conexion() as conn:
        cur = conn.execute(
            "SELECT hashtag FROM hashtags_usados ORDER BY veces DESC LIMIT ?",
            (n,),
        )
        return [r[0] for r in cur.fetchall()]


def ultimos_tipos_video(n: int = 5) -> list:
    """Últimos N tipos de video usados, para que el SEO Agent rote formato."""
    with _conexion() as conn:
        cur = conn.execute(
            "SELECT tipo_video FROM productos_publicados "
            "WHERE tipo_video != '' ORDER BY fecha DESC LIMIT ?",
            (n,),
        )
        return [r[0] for r in cur.fetchall()]


def registrar_error(contexto: str, mensaje: str):
    with _conexion() as conn:
        conn.execute(
            "INSERT INTO errores (contexto, mensaje, fecha) VALUES (?, ?, ?)",
            (contexto, str(mensaje)[:2000], datetime.datetime.now().isoformat()),
        )


def resumen() -> dict:
    """Pequeño resumen para logging/debug del estado de la memoria."""
    with _conexion() as conn:
        total_prod = conn.execute(
            "SELECT COUNT(*) FROM productos_publicados").fetchone()[0]
        total_err = conn.execute(
            "SELECT COUNT(*) FROM errores").fetchone()[0]
    return {"productos_publicados": total_prod, "errores_registrados": total_err}


if __name__ == "__main__":
    init_db()
    print("Memoria inicializada en:", MEMORY_DB)
    print(resumen())
