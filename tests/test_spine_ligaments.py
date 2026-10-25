"""Ligamentos de toda la columna y articulaciones cigapofisarias: cada nivel C2/C3 ... L5/S1 con su juego completo, sobre el hueso."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations, validation  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

LEVELS = [f"C{k}" for k in range(2, 8)] + [f"T{k}" for k in range(1, 13)] + [f"L{k}" for k in range(1, 6)] + ["sacrum"]
PAIRS = list(zip(LEVELS, LEVELS[1:]))
CENTRAL = ("anterior_longitudinal", "posterior_longitudinal", "flavum", "interspinous")


def build_all(height=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    return base, anat, articulations.build_articulations(base, anat, articulations.load_articulation_data())


class TestSpineLigaments(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()
        self.lg = {n: x for n, x in self.art.ligaments.items() if x.region == "spine"}
        self.tol = 0.012 * self.base.height_m / 1.75

    def test_counts_and_validation(self):
        self.assertEqual(len(PAIRS), 23)
        self.assertEqual(len(self.lg), 23 * (4 + 2) + 1)  # 4 centrales + intertransverso por lado, y el supraespinoso
        self.assertEqual(len([j for j in self.art.joints.values() if j.region == "spine"]), 23 * 2)
        issues = validation.validate_articulations(self.base, self.anat, self.art)
        self.assertEqual([i for i in issues if i.severity == "error"], [])

    def test_every_level_has_the_complete_set_on_its_joint(self):
        for up, lo in PAIRS:
            joint = "lumbosacral_L5_S1" if lo == "sacrum" else f"intervertebral_{up}_{lo}"
            self.assertIn(joint, self.art.joints)
            for kind in CENTRAL:
                x = self.lg[f"{kind}_{up}_{lo}"]
                self.assertEqual((x.from_bone, x.to_bone, x.joint), (up, lo, joint), kind)
            for s in "LR":
                self.assertEqual(self.lg[f"intertransverse_{up}_{lo}.{s}"].joint, joint)

    def test_every_end_is_on_its_vertebra_and_the_layout_front_to_back_is_right(self):
        for up, lo in PAIRS:
            all_, pll, fl, isp = (self.lg[f"{k}_{up}_{lo}"] for k in CENTRAL)
            for x in (all_, pll, fl, isp, self.lg[f"intertransverse_{up}_{lo}.L"], self.lg[f"intertransverse_{up}_{lo}.R"]):
                self.assertLess(articulations.bone_distance(x.a, x.from_bone, self.base, self.anat), self.tol, x.name)
                self.assertLess(articulations.bone_distance(x.b, x.to_bone, self.base, self.anat), self.tol, x.name)
                self.assertTrue(0.005 < length(sub(x.a, x.b)) < 0.06, (x.name, length(sub(x.a, x.b))))  # abarca un nivel
            # desplazamiento en Y respecto al eje del hueso a la misma altura (+Y atras): longitudinal anterior < eje < longitudinal posterior < amarillo < interespinoso
            def off(x, bone, point):
                b = self.anat.bones.get(bone) or self.base.bones[bone]
                t = (point[2] - b.head[2]) / (b.tail[2] - b.head[2])
                return point[1] - (b.head[1] + t * (b.tail[1] - b.head[1]))

            o_all, o_pll, o_fl, o_isp = (off(x, up, x.a) for x in (all_, pll, fl, isp))
            self.assertLess(o_all, -0.009)
            self.assertTrue(0 < o_pll < o_fl < o_isp, (up, o_pll, o_fl, o_isp))
            self.assertGreater(self.lg[f"intertransverse_{up}_{lo}.L"].a[0], 0.005)  # lateral
            self.assertLess(self.lg[f"intertransverse_{up}_{lo}.R"].a[0], -0.005)

    def test_ligaments_run_between_adjacent_vertebrae_from_the_upper_to_the_lower_one(self):
        for up, lo in PAIRS:
            for kind in CENTRAL:
                x = self.lg[f"{kind}_{up}_{lo}"]
                self.assertGreater(x.a[2], x.b[2], x.name)  # la vertebra de arriba esta mas alta

    def test_supraspinous_runs_the_whole_spine_behind_the_bodies(self):
        x = self.lg["supraspinous"]
        self.assertEqual((x.from_bone, x.to_bone), ("C7", "sacrum"))
        self.assertGreater(length(sub(x.a, x.b)), 0.3)
        self.assertGreater(x.a[1], self.anat.bones["C7"].head[1])  # por detras del cuerpo de C7
        self.assertIn("verificar", x.notes.lower())

    def test_facet_joints_are_lateral_and_posterior_to_the_bodies(self):
        for up, lo in PAIRS:
            for s, sx in (("L", 1), ("R", -1)):
                j = self.art.joints[f"zygapophyseal_{up}_{lo}.{s}"]
                self.assertEqual((j.bones, j.carrier), ((up, lo), lo))
                self.assertGreater(sx * j.center[0], 0.01)
                self.assertGreater(j.center[1], self.anat.bones[up].head[1] if up in self.anat.bones else 0)  # por detras del eje
                self.assertIsNone(j.dofs[0].total_deg)  # sin cifra: no se inventa

    def test_symmetry_and_scale(self):
        for n, x in self.lg.items():
            if n.endswith(".L"):
                r = self.lg[n[:-2] + ".R"]
                for p, q in ((x.a, r.a), (x.b, r.b)):
                    self.assertLess(length(sub(mirror_point(p), q)), 1e-12, n)
        base2, anat2, art2 = build_all(1.5)
        k = 1.5 / self.base.height_m
        for n, x in self.lg.items():
            y = art2.ligaments[n]
            for p, q in ((x.a, y.a), (x.b, y.b)):
                self.assertLess(length(sub(tuple(k * c for c in p), q)), 1e-9, n)
            self.assertLess(articulations.bone_distance(y.a, y.from_bone, base2, anat2), 0.012 * 1.5 / 1.75, n)


if __name__ == "__main__":
    unittest.main()
