"""Punto de entrada para Blender.

    blender -b --python scripts/generate_skeleton.py -- [--output RUTA] [--height M]
            [--set hueso=fraccion ...] [--no-preview] [--config-dir DIR]

Codigos de salida: 0 ok, 2 validacion/generacion fallida, 3 error inesperado.
"""
import argparse
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import pipeline  # noqa: E402
from anatomical_core.config import ConfigError  # noqa: E402


def main(argv):
    p = argparse.ArgumentParser(prog="generate_skeleton")
    p.add_argument("--output", default=str(ROOT / "output" / "skeleton_core.blend"))
    p.add_argument("--config-dir", default=None)
    p.add_argument("--height", default=None, help="altura total: metros (1.70) o con unidades (170cm, 5ft7in)")
    p.add_argument("--set", action="append", default=[], metavar="HUESO=FRACCION",
                   help="sustituye una longitud (fraccion de la altura), p. ej. thigh=0.25")
    p.add_argument("--pose", action="append", default=[], metavar="ARTICULACION.DOF=GRADOS",
                   help="sustituye un angulo de la pose A, p. ej. shoulder.abduction=35")
    p.add_argument("--neutral", action="store_true", help="no aplica la pose A: deja el esqueleto neutro")
    p.add_argument("--no-preview", action="store_true")
    args = p.parse_args(argv)

    def parse_pairs(items, what):
        out = {}
        for item in items:
            key, sep, val = item.partition("=")
            try:
                if not sep:
                    raise ValueError
                out[key.strip()] = float(val)
            except ValueError:
                raise ConfigError(f"{what} invalido '{item}': usa clave=numero") from None
        return out

    try:
        overrides = parse_pairs(args.set, "--set")
        pose_overrides = parse_pairs(args.pose, "--pose")
        result = pipeline.generate(
            args.output, args.config_dir, args.height, overrides or None, pose_overrides or None,
            neutral_only=args.neutral, preview=not args.no_preview,
        )
    except (pipeline.GenerationError, ConfigError) as exc:
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
