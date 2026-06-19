"""Root entry point for Streamlit Community Cloud.

Streamlit's "Main file path" can stay as `app.py`. This shim puts the repo root
on sys.path and runs the real dashboard in dashboard/app.py. The whole project
(requirements.txt, src/, config/, scripts/, dashboard/) must be committed to the
repo for this to work — see DEPLOY.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dashboard.app import main

main()
