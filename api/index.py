import os
import sys

# Add project root directory to Python module search path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app

# Export app for Vercel serverless execution
__all__ = ["app"]
