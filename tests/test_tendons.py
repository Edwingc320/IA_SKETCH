"""Capa de tendones (rama muscle-model): unidades musculo-tendinosas de todo el cuerpo, sobre el hueso, con tendon y vientre."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import bpy  # noqa: F401
    HAVE_BPY = True
except ImportError:
    HAVE_BPY = False

from anatomical_core import anatomy, articulations, tendons  # noqa: E402
from anatomical_core.config import ConfigError, load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

TEST_OUT = ROOT / "output" / "_test"


def build_all(height=None, data=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    art = articulations.build_articulations(base, anat, articulations.load_articulation_data())
    return base, anat, art, tendons.build_tendons(base, anat, art, data if data is not None else tendons.load_tendon_data())


def path_length(points):
    return sum(length(sub(b, a)) for a, b in zip(points, points[1:]))


class TestTendonLayer(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art, self.m = build_all()
        self.t = self.m.tendons

    def test_counts_and_validation(self):
        self.assertEqual(len(self.t), 2 * (19 + 37 + 31))  # las 160 originales + 12 + la cintilla iliotibial (CM-5): triceps de 3 cabezas, cabeza corta del biceps femoral, gastrocnemio lateral, pectoral menor, trapecio medio e inferior
        self.assertEqual(tendons.validate_tendons(self.base, self.anat, self.art, self.m), [])
        for n, x in self.t.items():
            self.assertTrue(x.muscles, n)

    def test_the_layer_covers_every_region_of_the_body(self):
        hosts = {s.bone.split(".")[0] for x in self.t.values() for s in x.sites}
        required = {"cranium", "mandible", "sternum", "clavicle", "scapula", "humerus", "radius", "ulna", "pisiform", "metacarpal_1", "metacarpal_2", "thumb_proximal", "index_middle",
                    "little_distal", "ilium", "ischium", "pubis", "femur", "patella", "tibia", "fibula", "calcaneus", "navicular", "medial_cuneiform", "metatarsal_1", "toe_1_distal",
                    "toe_5_distal", "rib_04", "rib_12", "L2", "L3", "C2", "C7", "T4", "sacrum"}
        self.assertEqual(sorted(required - hosts), [])

    def test_tendon_lengths_follow_the_declared_visual_classes(self):
        for n, x in self.t.items():
            total = x.total_length
            if x.origin_class:
                self.assertAlmostEqual(path_length(x.origin_tendon), tendons.CLASSES[x.origin_class] * total, places=9, msg=n)
                self.assertLess(length(sub(x.origin_tendon[0], x.sites[0].point)), 1e-12, n)  # nace en el origen oseo
            if x.insertion_class:
                self.assertAlmostEqual(path_length(x.insertion_tendon), tendons.CLASSES[x.insertion_class] * total, places=9, msg=n)
                self.assertLess(length(sub(x.insertion_tendon[-1], x.sites[-1].point)), 1e-12, n)  # y termina en la insercion
            belly = x.belly
            self.assertGreaterEqual(path_length(belly), tendons.MIN_BELLY * total - 1e-12, n)
            # el vientre une las dos uniones miotendinosas y las tres partes recomponen la unidad
            parts = path_length(x.origin_tendon) + path_length(belly) + path_length(x.insertion_tendon)
            self.assertAlmostEqual(parts, total, places=9, msg=n)
            if x.origin_class:
                self.assertLess(length(sub(belly[0], x.origin_tendon[-1])), 1e-9, n)
            if x.insertion_class:
                self.assertLess(length(sub(belly[-1], x.insertion_tendon[0])), 1e-9, n)

    def test_long_tendons_pass_through_their_bony_guides(self):
        def vias(n):
            return [s.landmark or s.structure for s in self.t[n].sites[1:-1]]
        self.assertEqual(vias("flexor_carpi_radialis.L"), ["trapezium_tubercle.L"])
        self.assertEqual(vias("flexor_pollicis_longus.L"), ["scaphoid_tubercle.L"])
        for f in ("index", "middle", "ring", "little"):
            for kind in ("flexor_digitorum_superficialis", "flexor_digitorum_profundus"):
                self.assertEqual(len(self.t[f"{kind}_{f}.L"].sites), 3, kind)  # origen, tunel carpiano, insercion
            self.assertEqual(self.t[f"extensor_digitorum_{f}.L"].sites[1].bone, "radius.L")  # por el dorso de la muneca
        for n, guide in (("tibialis_posterior.L", "medial_malleolus.L"), ("peroneus_longus.L", "lateral_malleolus.L"), ("peroneus_brevis.L", "lateral_malleolus.L"),
                         ("flexor_digitorum_longus_3.L", "medial_malleolus.L"), ("flexor_hallucis_longus.L", "sustentaculum_tali.L")):
            self.assertIn(guide, vias(n), n)
        self.assertEqual(self.t["biceps_long_head.L"].sites[1].bone, "humerus.L")  # surco intertubercular

    def test_named_anchors_match_the_bone_model(self):
        for s in "LR":
            t = self.t
            site = lambda n, i: t[f"{n}.{s}"].sites[i]  # noqa: E731
            self.assertEqual(site("gastrocnemius", -1).landmark, f"calcaneal_tuberosity.{s}")  # tendon calcaneo
            self.assertEqual(site("soleus", -1).landmark, f"calcaneal_tuberosity.{s}")
            self.assertEqual(site("soleus", 0).landmark, f"fibular_head.{s}")
            self.assertEqual({site(n, -1).landmark for n in ("rectus_femoris", "vastus_lateralis", "vastus_medialis", "vastus_intermedius")}, {f"patella_base.{s}"})  # cuadriceps
            self.assertEqual({site(n, 0).landmark for n in ("semitendinosus", "semimembranosus", "biceps_femoris")}, {f"ischial_tuberosity.{s}"})  # isquiotibiales
            self.assertEqual(site("biceps_femoris", -1).landmark, f"fibular_head.{s}")
            self.assertEqual(site("tensor_fasciae_latae", -1).landmark, f"gerdy_tubercle.{s}")  # cintilla iliotibial
            self.assertEqual({site(n, -1).landmark for n in ("supraspinatus",)}, {f"greater_tubercle.{s}"})
            self.assertEqual(site("subscapularis", -1).landmark, f"lesser_tubercle.{s}")
            self.assertEqual({site(n, -1).landmark for n in ("deltoid_acromial", "deltoid_clavicular", "deltoid_spinal")}, {f"deltoid_tuberosity.{s}"})
            self.assertEqual(site("triceps_long_head", -1).landmark, f"olecranon.{s}")
            self.assertEqual(site("biceps_long_head", -1).landmark, f"radial_tuberosity.{s}")
            self.assertEqual({site(n, 0).landmark for n in ("flexor_carpi_radialis", "flexor_carpi_ulnaris", "pronator_teres")}, {f"medial_epicondyle.{s}"})
            self.assertEqual({site(n, 0).landmark for n in ("extensor_carpi_radialis_brevis", "extensor_carpi_ulnaris")}, {f"lateral_epicondyle.{s}"})
            self.assertEqual(site("sternocleidomastoid", -1).landmark, f"mastoid_process.{s}")
            self.assertEqual({site(n, -1).landmark for n in ("psoas_major", "iliacus")}, {f"lesser_trochanter.{s}"})  # iliopsoas

    def test_every_anchor_is_on_a_bone_and_weak_sources_say_verify(self):
        tol = tendons.SITE_TOL_M
        weak = {k for k, s in self.m.sources.items() if s["reliability"] == "baja"}
        for n, x in self.t.items():
            for s in x.sites:
                self.assertLess(articulations.bone_distance(s.point, s.bone, self.base, self.anat, self.art.surfaces), tol, (n, s.kind))
            if not x.sources or set(x.sources) <= weak:
                self.assertIn("verificar", x.notes.lower(), n)
        for f in tendons.FILES:
            d = json.loads((ROOT / "config" / "muscles" / f"{f}.json").read_text(encoding="utf-8"))
            self.assertEqual(d["tendon_classes"], {"corto": 0.10, "medio": 0.25, "largo": 0.45})
            self.assertIn("CONVENCION VISUAL", d["tendon_length_note"])  # la unica cifra no anatomica esta declarada como convencion

    def test_symmetry_and_scale(self):
        for n, x in self.t.items():
            if n.endswith(".L"):
                for a, b in zip(x.sites, self.t[n[:-2] + ".R"].sites):
                    self.assertLess(length(sub(mirror_point(a.point), b.point)), 1e-12, n)
        _, _, _, small = build_all(1.5)
        k = 1.5 / self.base.height_m
        for n, x in self.t.items():
            for a, b in zip(x.sites, small.tendons[n].sites):
                self.assertLess(length(sub(tuple(k * c for c in a.point), b.point)), 1e-9, n)
            self.assertAlmostEqual(small.tendons[n].total_length, k * x.total_length, places=9)

    def test_bad_data_is_rejected(self):
        import copy
        data = copy.deepcopy(tendons.load_tendon_data())
        data[0]["tendons"][0]["origin"] = {"landmark": "no_such_landmark.L"}
        with self.assertRaises(ConfigError):
            build_all(data=data)
        data = copy.deepcopy(tendons.load_tendon_data())
        data[0]["tendons"][0]["insertion_tendon"] = "enorme"
        with self.assertRaises(ConfigError):
            build_all(data=data)
        data = copy.deepcopy(tendons.load_tendon_data())
        data[1]["tendons"][0]["origin_tendon"], data[1]["tendons"][0]["insertion_tendon"] = "largo", "largo"  # 90 %: sin vientre
        _, anat, art, bad = build_all(data=data)
        self.assertIn("TEN_NO_BELLY", [i.code for i in tendons.validate_tendons(self.base, anat, art, bad)])
        data = copy.deepcopy(tendons.load_tendon_data())
        data[2]["tendons"][0]["insertion"] = {"bone": "femur.L", "point": {"at": "thigh.L.head", "offset_h": [0.2, 0.0, 0.0]}, "structure": "lejos"}
        _, anat, art, bad = build_all(data=data)
        self.assertIn("TEN_SITE_OFF_BONE", [i.code for i in tendons.validate_tendons(self.base, anat, art, bad)])
        data = copy.deepcopy(tendons.load_tendon_data())
        data[2]["tendons"][0]["origin_tendon"] = data[2]["tendons"][0]["insertion_tendon"] = None
        _, anat, art, bad = build_all(data=data)
        self.assertIn("TEN_NO_TENDON", [i.code for i in tendons.validate_tendons(self.base, anat, art, bad)])


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestTendonsInBlender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from anatomical_core import anatomy_pipeline, scene, tendons_scene
        cls.scene, cls.tendons_scene = scene, tendons_scene
        TEST_OUT.mkdir(parents=True, exist_ok=True)
        cls.path = TEST_OUT / "tendons_a.blend"
        cls.res = anatomy_pipeline.generate(cls.path, preview=False, log=lambda *_: None)

    def test_file_validates_and_objects_follow_their_bones(self):
        import bpy
        from mathutils import Euler
        self.scene.open_blend(self.path)
        snap = self.tendons_scene.read_back_tendons()
        base, anat = self.res.base, self.res.anatomy
        art = articulations.build_articulations(base, anat, articulations.load_articulation_data())
        model = tendons.build_tendons(base, anat, art, tendons.load_tendon_data())
        self.assertEqual(tendons.validate_tendons_snapshot(model, snap), [])
        expected = sum((1 if t.origin_class else 0) + (1 if t.insertion_class else 0) + 1 for t in model.tendons.values())
        self.assertEqual(len(snap), expected)
        # al flexionar la rodilla, el tendon de Aquiles (en el calcaneo) sigue a la pierna y el vientre (en el femur) se queda
        arm = bpy.data.objects["AC_Armature"]
        pb = arm.pose.bones["shin.L"]
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = Euler((0.8, 0.0, 0.0))
        bpy.context.view_layer.update()
        after = self.tendons_scene.read_back_tendons()
        moved = lambda n: length(sub(tuple(after[n]["points"][1]), tuple(snap[n]["points"][1])))  # noqa: E731
        self.assertGreater(moved("TEN_insertion_gastrocnemius.L"), 0.05)
        self.assertLess(moved("TEN_belly_gastrocnemius.L"), 1e-4)  # el vientre cuelga del femur: no se mueve con la pierna
        self.assertLess(length(sub(tuple(after["TEN_belly_gastrocnemius.L"]["points"][0]), tuple(snap["TEN_belly_gastrocnemius.L"]["points"][0]))), 1e-4)
        self.assertEqual((snap["TEN_insertion_gastrocnemius.L"]["parent_bone"], snap["TEN_belly_gastrocnemius.L"]["parent_bone"]), ("calcaneus.L", "femur.L"))


if __name__ == "__main__":
    unittest.main()
