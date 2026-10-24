"""Nivel 1 (anatomia) sobre la base: referencia, estructura, region pelvica y validador (Python puro)."""
import dataclasses
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from anatomical_core import anatomy, validation  # noqa: E402
from anatomical_core.config import ConfigError, load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402
from test_base_frozen import GOLDEN, diff_against_golden  # noqa: E402

H = 1.75


def build(**kw):
    base = build_model(load_config(**kw))
    return base, anatomy.build_anatomy(base, anatomy.load_anatomy_config())


def codes(issues):
    return {i.code for i in validation.errors(issues)}


class TestReference(unittest.TestCase):
    def test_reference_json_is_stored_verbatim_for_traceability(self):
        data = json.loads((ROOT / "config" / "reference" / "human_skeleton_reference.json").read_text(encoding="utf-8"))
        self.assertEqual(data["skeleton_metadata"]["approx_total_bones"], 206)  # tal como lo entrego el usuario
        names = anatomy.load_reference()
        self.assertEqual(len(names), 185)
        self.assertEqual(len(set(names)), 185)

    def test_name_normalization_rules(self):
        norm = [anatomy.normalize_reference_name(n) for n in anatomy.load_reference()]
        self.assertEqual(len(set(norm)), 185)  # la normalizacion no fusiona nombres por accidente
        self.assertFalse([n for n in norm if "_L_" in n or "_R_" in n], "el lado va como sufijo final")
        self.assertFalse([n for n in norm if "pinky" in n])
        self.assertIn("sternum_body", norm)
        self.assertNotIn("body", norm)
        self.assertIn("rib_01.L", norm)
        self.assertIn("little_distal.R", norm)
        self.assertEqual(anatomy.normalize_reference_name("C1_atlas"), "C1_atlas")  # el resto se conserva
        left = [n for n in norm if n.endswith(".L")]
        right = [n for n in norm if n.endswith(".R")]
        self.assertEqual(len(left), len(right))
        self.assertEqual({n[:-2] for n in left}, {n[:-2] for n in right})


class TestLevel1OnTopOfTheBase(unittest.TestCase):
    def setUp(self):
        self.base, self.anat = build()

    def test_validation_passes(self):
        self.assertEqual(validation.validate_anatomy(self.base, self.anat), [])

    def test_building_level_1_does_not_change_the_base(self):
        golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.assertEqual(diff_against_golden(self.base, golden), [])
        self.assertEqual(self.anat.base_signature, golden["model_signature"])
        self.assertEqual(len(self.base.bones), 20)

    def test_every_level_1_bone_descends_from_a_base_bone(self):
        for n in self.anat.bones:
            cur, steps = n, 0
            while cur in self.anat.bones:
                cur = self.anat.bones[cur].parent
                steps += 1
                self.assertLess(steps, 100)
            self.assertIn(cur, self.base.bones, n)
            self.assertNotIn(n, self.base.bones)

    def test_coverage_accounts_for_every_reference_name(self):
        cov = anatomy.coverage(self.anat, self.base)
        total = len(cov["implemented"]) + len(cov["base"]) + len(cov["pending"])
        self.assertEqual(total, 185)
        self.assertEqual(sorted(cov["base"]), ["clavicle.L", "clavicle.R"])  # reutilizados de la base

    def test_reproducible(self):
        self.assertEqual(self.anat.signature(), build()[1].signature())


