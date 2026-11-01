"""Vercel entrypoint.

Vercel's Python runtime auto-detects a root ``app.py`` that exposes an ASGI/WSGI
``app`` and routes every request to it. This project keeps its package under
``src/``, so add that directory to the import path before loading the API.

Locally this is equivalent to::

    uvicorn drainage_rec.web_api:app --reload
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from drainage_rec.web_api import app  # noqa: E402,F401  (Vercel loads ``app``)
