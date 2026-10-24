"""Columna lumbar, sacro y pelvis: jerarquia, parametros espinopelvicos, centro de masas y puntos de union."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations, validation  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.geometry import dot, length, mirror_point, normalize, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

H = 1.75
LUMBAR = ["L5", "L4", "L3", "L2", "L1"]  # de abajo arriba


def build_all(**kw):
    base = build_model(load_config(**kw))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    return base, anat, articulations.build_articulations(base, anat, articulations.load_articulation_data())


def angle(u, v):
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(normalize(u), normalize(v))))))


def spinopelvic(base, anat):
    """SS, PT, PI y LL (L1-S1) medidos en el modelo. La placa de S1 se toma perpendicular al eje del sacro."""
    b = anat.bones
    sac = b["sacrum"]
    s1_up = sub(sac.head, sac.tail)  # normal de la placa superior de S1
    ss = angle(s1_up, (0, 0, 1))
    hips = tuple((x + y) / 2 for x, y in zip(base.bones["thigh.L"].head, base.bones["thigh.R"].head))
    to_s1 = sub(sac.head, hips)
    pt = math.degrees(math.atan2(to_s1[1], to_s1[2]))  # + si S1 queda por detras del eje de las caderas
    ll = angle(sub(b["L1"].tail, b["L1"].head), s1_up)
    return ss, pt, ss + pt, ll


class TestLumbarPelvisStructure(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()
        self.b = self.anat.bones

    def test_hierarchy(self):
        self.assertEqual(self.b["sacrum"].parent, "pelvis")  # raiz del bloque pelvico del nivel 1
        for n in ("coccyx", "ilium.L", "ilium.R"):
            self.assertEqual(self.b[n].parent, "sacrum", n)
            self.assertEqual(self.b[n].anatomical_parent, "sacrum", n)
        for s in "LR":  # el isquion y el pubis nacen en el acetabulo y cuelgan del ilion
            for n in ("ischium", "pubis"):
                self.assertEqual(self.b[f"{n}.{s}"].parent, f"ilium.{s}", n)
        chain = ["sacrum"] + LUMBAR + ["T12"]
        for lower, upper in zip(chain, chain[1:]):
            self.assertEqual(self.b[upper].anatomical_parent, lower, upper)  # cadena de abajo arriba
        self.assertLess(length(sub(self.b["L5"].head, self.b["sacrum"].head)), 1e-12)  # L5 sobre la meseta de S1
        for lower, upper in zip(LUMBAR, LUMBAR[1:]):
            self.assertLess(length(sub(self.b[upper].head, self.b[lower].tail)), 1e-12, upper)
        self.assertLess(length(sub(self.b["coccyx"].head, self.b["sacrum"].tail)), 1e-12)

    def test_spinopelvic_parameters_against_the_sources(self):
        ss, pt, pi, ll = spinopelvic(self.base, self.anat)
        self.assertAlmostEqual(ss, 37.0, delta=0.1)  # media de Sudhir 2016 (35.99) y Cureus 2025 (38.11)
        self.assertTrue(35.99 <= ss <= 38.11)
        self.assertAlmostEqual(ll, 51.9, delta=0.3)  # media de 48.84 y 54.9
        self.assertTrue(48.84 <= ll <= 54.9)
        # Base v2: la pelvis se inclina 15.5 grados (media de Sudhir 17.97 y Cureus 13.0); la incidencia pelvica
        # (PI = SS + PT) cae asi dentro de lo publicado (55.48 y 50.95). Antes S1 estaba sobre el eje de las caderas (PT = 0).
        self.assertAlmostEqual(pt, 15.5, delta=0.1)
        self.assertTrue(13.0 <= pt <= 17.97)
        self.assertTrue(50.95 <= pi <= 55.48)

    def test_lumbar_lordosis_and_lumbosacral_angulation(self):
        line = self.base.bones["spine_lumbar"]
        offsets = []
        for n in LUMBAR:
            v = self.b[n]
            c = tuple((x + y) / 2 for x, y in zip(v.head, v.tail))
            t = (c[2] - line.head[2]) / (line.tail[2] - line.head[2])
            offsets.append(c[1] - (line.head[1] + t * (line.tail[1] - line.head[1])))
        self.assertTrue(all(o < 0 for o in offsets))  # convexa hacia delante (-Y)
        self.assertEqual(offsets.index(min(offsets)), 2)  # vertice en L3
        l5, sac = self.b["L5"], self.b["sacrum"]
        l5_up = sub(l5.tail, l5.head)
        self.assertLess(l5_up[1], 0)  # L5 inclinada hacia delante sobre el sacro
        # Angulacion lumbosacra: angulo entre el eje de L5 y la normal de S1 (7.7 grados con la lordosis calibrada a
        # los datos publicados). Cota solo geometrica: el reparto de la lordosis por nivel NO esta validado con una fuente.
        self.assertGreater(angle(l5_up, sub(sac.head, sac.tail)), 5)

    def test_pelvic_cup_holds_the_body_center_of_mass(self):
        com = self.art.attachments["body_center_of_mass"].point
        self.assertAlmostEqual(com[2], 0.557 * H, places=9)  # 55.7% de la estatura (Palmer)
        hip_z = self.base.bones["thigh.L"].head[2]
        promontory = self.b["sacrum"].head
        self.assertTrue(hip_z < com[2] < promontory[2])  # entre el eje de las caderas y el promontorio
        sac = self.b["sacrum"]
        s2 = tuple(a + 0.25 * (b - a) for a, b in zip(sac.head, sac.tail))
        self.assertLess(com[1], s2[1])  # delante de S2
        crest = [self.b[f"ilium.{s}"].outline[2][0] for s in "LR"]
        self.assertTrue(min(crest) < com[0] < max(crest))  # dentro de la copa pelvica


class TestLumbarPelvisUnions(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()

    def region(self, store):
        return {n: x for n, x in store.items() if x.region == "lumbar_pelvis"}

    def test_counts_and_validation(self):
        self.assertEqual(len(self.region(self.art.joints)), 4 + 1 + 2 + 1 + 1 + 2)
        self.assertEqual(len(self.region(self.art.ligaments)), 6 * 2)
        self.assertEqual(len(self.region(self.art.attachments)), 8 * 2 + 2)  # hitos oseos + centro de masas + apice del coccix
        issues = validation.validate_articulations(self.base, self.anat, self.art)
        self.assertEqual([i for i in issues if i.severity == "error"], [])
        self.assertFalse([i for i in issues if any(n in i.message for n in self.region(self.art.joints))])

    def test_rig_drivers_and_centers(self):
        j = self.art.joints
        self.assertEqual(j["lumbosacral_L5_S1"].rig_driver, "lumbar")
        self.assertLess(length(sub(j["lumbosacral_L5_S1"].center, self.base.joints["lumbar"].pivot)), 1e-12)
        for s in "LR":
            self.assertEqual(j[f"coxofemoral.{s}"].rig_driver, f"hip.{s}")
            self.assertLess(length(sub(j[f"coxofemoral.{s}"].center, self.base.joints[f"hip.{s}"].pivot)), 1e-12)
            self.assertLess(length(sub(j[f"sacroiliac.{s}"].center, self.anat.bones[f"ilium.{s}"].head)), 1e-12)
        self.assertAlmostEqual(j["pubic_symphysis"].center[0], 0.0, places=12)  # linea media

    def test_published_ranges_units_and_sources(self):
        d = lambda jn: {x.name: x for x in self.art.joints[jn].dofs}  # noqa: E731
        self.assertEqual(d("intervertebral_L4_L5")["flexion_extension"].total_deg, (18.2, 18.2))  # Dvorak 1991
        self.assertEqual(d("lumbosacral_L5_S1")["flexion_extension"].total_deg, (17.0, 17.0))
        si = d("sacroiliac.L")
        self.assertEqual(si["nutacion_contranutacion"].total_deg, (1.0, 4.0))
        self.assertEqual((si["traslacion"].total_deg, si["traslacion"].unit), ((0.32, 0.32), "mm"))
        ps = d("pubic_symphysis")
        self.assertEqual((ps["traslacion_total"].total_deg, ps["traslacion_total"].unit), ((1.4, 3.1), "mm"))
        hip = d("coxofemoral.R")
        self.assertEqual({k: v.total_deg[0] for k, v in hip.items()},
                         {"flexion": 120, "extension": 10, "abduccion": 45, "aduccion": 25, "rotacion_interna": 15, "rotacion_externa": 35})
        self.assertIsNone(d("intervertebral_L2_L3")["rotacion_axial"].total_deg)  # sin cifra por nivel: no se inventa
        weak = {k for k, s in self.art.sources.items() if s["reliability"] == "baja"}
        for a in self.region(self.art.attachments).values():
            if a.sources and set(a.sources) <= weak:  # sin fuente = extremo definicional del hueso
                self.assertIn("verificar", a.notes.lower(), a.name)

    def test_ligaments_attach_where_described(self):
        lg, b = self.art.ligaments, self.anat.bones
        for s in "LR":
            self.assertEqual((lg[f"iliolumbar.{s}"].from_bone, lg[f"iliolumbar.{s}"].to_bone), ("L5", f"ilium.{s}"))
            self.assertEqual(lg[f"sacrotuberous.{s}"].to_bone, f"ischium.{s}")
            self.assertLess(length(sub(lg[f"sacrotuberous.{s}"].b, b[f"ischium.{s}"].tail)), 1e-12)  # tuberosidad isquiatica
            self.assertEqual((lg[f"pubofemoral.{s}"].from_bone, lg[f"ischiofemoral.{s}"].from_bone), (f"pubis.{s}", f"ischium.{s}"))
            self.assertEqual(lg[f"iliofemoral.{s}"].to_bone, f"femur.{s}")
            self.assertLess(lg[f"sacrospinous.{s}"].b[2], b[f"ilium.{s}"].tail[2])  # espina isquiatica por debajo del acetabulo

    def test_symmetry(self):
        for store, pts in ((self.art.joints, lambda x: [x.center]), (self.art.ligaments, lambda x: [x.a, x.b]),
                           (self.art.attachments, lambda x: [x.point])):
            for n, x in self.region(store).items():
                if ".L" in n:
                    for p, q in zip(pts(x), pts(store[n.replace(".L", ".R")])):
                        self.assertLess(length(sub(mirror_point(p), q)), 1e-12, n)


if __name__ == "__main__":
    unittest.main()