class TestPelvicGirdle(unittest.TestCase):
    """Region 1: par de coxales + sacro + coxis; cabezas femorales ancladas."""

    def setUp(self):
        self.base, self.anat = build()
        self.b = self.anat.bones

    def test_bones_parents_and_traceability(self):
        self.assertEqual({n for n, x in self.b.items() if x.region == "pelvic_girdle"},
                         {"sacrum_fused", "coccyx_fused", *(f"{n}.{s}" for n in ("ilium", "ischium", "pubis") for s in "LR")})
        self.assertEqual(self.b["sacrum_fused"].parent, "pelvis")
        self.assertEqual(self.b["coccyx_fused"].parent, "sacrum_fused")
        # el coxal esta separado en tres huesos: el ilion cuelga del sacro (sacroiliaca) y el isquion y el pubis, del ilion
        for s in "LR":
            self.assertEqual(self.b[f"ilium.{s}"].parent, "sacrum_fused")
            self.assertEqual(self.b[f"ischium.{s}"].parent, f"ilium.{s}")
            self.assertEqual(self.b[f"pubis.{s}"].parent, f"ilium.{s}")
            for n in ("ilium", "ischium", "pubis"):
                self.assertEqual(self.b[f"{n}.{s}"].anatomical_parent, self.b[f"{n}.{s}"].parent)
                self.assertEqual(self.b[f"{n}.{s}"].reference, (f"{n}.{s}",))  # un hueso por nombre de la referencia
                self.assertEqual(base_ancestor(self.anat, f"{n}.{s}"), "pelvis")
        self.assertNotIn("hip_bone.L", self.b)
        cov = anatomy.coverage(self.anat, self.base)["implemented"]
        for r in ("sacrum_fused", "coccyx_fused", "ilium.L", "ischium.L", "pubis.L", "ilium.R", "ischium.R", "pubis.R"):
            self.assertIn(r, cov)

    def test_femoral_heads_are_anchored_exactly_in_the_acetabulum(self):
        for s in "LR":  # los tres huesos coinciden en el acetabulo, que es el pivote de la cadera de la base
            head = self.base.bones[f"thigh.{s}"].head
            self.assertLess(length(sub(self.b[f"ilium.{s}"].tail, head)), 1e-12)
            self.assertLess(length(sub(self.b[f"ischium.{s}"].head, head)), 1e-12)
            self.assertLess(length(sub(self.b[f"pubis.{s}"].head, head)), 1e-12)
        self.assertLess(length(sub(self.b["sacrum_fused"].head, self.base.bones["spine_lumbar"].head)), 1e-12)
        self.assertLess(length(sub(self.b["coccyx_fused"].head, self.b["sacrum_fused"].tail)), 1e-12)

    def test_anatomical_orientation(self):
        sac = self.b["sacrum_fused"]
        self.assertLess(sac.tail[2], sac.head[2])  # baja
        self.assertGreater(sac.tail[1], sac.head[1])  # hacia atras
        for s, sx in (("L", 1), ("R", -1)):
            il, isch, pub = (self.b[f"{n}.{s}"] for n in ("ilium", "ischium", "pubis"))
            self.assertLess(abs(il.head[0]), abs(il.tail[0]))  # la sacroiliaca es medial al acetabulo
            self.assertGreater(il.head[2], il.tail[2])  # y esta por encima
            self.assertGreater(il.head[1], il.tail[1])  # y por detras
            hip_z = self.base.bones[f"thigh.{s}"].head[2]
            crest, asis = il.outline[2], il.outline[3]
            symphysis, ischial = pub.tail, isch.tail
            self.assertEqual(max(p[2] for p in il.outline), crest[2])  # la cresta iliaca es lo mas alto
            self.assertGreater(crest[2], hip_z)
            self.assertLess(asis[1], 0.0)  # espina iliaca anterosuperior: delante
            self.assertLess(symphysis[1], 0.0)  # sinfisis: delante, abajo y casi en la linea media
            self.assertLess(symphysis[2], hip_z)
            self.assertLess(abs(symphysis[0]), 0.01 * H)
            lowest = min(p[2] for b in (il, isch, pub) for p in (b.head, b.tail) + b.outline)
            self.assertEqual(lowest, ischial[2])  # la tuberosidad isquiatica es lo mas bajo de la pelvis
            self.assertGreater(ischial[1], symphysis[1])  # y queda por detras de la sinfisis
            self.assertGreater(crest[0] * sx, self.base.bones[f"thigh.{s}"].head[0] * sx)  # pelvis mas ancha que las caderas

    def test_symmetry_including_outlines(self):
        for n in ("ilium", "ischium", "pubis"):
            l, r = self.b[f"{n}.L"], self.b[f"{n}.R"]
            for p, q in zip((l.head, l.tail) + l.outline, (r.head, r.tail) + r.outline):
                self.assertLess(length(sub(mirror_point(p), q)), 1e-12, n)
        for n in ("sacrum_fused", "coccyx_fused"):
            self.assertAlmostEqual(self.b[n].head[0], 0.0, places=12)
            self.assertAlmostEqual(self.b[n].tail[0], 0.0, places=12)

    def test_scales_with_the_base_proportions_and_stays_anchored(self):
        base2, anat2 = build(height_m=1.90)
        self.assertAlmostEqual(anat2.bones["sacrum_fused"].length / self.b["sacrum_fused"].length, 1.90 / 1.75, places=9)
        self.assertEqual(validation.validate_anatomy(base2, anat2), [])
        base3, anat3 = build(length_overrides={"pelvis": 0.06, "thigh": 0.27})
        self.assertEqual(validation.validate_anatomy(base3, anat3), [])
        self.assertLess(length(sub(anat3.bones["ilium.L"].tail, base3.bones["thigh.L"].head)), 1e-12)
        self.assertLess(length(sub(anat3.bones["pubis.L"].head, base3.bones["thigh.L"].head)), 1e-12)
        self.assertLess(length(sub(anat3.bones["sacrum_fused"].head, base3.bones["spine_lumbar"].head)), 1e-12)


def perp_distance(p, a, b):
    """Distancia del punto p a la recta a-b."""
    from anatomical_core.geometry import cross, normalize
    return length(cross(sub(p, a), normalize(sub(b, a))))


