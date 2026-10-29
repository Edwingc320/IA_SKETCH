"""Utilidades de prueba compartidas por la suite del esqueleto oseo actual (sin depender de las pruebas del modelo viejo)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402


def build_reference(height=None):
    """(base, anatomia de nivel 1, hitos y articulaciones) a la altura `height`: los 69 hitos de pelvis, femur, craneo y mandibula contra los que se valida `cp.*`."""
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    return base, anat, articulations.build_articulations(base, anat, articulations.load_articulation_data())
