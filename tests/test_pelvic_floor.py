"""Ligamentos del suelo pelvico: sinfisis del pubis, sacrococcigeos y sacroiliacos."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations, validation  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402


def build_all(height=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    return base, anat, articulations.build_articulations(base, anat, articulations.load_articulation_data())


class TestPelvicFloorLigaments(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()
        self.lg = {n: x for n, x in self.art.ligaments.items() if x.region == "pelvic_floor"}
        self.tol = 0.012 * self.base.height_m / 1.75

    def test_counts_validation_and_joint_coverage(self):
        self.assertEqual(sorted(self.lg), sorted(["superior_pubic", "arcuate_pubic", "anterior_sacrococcygeal", "posterior_sacrococcygeal"]
                                                 + [f"{n}.{s}" for n in ("lateral_sacrococcygeal", "anterior_sacroiliac", "interosseous_sacroiliac", "posterior_sacroiliac") for s in "LR"]))
        self.assertEqual([i for i in validation.validate_articulations(self.base, self.anat, self.art) if i.severity == "error"], [])
        covered = {x.joint for x in self.art.ligaments.values()}
        for j in ("pubic_symphysis", "sacrococcygeal", "sacroiliac.L", "sacroiliac.R"):
            self.assertIn(j, covered)

    def test_every_end_is_on_its_bone_surface(self):
        for n, x in self.lg.items():
            self.assertLess(articulations.bone_distance(x.a, x.from_bone, self.base, self.anat), self.tol, n + ".a")
            self.assertLess(articulations.bone_distance(x.b, x.to_bone, self.base, self.anat), self.tol, n + ".b")

    def test_pubic_ligaments_cross_the_midline_above_and_below_the_disc(self):
        sup, arc = self.lg["superior_pubic"], self.lg["arcuate_pubic"]
        for x in (sup, arc):
            self.assertEqual((x.from_bone, x.to_bone), ("pubis.L", "pubis.R"))
            self.assertGreater(x.a[0], 0)  # de un pubis (lado izquierdo, +X)...
            self.assertLess(x.b[0], 0)  # ...al otro, cruzando la linea media
            self.assertAlmostEqual(x.a[0], -x.b[0], places=12)
        self.assertGreater(sup.a[2], self.art.joints["pubic_symphysis"].center[2] - 0.05)
        self.assertGreater(sup.a[2], arc.a[2])  # el superior por encima del arqueado
        self.assertAlmostEqual(self.anat.bones["pubis.L"].tail[0], 0.0, places=12)

    def test_sacrococcygeal_ligaments(self):
        ant, post, lat = (self.lg[n] for n in ("anterior_sacrococcygeal", "posterior_sacrococcygeal", "lateral_sacrococcygeal.L"))
        for x in (ant, post, lat):
            self.assertEqual((x.from_bone, x.to_bone, x.joint), ("sacrum", "coccyx", "sacrococcygeal"))
            self.assertGreater(x.a[2], x.b[2])  # del sacro (arriba) al coxis (abajo)
        self.assertLess(ant.a[1], post.a[1])  # anterior delante de posterior (-Y delante)
        self.assertGreater(lat.b[0], 0.004)  # lateral del lado izquierdo
        self.assertLess(self.lg["lateral_sacrococcygeal.R"].b[0], -0.004)

    def test_sacroiliac_ligaments_span_the_closed_joint(self):
        for s in "LR":
            ant, itr, post = (self.lg[f"{n}_sacroiliac.{s}"] for n in ("anterior", "interosseous", "posterior"))
            for x in (ant, itr, post):
                self.assertEqual((x.from_bone, x.to_bone, x.joint), ("sacrum", f"ilium.{s}", f"sacroiliac.{s}"))
            self.assertLess(ant.a[1], post.a[1])  # anterior delante de posterior
            self.assertLess(length(sub(itr.a, itr.b)), length(sub(post.a, post.b)))  # el interoseo es corto; el posterior, largo
            self.assertLess(length(sub(post.b, self.anat.bones[f"ilium.{s}"].outline[1])), 1e-12)  # el posterior llega a la espina iliaca posterior

    def test_symmetry_and_scale(self):
        for n, x in self.lg.items():
            if n.endswith(".L"):
                r = self.lg[n[:-2] + ".R"]
                for p, q in ((x.a, r.a), (x.b, r.b)):
                    self.assertLess(length(sub(mirror_point(p), q)), 1e-12, n)
        base2, anat2, art2 = build_all(1.6)
        k = 1.6 / self.base.height_m
        for n, x in self.lg.items():
            y = art2.ligaments[n]
            self.assertLess(length(sub(tuple(k * c for c in x.b), y.b)), 1e-9, n)
            self.assertLess(articulations.bone_distance(y.a, y.from_bone, base2, anat2), 0.012 * 1.6 / 1.75, n)


if __name__ == "__main__":
    unittest.main()
