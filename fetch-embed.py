#!/usr/bin/env python3
"""
Fetch-Embed: Main entry point

This is a convenience script to run the CLI without installing the package.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.cli import cli

if __name__ == '__main__':
    cli()
