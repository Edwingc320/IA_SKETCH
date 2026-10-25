"""CM-6 en Blender: los 8 musculos profundos de la cadera y aductores (tubos deformados por la armadura) siguen a sus huesos y no atraviesan los
obstaculos de la pelvis y el femur en el barrido de 22 poses de cadera y rodilla. Cada anillo evaluado por Blender coincide con la cinematica directa
del modelo; incluye el CONTROL NEGATIVO (modificador silenciado)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    import bpy  # noqa: F401
    HAVE_BPY = True
except ImportError:
    HAVE_BPY = False

import test_iliopsoas_itb_blender as base_tests  # noqa: E402  (solo se usa su funcion expected_rings)
from anatomical_core import articulations, ligament_paths as lp, pose as pose_mod, tendons  # noqa: E402
from anatomical_core.config import PoseDef  # noqa: E402
from anatomical_core.geometry import length, sub  # noqa: E402

TEST_OUT = ROOT / "output" / "_test"
UNITS = ("piriformis", "obturator_internus", "gemellus_superior", "gemellus_inferior", "obturator_externus", "quadratus_femoris", "pectineus", "adductor_brevis")
TOL = 1e-4
PARTS = ("origin", "belly", "insertion")


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestDeepHipInBlender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from anatomical_core import anatomy_pipeline, scene, tendons_scene
        cls.scene, cls.tscene = scene, tendons_scene
        TEST_OUT.mkdir(parents=True, exist_ok=True)
        cls.path = TEST_OUT / "deep_hip.blend"
        cls.res = anatomy_pipeline.generate(cls.path, preview=False, log=lambda *_: None)
        cls.base, cls.anat = cls.res.base, cls.res.anatomy
        cls.art = articulations.build_articulations(cls.base, cls.anat, articulations.load_articulation_data())
        cls.tm = tendons.build_tendons(cls.base, cls.anat, cls.art, tendons.load_tendon_data())

    def open_reset(self):
        import bpy
        self.scene.open_blend(self.path)
        arm = bpy.data.objects["AC_Armature"]
        for pb in arm.pose.bones:
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            pb.location = (0.0, 0.0, 0.0)
        bpy.context.view_layer.update()
        return arm

    def pose_leg(self, arm, side, rotations):
        import bpy
        posed = pose_mod.apply_pose(self.base, PoseDef("t", {f"{j}.{side}": dict(r) for j, r in rotations.items()}))
        for j in rotations:
            bone = self.base.joints[f"{j}.{side}"].bone
            arm.pose.bones[bone].rotation_quaternion = posed.bones[bone].local_quat
        bpy.context.view_layer.update()
        return posed

    def parts_of(self, t):
        parts = {"origin": (t.origin_class, t.origin_tendon), "insertion": (t.insertion_class, t.insertion_tendon), "belly": (True, t.belly)}
        return [(f"TEN_{kind}_{t.name}", parts[kind][1]) for kind in PARTS if parts[kind][0]]

    def check_pose(self, side, pose_name, rotations):
        arm = self.open_reset()
        posed = self.pose_leg(arm, side, rotations)
        snap = self.tscene.read_back_tendons()
        surfaces = {s.name: s for s in lp.posed_surfaces(self.art, self.base, self.anat, posed)}
        for n in UNITS:
            t = self.tm.tendons[f"{n}.{side}"]
            parts = self.parts_of(t)
            for obj, pts in parts:
                got = snap[obj]["rings"]
                want = base_tests.expected_rings(t, pts, posed, self.base, self.anat)
                self.assertEqual(len(got), len(want), obj)
                for g, w in zip(got, want):
                    self.assertLess(length(sub(g, w)), TOL, (side, pose_name, obj))
                exact = base_tests.exact_rings(t, pts, posed, self.base, self.anat)
                self.assertLess(max(length(sub(w, e)) for w, e in zip(want, exact)), base_tests.LBS_VISUAL_LIMIT_M, (side, pose_name, obj))
            nodes = base_tests.node_ring_path(t, parts, {o: snap[o]["rings"] for o, _ in parts})
            self.assertEqual(len(nodes), len(t.sites))
            for g, w in zip(nodes, lp.posed_nodes(lp.tendon_nodes(t), self.base, self.anat, posed)):
                self.assertLess(length(sub(g, w)), TOL, (side, pose_name, n))
            self.assertGreaterEqual(lp.path_clearance(nodes, [surfaces[a] for a in t.avoid]), -TOL / 10, (side, pose_name, n))

    def test_the_tubes_are_armature_deformed_with_one_group_per_site_bone(self):
        import bpy
        self.scene.open_blend(self.path)
        for n in UNITS:
            for s in "LR":
                t = self.tm.tendons[f"{n}.{s}"]
                for obj, _ in self.parts_of(t):
                    o = bpy.data.objects[obj]
                    self.assertEqual((o.parent.name, o.parent_type, [m.type for m in o.modifiers]), ("AC_Armature", "OBJECT", ["ARMATURE"]), obj)
                    self.assertEqual({g.name for g in o.vertex_groups}, {x.bone for x in t.sites}, obj)

    def test_the_file_validates_in_rest(self):
        self.scene.open_blend(self.path)
        self.assertEqual(tendons.validate_tendons_snapshot(self.tm, self.tscene.read_back_tendons()), [])
        self.assertEqual(tendons.validate_tendon_poses(self.base, self.anat, self.art, self.tm), [])

    def test_blender_follows_the_model_fk_and_never_penetrates_in_the_left_sweep(self):
        for pose_name, rotations in lp.LEG_SWEEP:
            self.check_pose("L", pose_name, rotations)

    def test_blender_follows_the_model_fk_and_never_penetrates_on_the_right_side(self):
        sweep = dict(lp.LEG_SWEEP)
        for pose_name in ("flexion_120", "extension_15", "abduction_45", "adduction_30", "internal_rotation_40", "external_rotation_40", "hip_120_knee_135"):
            self.check_pose("R", pose_name, sweep[pose_name])

    def test_insertions_travel_with_the_femur_and_origins_stay_on_the_pelvis(self):
        arm = self.open_reset()
        rest = self.tscene.read_back_tendons()
        self.pose_leg(arm, "L", {"hip": {"flexion": 90.0}})
        moved = self.tscene.read_back_tendons()
        for n in UNITS:
            ins = f"TEN_insertion_{n}.L"
            self.assertGreater(length(sub(moved[ins]["points"][1], rest[ins]["points"][1])), 0.02, n)
            belly = f"TEN_belly_{n}.L"
            self.assertLess(length(sub(moved[belly]["points"][0], rest[belly]["points"][0])), TOL, n)
            self.assertLess(max(length(sub(a, b)) for a, b in zip(moved[f"TEN_belly_{n}.R"]["rings"], rest[f"TEN_belly_{n}.R"]["rings"])), TOL, n)

    def test_negative_control_a_muted_armature_leaves_the_route_behind(self):
        import bpy
        arm = self.open_reset()
        for n in UNITS:
            for o in bpy.data.objects:
                if o.name.startswith("TEN_") and o.name.endswith(f"{n}.L"):
                    o.modifiers["AC_Armature"].show_viewport = False
        posed = self.pose_leg(arm, "L", {"hip": {"flexion": 90.0}})
        snap = self.tscene.read_back_tendons()
        for n in UNITS:
            t = self.tm.tendons[f"{n}.L"]
            obj, pts = self.parts_of(t)[-1]
            got, want = snap[obj]["rings"], base_tests.expected_rings(t, pts, posed, self.base, self.anat)
            self.assertGreater(max(length(sub(g, w)) for g, w in zip(got, want)), 0.02, n)


if __name__ == "__main__":
    unittest.main()
