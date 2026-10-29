"""Ejecuta las pruebas dentro de Blender:

    blender -b --factory-startup --python tests/run_tests.py                       # suite ACTUAL: el esqueleto oseo `cp.*` (por defecto)
    blender -b --factory-startup --python tests/run_tests.py -- --suite legacy     # pruebas del modelo VIEJO (nivel 1, BM_, ligamentos, musculos...)
    blender -b --factory-startup --python tests/run_tests.py -- --suite all        # todas
    blender -b --factory-startup --python tests/run_tests.py -- --only test_cp_skeleton,test_height   # modulos concretos

La agrupacion esta en `tests/suites.py`. Sale con codigo != 0 si falla alguna prueba o si no se ejecuto ninguna.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import argparse  # noqa: E402

import suites  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--suite", choices=("current", "legacy", "all"), default="current")
ap.add_argument("--only", default="", help="modulos separados por comas (anula --suite)")
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
names = [n.strip() for n in args.only.split(",") if n.strip()] or suites.modules(args.suite)
print(f"[SUITE] {'only' if args.only else args.suite}: {len(names)} modulos: {', '.join(names)}")
suite = unittest.defaultTestLoader.loadTestsFromNames(names)
result = unittest.TextTestRunner(verbosity=2).run(suite)
skipped_bpy = [s for s in result.skipped if "bpy" in s[1]]
if result.testsRun == 0:
    print("[FAIL] No se ejecuto ninguna prueba")
    sys.exit(1)
if skipped_bpy:
    print(f"[FAIL] {len(skipped_bpy)} pruebas de Blender se omitieron: no se esta ejecutando dentro de Blender")
    sys.exit(1)
print(f"[SUMMARY] ejecutadas={result.testsRun} fallos={len(result.failures)} errores={len(result.errors)} omitidas={len(result.skipped)}")
sys.exit(0 if result.wasSuccessful() else 1)
