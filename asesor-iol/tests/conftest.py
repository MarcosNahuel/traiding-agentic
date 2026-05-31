import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Evita que un .env del repo raíz contamine los tests.
os.environ.setdefault("IOL_USERNAME", "x")
