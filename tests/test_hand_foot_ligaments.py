"""Cobertura de ligamentos en TODO el modelo oseo y los ligamentos de mano y pie anadidos al final (carpometacarpianos, transversos
profundos, cuneonavicular, intercuneiformes, cuneocuboideo, tarsometatarsianos y dedos del pie)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations, validation  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

NO_LIGAMENTS = {"scapulothoracic.L": "se sostiene por musculos y fascia, no por ligamentos", "scapulothoracic.R": "idem"}


def build_all(height=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    return base, anat, articulations.build_articulations(base, anat, articulations.load_articulation_data())


class TestEveryJointHasLigaments(unittest.TestCase):
    def test_no_joint_is_left_without_ligaments_except_the_documented_one(self):
        _, _, art = build_all()
        covered = {x.joint for x in art.ligaments.values()} | {n for n, j in art.joints.items() if j.ligaments}
        missing = sorted(n for n in art.joints if n not in covered)
        self.assertEqual(missing, sorted(NO_LIGAMENTS))
        for n, why in NO_LIGAMENTS.items():
            self.assertTrue(why)

    def test_ligament_and_joint_references_are_consistent(self):
        _, _, art = build_all()
        for n, x in art.ligaments.items():
            self.assertTrue(x.joint is None or x.joint in art.joints, n)
        for n, j in art.joints.items():
            for l in j.ligaments:
                self.assertIn(l, art.ligaments, f"{n} -> {l}")

    def test_every_ligament_end_is_on_its_bone_or_in_the_known_debt(self):
        """Los extremos de los ligamentos nuevos estan a menos de 12 mm; los antiguos fuera de 12 mm estan fijados en test_anchor_debt."""
        from test_anchor_debt import KNOWN_DEBT
        base, anat, art = build_all()
        tol = 0.012 * base.height_m / 1.75
        debt = {(n, b) for k, n, b in KNOWN_DEBT if k == "LIG"}
        for n, x in art.ligaments.items():
            if n.endswith(".R"):
                continue
            for end, bone, p in (("a", x.from_bone, x.a), ("b", x.to_bone, x.b)):
                if articulations.bone_distance(p, bone, base, anat, art.surfaces) > tol:  # con la superficie de la cabeza y el cuello del femur
                    self.assertIn((f"{n}.{end}", bone), debt, n)


class TestHandFootLigaments(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()
        self.lg = {n: x for n, x in self.art.ligaments.items() if x.region == "hand_foot_ligaments"}
        self.tol = 0.012 * self.base.height_m / 1.75

    def test_counts_and_validation(self):
        per_side = 4 * 2 + 3 + 3 * 3 + 6 + 5 * 2 + 4 + 2 * (5 + 1 + 4 + 4)  # CMC, DTM mano, 3 articulaciones del tarso, cuneonavicular, TMT, DTM pie, dedos
        self.assertEqual(len(self.lg), 2 * per_side)
        self.assertEqual(per_side, 68)
        new = {n: j for n, j in self.art.joints.items() if j.region == "hand_foot_ligaments"}
        self.assertEqual(sorted(new), sorted(f"{n}.{s}" for n in ("intercuneiform_1_2", "intercuneiform_2_3", "cuneocuboid") for s in "LR"))
        self.assertEqual([i for i in validation.validate_articulations(self.base, self.anat, self.art) if i.severity == "error"], [])

    def test_every_end_is_on_its_bone_surface(self):
        for n, x in self.lg.items():
            self.assertLess(articulations.bone_distance(x.a, x.from_bone, self.base, self.anat), self.tol, n + ".a")
            self.assertLess(articulations.bone_distance(x.b, x.to_bone, self.base, self.anat), self.tol, n + ".b")
        for n, j in self.art.joints.items():
            if j.region == "hand_foot_ligaments":
                for bone in j.bones:
                    self.assertLess(articulations.bone_distance(j.center, bone, self.base, self.anat), self.tol, n)

    def test_hand_ligaments(self):
        for s in "LR":
            for k, carpal in ((2, "trapezoid"), (3, "capitate"), (4, "hamate"), (5, "hamate")):
                d, p = self.lg[f"dorsal_carpometacarpal_{k}.{s}"], self.lg[f"palmar_carpometacarpal_{k}.{s}"]
                for x in (d, p):
                    self.assertEqual((x.from_bone, x.to_bone, x.joint), (f"{carpal}.{s}", f"metacarpal_{k}.{s}", f"carpometacarpal_{k}.{s}"))
                self.assertGreater(d.a[1], p.a[1])  # dorsal = detras (+Y), palmar = delante (-Y): la palma mira a -Y
            for k in (2, 3, 4):
                x = self.lg[f"deep_transverse_metacarpal_{k}_{k + 1}.{s}"]
                self.assertEqual((x.from_bone, x.to_bone), (f"metacarpal_{k}.{s}", f"metacarpal_{k + 1}.{s}"))
                self.assertTrue(0.010 < length(sub(x.a, x.b)) < 0.035)  # une cabezas vecinas

    def test_foot_ligaments_and_new_tarsal_joints(self):
        for s in "LR":
            for jn in ("intercuneiform_1_2", "intercuneiform_2_3", "cuneocuboid"):
                d, i, p = (self.lg[f"{k}_{jn}.{s}"] for k in ("dorsal", "interosseous", "plantar"))
                self.assertGreater(d.a[2], i.a[2])  # dorsal arriba, interoseo en medio, plantar abajo
                self.assertGreater(i.a[2], p.a[2])
                self.assertEqual(d.joint, f"{jn}.{s}")
            for cn in ("medial", "intermediate", "lateral"):
                x = self.lg[f"dorsal_cuneonavicular_{cn}.{s}"]
                self.assertEqual((x.from_bone, x.to_bone), (f"navicular.{s}", f"{cn}_cuneiform.{s}"))
            for k, tarsal in ((1, "medial_cuneiform"), (2, "intermediate_cuneiform"), (3, "lateral_cuneiform"), (4, "cuboid"), (5, "cuboid")):
                d = self.lg[f"dorsal_tarsometatarsal_{k}.{s}"]
                self.assertEqual((d.from_bone, d.to_bone), (f"{tarsal}.{s}", f"metatarsal_{k}.{s}"))
                self.assertGreater(d.a[2], self.lg[f"plantar_tarsometatarsal_{k}.{s}"].a[2])
            for k in (1, 2, 3, 4):
                x = self.lg[f"deep_transverse_metatarsal_{k}_{k + 1}.{s}"]
                self.assertEqual((x.from_bone, x.to_bone), (f"metatarsal_{k}.{s}", f"metatarsal_{k + 1}.{s}"))

    def test_toe_collaterals_and_plantar_plates_flag_their_weak_source(self):
        tags = [f"mtp_{k}" for k in range(1, 6)] + ["ip_1"] + [f"{p}_{k}" for k in range(2, 6) for p in ("pip", "dip")]
        for s in "LR":
            for tag in tags:
                c, p = self.lg[f"collateral_{tag}_toe.{s}"], self.lg[f"plantar_plate_{tag}_toe.{s}"]
                self.assertIn("verificar", c.notes.lower(), c.name)  # sin fuente propia en el pie: lo dicen
                self.assertIn("verificar", p.notes.lower(), p.name)
                self.assertGreater(c.a[2], p.a[2] - 0.006)  # la placa plantar queda por debajo del colateral
        self.assertEqual(len([n for n in self.lg if n.startswith("collateral_") and n.endswith(".L")]), len(tags))

    def test_symmetry_and_scale(self):
        for n, x in self.lg.items():
            if n.endswith(".L"):
                r = self.lg[n[:-2] + ".R"]
                for p, q in ((x.a, r.a), (x.b, r.b)):
                    self.assertLess(length(sub(mirror_point(p), q)), 1e-12, n)
        base2, anat2, art2 = build_all(1.85)
        k = 1.85 / self.base.height_m
        for n, x in self.lg.items():
            y = art2.ligaments[n]
            self.assertLess(length(sub(tuple(k * c for c in x.a), y.a)), 1e-9, n)
            self.assertLess(articulations.bone_distance(y.b, y.to_bone, base2, anat2), 0.012 * 1.85 / 1.75, n)


if __name__ == "__main__":
    unittest.main()
