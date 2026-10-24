"""Punto de entrada para Blender del nivel 1 (anatomia sobre la base).

    blender -b --factory-startup --python scripts/generate_anatomy.py -- [--output RUTA] [--height 1.70|170cm|5ft7in] [--no-preview]

Codigos de salida: 0 ok, 2 validacion/generacion fallida, 3 error inesperado.
"""
import argparse
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy_pipeline  # noqa: E402
from anatomical_core.config import ConfigError  # noqa: E402


def main(argv):
    p = argparse.ArgumentParser(prog="generate_anatomy")
    p.add_argument("--output", default=str(ROOT / "output" / "anatomy_level1.blend"))
    p.add_argument("--anatomy-dir", default=None, help="carpeta alternativa con las regiones del nivel 1")
    p.add_argument("--height", default=None, help="altura total: metros (1.70) o con unidades (170cm, 5ft7in)")
    p.add_argument("--no-preview", action="store_true")
    args = p.parse_args(argv)
    try:
        result = anatomy_pipeline.generate(args.output, anatomy_dir=args.anatomy_dir, preview=not args.no_preview, height_m=args.height)
    except (anatomy_pipeline.AnatomyGenerationError, ConfigError) as exc:
        print(f"[FAIL] {exc}")
        for i in getattr(exc, "issues", ()):
            print(f"       {i}")
        return 2
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print("[FAIL] Error inesperado")
        return 3
    print(f"[OK] BLEND={result.blend_path}")
    print(f"[OK] REPORT={result.report_path}")
    return 0


if __name__ == "__main__":
    extra = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    sys.exit(main(extra))
