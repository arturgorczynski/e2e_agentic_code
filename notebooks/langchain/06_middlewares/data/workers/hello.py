"""A successful worker used by both the local and Docker examples."""
from pathlib import Path
import sys

print("Python:", sys.version.split()[0])
print("Working directory:", Path.cwd())
print("Result:", 6 * 7)
