"""Ejecuta toda la suite dentro de Blender:

    blender -b --factory-startup --python tests/run_tests.py

Sale con codigo != 0 si falla alguna prueba o si no se ejecuto ninguna.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py", top_level_dir=str(ROOT / "tests"))
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
