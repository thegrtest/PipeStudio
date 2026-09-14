"""Rebuild the current body print from the supplied reference's ink shapes."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('extract_reference_print.py')),run_name='__main__')
