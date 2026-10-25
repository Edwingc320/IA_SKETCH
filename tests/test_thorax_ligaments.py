"""Ligamentos del torax y del hombro: costovertebrales, costotransversos, esternocostales, interchondrales, esternales, glenohumerales
y esternoclaviculares, todos con sus extremos a menos de 12 mm de su hueso."""
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


class TestThoraxLigaments(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()
        self.lg = {n: x for n, x in self.art.ligaments.items() if x.region == "thorax_ligaments"}
        self.tol = 0.012 * self.base.height_m / 1.75
        self.b = self.anat.bones

    def test_counts_and_validation(self):
        per_side = (12 + 9) + 10 * 3 + 7 * 2 + 3 + 5 + 2  # radiado, costotransversos, esternocostales, interchondrales, glenohumerales, esternoclaviculares
        self.assertEqual(len(self.lg), 2 * per_side + 4)  # + 4 esternales (linea media)
        issues = validation.validate_articulations(self.base, self.anat, self.art)
        self.assertEqual([i for i in issues if i.severity == "error"], [])
        self.assertEqual(validation.validate_anatomy(self.base, self.anat) and [i for i in validation.validate_anatomy(self.base, self.anat) if i.severity == "error"], [])

    def test_every_thoracic_joint_has_ligaments_except_the_scapulothoracic(self):
        lig_joints = {x.joint for x in self.art.ligaments.values()}
        for n, j in self.art.joints.items():
            if j.region != "thorax_shoulder":
                continue
            if n.startswith("scapulothoracic"):
                self.assertNotIn(n, lig_joints)  # se sostiene por musculos y fascia: sin ligamentos
            elif not n.startswith(("intervertebral",)):
                self.assertIn(n, lig_joints, n)

    def test_all_ends_are_on_their_bone_surface(self):
        for n, x in self.lg.items():
            self.assertLess(articulations.bone_distance(x.a, x.from_bone, self.base, self.anat), self.tol, n + ".a")
            self.assertLess(articulations.bone_distance(x.b, x.to_bone, self.base, self.anat), self.tol, n + ".b")

    def test_rib_ligaments(self):
        for s, sx in (("L", 1), ("R", -1)):
            for k in range(1, 13):
                x = self.lg[f"radiate_costovertebral_{k:02d}.{s}"]
                self.assertEqual((x.from_bone, x.to_bone), (f"rib_{k:02d}.{s}", f"T{k}"))
                self.assertLess(length(sub(x.a, self.b[f"rib_{k:02d}.{s}"].head)), 1e-12)  # nace en la cabeza de la costilla
                self.assertLess(sx * x.b[0], sx * x.a[0])  # y va hacia el cuerpo vertebral (medial)
            for k in range(2, 11):
                self.assertEqual(self.lg[f"radiate_costovertebral_upper_{k:02d}.{s}"].to_bone, f"T{k - 1}")  # hemifaceta superior
            for k in range(1, 11):
                self.assertEqual(self.lg[f"superior_costotransverse_{k:02d}.{s}"].to_bone, "C7" if k == 1 else f"T{k - 1}")
                self.assertEqual(self.lg[f"costotransverse_ligament_{k:02d}.{s}"].to_bone, f"T{k}")
                self.assertGreater(self.lg[f"costotransverse_ligament_{k:02d}.{s}"].a[2], 0.1)

    def test_sternocostal_and_interchondral_ligaments_hang_from_the_cartilage(self):
        sternum = self.b["sternum"]
        for s in "LR":
            for k in range(1, 8):
                a, p = (self.lg[f"radiate_sternocostal_{f}_{k:02d}.{s}"] for f in ("anterior", "posterior"))
                for x in (a, p):
                    self.assertLess(length(sub(x.a, self.b[f"rib_{k:02d}.{s}"].cartilage[-1])), 1e-12)  # del extremo del cartilago
                    self.assertEqual((x.from_bone, x.to_bone), (f"rib_{k:02d}.{s}", "sternum"))
                self.assertLess(a.b[1], p.b[1])  # la cara anterior del esternon (-Y) esta delante de la posterior
            for k in (8, 9, 10):
                x = self.lg[f"interchondral_ligament_{k:02d}.{s}"]
                self.assertEqual((x.from_bone, x.to_bone), (f"rib_{k:02d}.{s}", f"rib_{k - 1:02d}.{s}"))
                self.assertGreater(length(sub(x.a, x.b)), 0.002)
        self.assertLess(length(sub(self.lg["manubriosternal_anterior"].a, self.art.joints["manubriosternal"].center)), 0.012)  # junto a su articulacion
        for n in ("manubriosternal_anterior", "manubriosternal_posterior", "xiphisternal_anterior", "xiphisternal_posterior"):
            self.assertEqual((self.lg[n].from_bone, self.lg[n].to_bone), ("sternum", "sternum"))
        self.assertLess(self.lg["manubriosternal_anterior"].a[1], self.lg["manubriosternal_posterior"].a[1])
        self.assertGreater(self.lg["manubriosternal_anterior"].a[2], self.lg["xiphisternal_anterior"].a[2])  # el manubrio esta arriba del xifoides

    def test_glenohumeral_ligaments_form_the_anterior_inferior_hammock(self):
        for s, sx in (("L", 1), ("R", -1)):
            sup, mid, ia, ip, ch = (self.lg[f"{n}.{s}"] for n in ("superior_glenohumeral", "middle_glenohumeral", "inferior_glenohumeral_anterior",
                                                                  "inferior_glenohumeral_posterior", "coracohumeral"))
            for x in (sup, mid, ia, ip, ch):
                self.assertEqual((x.from_bone, x.to_bone, x.joint), (f"scapula.{s}", f"humerus.{s}", f"glenohumeral.{s}"))
            self.assertGreater(sup.a[2], mid.a[2])  # del glenoides superior al inferior
            self.assertGreater(mid.a[2], ia.a[2])
            self.assertLess(ia.a[1], ip.a[1])  # banda anterior delante de la posterior (-Y delante)
            self.assertLess(ia.b[1], ip.b[1])
            self.assertLess(sup.b[1], self.b[f"humerus.{s}"].head[1])  # sobre el tuberculo menor (anterior)
            self.assertLess(length(sub(ch.a, self.b[f"scapula.{s}"].outline[5])), 1e-12)  # el coracohumeral nace en la coracoides
            self.assertGreater(sx * (ch.b[0] - self.b[f"humerus.{s}"].head[0]), 0.005)  # y llega a la cara lateral (tuberculo mayor)
            for x in (sup, mid, ia, ip):  # los glenohumerales llegan al tercio proximal del humero
                self.assertLess(self.b[f"humerus.{s}"].head[2] - x.b[2], 0.04)

    def test_sternoclavicular_ligaments_and_scapula_shape(self):
        for s in "LR":
            a, p = self.lg[f"anterior_sternoclavicular.{s}"], self.lg[f"posterior_sternoclavicular.{s}"]
            self.assertEqual((a.from_bone, a.to_bone), (f"clavicle.{s}", "sternum"))
            self.assertLess(a.a[1], p.a[1])  # anterior delante de posterior
            self.assertLess(a.b[1], p.b[1])
            sc = self.b[f"scapula.{s}"]
            self.assertEqual(len(sc.outline), 6)  # glenoides, acromion, raiz, angulo, glenoides (borde lateral), coracoides
            self.assertLess(length(sub(sc.outline[4], sc.head)), 1e-12)
            self.assertEqual(self.art.attachments[f"coracoid_process.{s}"].point, sc.outline[5])
            for n in ("greater_tubercle", "lesser_tubercle", "deltoid_tuberosity"):
                at = self.art.attachments[f"{n}.{s}"]
                self.assertLess(articulations.bone_distance(at.point, at.bone, self.base, self.anat), self.tol, n)

    def test_symmetry_and_scale(self):
        for n, x in self.lg.items():
            if n.endswith(".L"):
                r = self.lg[n[:-2] + ".R"]
                for p, q in ((x.a, r.a), (x.b, r.b)):
                    self.assertLess(length(sub(mirror_point(p), q)), 1e-12, n)
        base2, anat2, art2 = build_all(1.9)
        k = 1.9 / self.base.height_m
        for n, x in self.lg.items():
            y = art2.ligaments[n]
            self.assertLess(length(sub(tuple(k * c for c in x.a), y.a)), 1e-9, n)
            self.assertLess(articulations.bone_distance(y.b, y.to_bone, base2, anat2), 0.012 * 1.9 / 1.75, n)


if __name__ == "__main__":
    unittest.main()
