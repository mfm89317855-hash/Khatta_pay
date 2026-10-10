"""Gradio entry point proxy inside khatatalk package."""

import sys
from pathlib import Path

# Add root directory to path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app import build_app, main

if __name__ == "__main__":
    main()
