"""
core/llm_router.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Punto único de acceso a cualquier LLM. Todos los agentes (script,
seo, amazon-completado, etc.) deben llamar SOLO a `generar_texto()`
de este módulo — nunca importar `google.genai` o `anthropic`
directamente — así cambiar de proveedor es editar UNA variable en
config.py (o el env var LLM_PROVIDER) sin tocar ningún agente.

Proveedores soportados:
  - gemini      (gratis, recomendado por defecto)
  - claude      (Anthropic, de pago)
  - openai      (de pago)
  - openrouter  (marketplace de modelos, algunos gratis)
  - ollama      (modelos locales, gratis, requiere Ollama corriendo;
                 no viable dentro de GitHub Actions por falta de
                 recursos/tiempo de descarga del modelo, pero sí para
                 correr el pipeline localmente)
"""

import json
import re
from config import (
    LLM_PROVIDER, GEMINI_API_KEY, GEMINI_MODEL,
    ANTHROPIC_API_KEY, CLAUDE_MODEL,
)

import os
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")


def limpiar_json(texto: str):
    """Extrae y parsea JSON de una respuesta de LLM que puede venir
    con backticks o texto alrededor."""
    texto = re.sub(r"```json|```", "", texto).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r"[\{\[][\s\S]*[\}\]]", texto)
        if m:
            return json.loads(m.group())
        raise RuntimeError(f"Respuesta no es JSON válido:\n{texto[:500]}")


def _gemini(system: str, user: str, temperature: float, con_busqueda: bool) -> str:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=GEMINI_API_KEY)
    config_kwargs = {"system_instruction": system, "temperature": temperature}
    if con_busqueda:
        config_kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    response = client.models.generate_content(
        model=GEMINI_MODEL, contents=user,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    return response.text


def _claude(system: str, user: str, temperature: float) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=CLAUDE_MODEL, max_tokens=1600, temperature=temperature,
        system=system, messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def _openai(system: str, user: str, temperature: float) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=OPENAI_MODEL, temperature=temperature,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )
    return response.choices[0].message.content


def _openrouter(system: str, user: str, temperature: float) -> str:
    import requests
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json={
            "model": OPENROUTER_MODEL, "temperature": temperature,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _ollama(system: str, user: str, temperature: float) -> str:
    import requests
    resp = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": OLLAMA_MODEL, "stream": False,
            "options": {"temperature": temperature},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def generar_texto(system: str, user: str, temperature: float = 0.7,
                   con_busqueda: bool = False, provider: str = None) -> str:
    """
    Genera texto con el proveedor configurado en config.LLM_PROVIDER
    (o el que se pase explícitamente en `provider`).

    con_busqueda: solo tiene efecto con Gemini (Google Search grounding),
                  útil para el Research Agent. Otros proveedores lo ignoran.
    """
    proveedor = provider or LLM_PROVIDER
    if proveedor == "gemini":
        return _gemini(system, user, temperature, con_busqueda)
    elif proveedor == "claude":
        return _claude(system, user, temperature)
    elif proveedor == "openai":
        return _openai(system, user, temperature)
    elif proveedor == "openrouter":
        return _openrouter(system, user, temperature)
    elif proveedor == "ollama":
        return _ollama(system, user, temperature)
    raise ValueError(f"LLM_PROVIDER desconocido: {proveedor}")


def generar_json(system: str, user: str, temperature: float = 0.7,
                  con_busqueda: bool = False, provider: str = None) -> dict:
    """Igual que generar_texto pero parsea la respuesta como JSON."""
    texto = generar_texto(system, user, temperature, con_busqueda, provider)
    return limpiar_json(texto)
