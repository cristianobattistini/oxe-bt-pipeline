import sys
from pathlib import Path

# aggiunge la root del repo ( due livelli sopra ) al sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
