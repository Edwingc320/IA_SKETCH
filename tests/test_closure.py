"""Volumen del craneo y cierres estructurales: costillas, anillo pelvico y extremos de hueso sin termino."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations, validation, volumes  # noqa: E402
from anatomical_core.anatomy import point_segment_distance  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402


def build_all(height=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    return base, anat, articulations.build_articulations(base, anat, articulations.load_articulation_data())


def polyline_distance(p, pts, closed=True):
    pairs = list(zip(pts, pts[1:] + (pts[:1] if closed else ())))
    return min(point_segment_distance(p, a, b) for a, b in pairs)


class TestCraniumVolume(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, _ = build_all()
        self.c = self.anat.bones["cranium"]
        self.verts, self.faces = volumes.volume_mesh(self.c)

    def test_closed_round_surface_with_a_plausible_volume(self):
        self.assertEqual(volumes.euler_characteristic(self.verts, self.faces), 2)  # esfera topologica: sin agujeros ni bordes abiertos
        litres = volumes.signed_volume(self.verts, self.faces) * 1000
        self.assertGreater(litres, 0)  # normales hacia fuera
        self.assertTrue(2.0 < litres < 3.5, litres)  # craneo + macizo facial, por fuera (capacidad craneal ~1.4 L + hueso)

    def test_dimensions_follow_the_cephalic_index(self):
        lo, hi = volumes.bounding_box(self.verts)
        width, depth = hi[0] - lo[0], hi[1] - lo[1]
        profile = volumes.smooth_closed_profile([(p[1], p[2]) for p in self.c.outline])
        length_y = max(p[0] for p in profile) - min(p[0] for p in profile)
        self.assertAlmostEqual(width, self.c.volume["cephalic_index"] * length_y, places=9)  # ancho biparietal = indice x longitud sagital
        self.assertAlmostEqual(width / depth, self.c.volume["cephalic_index"], delta=0.01)  # y asi se ve en la malla
        self.assertTrue(0.14 < width < 0.17, width)  # ancho biparietal humano medio (~15 cm en vivo)
        self.assertTrue(0.18 < depth < 0.21, depth)  # longitud frente-occipucio (~19 cm)
        outline_y = [p[1] for p in self.c.outline]
        self.assertLess(abs(depth - (max(outline_y) - min(outline_y))), 0.01)  # coincide con el contorno sagital
        self.assertLessEqual(hi[2], self.c.tail[2] + 1e-9)  # redondeada: nunca sobrepasa el vertex del contorno...
        self.assertGreater(hi[2], self.c.tail[2] - 0.025)  # ...y se queda a menos de 2.5 cm de el

    def test_midline_section_is_the_outline_and_the_shape_is_symmetric(self):
        profile = volumes.smooth_closed_profile([(p[1], p[2]) for p in self.c.outline])
        ring = [v for v in self.verts if abs(v[0]) < 1e-12]  # anillo central (psi = 0)
        self.assertGreater(len(ring), 40)
        for v in ring:  # cada punto del corte central esta sobre el perfil suavizado
            edge = polyline_distance((0.0, v[1], v[2]), [(0.0, y, z) for y, z in profile])
            self.assertLess(edge, 1e-9)
        keys = {tuple(round(c, 9) for c in v) for v in self.verts}
        for v in self.verts:
            self.assertIn(tuple(round(c, 9) for c in mirror_point(v)), keys)

    def test_origin_stays_at_the_occipital_condyles_and_the_hierarchy_is_untouched(self):
        a = self.anat.bones
        self.assertLess(length(sub(self.c.head, a["C1"].tail)), 1e-12)  # origen del hueso en C1 / condilos
        self.assertEqual((self.c.parent, self.c.anatomical_parent), ("head", "C1"))
        m = a["mandible"]  # la mandibula conserva su pivote en el eje de las ATM
        self.assertEqual(m.parent, "cranium")
        h = self.base.height_m
        expected = tuple(c + o * h for c, o in zip(self.base.bones["head"].head, (0.0, -0.01029, 0.00571)))
        self.assertLess(length(sub(m.head, expected)), 1e-9)
        # el origen queda dentro de la envolvente de la forma
        lo, hi = volumes.bounding_box(self.verts)
        self.assertTrue(all(l - 1e-9 <= c <= u + 1e-9 for l, c, u in zip(lo, self.c.head, hi)))

    def test_scales_linearly_with_height(self):
        _, anat2, _ = build_all(1.5)
        v2, _ = volumes.volume_mesh(anat2.bones["cranium"])
        k = 1.5 / self.base.height_m
        self.assertEqual(len(v2), len(self.verts))
        for p, q in zip(self.verts, v2):
            self.assertLess(length(sub(tuple(k * c for c in p), q)), 1e-9)

    def test_other_bones_keep_their_thin_shape(self):
        self.assertEqual([n for n, b in self.anat.bones.items() if b.volume], ["cranium"])


class TestVolumeAwareBoneDistance(unittest.TestCase):
    """El craneo tiene volumen: un punto dentro de la boveda esta sobre el hueso y uno fuera se mide hasta su superficie."""

    def test_point_inside_on_a_unit_cube(self):
        v = [(x, y, z) for x in (0.0, 1.0) for y in (0.0, 1.0) for z in (0.0, 1.0)]
        f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        self.assertTrue(volumes.point_inside((0.5, 0.5, 0.5), v, f))
        self.assertTrue(volumes.point_inside((0.1, 0.9, 0.2), v, f))
        self.assertFalse(volumes.point_inside((1.5, 0.5, 0.5), v, f))
        self.assertFalse(volumes.point_inside((0.5, -0.2, 0.5), v, f))

    def test_cranial_landmarks_are_on_the_skull_volume(self):
        base, anat, art = build_all()
        tol = 0.012
        c = anat.bones["cranium"]
        lo, hi = volumes.bounding_box(volumes.volume_mesh(c)[0])
        center = tuple((a + b) / 2 for a, b in zip(lo, hi))
        self.assertEqual(articulations.bone_distance(center, "cranium", base, anat), 0.0)  # dentro de la boveda
        out = (hi[0] + 0.03, center[1], center[2])
        self.assertTrue(0.025 < articulations.bone_distance(out, "cranium", base, anat) < 0.035)  # 3 cm fuera de la superficie lateral
        for n in ("porion", "orbitale", "zygomatic_arch", "temporal_fossa", "mastoid_process"):
            a = art.attachments[f"{n}.L"]
            self.assertLess(articulations.bone_distance(a.point, "cranium", base, anat), 0.018, n)  # los de antes estaban a 30-66 mm


class TestCostalClosure(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, _ = build_all()
        self.b = self.anat.bones

    def test_validator_reports_no_closure_problem(self):
        self.assertEqual(validation.validate_closures(self.anat), [])

    def test_true_ribs_reach_the_sternum_and_false_ribs_chain_to_them(self):
        st = self.b["sternum"]
        for s in "LR":
            for k in range(1, 8):
                rib = self.b[f"rib_{k:02d}.{s}"]
                self.assertLess(length(sub(rib.cartilage[0], rib.tail)), 1e-12, rib.name)  # el cartilago nace en la cola
                self.assertLess(polyline_distance(rib.cartilage[-1], st.outline), 1e-9, rib.name)  # y llega al esternon
            for k in range(8, 11):
                rib, above = self.b[f"rib_{k:02d}.{s}"], self.b[f"rib_{k - 1:02d}.{s}"]
                self.assertLess(length(sub(rib.cartilage[0], rib.tail)), 1e-12, rib.name)
                self.assertLess(point_segment_distance(rib.cartilage[-1], above.cartilage[0], above.cartilage[-1]), 1e-9, rib.name)
            for k in (11, 12):
                self.assertEqual(self.b[f"rib_{k}.{s}"].cartilage, ())  # flotantes: terminan libres por anatomia

    def test_every_rib_reaches_the_sternum_through_its_chain(self):
        st = self.b["sternum"]
        for s in "LR":
            for k in range(1, 11):
                j = k
                while j > 7:  # 10 -> 9 -> 8 -> 7: se sube por los cartilagos hasta una costilla verdadera
                    j -= 1
                end = self.b[f"rib_{j:02d}.{s}"].cartilage[-1]
                self.assertLess(polyline_distance(end, st.outline), 1e-9, f"rib_{k:02d}.{s}")

    def test_sternocostal_and_interchondral_joints_sit_at_the_cartilage_ends(self):
        _, anat, art = build_all()
        for s in "LR":
            for k in range(1, 8):
                self.assertLess(length(sub(art.joints[f"sternocostal_{k:02d}.{s}"].center, anat.bones[f"rib_{k:02d}.{s}"].cartilage[-1])), 1e-12)
            for k in range(8, 11):
                self.assertLess(length(sub(art.joints[f"interchondral_{k:02d}.{s}"].center, anat.bones[f"rib_{k:02d}.{s}"].cartilage[-1])), 1e-12)

    def test_cartilage_length_matches_the_old_costal_outline(self):
        """El cartilago es el tramo que antes cerraba el contorno: longitud mayor en las costillas bajas, nula en las flotantes."""
        lengths = [length(sub(self.b[f"rib_{k:02d}.L"].cartilage[-1], self.b[f"rib_{k:02d}.L"].tail)) for k in range(1, 11)]
        self.assertTrue(all(0.02 < x < 0.12 for x in lengths), lengths)


class TestPelvicRing(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, _ = build_all()
        self.b = self.anat.bones

    def test_ring_is_closed_and_continuous(self):
        b = self.b
        for s, sx in (("L", 1), ("R", -1)):
            corner = min(b["sacrum"].outline, key=lambda p: length(sub(p, b[f"ilium.{s}"].head)))
            self.assertLess(length(sub(corner, b[f"ilium.{s}"].head)), 1e-12)  # sacro - ilion (sacroiliaca)
            self.assertGreater(corner[0] * sx, 0.03)
            acetabulum = self.base.bones[f"thigh.{s}"].head
            for n in ("ilium", "ischium", "pubis"):  # ilion, isquion y pubis confluyen en el acetabulo
                bone = b[f"{n}.{s}"]
                self.assertLess(length(sub(bone.tail if n == "ilium" else bone.head, acetabulum)), 1e-12, n)
            self.assertAlmostEqual(b[f"pubis.{s}"].tail[0], 0.0, places=12)  # pubis - pubis (sinfisis) en la linea media
        self.assertLess(length(sub(b["pubis.L"].tail, b["pubis.R"].tail)), 1e-12)
        self.assertLess(length(sub(b["coccyx"].head, b["sacrum"].tail)), 1e-12)

    def test_pelvic_landmarks_lie_on_the_ring(self):
        _, anat, art = build_all()
        for s in "LR":
            for n in ("anterior_superior_iliac_spine", "anterior_inferior_iliac_spine", "iliac_crest", "iliac_fossa", "ischial_tuberosity", "pubic_body",
                      "lesser_trochanter", "gluteal_tuberosity"):
                a = art.attachments[f"{n}.{s}"]
                self.assertLess(articulations.bone_distance(a.point, a.bone, self.base, anat), a.tolerance_m, a.name)
            lg = art.ligaments
            for n in ("sacrotuberous", "sacrospinous", "iliolumbar"):  # los ligamentos del anillo unen hueso con hueso
                self.assertNotEqual(lg[f"{n}.{s}"].from_bone, lg[f"{n}.{s}"].to_bone, n)


class TestNoDanglingBoneEnds(unittest.TestCase):
    """Ningun extremo de hueso queda sin termino: cada cabeza y cola esta a menos de 12 mm de otra estructura definida (hueso,
    cartilago, articulacion, ligamento o hito)."""

    TOL_M = 0.012

    def test_every_end_touches_something(self):
        base, anat, art = build_all()
        pts = []
        for n, x in anat.bones.items():
            pts += [(f"{n}.head", x.head), (f"{n}.tail", x.tail)] + [(f"{n}.o{i}", p) for i, p in enumerate(x.outline)] + [(f"{n}.c{i}", p) for i, p in enumerate(x.cartilage)]
        for n, x in base.bones.items():
            pts += [(f"base:{n}.head", x.head), (f"base:{n}.tail", x.tail)]
        pts += [(f"J:{n}", j.center) for n, j in art.joints.items()]
        pts += [(f"L:{n}.{e}", p) for n, lg in art.ligaments.items() for e, p in (("a", lg.a), ("b", lg.b))]
        pts += [(f"A:{n}", a.point) for n, a in art.attachments.items()]
        tol = self.TOL_M * base.height_m / 1.75
        dangling = []
        for n, x in anat.bones.items():
            for end, p in (("head", x.head), ("tail", x.tail)):
                if min(length(sub(p, q)) for k, q in pts if k != f"{n}.{end}") > tol:
                    dangling.append(f"{n}.{end}")
        self.assertEqual(dangling, [])

    def test_the_distal_tufts_and_other_free_tips_are_defined_landmarks(self):
        _, anat, art = build_all()
        for s in "LR":
            for f in ("thumb", "index", "middle", "ring", "little"):
                a = art.attachments[f"distal_phalanx_tuft_{f}.{s}"]
                self.assertLess(length(sub(a.point, anat.bones[f"{f}_distal.{s}"].tail)), 1e-12)
            for k in range(1, 6):
                a = art.attachments[f"distal_phalanx_tuft_toe_{k}.{s}"]
                self.assertLess(length(sub(a.point, anat.bones[f"toe_{k}_distal.{s}"].tail)), 1e-12)
            self.assertLess(length(sub(art.attachments[f"patella_base.{s}"].point, anat.bones[f"patella.{s}"].head)), 1e-12)
        self.assertLess(length(sub(art.attachments["coccyx_apex"].point, anat.bones["coccyx"].tail)), 1e-12)
        self.assertLess(length(sub(art.attachments["jugular_notch"].point, anat.bones["sternum"].head)), 1e-12)


if __name__ == "__main__":
    unittest.main()
