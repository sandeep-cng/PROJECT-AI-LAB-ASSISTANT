import os
import sys

# Add project root directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import app

# Export FastAPI instance for Vercel zero-config discovery
__all__ = ["app"]
