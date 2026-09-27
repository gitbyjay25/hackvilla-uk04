"""Test configuration"""
import sys
from pathlib import Path

# Add nexarch package to path
sdk_path = Path(__file__).parent.parent
sys.path.insert(0, str(sdk_path))
