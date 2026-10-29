"""Agrupacion de las pruebas del proyecto.

* CURRENT: el esqueleto oseo ACTUAL (linea `cp.*`: pelvis, femures, columna, craneo y mandibula, y las etapas siguientes de la reconstruccion central). Es la suite por
  defecto de `tests/run_tests.py`.
* LEGACY: las pruebas del modelo VIEJO (nivel 1 de lineas y contornos, `BM_*`, articulaciones, ligamentos, musculos, tendones, rig, pose y base congelada). Siguen
  intactas y se ejecutan con `--suite legacy` (o `--suite all`); no se eliminan ni se relajan.

Una prueba nueva del esqueleto actual se anade a CURRENT; el resto se descubre solo como LEGACY."""
from pathlib import Path

CURRENT = ("test_cp_skeleton",)


def all_modules(tests_dir: Path | None = None) -> list:
    d = tests_dir or Path(__file__).resolve().parent
    return sorted(p.stem for p in d.glob("test_*.py"))


def modules(suite: str, tests_dir: Path | None = None) -> list:
    everything = all_modules(tests_dir)
    if suite == "current":
        return [m for m in everything if m in CURRENT]
    if suite == "legacy":
        return [m for m in everything if m not in CURRENT]
    if suite == "all":
        return everything
    raise ValueError(f"Suite desconocida '{suite}' (current, legacy o all)")
