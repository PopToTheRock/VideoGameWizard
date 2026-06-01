import sys
from pathlib import Path

# Make server.py / chunker.py / config.py importable as top-level modules
# (they live in the rag/ directory, one level up from this tests/ package).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
