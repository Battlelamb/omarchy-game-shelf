"""Resolve standalone runtime from manifest, or central development templates."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'manifest.json'
RUNTIME = (ROOT / json.loads(MANIFEST.read_text())['entryPoints']['overlay']).parent if MANIFEST.is_file() else ROOT / 'templates'
PREFERENCES = RUNTIME / ('preferences.py' if MANIFEST.is_file() else 'Preferences.py')
