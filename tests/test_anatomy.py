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
                         {"sacrum_fused", "coccyx_fused", "hip_bone.L", "hip_bone.R"})
        self.assertEqual(self.b["sacrum_fused"].parent, "pelvis")
        self.assertEqual(self.b["coccyx_fused"].parent, "sacrum_fused")
        self.assertEqual(self.b["hip_bone.L"].parent, "pelvis")
        self.assertEqual(self.b["hip_bone.R"].parent, "pelvis")
        self.assertEqual(self.b["hip_bone.R"].reference, ("ilium.R", "ischium.R", "pubis.R"))
        cov = anatomy.coverage(self.anat, self.base)["implemented"]
        for r in ("sacrum_fused", "coccyx_fused", "ilium.L", "ischium.L", "pubis.L", "ilium.R", "ischium.R", "pubis.R"):
            self.assertIn(r, cov)

    def test_femoral_heads_are_anchored_exactly_in_the_acetabulum(self):
        for s in "LR":
            self.assertLess(length(sub(self.b[f"hip_bone.{s}"].tail, self.base.bones[f"thigh.{s}"].head)), 1e-12)
        self.assertLess(length(sub(self.b["sacrum_fused"].head, self.base.bones["spine_lumbar"].head)), 1e-12)
        self.assertLess(length(sub(self.b["coccyx_fused"].head, self.b["sacrum_fused"].tail)), 1e-12)

    def test_anatomical_orientation(self):
        sac = self.b["sacrum_fused"]
        self.assertLess(sac.tail[2], sac.head[2])  # baja
        self.assertGreater(sac.tail[1], sac.head[1])  # hacia atras
        for s, sx in (("L", 1), ("R", -1)):
            hb = self.b[f"hip_bone.{s}"]
            self.assertLess(abs(hb.head[0]), abs(hb.tail[0]))  # la sacroiliaca es medial al acetabulo
            self.assertGreater(hb.head[2], hb.tail[2])  # y esta por encima
            self.assertGreater(hb.head[1], hb.tail[1])  # y por detras
            hip_z = self.base.bones[f"thigh.{s}"].head[2]
            crest, asis, symphysis, ischial = hb.outline[2], hb.outline[3], hb.outline[5], hb.outline[6]
            self.assertEqual(max(p[2] for p in hb.outline), crest[2])  # la cresta iliaca es lo mas alto
            self.assertGreater(crest[2], hip_z)
            self.assertLess(asis[1], 0.0)  # espina iliaca anterosuperior: delante
            self.assertLess(symphysis[1], 0.0)  # sinfisis: delante, abajo y casi en la linea media
            self.assertLess(symphysis[2], hip_z)
            self.assertLess(abs(symphysis[0]), 0.01 * H)
            self.assertEqual(min(p[2] for p in hb.outline), ischial[2])  # la tuberosidad isquiatica es lo mas bajo
            self.assertGreater(crest[0] * sx, self.base.bones[f"thigh.{s}"].head[0] * sx)  # pelvis mas ancha que las caderas

    def test_symmetry_including_outlines(self):
        l, r = self.b["hip_bone.L"], self.b["hip_bone.R"]
        for p, q in zip((l.head, l.tail) + l.outline, (r.head, r.tail) + r.outline):
            self.assertLess(length(sub(mirror_point(p), q)), 1e-12)
        for n in ("sacrum_fused", "coccyx_fused"):
            self.assertAlmostEqual(self.b[n].head[0], 0.0, places=12)
            self.assertAlmostEqual(self.b[n].tail[0], 0.0, places=12)

    def test_scales_with_the_base_proportions_and_stays_anchored(self):
        base2, anat2 = build(height_m=1.90)
        self.assertAlmostEqual(anat2.bones["sacrum_fused"].length / self.b["sacrum_fused"].length, 1.90 / 1.75, places=9)
        self.assertEqual(validation.validate_anatomy(base2, anat2), [])
        base3, anat3 = build(length_overrides={"pelvis": 0.06, "thigh": 0.27})
        self.assertEqual(validation.validate_anatomy(base3, anat3), [])
        self.assertLess(length(sub(anat3.bones["hip_bone.L"].tail, base3.bones["thigh.L"].head)), 1e-12)
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
        self.assertEqual(self.b["sternum"].parent, "thorax")
        self.assertEqual(self.b["sternum"].reference, ("manubrium", "sternum_body", "xiphoid_process"))
        for s in "LR":
            for k, rib in enumerate(self.ribs[s], start=1):
                self.assertEqual(rib.parent, "thorax" if k <= 6 else "spine_thoracic", rib.name)
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
        for r in self.ribs["L"]:  # cada cabeza costal pegada a la columna (articulacion costovertebral)
            seg = self.base.bones[r.parent]
            self.assertLess(perp_distance(r.head, seg.head, seg.tail), 0.02 * H)

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


class TestAnatomyValidatorDetectsProblems(unittest.TestCase):
    def setUp(self):
        self.base, self.anat = build()

    def with_bone(self, name, **changes):
        return dataclasses.replace(self.anat, bones={**self.anat.bones, name: dataclasses.replace(self.anat.bones[name], **changes)})

    def test_broken_anchor(self):
        b = self.anat.bones["hip_bone.L"]
        m = self.with_bone("hip_bone.L", tail=(b.tail[0] + 0.01, b.tail[1], b.tail[2]))
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
        r = self.anat.bones["hip_bone.R"]
        moved = self.with_bone("hip_bone.R", head=(r.head[0] - 0.01, r.head[1], r.head[2]))
        self.assertTrue({"ANAT_ASYMMETRIC", "ANAT_LENGTH_MISMATCH"} & codes(validation.validate_anatomy(self.base, moved)))
        outline = list(r.outline)
        outline[2] = (outline[2][0] - 0.02, outline[2][1], outline[2][2])
        self.assertIn("ANAT_OUTLINE_ASYMMETRIC", codes(validation.validate_anatomy(self.base, self.with_bone("hip_bone.R", outline=tuple(outline)))))

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
