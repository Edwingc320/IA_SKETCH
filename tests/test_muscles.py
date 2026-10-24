"""Capa muscular (rama muscle-model): gluteos anclados a los hitos oseos, a menos de 12 mm de la superficie de su hueso."""
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

from anatomical_core import anatomy, articulations, muscles  # noqa: E402
from anatomical_core.config import ConfigError, load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

TEST_OUT = ROOT / "output" / "_test"


def build_all(height=None, data=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    art = articulations.build_articulations(base, anat, articulations.load_articulation_data())
    return base, anat, art, muscles.build_muscles(base, anat, art, data if data is not None else muscles.load_muscle_data())


class TestGlutealMuscles(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art, self.m = build_all()

    def sites(self, name, kind):
        return [s for s in self.m.muscles[name].sites if s.kind == kind]

    def test_three_muscles_per_side_validate_without_issues(self):
        self.assertEqual(sorted(self.m.muscles), sorted(f"gluteus_{k}.{s}" for k in ("maximus", "medius", "minimus") for s in "LR"))
        self.assertEqual(muscles.validate_muscles(self.base, self.anat, self.art, self.m), [])
        for m in self.m.muscles.values():
            self.assertTrue(self.sites(m.name, "origin") and self.sites(m.name, "insertion"), m.name)
            self.assertEqual(len(m.fibers), len(self.sites(m.name, "origin")) * len(self.sites(m.name, "insertion")))

    def test_origins_are_on_the_iliac_surface_sacrum_and_thoracolumbar_crest(self):
        for s in "LR":
            mx = {x.landmark: x for x in self.sites(f"gluteus_maximus.{s}", "origin")}
            self.assertEqual(set(mx), {f"posterior_gluteal_line.{s}", f"sacral_lateral_mass.{s}", f"iliac_crest.{s}"})
            self.assertEqual({x.bone for x in mx.values()}, {f"ilium.{s}", "sacrum"})
            for name, lines in ((f"gluteus_medius.{s}", {"posterior_gluteal_line", "anterior_gluteal_line"}),
                                (f"gluteus_minimus.{s}", {"anterior_gluteal_line", "inferior_gluteal_line"})):
                got = self.sites(name, "origin")
                self.assertEqual({x.landmark.split(".")[0] for x in got}, lines, name)
                self.assertTrue(all(x.bone == f"ilium.{s}" for x in got), name)

    def test_insertions_reach_the_femur_the_iliotibial_tract_and_the_greater_trochanter(self):
        for s, sx in (("L", 1), ("R", -1)):
            mx = {x.bone: x for x in self.sites(f"gluteus_maximus.{s}", "insertion")}
            self.assertEqual(set(mx), {f"femur.{s}", f"tibia.{s}"})  # tuberosidad glutea y cintilla iliotibial (tuberculo de Gerdy)
            self.assertEqual(mx[f"femur.{s}"].landmark, f"gluteal_tuberosity.{s}")
            self.assertEqual(mx[f"tibia.{s}"].landmark, f"gerdy_tubercle.{s}")
            gt = self.art.attachments[f"greater_trochanter.{s}"].point
            (med,), (mini,) = self.sites(f"gluteus_medius.{s}", "insertion"), self.sites(f"gluteus_minimus.{s}", "insertion")
            for x in (med, mini):
                self.assertEqual((x.bone, x.landmark), (f"femur.{s}", f"greater_trochanter.{s}"))
                self.assertLess(length(sub(x.point, gt)), 0.008)  # junto al trocanter mayor
            self.assertGreater(sx * (med.point[0] - gt[0]), 0)  # el mediano, en la cara lateral
            self.assertLess(mini.point[1], gt[1])  # el menor, en la anterior (-Y)
            self.assertLess(mini.point[1], med.point[1])

    def test_every_site_is_on_a_bone_surface_and_fibers_join_origin_to_insertion(self):
        tol = muscles.SITE_TOL_M
        for m in self.m.muscles.values():
            for s in m.sites:
                self.assertLess(articulations.bone_distance(s.point, s.bone, self.base, self.anat), tol, (m.name, s.index))
            for o, t in m.fibers:
                self.assertEqual((m.sites[o].kind, m.sites[t].kind), ("origin", "insertion"))
                self.assertGreater(length(sub(m.sites[o].point, m.sites[t].point)), 0.03)  # la fibra tiene longitud real

    def test_sites_coincide_with_the_bone_landmarks(self):
        for m in self.m.muscles.values():
            for s in m.sites:
                lm = self.art.attachments[s.landmark]
                self.assertEqual(s.bone, lm.bone)
                self.assertLess(length(sub(s.point, lm.point)), 0.007)  # el sitio parte del hito (las facetas del trocanter se desplazan algunos mm)

    def test_symmetry_and_scaling(self):
        for n, m in self.m.muscles.items():
            if n.endswith(".L"):
                for a, b in zip(m.sites, self.m.muscles[n[:-2] + ".R"].sites):
                    self.assertLess(length(sub(mirror_point(a.point), b.point)), 1e-12, n)
        _, _, _, small = build_all(1.5)
        k = 1.5 / self.base.height_m
        for n, m in self.m.muscles.items():
            for a, b in zip(m.sites, small.muscles[n].sites):
                self.assertLess(length(sub(tuple(k * c for c in a.point), b.point)), 1e-9, n)

    def test_bad_data_is_rejected(self):
        import copy
        data = copy.deepcopy(muscles.load_muscle_data())
        data[0]["muscles"][0]["sites"][0]["landmark"] = "no_such_landmark.L"
        with self.assertRaises(ConfigError):
            build_all(data=data)
        data = copy.deepcopy(muscles.load_muscle_data())
        data[0]["muscles"][1]["sites"][2]["offset_h"] = [0.2, 0.0, 0.0]  # insercion lejos del femur
        _, anat, art, bad = build_all(data=data)
        self.assertIn("MUS_SITE_OFF_BONE", [i.code for i in muscles.validate_muscles(self.base, anat, art, bad)])
        data = copy.deepcopy(muscles.load_muscle_data())
        data[0]["muscles"][2]["sites"] = [s for s in data[0]["muscles"][2]["sites"] if s["kind"] == "origin"]
        _, anat, art, bad = build_all(data=data)
        self.assertIn("MUS_KINDS", [i.code for i in muscles.validate_muscles(self.base, anat, art, bad)])

    def test_bone_model_does_not_depend_on_muscles(self):
        """La capa muscular se construye sobre el modelo oseo; este no la conoce (puede cargarse sin ella)."""
        base = build_model(load_config())
        anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
        art = articulations.build_articulations(base, anat, articulations.load_articulation_data())
        self.assertEqual(muscles.build_muscles(base, anat, art, []).muscles, {})
        self.assertTrue(all(all(s.startswith("hito") for s in a.structures) for a in art.attachments.values()))


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestMusclesInBlender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from anatomical_core import anatomy_pipeline, muscles_scene, scene
        cls.scene, cls.muscles_scene = scene, muscles_scene
        TEST_OUT.mkdir(parents=True, exist_ok=True)
        cls.path = TEST_OUT / "muscles_a.blend"
        cls.res = anatomy_pipeline.generate(cls.path, preview=False, log=lambda *_: None)

    def test_file_validates_and_markers_follow_their_bones(self):
        import bpy
        from mathutils import Euler
        self.scene.open_blend(self.path)
        snap = self.muscles_scene.read_back_muscles()
        base, anat, art = self.res.base, self.res.anatomy, None
        art = articulations.build_articulations(base, anat, articulations.load_articulation_data())
        model = muscles.build_muscles(base, anat, art, muscles.load_muscle_data())
        self.assertEqual(muscles.validate_muscles_snapshot(model, snap), [])
        self.assertEqual(len([n for n in snap if n.startswith("MUS_site_")]), sum(len(m.sites) for m in model.muscles.values()))
        # girar la cadera mueve la insercion en el trocanter pero no el origen en el ilion
        arm = bpy.data.objects["AC_Armature"]
        pb = arm.pose.bones["thigh.L"]
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = Euler((0.6, 0.0, 0.2))
        bpy.context.view_layer.update()
        after = self.muscles_scene.read_back_muscles()
        moved = lambda n: sum((a - b) ** 2 for a, b in zip(after[n]["points"][0], snap[n]["points"][0])) ** 0.5  # noqa: E731
        site = {s.kind: s for s in model.muscles["gluteus_medius.L"].sites}
        self.assertGreater(moved("MUS_site_gluteus_medius.L_2"), 0.01)  # insercion (femur)
        self.assertLess(moved("MUS_site_gluteus_medius.L_0"), 1e-4)  # origen (ilion)
        self.assertEqual((site["origin"].bone, site["insertion"].bone), ("ilium.L", "femur.L"))


if __name__ == "__main__":
    unittest.main()
