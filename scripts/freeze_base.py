"""Congela la BASE (esqueleto neutro de referencia) en tests/golden/base_skeleton.json. No usa Blender.

La base es el nivel 0: los 20 huesos y 19 articulaciones de config/. Todo nivel posterior (huesos
anatomicos detallados) se construye SOBRE ella sin modificarla; tests/test_base_frozen.py compara
el modelo actual con esta instantanea y falla ante cualquier cambio.

    py scripts\\freeze_base.py            # crea la instantanea; se niega a sobrescribirla
    py scripts\\freeze_base.py --update   # sobrescribe a proposito (cambio DELIBERADO de la base)
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

GOLDEN = ROOT / "tests" / "golden" / "base_skeleton.json"


def snapshot(model) -> dict:
    return {
        "schema": 1,
        "description": "Instantanea de la BASE: esqueleto neutro de referencia (nivel 0). No editar a mano: usar scripts/freeze_base.py --update solo si el cambio de la base es deliberado.",
        "height_m": model.height_m,
        "ankle_height_m": model.ankle_height_m,
        "config_signature": model.config_signature,
        "model_signature": model.signature(),
        "bones": {
            n: {"parent": b.parent, "head": list(b.head), "tail": list(b.tail), "length": b.length,
                "frame": [list(a) for a in b.frame]}
            for n, b in model.bones.items()
        },
        "joints": {
            n: {
                "bone": j.bone, "parent_bone": j.parent_bone, "pivot": list(j.pivot),
                "dofs": [{"name": d.name, "axis": list(d.axis), "axis_local": d.axis_local, "axis_sign": d.axis_sign,
                          "min_deg": d.min_deg, "max_deg": d.max_deg, "positive_motion": d.positive_motion} for d in j.dofs],
            }
            for n, j in model.joints.items()
        },
    }


def main(argv):
    p = argparse.ArgumentParser(prog="freeze_base")
    p.add_argument("--update", action="store_true", help="sobrescribe la instantanea existente")
    args = p.parse_args(argv)
    if GOLDEN.exists() and not args.update:
        print(f"[FAIL] Ya existe {GOLDEN}. Usa --update solo si el cambio de la base es deliberado.")
        return 2
    model = build_model(load_config())
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps(snapshot(model), indent=1), encoding="utf-8")
    print(f"[OK] Base congelada: {len(model.bones)} huesos, {len(model.joints)} articulaciones -> {GOLDEN}")
    print(f"[OK] firma del modelo: {model.signature()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
