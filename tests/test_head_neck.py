"""Cabeza y columna cervical: jerarquia, lordosis, plano de Frankfort, centro de gravedad, ATM y puntos de union."""
import collections
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations, validation  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.geometry import cross, dot, length, mirror_point, normalize, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

H = 1.75
CERVICAL = [f"C{k}" for k in range(7, 0, -1)]  # de abajo arriba


def build_all(**kw):
    base = build_model(load_config(**kw))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    return base, anat, articulations.build_articulations(base, anat, articulations.load_articulation_data())


def angle(u, v):
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(normalize(u), normalize(v))))))


class TestHeadNeckStructure(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()
        self.b = self.anat.bones

    def test_bones_and_hierarchy(self):
        for n in CERVICAL + ["cranium", "mandible"]:
            self.assertIn(n, self.b)
        chain = ["T1"] + CERVICAL + ["cranium", "mandible"]
        for lower, upper in zip(chain, chain[1:]):
            self.assertEqual(self.b[upper].anatomical_parent, lower, upper)  # cadena de abajo arriba
        for lower, upper in zip(chain[:-1], chain[1:-1]):  # continuidad geometrica hasta el craneo (la mandibula nace en la ATM)
            self.assertLess(length(sub(self.b[upper].head, self.b[lower].tail)), 1e-12, upper)
        self.assertEqual(self.b["mandible"].parent, "cranium")  # rig: la mandibula cuelga del craneo
        self.assertEqual(self.b["cranium"].parent, "head")  # rig: el craneo lo mueve la cabeza base
        self.assertEqual(self.b["C7"].parent, "neck")

    def test_cervical_lordosis_matches_the_published_mean(self):
        c2, c7 = self.b["C2"], self.b["C7"]
        cobb = angle(sub(c2.tail, c2.head), sub(c7.tail, c7.head))
        self.assertAlmostEqual(cobb, 17.1, delta=0.2)  # Zhu et al. 2020: 17.11 +- 6.31
        neck = self.base.bones["neck"]
        for n in CERVICAL[1:-1]:  # C6..C2: por delante (-Y) de la linea del cuello base
            v = self.b[n]
            c = tuple((x + y) / 2 for x, y in zip(v.head, v.tail))
            t = (c[2] - neck.head[2]) / (neck.tail[2] - neck.head[2])
            self.assertLess(c[1], neck.head[1] + t * (neck.tail[1] - neck.head[1]), n)

    def test_frankfort_plane_is_horizontal_and_the_face_looks_forward(self):
        at = self.art.attachments
        po_l, po_r, or_l, or_r = at["porion.L"].point, at["porion.R"].point, at["orbitale.L"].point, at["orbitale.R"].point
        normal = cross(sub(po_r, po_l), sub(or_l, po_l))
        self.assertLess(angle(normal, (0, 0, 1)) if normal[2] > 0 else angle(normal, (0, 0, -1)), 1.0)  # horizontal
        self.assertAlmostEqual(or_r[2], po_l[2], places=9)
        self.assertLess(or_l[1], po_l[1] - 0.05)  # la cara (orbitas) mira hacia delante (-Y)
        cr = self.b["cranium"]
        self.assertLess(min(p[1] for p in cr.outline), cr.head[1] - 0.08)  # cara delante
        self.assertGreater(max(p[1] for p in cr.outline), cr.head[1] + 0.05)  # occipital detras

    def test_head_center_of_gravity_is_in_front_of_the_occipital_condyles(self):
        cog = self.art.attachments["head_center_of_gravity"].point
        nasion = self.art.attachments["nasion"].point
        inion = self.art.attachments["external_occipital_protuberance"].point
        self.assertLess(length(sub(cog, tuple((a + b) / 2 for a, b in zip(nasion, inion)))), 1e-12)  # punto medio nasion-inion
        condyles = self.b["C1"].tail
        self.assertLess(cog[1], condyles[1])  # por delante: momento de flexion que equilibran los extensores
        self.assertGreater(cog[2], self.art.attachments["porion.L"].point[2])  # por encima del conducto auditivo

    def test_mandible_pivots_exactly_on_the_tmj_axis(self):
        md = self.b["mandible"]
        tl, tr = self.art.joints["temporomandibular.L"].center, self.art.joints["temporomandibular.R"].center
        self.assertLess(length(sub(md.head, tuple((a + b) / 2 for a, b in zip(tl, tr)))), 1e-12)  # centro del eje de bisagra
        self.assertAlmostEqual(abs(dot(md.frame[0], normalize(sub(tl, tr)))), 1.0, places=9)  # eje local X = eje entre condilos
        self.assertLess(length(sub(md.outline[0], tl)), 1e-12)  # el contorno nace en los condilos
        self.assertLess(length(sub(md.outline[-1], tr)), 1e-12)
        self.assertLess(md.tail[1], md.head[1] - 0.05)  # menton hacia delante
        self.assertLess(md.tail[2], md.head[2])  # y hacia abajo
        porion = self.art.attachments["porion.L"].point
        self.assertLess(tl[2], porion[2])  # el condilo queda por debajo del plano de Frankfort
        self.assertLess(tl[1], porion[1])  # y por delante del conducto auditivo

    def test_widths_match_the_measured_source(self):
        md = self.b["mandible"]
        gonion_l, gonion_r = md.outline[1], md.outline[-2]
        self.assertAlmostEqual(length(sub(gonion_l, gonion_r)), 0.111, delta=0.001)  # bigoniaca 111.5 mm (acta_odont_head)
        zl, zr = self.art.attachments["zygomatic_arch.L"].point, self.art.attachments["zygomatic_arch.R"].point
        self.assertAlmostEqual(length(sub(zl, zr)), 0.133, delta=0.001)  # bicigomatica 133.4 mm


class TestHeadNeckUnions(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()

    def region(self, store):
        return {n: x for n, x in store.items() if x.region == "head_neck"}

    def test_counts_and_validation(self):
        self.assertEqual(len(self.region(self.art.joints)), 2 + 5 + 2)  # AO, AA, C2/C3..C6/C7, ATM x2
        self.assertEqual(len(self.region(self.art.ligaments)), 7 + 3 * 2 + 1)  # craneovertebrales y nucal, ATM x2, alar.R
        self.assertEqual(len(self.region(self.art.attachments)), 23)  # solo hitos oseos; los musculos estan en muscle-model
        issues = validation.validate_articulations(self.base, self.anat, self.art)
        self.assertEqual([i for i in issues if i.severity == "error"], [])
        regions = collections.Counter(i.message.split("'")[1].split(".")[0] for i in issues)
        for name in regions:  # los unicos avisos siguen siendo los huecos documentados de la clavicula
            self.assertTrue(name.startswith(("sternoclavicular", "acromioclavicular", "costoclavicular")), name)

    def test_rig_driver_and_centers(self):
        j = self.art.joints
        self.assertEqual(j["atlanto_occipital"].rig_driver, "head")
        self.assertLess(length(sub(j["atlanto_occipital"].center, self.base.joints["head"].pivot)), 1e-12)
        self.assertLess(length(sub(j["atlanto_axial"].center, self.anat.bones["C2"].tail)), 1e-12)
        for k in range(2, 7):
            self.assertLess(length(sub(j[f"intervertebral_C{k}_C{k + 1}"].center, self.anat.bones[f"C{k}"].head)), 1e-12)

    def test_published_ranges_units_and_sides(self):
        d = lambda jn: {x.name: x for x in self.art.joints[jn].dofs}  # noqa: E731
        ao, aa, tmj = d("atlanto_occipital"), d("atlanto_axial"), d("temporomandibular.L")
        self.assertEqual((ao["flexion_extension"].total_deg, ao["flexion_extension"].source), ((14.0, 18.0), "schops_1997"))
        self.assertTrue(ao["rotacion_axial"].per_side)
        self.assertEqual((aa["rotacion_axial"].total_deg, aa["rotacion_axial"].per_side), ((40.0, 45.0), True))  # la gran rotacion del cuello
        self.assertEqual((tmj["apertura_interincisal"].total_deg, tmj["apertura_interincisal"].unit), ((44.8, 44.8), "mm"))
        self.assertIsNone(tmj["traslacion_del_condilo"].total_deg)  # sin cifra en las fuentes: no se inventa
        self.assertEqual(d("intervertebral_C4_C5")["flexion_extension"].total_deg, (8.0, 8.0))
        self.assertEqual(d("intervertebral_C4_C5")["rotacion_axial"].total_deg, (5.3, 5.3))
        for jn, j in self.region(self.art.joints).items():
            for x in j.dofs:
                if x.total_deg is not None:
                    self.assertIn(x.source, self.art.sources, f"{jn}.{x.name}")

    def test_ligaments_and_attachments(self):
        lg, at = self.art.ligaments, self.art.attachments
        for s in "LR":
            self.assertEqual((lg[f"alar.{s}"].from_bone, lg[f"alar.{s}"].to_bone), ("C2", "cranium"))
            self.assertEqual(lg[f"temporomandibular_lateral.{s}"].to_bone, "mandible")
        self.assertEqual((lg["nuchal"].from_bone, lg["nuchal"].to_bone), ("C7", "cranium"))
        self.assertLess(length(sub(lg["nuchal"].b, at["external_occipital_protuberance"].point)), 1e-12)
        self.assertGreater(at["mastoid_process.L"].point[0], 0.03)  # lateral
        self.assertEqual(at["mandibular_angle.R"].bone, "mandible")
        weak = {k for k, s in self.art.sources.items() if s["reliability"] == "baja"}
        for a in self.region(at).values():
            if a.sources and set(a.sources) <= weak:  # sin fuente = extremo definicional del hueso
                self.assertIn("verificar", a.notes.lower(), a.name)

    def test_symmetry(self):
        for store, pts in ((self.art.joints, lambda x: [x.center]), (self.art.ligaments, lambda x: [x.a, x.b]),
                           (self.art.attachments, lambda x: [x.point])):
            for n, x in self.region(store).items():
                if ".L" in n:
                    for p, q in zip(pts(x), pts(store[n.replace(".L", ".R")])):
                        self.assertLess(length(sub(mirror_point(p), q)), 1e-12, n)


if __name__ == "__main__":
    unittest.main()
