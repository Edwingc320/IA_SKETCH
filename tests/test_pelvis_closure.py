"""Pelvis posterior y region glutea (modelo oseo): sacroiliaca sin hueco, ligamentos sacrociaticos cerrando el piso posterior y
todo hito o extremo de ligamento sobre la superficie de su hueso (< 12 mm)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations  # noqa: E402
from anatomical_core.anatomy import point_segment_distance  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.geometry import length, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

TOL_M = 0.012  # a 1.75 m; escala con la altura
NOT_ON_BONE = {"body_center_of_mass", "head_center_of_gravity"}  # puntos calculados, no puntos del hueso
PELVIC_BONES = ("sacrum", "coccyx", "ilium", "ischium", "pubis", "femur")


def build_all(height=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    return base, anat, articulations.build_articulations(base, anat, articulations.load_articulation_data())


class TestPelvicClosure(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()
        self.b = self.anat.bones
        self.tol = TOL_M * self.base.height_m / 1.75

    def on_surface(self, point, bone):
        return articulations.bone_distance(point, bone, self.base, self.anat)

    def test_sacroiliac_has_no_gap(self):
        """El borde de la cara auricular del ilion (cabeza -> ultimo punto del contorno) esta sobre el borde lateral del sacro."""
        sac = self.b["sacrum"]
        for s, sx in (("L", 1), ("R", -1)):
            ilium = self.b[f"ilium.{s}"]
            border = (sac.outline[0], sac.outline[1]) if s == "L" else (sac.outline[2], sac.outline[1])
            for end in (ilium.head, ilium.outline[-1]):
                self.assertLess(point_segment_distance(end, *border), 1e-9, f"ilium.{s}")
            self.assertGreater(length(sub(ilium.head, ilium.outline[-1])), 0.03)  # la cara auricular no es un punto: ~5 cm
            for name, bone in ((f"iliac_auricular_surface.{s}", f"ilium.{s}"), (f"sacral_auricular_surface.{s}", "sacrum")):
                self.assertEqual(self.art.attachments[name].bone, bone)
            self.assertLess(length(sub(self.art.attachments[f"iliac_auricular_surface.{s}"].point,
                                       self.art.attachments[f"sacral_auricular_surface.{s}"].point)), 1e-12)  # el mismo punto: sin separacion
            self.assertGreater(self.art.attachments[f"iliac_auricular_surface.{s}"].point[0] * sx, 0)
            self.assertLess(self.on_surface(self.art.joints[f"sacroiliac.{s}"].center, f"ilium.{s}"), 1e-9)
            self.assertLess(self.on_surface(self.art.joints[f"sacroiliac.{s}"].center, "sacrum"), 1e-9)

    def test_sacrotuberous_and_sacrospinous_close_the_posterior_floor(self):
        sac, lg, at = self.b["sacrum"], self.art.ligaments, self.art.attachments
        for s in "LR":
            border = (sac.outline[0], sac.outline[1]) if s == "L" else (sac.outline[2], sac.outline[1])
            tub, spi = lg[f"sacrotuberous.{s}"], lg[f"sacrospinous.{s}"]
            for lig, far in ((tub, self.b[f"ischium.{s}"].tail), (spi, at[f"ischial_spine.{s}"].point)):
                self.assertLess(point_segment_distance(lig.a, *border), 1e-9, lig.name)  # nace en el borde lateral del sacro
                self.assertEqual((lig.from_bone, lig.to_bone), ("sacrum", f"ischium.{s}"))
                self.assertLess(length(sub(lig.b, far)), 1e-12, lig.name)  # y llega a la tuberosidad / la espina isquiatica
            self.assertLess(length(sub(tub.b, at[f"ischial_tuberosity.{s}"].point)), 1e-12)
            # el sacrotuberoso baja desde mas arriba que el sacroespinoso y llega mas abajo (tuberosidad por debajo de la espina)
            self.assertGreater(tub.a[2], spi.a[2])
            self.assertLess(tub.b[2], spi.b[2])

    def test_every_pelvic_anchor_is_on_its_bone_surface(self):
        far = []
        for store, pts in ((self.art.ligaments, lambda x: [(x.from_bone, x.a), (x.to_bone, x.b)]),
                           (self.art.attachments, lambda x: [(x.bone, x.point)])):
            for n, x in store.items():
                if x.region not in ("lumbar_pelvis", "leg_foot") or n in NOT_ON_BONE:
                    continue
                if store is self.art.ligaments and x.from_bone.split(".")[0] not in PELVIC_BONES + ("L5",) and x.to_bone.split(".")[0] not in PELVIC_BONES:
                    continue
                for bone, p in pts(x):
                    d = self.on_surface(p, bone)
                    if d > self.tol:
                        far.append((n, bone, round(d * 1000, 1)))
        # los ligamentos de la rodilla y el tobillo (leg_foot) tienen sus propias tolerancias; aqui solo la pelvis, la cadera y los hitos gluteos
        far = [f for f in far if f[0] in self.pelvic_names()]
        self.assertEqual(far, [])

    def pelvic_names(self):
        return {n for n, x in {**self.art.ligaments, **self.art.attachments}.items()
                if x.region == "lumbar_pelvis" or n.startswith(("gerdy",))}

    def test_nothing_floats_behind_or_beside_the_pelvis(self):
        """Todo punto pelvico queda dentro de la caja de los huesos de la pelvis (mas la tolerancia): ningun vector apunta fuera del cuerpo."""
        pts = []
        for n, bone in self.b.items():
            if n.split(".")[0] in PELVIC_BONES[:5]:
                pts += [bone.head, bone.tail, *bone.outline]
        lo = tuple(min(p[i] for p in pts) - self.tol for i in range(3))
        hi = tuple(max(p[i] for p in pts) + self.tol for i in range(3))
        for n, x in {**self.art.ligaments, **self.art.attachments}.items():
            if x.region != "lumbar_pelvis" or n in NOT_ON_BONE or n.startswith(("iliofemoral", "pubofemoral", "ischiofemoral", "lesser", "gluteal", "greater", "iliolumbar")):
                continue
            for p in ([x.a, x.b] if hasattr(x, "a") else [x.point]):
                self.assertTrue(all(l <= c <= h for l, c, h in zip(lo, p, hi)), n)

    def test_gluteal_landmarks_are_on_the_outer_iliac_surface_and_the_femur(self):
        at = self.art.attachments
        for s, sx in (("L", 1), ("R", -1)):
            for n in ("posterior_gluteal_line", "anterior_gluteal_line", "inferior_gluteal_line"):
                a = at[f"{n}.{s}"]
                self.assertEqual(a.bone, f"ilium.{s}")
                self.assertLess(self.on_surface(a.point, a.bone), 1e-9, n)  # sobre la cara externa del ilion
                self.assertGreater(a.point[0] * sx, 0.05)  # lateral
            post, ant, inf = (at[f"{n}_gluteal_line.{s}"].point for n in ("posterior", "anterior", "inferior"))
            self.assertGreater(post[1], ant[1])  # la linea posterior queda por detras de la anterior...
            self.assertGreater(ant[1], inf[1])  # ...y la inferior es la mas anterior
            gt = at[f"greater_trochanter.{s}"]
            self.assertEqual(gt.bone, f"femur.{s}")
            self.assertLess(length(sub(gt.point, self.b[f"femur.{s}"].outline[1])), 1e-12)  # trocanter mayor = punto lateral proximal del femur
            self.assertGreater(gt.point[0] * sx, self.b[f"femur.{s}"].head[0] * sx + 0.03)  # lateral al eje del femur
            for n in ("gluteal_tuberosity", "lesser_trochanter"):
                self.assertLess(self.on_surface(at[f"{n}.{s}"].point, f"femur.{s}"), self.tol, n)
            g = at[f"gerdy_tubercle.{s}"]
            self.assertEqual(g.bone, f"tibia.{s}")
            self.assertGreater(g.point[0] * sx, self.b[f"tibia.{s}"].head[0] * sx)  # lateral

    def test_hip_ligaments_end_on_the_femur(self):
        lg = self.art.ligaments
        for s in "LR":
            for n in ("iliofemoral", "pubofemoral", "ischiofemoral"):
                x = lg[f"{n}.{s}"]
                self.assertEqual(x.to_bone, f"femur.{s}")
                self.assertLess(self.on_surface(x.b, x.to_bone), self.tol, n)
                self.assertLess(self.on_surface(x.a, x.from_bone), self.tol, n)

    def test_closure_holds_at_other_heights(self):
        for height in (1.5, 1.9):
            base, anat, art = build_all(height)
            tol = TOL_M * height / 1.75
            for n in ("sacrotuberous.L", "sacrospinous.R", "iliofemoral.L"):
                x = art.ligaments[n]
                self.assertLess(articulations.bone_distance(x.a, x.from_bone, base, anat), tol, (n, height))
                self.assertLess(articulations.bone_distance(x.b, x.to_bone, base, anat), tol, (n, height))


if __name__ == "__main__":
    unittest.main()