class TestThoracicCage(unittest.TestCase):
    """Region 2: esternon (una pieza) + 12 pares de costillas ancladas a sus vertebras."""

    def setUp(self):
        self.base, self.anat = build()
        self.b = self.anat.bones
        self.ribs = {s: [self.b[f"rib_{k:02d}.{s}"] for k in range(1, 13)] for s in "LR"}

    def test_bones_parents_and_traceability(self):
        region = {n for n, x in self.b.items() if x.region == "thoracic_cage"}
        self.assertEqual(region, {"sternum"} | {f"rib_{k:02d}.{s}" for k in range(1, 13) for s in "LR"})
        # especificacion torax/cintura escapular: cada costilla cuelga de su vertebra; el esternon de T4
        self.assertEqual(self.b["sternum"].parent, "T4")
        self.assertEqual(base_ancestor(self.anat, "sternum"), "thorax")
        self.assertEqual(self.b["sternum"].reference, ("manubrium", "sternum_body", "xiphoid_process"))
        for s in "LR":
            for k, rib in enumerate(self.ribs[s], start=1):
                self.assertEqual(rib.parent, f"T{k}", rib.name)
                self.assertEqual(base_ancestor(self.anat, rib.name), "thorax" if k <= 6 else "spine_thoracic", rib.name)
                self.assertEqual(rib.reference, (f"rib_{k:02d}.{s}",))
        cov = anatomy.coverage(self.anat, self.base)["implemented"]
        for r in ["manubrium", "sternum_body", "xiphoid_process"] + [f"rib_{k:02d}.{s}" for k in range(1, 13) for s in "LR"]:
            self.assertIn(r, cov)

    def test_rib_heads_sit_on_evenly_spaced_thoracic_levels(self):
        top, bottom = self.base.bones["thorax"].tail, self.base.bones["spine_thoracic"].head
        heads = [r.head for r in self.ribs["L"]]
        for a, b in zip(heads, heads[1:]):
            self.assertGreater(a[2], b[2])  # T1 arriba ... T12 abajo
        self.assertLess(heads[0][2], top[2])
        self.assertGreater(heads[-1][2], bottom[2])
        gaps = [length(sub(a, b)) for a, b in zip(heads, heads[1:])]
        mean = sum(gaps) / len(gaps)
        for g in gaps:
            self.assertLess(abs(g - mean) / mean, 0.05)  # niveles vertebrales uniformes
        for k, r in enumerate(self.ribs["L"], start=1):  # cada cabeza costal pegada a su vertebra (costovertebral)
            seg = self.base.bones[base_ancestor(self.anat, r.name)]
            self.assertLess(perp_distance(r.head, seg.head, seg.tail), 0.02 * H)
            t = self.b[f"T{k}"]
            mid = tuple((a + c) / 2 for a, c in zip(t.head, t.tail))
            self.assertLess(abs(length(sub(r.head, mid)) - 0.012 * H), 1e-9)  # a 0.012 H del eje de T_k
            self.assertAlmostEqual(r.head[2], mid[2], places=9)  # a media altura de su vertebra

    def test_the_torso_now_has_anteroposterior_depth(self):
        spine_y = self.base.bones["thorax"].tail[1]
        st = self.b["sternum"]
        self.assertLess(st.head[1], spine_y - 0.04 * H)  # el esternon esta delante de la columna
        self.assertLess(st.tail[1], st.head[1])  # y su parte inferior, mas adelantada
        self.assertLess(st.tail[2], st.head[2])
        ys = [p[1] for r in self.ribs["L"] for p in r.outline] + [p[1] for p in st.outline]
        self.assertGreater(max(ys) - min(ys), 0.08 * H)  # profundidad de la caja (antes: ~0.016 m)
        self.assertGreater(max(ys), spine_y)  # los angulos costales quedan por detras de la columna

    def test_costal_cartilages(self):
        st = self.b["sternum"]
        for s, sx in (("L", 1), ("R", -1)):
            for k, rib in enumerate(self.ribs[s], start=1):
                end = rib.outline[-1]
                if k <= 7:  # verdaderas: el cartilago llega al borde del esternon
                    self.assertAlmostEqual(perp_distance(end, st.head, st.tail), 0.012 * H, places=9, msg=rib.name)
                    self.assertGreater(end[0] * sx, 0)
                elif k <= 10:  # falsas: reborde costal, por debajo de la punta del esternon
                    self.assertLess(end[2], st.tail[2], rib.name)
                    self.assertGreater(end[0] * sx, 0)
                else:  # flotantes: el contorno termina en la cola del hueso
                    self.assertLess(length(sub(end, rib.tail)), 1e-12, rib.name)

    def test_cage_shape_widens_then_narrows(self):
        width = [max(p[0] for p in r.outline) for r in self.ribs["L"]]
        self.assertEqual(width.index(max(width)) + 1 in (7, 8), True)
        for a, b in zip(width[:6], width[1:7]):
            self.assertLessEqual(a, b)
        for a, b in zip(width[7:], width[8:]):
            self.assertGreaterEqual(a, b)
        self.assertGreater(2 * max(width), 2 * self.base.bones["thigh.L"].head[0])  # torax mas ancho que las caderas

    def test_symmetry(self):
        for k in range(1, 13):
            l, r = self.b[f"rib_{k:02d}.L"], self.b[f"rib_{k:02d}.R"]
            for p, q in zip((l.head, l.tail) + l.outline, (r.head, r.tail) + r.outline):
                self.assertLess(length(sub(mirror_point(p), q)), 1e-12)
        st = self.b["sternum"]
        self.assertAlmostEqual(st.head[0], 0.0, places=12)
        n = len(st.outline)
        for i in range(n // 2):
            self.assertLess(length(sub(mirror_point(st.outline[i]), st.outline[n - 1 - i])), 1e-12)

    def test_ribs_follow_base_proportions(self):
        base2, anat2 = build(length_overrides={"thorax": 0.10, "spine_thoracic": 0.07})
        self.assertEqual(validation.validate_anatomy(base2, anat2), [])
        heads = [anat2.bones[f"rib_{k:02d}.L"].head for k in range(1, 13)]
        top, bottom = base2.bones["thorax"].tail, base2.bones["spine_thoracic"].head
        self.assertLess(heads[0][2], top[2])
        self.assertGreater(heads[-1][2], bottom[2])


def base_ancestor(anat, name):
    cur = name
    while cur in anat.bones:
        cur = anat.bones[cur].parent
    return cur


def reference_group(*path):
    data = json.loads((ROOT / "config" / "reference" / "human_skeleton_reference.json").read_text(encoding="utf-8"))
    node = data["bone_hierarchy"]
    for p in path:
        node = node[p]
    return [anatomy.normalize_reference_name(n) for n in anatomy._leaves(node)]


class TestHandsFeet(unittest.TestCase):
    """Region 3: carpo, metacarpo y falanges; tarso, metatarso y falanges (53 huesos por lado)."""

    def setUp(self):
        self.base, self.anat = build()
        self.b = self.anat.bones
        self.region = {n for n, x in self.b.items() if x.region == "hands_feet"}

    def test_bones_are_exactly_the_reference_hand_and_foot_bones(self):
        expected = set()
        for side in ("left", "right"):
            for g in ("carpal", "metacarpals", "phalanges"):
                expected |= set(reference_group("appendicular_skeleton", "upper_limbs", f"arm_{side}", g))
            for g in ("tarsal", "metatarsals", "phalanges"):
                expected |= set(reference_group("appendicular_skeleton", "lower_limbs", f"leg_{side}", g))
        self.assertEqual(len(expected), 106)
        self.assertEqual(self.region, expected)
        for n in self.region:
            self.assertEqual(self.b[n].reference, (n,))  # un hueso por nombre de referencia

    def test_rooted_in_the_base_hand_and_foot_segments(self):
        hand_groups = ("scaphoid", "lunate", "triquetrum", "pisiform", "trapezium", "trapezoid", "capitate", "hamate",
                       "metacarpal", "thumb", "index", "middle", "ring", "little")
        for n in self.region:
            side = n[-1]
            expected = f"hand.{side}" if n.startswith(hand_groups) else f"foot.{side}"
            self.assertEqual(base_ancestor(self.anat, n), expected, n)

    def test_digit_chains_are_exact(self):
        for n in self.region:
            b = self.b[n]
            if b.parent in self.b and n.split("_")[0] in ("thumb", "index", "middle", "ring", "little", "toe"):
                self.assertLess(length(sub(b.head, self.b[b.parent].tail)), 1e-12, n)  # cada falange nace en la cola de su padre
        for s in "LR":
            self.assertEqual(self.b[f"index_proximal.{s}"].parent, f"metacarpal_2.{s}")
            self.assertEqual(self.b[f"thumb_proximal.{s}"].parent, f"metacarpal_1.{s}")
            self.assertEqual(self.b[f"metacarpal_1.{s}"].parent, f"trapezium.{s}")
            self.assertEqual(self.b[f"toe_1_proximal.{s}"].parent, f"metatarsal_1.{s}")
            self.assertEqual(self.b[f"metatarsal_5.{s}"].parent, f"cuboid.{s}")
            self.assertEqual(self.b[f"calcaneus.{s}"].parent, f"talus.{s}")
            for k, cun in ((1, "medial"), (2, "intermediate"), (3, "lateral")):
                self.assertLess(length(sub(self.b[f"metatarsal_{k}.{s}"].head, self.b[f"{cun}_cuneiform.{s}"].tail)), 1e-12)
            self.assertNotIn(f"thumb_middle.{s}", self.b)  # el pulgar tiene 2 falanges
            self.assertNotIn(f"toe_1_middle.{s}", self.b)  # el dedo gordo tambien

    def test_hand_fits_its_base_segment(self):
        from anatomical_core.geometry import dot, normalize
        for s, sx in (("L", 1), ("R", -1)):
            hb = self.base.bones[f"hand.{s}"]
            axis, ln = normalize(sub(hb.tail, hb.head)), hb.length
            pts = [p for n in self.region if base_ancestor(self.anat, n) == f"hand.{s}" for p in (self.b[n].head, self.b[n].tail)]
            for p in pts:
                t = dot(sub(p, hb.head), axis) / ln
                self.assertGreaterEqual(t, -1e-9)
                self.assertLessEqual(t, 1.0 + 1e-9)
                self.assertLess(perp_distance(p, hb.head, hb.tail), 0.035 * H)
            tips = {f: self.b[f"{f}_distal.{s}"].tail for f in ("thumb", "index", "middle", "ring", "little")}
            self.assertLess(length(sub(tips["middle"], hb.tail)), 0.005)  # el dedo medio llega a la punta del segmento base
            self.assertEqual(min(tips, key=lambda f: tips[f][2]), "middle")  # el mas largo
            self.assertEqual(max((f for f in tips if f != "thumb"), key=lambda f: tips[f][2]), "little")  # el mas corto
            self.assertEqual(max(tips, key=lambda f: tips[f][0] * sx), "thumb")  # pulgar lateral
            self.assertLess(tips["thumb"][1], hb.head[1])  # y algo hacia la palma (anterior)

    def test_foot_rests_on_the_ground(self):
        for s, sx in (("L", 1), ("R", -1)):
            fb = self.base.bones[f"foot.{s}"]
            names = [n for n in self.region if base_ancestor(self.anat, n) == f"foot.{s}"]
            pts = [p for n in names for p in (self.b[n].head, self.b[n].tail)]
            self.assertGreaterEqual(min(p[2] for p in pts), 0.0)  # nada bajo el suelo
            heel = self.b[f"calcaneus.{s}"].tail
            self.assertLess(heel[2], 0.012)  # apoyo del talon
            self.assertGreater(heel[1], fb.head[1] + 0.03)  # detras del tobillo
            for k in range(1, 6):
                self.assertLess(self.b[f"metatarsal_{k}.{s}"].tail[2], 0.012)  # apoyo de las cabezas metatarsianas
            tips = {k: self.b[f"toe_{k}_distal.{s}"].tail for k in range(1, 6)}
            for p in tips.values():
                self.assertLess(p[2], 0.012)
            self.assertLess(abs(tips[1][1] - fb.tail[1]), 0.002)  # el dedo gordo llega a la punta del pie base
            self.assertEqual(min(tips, key=lambda k: tips[k][0] * sx), 1)  # dedo gordo medial
            self.assertEqual(max(tips, key=lambda k: tips[k][0] * sx), 5)  # quinto dedo lateral
            arch = min(self.b[f"navicular.{s}"].tail[2], self.b[f"medial_cuneiform.{s}"].head[2])
            self.assertGreater(arch, 0.02)  # arco longitudinal medial

    def test_scales_with_the_base(self):
        base2, anat2 = build(height_m=1.90)
        self.assertEqual(validation.validate_anatomy(base2, anat2), [])
        self.assertAlmostEqual(anat2.bones["metacarpal_3.L"].length / self.b["metacarpal_3.L"].length, 1.90 / 1.75, places=9)
        self.assertGreaterEqual(min(anat2.bones[n].tail[2] for n in anat2.bones if n.startswith(("toe_", "calcaneus"))), 0.0)


def rig_base_carrier(anat, name):
    """Hueso base que mueve a un hueso del nivel 1 (subiendo por padres del RIG)."""
    return base_ancestor(anat, name)


VERTEBRAE = [f"L{k}" for k in range(5, 0, -1)] + [f"T{k}" for k in range(12, 0, -1)] + [f"C{k}" for k in range(7, 0, -1)]


class TestSpineHead(unittest.TestCase):
    """Region 4: C1-C7, T1-T12, L1-L5, cranium, mandible."""

    def setUp(self):
        self.base, self.anat = build()
        self.b = self.anat.bones

    def test_names_and_traceability_against_the_reference(self):
        region = {n for n, x in self.b.items() if x.region == "spine_head"}
        self.assertEqual(region, set(VERTEBRAE) | {"cranium", "mandible"})
        self.assertEqual(len(region), 26)
        expected_refs = set()
        for g in ("cervical", "thoracic", "lumbar"):
            expected_refs |= set(reference_group("axial_skeleton", "vertebral_column", g))
        expected_refs |= set(reference_group("axial_skeleton", "skull"))
        self.assertEqual({r for n in region for r in self.b[n].reference}, expected_refs)
        self.assertEqual(self.b["C1"].reference, ("C1_atlas",))
        self.assertEqual(self.b["C2"].reference, ("C2_axis",))
        for n in region - {"C1", "C2"}:
            self.assertEqual(self.b[n].reference, (n,))

    def test_reference_is_now_fully_covered(self):
        cov = anatomy.coverage(self.anat, self.base)
        self.assertEqual(cov["pending"], [])
        self.assertEqual(len(cov["implemented"]), 183)
        self.assertEqual(len(cov["implemented"]) + len(cov["base"]), 185)

    def test_anatomical_chain_bottom_up_as_specified(self):
        chain = ["sacrum_fused"] + VERTEBRAE + ["cranium", "mandible"]
        for lower, upper in zip(chain, chain[1:]):
            self.assertEqual(self.b[upper].anatomical_parent, lower, upper)

    def test_vertebral_column_is_continuous_and_anchored_to_the_base(self):
        self.assertLess(length(sub(self.b["L5"].head, self.b["sacrum_fused"].head)), 1e-12)  # L5 sobre el sacro
        for lower, upper in zip(VERTEBRAE, VERTEBRAE[1:]):
            self.assertLess(length(sub(self.b[upper].head, self.b[lower].tail)), 1e-12, upper)
        pivots = (("L1", "spine_thoracic"), ("T1", "neck"), ("C1", "head"))
        for v, seg in pivots:
            self.assertLess(length(sub(self.b[v].tail, self.base.bones[seg].head)), 1e-12, v)
        self.assertLess(length(sub(self.b["cranium"].head, self.b["C1"].tail)), 1e-12)
        self.assertLess(length(sub(self.b["cranium"].tail, self.base.bones["head"].tail)), 1e-12)

    def test_rig_carriers(self):
        carrier = {**{f"L{k}": "spine_lumbar" for k in range(1, 6)},
                   **{f"T{k}": "spine_thoracic" for k in range(7, 13)}, **{f"T{k}": "thorax" for k in range(1, 7)},
                   **{f"C{k}": "neck" for k in range(1, 8)}, "cranium": "head", "mandible": "head"}
        for n, seg in carrier.items():
            self.assertEqual(rig_base_carrier(self.anat, n), seg, n)
        self.assertEqual(self.b["mandible"].parent, "cranium")

    def _sagittal_offsets(self, names):
        """Desplazamiento en Y (+atras) del centro de cada vertebra respecto a la linea base a su altura."""
        out = []
        for n in names:
            v = self.b[n]
            c = tuple((a + b) / 2 for a, b in zip(v.head, v.tail))
            seg = self.base.bones[rig_base_carrier(self.anat, n)]
            t = (c[2] - seg.head[2]) / (seg.tail[2] - seg.head[2])
            out.append(c[1] - (seg.head[1] + t * (seg.tail[1] - seg.head[1])))
        return out

    def test_s_curve(self):
        lumbar = self._sagittal_offsets([f"L{k}" for k in range(5, 0, -1)])
        thoracic = self._sagittal_offsets([f"T{k}" for k in range(12, 6, -1)]) + self._sagittal_offsets([f"T{k}" for k in range(6, 0, -1)])
        cervical = self._sagittal_offsets([f"C{k}" for k in range(7, 0, -1)])
        self.assertTrue(all(o < 0 for o in lumbar))  # lordosis lumbar: hacia delante (-Y)
        self.assertTrue(all(o > 0 for o in thoracic))  # cifosis toracica: hacia atras (+Y)
        self.assertTrue(all(o < 0 for o in cervical))  # lordosis cervical: hacia delante
        self.assertEqual(lumbar.index(min(lumbar)), 2)  # vertice en L3
        self.assertIn(thoracic.index(max(thoracic)), (5, 6))  # vertice en T7-T6
        self.assertEqual(cervical.index(min(cervical)), 3)  # vertice en C4
        self.assertTrue(0.008 * H < -min(lumbar) < 0.012 * H)  # calibrada para LL L1-S1 = 51.9 grados sobre la base v2 (test_lumbar_pelvis)
        self.assertTrue(0.006 * H < max(thoracic) < 0.011 * H)
        self.assertTrue(0.002 * H < -min(cervical) < 0.006 * H)
        for n in VERTEBRAE + ["cranium", "mandible"]:  # todo en el plano medio (X = 0)
            self.assertAlmostEqual(self.b[n].head[0], 0.0, places=12)
            self.assertAlmostEqual(self.b[n].tail[0], 0.0, places=12)

    def test_vertebra_sizes_are_uniform_per_region_and_match_the_rib_levels(self):
        for group in ([f"L{k}" for k in range(1, 6)], [f"T{k}" for k in range(1, 13)], [f"C{k}" for k in range(1, 8)]):
            heights = [self.b[n].tail[2] - self.b[n].head[2] for n in group]
            mean = sum(heights) / len(heights)
            for hgt in heights:
                self.assertLess(abs(hgt - mean) / mean, 0.05, group)
        for k in range(1, 13):  # cada costilla nace a la altura media de su vertebra
            t = self.b[f"T{k}"]
            self.assertLess(abs(self.b[f"rib_{k:02d}.L"].head[2] - (t.head[2] + t.tail[2]) / 2), 0.002)

    def test_head(self):
        cr, md = self.b["cranium"], self.b["mandible"]
        self.assertLess(md.head[1], cr.head[1])  # ATM por delante de los condilos occipitales
        self.assertLess(md.tail[1], md.head[1] - 0.05)  # menton hacia delante
        self.assertLess(md.tail[2], md.head[2])  # y por debajo
        self.assertLess(min(p[1] for p in cr.outline), cr.head[1] - 0.08)  # la cara queda delante
        self.assertGreater(max(p[1] for p in cr.outline), cr.head[1] + 0.05)  # el occipital detras
        for p in cr.outline:
            self.assertAlmostEqual(p[0], 0.0, places=12)  # perfil medio-sagital
        n = len(md.outline)
        for i in range(n // 2):  # mandibula en U simetrica
            self.assertLess(length(sub(mirror_point(md.outline[i]), md.outline[n - 1 - i])), 1e-12)


class TestLongBones(unittest.TestCase):
    """Region 5: escapula y huesos largos."""

    SPEC_ANATOMICAL = {"scapula": "clavicle", "humerus": "scapula", "radius": "humerus", "ulna": "humerus",
                       "femur": "ilium", "patella": "femur", "tibia": "femur", "fibula": "femur"}
    RIG = {"scapula": "clavicle", "humerus": "upper_arm", "radius": "forearm", "ulna": "forearm",
           "femur": "thigh", "patella": "thigh", "tibia": "shin", "fibula": "shin"}

    def setUp(self):
        self.base, self.anat = build()
        self.b = self.anat.bones

    def test_names_and_traceability(self):
        region = {n for n, x in self.b.items() if x.region == "long_bones"}
        self.assertEqual(region, {f"{n}.{s}" for n in self.SPEC_ANATOMICAL for s in "LR"})
        expected = set()
        for side in ("left", "right"):
            expected |= set(reference_group("appendicular_skeleton", "pectoral_girdle", side)) - {"clavicle.L", "clavicle.R"}
            arm = reference_group("appendicular_skeleton", "upper_limbs", f"arm_{side}", "humerus") + \
                reference_group("appendicular_skeleton", "upper_limbs", f"arm_{side}", "forearm")
            leg = sum((reference_group("appendicular_skeleton", "lower_limbs", f"leg_{side}", g)
                       for g in ("femur", "patella", "lower_leg")), [])
            expected |= set(arm) | set(leg)
        self.assertEqual(region, expected)
        for n in region:
            self.assertEqual(self.b[n].reference, (n,))

    def test_anatomical_hierarchy_as_specified_and_rig_carriers(self):
        for s in "LR":
            for bone, ap in self.SPEC_ANATOMICAL.items():
                expected = f"{ap}.{s}"
                self.assertEqual(self.b[f"{bone}.{s}"].anatomical_parent, expected, bone)
                self.assertEqual(self.b[f"{bone}.{s}"].parent, f"{self.RIG[bone]}.{s}", bone)

    def test_long_bones_coincide_with_their_base_segments(self):
        for s in "LR":
            for bone, seg in (("humerus", "upper_arm"), ("femur", "thigh"), ("tibia", "shin")):
                self.assertLess(length(sub(self.b[f"{bone}.{s}"].head, self.base.bones[f"{seg}.{s}"].head)), 1e-12)
                self.assertLess(length(sub(self.b[f"{bone}.{s}"].tail, self.base.bones[f"{seg}.{s}"].tail)), 1e-12)
            self.assertLess(length(sub(self.b[f"scapula.{s}"].head, self.base.bones[f"upper_arm.{s}"].head)), 1e-12)  # glenoide
            self.assertLess(length(sub(self.b[f"femur.{s}"].head, self.b[f"ilium.{s}"].tail)), 1e-12)  # acetabulo

    def test_acromion_coincides_with_the_clavicle_tip_and_the_arm_hangs_from_the_glenoid(self):
        """Base v2: la clavicula va del manubrio al acromion; la glenoides (= pivote del hombro) queda 2.2 cm por
        debajo y 2 cm por delante del acromion, que coincide con el extremo de la clavicula."""
        for s in "LR":
            clav = self.base.bones[f"clavicle.{s}"]
            sc = self.b[f"scapula.{s}"]
            self.assertLess(length(sub(sc.outline[1], clav.tail)), 1e-12)  # acromion = extremo de la clavicula
            self.assertLess(length(sub(sc.head, self.base.joints[f"shoulder.{s}"].pivot)), 1e-12)  # glenoides = hombro
            d = sub(sc.outline[1], sc.head)
            self.assertAlmostEqual(d[2], 0.022, places=6)  # acromion por encima de la glenoides
            self.assertAlmostEqual(d[1], 0.020, places=6)  # y por detras
            self.assertAlmostEqual(abs(d[0]), 0.005, places=6)  # y algo lateral
            arm = self.base.bones[f"upper_arm.{s}"]
            self.assertEqual(arm.parent, f"clavicle.{s}")
            self.assertGreater(length(sub(arm.head, clav.tail)), 0.02)  # el brazo ya no nace en el extremo de la clavicula

    def test_anatomical_position_and_distal_attachments(self):
        for s, sx in (("L", 1), ("R", -1)):
            r, u = self.b[f"radius.{s}"], self.b[f"ulna.{s}"]
            elbow = self.base.bones[f"forearm.{s}"].head
            wrist = self.base.bones[f"hand.{s}"].head
            self.assertGreater(r.head[0] * sx, u.head[0] * sx)  # radio lateral (posicion anatomica)
            self.assertGreater(r.tail[0] * sx, u.tail[0] * sx)
            self.assertGreater(u.head[1], elbow[1])  # olecranon detras del codo
            self.assertLess(perp_distance(wrist, r.tail, u.tail), 0.006)  # la muneca entre radio y cubito distales
            self.assertTrue(min(r.tail[0] * sx, u.tail[0] * sx) < wrist[0] * sx < max(r.tail[0] * sx, u.tail[0] * sx))
            tib, fib = self.b[f"tibia.{s}"], self.b[f"fibula.{s}"]
            ankle = self.base.bones[f"foot.{s}"].head
            medial_malleolus = tib.outline[-1]
            self.assertTrue(medial_malleolus[0] * sx < ankle[0] * sx < fib.tail[0] * sx)  # tobillo entre maleolos
            self.assertGreater(fib.head[0] * sx, tib.head[0] * sx)  # perone lateral
            self.assertGreater(fib.head[1], tib.head[1])  # y algo posterior
            knee = self.base.bones[f"shin.{s}"].head
            pat = self.b[f"patella.{s}"]
            self.assertLess(max(pat.head[1], pat.tail[1]), knee[1] - 0.03)  # rotula delante de la rodilla
            self.assertTrue(pat.tail[2] < knee[2] < pat.head[2])
            fem = self.b[f"femur.{s}"]
            self.assertGreater(fem.outline[1][0] * sx, fem.head[0] * sx)  # trocanter mayor lateral a la cabeza

    def test_scapula_lies_on_the_back_of_the_thorax(self):
        for s, sx in (("L", 1), ("R", -1)):
            sc = self.b[f"scapula.{s}"]
            ribs_back = max(p[1] for k in range(1, 13) for p in self.b[f"rib_{k:02d}.{s}"].outline)
            self.assertGreater(sc.tail[1], ribs_back)  # el angulo inferior queda por detras de las costillas
            t7 = self.b["T7"]
            self.assertLess(abs(sc.tail[2] - (t7.head[2] + t7.tail[2]) / 2), 0.01)  # a la altura de T7
            medial = [sc.outline[2], sc.tail]  # angulo superior e inferior: borde medial
            for p in medial:
                self.assertTrue(0.03 * H < p[0] * sx < 0.06 * H)


class TestAnatomyValidatorDetectsProblems(unittest.TestCase):
    def setUp(self):
        self.base, self.anat = build()

    def with_bone(self, name, **changes):
        return dataclasses.replace(self.anat, bones={**self.anat.bones, name: dataclasses.replace(self.anat.bones[name], **changes)})

    def test_broken_anchor(self):
        b = self.anat.bones["ilium.L"]
        m = self.with_bone("ilium.L", tail=(b.tail[0] + 0.01, b.tail[1], b.tail[2]))
        self.assertIn("ANAT_ANCHOR", codes(validation.validate_anatomy(self.base, m)))

    def test_unknown_parent_and_not_rooted(self):
        self.assertIn("ANAT_PARENT_UNKNOWN", codes(validation.validate_anatomy(self.base, self.with_bone("coccyx_fused", parent="fantasma"))))
        m = self.with_bone("sacrum_fused", parent="coccyx_fused")  # ciclo sacro <-> coxis
        self.assertIn("ANAT_CYCLE", codes(validation.validate_anatomy(self.base, m)))

    def test_name_collision_and_references(self):
        bones = dict(self.anat.bones)
        bones["pelvis"] = dataclasses.replace(bones["coccyx_fused"], name="pelvis")
        self.assertIn("ANAT_NAME_COLLISION", codes(validation.validate_anatomy(self.base, dataclasses.replace(self.anat, bones=bones))))
        self.assertIn("ANAT_REFERENCE_UNKNOWN", codes(validation.validate_anatomy(self.base, self.with_bone("coccyx_fused", reference=("no_existe",)))))
        self.assertIn("ANAT_REFERENCE_DUPLICATE", codes(validation.validate_anatomy(self.base, self.with_bone("coccyx_fused", reference=("sacrum_fused",)))))
        self.assertIn("ANAT_REFERENCE_IN_BASE", codes(validation.validate_anatomy(self.base, self.with_bone("coccyx_fused", reference=("clavicle.L",)))))
        self.assertIn("ANAT_NO_REFERENCE", codes(validation.validate_anatomy(self.base, self.with_bone("coccyx_fused", reference=()))))

    def test_asymmetry_and_outline_asymmetry(self):
        r = self.anat.bones["ilium.R"]
        moved = self.with_bone("ilium.R", head=(r.head[0] - 0.01, r.head[1], r.head[2]))
        self.assertTrue({"ANAT_ASYMMETRIC", "ANAT_LENGTH_MISMATCH"} & codes(validation.validate_anatomy(self.base, moved)))
        outline = list(r.outline)
        outline[2] = (outline[2][0] - 0.02, outline[2][1], outline[2][2])
        self.assertIn("ANAT_OUTLINE_ASYMMETRIC", codes(validation.validate_anatomy(self.base, self.with_bone("ilium.R", outline=tuple(outline)))))

    def test_anatomical_parent_errors(self):
        self.assertIn("ANAT_ANATOMICAL_PARENT_UNKNOWN", codes(validation.validate_anatomy(self.base, self.with_bone("C1", anatomical_parent="fantasma"))))
        m = self.with_bone("L5", anatomical_parent="L4")  # L5 -> L4 -> L5
        self.assertIn("ANAT_ANATOMICAL_CYCLE", codes(validation.validate_anatomy(self.base, m)))

    def test_built_on_a_different_base(self):
        other_base = build_model(load_config(height_m=1.60))
        self.assertIn("ANAT_BASE_MISMATCH", codes(validation.validate_anatomy(other_base, self.anat)))

    def test_bad_configs_are_rejected(self):
        with self.assertRaises(ConfigError):
            anatomy._point_spec({"at": "pelvis.tail", "lerp": ["a.head", "b.head", 0.5]}, "x")
        with self.assertRaises(ConfigError):
            anatomy.resolve_point_ref("pelvis.middle", self.base, {})
        with self.assertRaises(ConfigError):
            anatomy.resolve_point_ref("no_existe.head", self.base, {})


if __name__ == "__main__":
    unittest.main()
