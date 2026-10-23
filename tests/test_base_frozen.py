"""La BASE (nivel 0: esqueleto neutro de 20 huesos) debe permanecer identica a su instantanea.

Cualquier nivel anatomico posterior se construye sobre la base sin modificarla. Si el cambio de la
base es deliberado: py scripts\\freeze_base.py --update (y se revisa el diff del golden).
"""
import dataclasses
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import pose  # noqa: E402
from anatomical_core.config import PoseDef, load_config  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

GOLDEN = ROOT / "tests" / "golden" / "base_skeleton.json"
TOL = 1e-9


def _close(a, b):
    return len(a) == len(b) and all(abs(x - y) <= TOL for x, y in zip(a, b))


def diff_against_golden(model, golden) -> list:
    """Lista de diferencias entre el modelo y la instantanea (vacia = base intacta)."""
    out = []
    if set(model.bones) != set(golden["bones"]):
        out.append(f"huesos distintos: +{sorted(set(model.bones) - set(golden['bones']))} -{sorted(set(golden['bones']) - set(model.bones))}")
    for n, g in golden["bones"].items():
        b = model.bones.get(n)
        if b is None:
            continue
        if b.parent != g["parent"]:
            out.append(f"{n}: padre {b.parent!r} != {g['parent']!r}")
        for label, mine, ref in (("head", b.head, g["head"]), ("tail", b.tail, g["tail"])):
            if not _close(mine, ref):
                out.append(f"{n}: {label} difiere")
        if abs(b.length - g["length"]) > TOL:
            out.append(f"{n}: longitud difiere")
        if not all(_close(a, r) for a, r in zip(b.frame, g["frame"])):
            out.append(f"{n}: marco local difiere")
    if set(model.joints) != set(golden["joints"]):
        out.append("articulaciones distintas")
    for n, g in golden["joints"].items():
        j = model.joints.get(n)
        if j is None:
            continue
        if (j.bone, j.parent_bone) != (g["bone"], g["parent_bone"]):
            out.append(f"{n}: hueso/padre difiere")
        if not _close(j.pivot, g["pivot"]):
            out.append(f"{n}: pivote difiere")
        if len(j.dofs) != len(g["dofs"]):
            out.append(f"{n}: numero de dof difiere")
            continue
        for d, gd in zip(j.dofs, g["dofs"]):
            if (d.name, d.axis_local, d.axis_sign, d.min_deg, d.max_deg, d.positive_motion) != (
                    gd["name"], gd["axis_local"], gd["axis_sign"], gd["min_deg"], gd["max_deg"], gd["positive_motion"]):
                out.append(f"{n}.{d.name}: definicion del dof difiere")
            if not _close(d.axis, gd["axis"]):
                out.append(f"{n}.{d.name}: eje difiere")
    if abs(model.ankle_height_m - golden["ankle_height_m"]) > TOL:
        out.append("altura del tobillo difiere")
    return out


class TestBaseIsFrozen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
        cls.model = build_model(load_config())

    def test_golden_describes_the_20_bone_base(self):
        self.assertEqual(len(self.golden["bones"]), 20)
        self.assertEqual(len(self.golden["joints"]), 19)
        self.assertEqual(sum(len(j["dofs"]) for j in self.golden["joints"].values()), 47)

    def test_current_base_is_identical_to_the_snapshot(self):
        self.assertEqual(diff_against_golden(self.model, self.golden), [])
        self.assertEqual(self.model.signature(), self.golden["model_signature"])
        self.assertEqual(self.model.config_signature, self.golden["config_signature"])

    def test_pose_never_changes_the_base(self):
        """Aplicar o cambiar la pose no toca la base (el modelo es de solo lectura para la pose)."""
        for p in (load_config().pose, PoseDef("x", {"shoulder": {"abduction": 90.0}, "hip": {"flexion": 60.0}})):
            pose.apply_pose(self.model, p)
            self.assertEqual(diff_against_golden(self.model, self.golden), [])

    def test_comparison_detects_changes_to_the_base(self):
        """Autocomprobacion: el comparador no es vacuo; detecta longitudes, jerarquia, pivotes y ejes."""
        self.assertTrue(diff_against_golden(build_model(load_config(height_m=1.80)), self.golden))
        self.assertTrue(diff_against_golden(build_model(load_config(length_overrides={"thigh": 0.25})), self.golden))
        b = self.model.bones["thigh.L"]
        moved = dataclasses.replace(self.model, bones={**self.model.bones, "thigh.L": dataclasses.replace(b, parent="spine_lumbar")})
        self.assertTrue(any("padre" in d for d in diff_against_golden(moved, self.golden)))
        j = self.model.joints["knee.L"]
        pivot = dataclasses.replace(j, pivot=(j.pivot[0] + 1e-6, j.pivot[1], j.pivot[2]))
        self.assertTrue(any("pivote" in d for d in diff_against_golden(
            dataclasses.replace(self.model, joints={**self.model.joints, "knee.L": pivot}), self.golden)))
        d0 = j.dofs[0]
        limits = dataclasses.replace(j, dofs=(dataclasses.replace(d0, max_deg=d0.max_deg + 1),) + j.dofs[1:])
        self.assertTrue(any("dof" in d for d in diff_against_golden(
            dataclasses.replace(self.model, joints={**self.model.joints, "knee.L": limits}), self.golden)))
        axis = dataclasses.replace(j, dofs=(dataclasses.replace(d0, axis=(0.0, 1.0, 0.0)),) + j.dofs[1:])
        self.assertTrue(any("eje" in d for d in diff_against_golden(
            dataclasses.replace(self.model, joints={**self.model.joints, "knee.L": axis}), self.golden)))


if __name__ == "__main__":
    unittest.main()
