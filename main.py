"""
main.py — Punto de entrada. Delega todo a core/orchestrator.py.

Se mantiene este archivo (en vez de borrarlo) por compatibilidad: el
workflow de GitHub Actions y cualquier script existente que llame
`python3 main.py` sigue funcionando exactamente igual.

Uso:
  python3 main.py                 → produce todos los videos del día
  python3 main.py --limite 1      → solo 1 (para probar)
  python3 main.py --categorias 3  → investiga 3 categorías (más volumen)
  python3 main.py --sin-amazon    → forzar Research Agent (Gemini) en vez
                                     de Amazon Agent (scraping real)
"""

from core.orchestrator import main

if __name__ == "__main__":
    main()
