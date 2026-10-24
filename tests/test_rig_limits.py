"""Restricciones de rotacion: orden Euler, limites por eje, acoples (rodilla) y su efecto real en Blender (Limit Rotation)."""
import math
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

from anatomical_core import pose as pose_mod, rig_limits, validation  # noqa: E402
from anatomical_core.config import ConfigError, PoseDef, load_config  # noqa: E402
from anatomical_core.geometry import mat_vec  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

TEST_OUT = ROOT / "output" / "_test"
TOL = 1e-4


def dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def model_and_pose(**overrides):
    cfg = load_config(pose_overrides=overrides or None)
    model = build_model(cfg)
    return model, pose_mod.apply_pose(model, cfg.pose)


class TestRigLimitsData(unittest.TestCase):
    def setUp(self):
        self.model = build_model(load_config())

    def test_euler_order_follows_the_dof_composition_order(self):
        j = self.model.joints
        self.assertEqual(rig_limits.euler_order(j["elbow.L"]), "YXZ")  # pronacion primero, despues flexion
        self.assertEqual(rig_limits.euler_order(j["knee.L"]), "XYZ")
        self.assertEqual(rig_limits.euler_order(j["shoulder.R"]), "XZY")
        self.assertEqual(rig_limits.euler_order(j["sternoclavicular.L"]), "XZY")  # dof x, z; el eje sin dof va al final

    def test_limits_follow_the_axis_sign_and_lock_the_other_axes(self):
        hip = rig_limits.channel_limits(self.model.joints["hip.L"])
        self.assertEqual((hip["x"].min_deg, hip["x"].max_deg), (-120, 15))  # flexion (x, signo -1): [-20..120] -> invertido
        self.assertEqual((hip["z"].min_deg, hip["z"].max_deg), (-45, 30))
        self.assertEqual((hip["y"].min_deg, hip["y"].max_deg), (-40, 45))
        elbow = rig_limits.channel_limits(self.model.joints["elbow.L"])
        self.assertTrue(elbow["z"].locked and (elbow["z"].min_deg, elbow["z"].max_deg) == (0, 0))  # la bisagra no gira en z
        self.assertFalse(elbow["x"].locked)
        self.assertEqual((elbow["x"].min_deg, elbow["x"].max_deg), (-145, 0))
        for name, joint in self.model.joints.items():
            for d in joint.dofs:  # cada dof esta contenido en su canal y el canal siempre contiene el 0
                ch = rig_limits.channel_limits(joint)[d.axis_local]
                self.assertLessEqual(ch.min_deg, 0, name)
                self.assertGreaterEqual(ch.max_deg, 0, name)

    def test_knee_axial_rotation_only_exists_with_flexion(self):
        couplings = rig_limits.load_couplings(self.model)
        self.assertEqual([(c.joint, c.dof, c.depends_on, c.full_at_deg) for c in couplings], [("knee", "axial", "flexion", 30.0)])
        allowed = lambda flex: rig_limits.allowed_range(self.model, couplings, "knee.L", "axial", {"flexion": flex})  # noqa: E731
        self.assertEqual(allowed(0.0), (0.0, 0.0))  # extendida: sin rotacion
        self.assertEqual(allowed(15.0), (-5.0, 5.0))  # mitad del camino
        self.assertEqual(allowed(30.0), (-10.0, 10.0))
        self.assertEqual(allowed(120.0), (-10.0, 10.0))
        self.assertEqual(rig_limits.allowed_range(self.model, couplings, "elbow.L", "flexion", {}), (0, 145))  # sin acople

    def test_bad_couplings_are_rejected(self):
        import json
        import tempfile
        for bad, text in (({"joint": "wing", "dof": "axial", "depends_on": "flexion", "full_at_deg": 30, "source": "x"}, "desconocida"),
                          ({"joint": "knee", "dof": "axial", "depends_on": "flexion", "full_at_deg": 0, "source": "x"}, "positivo"),
                          ({"joint": "knee", "dof": "flexion", "depends_on": "axial", "full_at_deg": 30, "source": "x"}, "antes")):
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / rig_limits.COUPLINGS_FILE).write_text(json.dumps({"couplings": [bad]}), encoding="utf-8")
                with self.assertRaises(ConfigError, msg=text) as cm:
                    rig_limits.load_couplings(self.model, tmp)
                self.assertIn(text, str(cm.exception))

    def test_pose_validation_applies_the_coupling(self):
        model, p = model_and_pose(**{"knee.axial": 10.0})  # rodilla extendida con rotacion axial
        codes = [i.code for i in validation.validate_pose(model, p)]
        self.assertIn("POSE_COUPLED_LIMIT", codes)
        model, p = model_and_pose(**{"knee.axial": 10.0, "knee.flexion": 40.0})
        self.assertNotIn("POSE_COUPLED_LIMIT", [i.code for i in validation.validate_pose(model, p)])
        model, p = model_and_pose(**{"knee.axial": 5.0, "knee.flexion": 15.0})  # justo en el limite parcial
        self.assertNotIn("POSE_COUPLED_LIMIT", [i.code for i in validation.validate_pose(model, p)])


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestLimitRotationInBlender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from anatomical_core import pipeline, scene
        cls.scene = scene
        TEST_OUT.mkdir(parents=True, exist_ok=True)
        cls.path = TEST_OUT / "rig_limits.blend"
        cls.res = pipeline.generate(cls.path, preview=False, log=lambda *_: None)
        cls.model = cls.res.model

    def open_reset(self):
        """Reabre el .blend y deja todos los pose bones sin rotar para aislar la articulacion bajo prueba."""
        import bpy
        self.scene.open_blend(self.path)
        arm = bpy.data.objects["AC_Armature"]
        for pb in arm.pose.bones:
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            pb.location = (0.0, 0.0, 0.0)
        bpy.context.view_layer.update()
        return arm

    def evaluated_matrix(self, arm, bone):
        import bpy
        ev = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return ev.pose.bones[bone].matrix.to_3x3()

    def request(self, arm, bone, rotations):
        """Pide en Blender la rotacion que daria la FK para `rotations`, sin recortar los angulos."""
        import bpy
        pb = pose_mod.apply_pose(self.model, PoseDef("t", rotations)).bones[bone]
        arm.pose.bones[bone].rotation_quaternion = pb.local_quat
        bpy.context.view_layer.update()

    def expected(self, bone, rotations):
        pb = pose_mod.apply_pose(self.model, PoseDef("t", rotations)).bones[bone]
        frame = self.model.bones[bone].frame
        return [mat_vec(pb.rotation, frame[i]) for i in range(3)]

    def assert_matches(self, arm, bone, rotations, msg):
        m3 = self.evaluated_matrix(arm, bone)
        for i, col in enumerate(self.expected(bone, rotations)):
            self.assertLess(dist(m3.col[i], col), TOL, f"{msg} eje {'XYZ'[i]}")

    def test_every_joint_bone_has_exact_limits(self):
        arm = self.open_reset()
        for name, joint in self.model.joints.items():
            cons = [c for c in arm.pose.bones[joint.bone].constraints if c.name == self.scene.LIMIT_CONSTRAINT]
            self.assertEqual(len(cons), 1, name)
            con = cons[0]
            self.assertEqual((con.type, con.owner_space, con.euler_order), ("LIMIT_ROTATION", "LOCAL", rig_limits.euler_order(joint)), name)
            self.assertTrue(con.use_transform_limit, name)
            for axis, lim in rig_limits.channel_limits(joint).items():
                self.assertTrue(getattr(con, f"use_limit_{axis}"), f"{name} {axis}")
                self.assertAlmostEqual(getattr(con, f"min_{axis}"), math.radians(lim.min_deg), places=5, msg=f"{name} min {axis}")
                self.assertAlmostEqual(getattr(con, f"max_{axis}"), math.radians(lim.max_deg), places=5, msg=f"{name} max {axis}")
            self.assertEqual(arm.animation_data is None or len(arm.animation_data.drivers) == 0, True)  # sin drivers: sin ciclos
        self.assertEqual(len(self.model.joints), 19)

    def test_pose_a_passes_through_the_limits_unchanged(self):
        import bpy
        self.scene.open_blend(self.path)
        arm = bpy.data.objects["AC_Armature"]
        bpy.context.view_layer.update()
        ev = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
        for n, pb in self.res.posed.bones.items():
            self.assertLess(dist(ev.pose.bones[n].tail, pb.tail), TOL, n)

    def test_elbow_cannot_hyperextend_or_exceed_its_flexion(self):
        arm = self.open_reset()
        self.request(arm, "forearm.L", {"elbow.L": {"flexion": 200.0}})
        self.assert_matches(arm, "forearm.L", {"elbow.L": {"flexion": 145.0}}, "flexion 200 -> 145")
        self.request(arm, "forearm.R", {"elbow.R": {"flexion": 90.0}})
        self.assert_matches(arm, "forearm.R", {"elbow.R": {"flexion": 90.0}}, "dentro del limite no se toca")

    def test_hinge_cannot_roll_on_its_locked_axis(self):
        import bpy
        from mathutils import Quaternion
        arm = self.open_reset()
        arm.pose.bones["forearm.L"].rotation_quaternion = Quaternion((0.0, 0.0, 1.0), math.radians(30.0))  # eje z local bloqueado
        bpy.context.view_layer.update()
        self.assert_matches(arm, "forearm.L", {}, "rotacion en el eje bloqueado")

    def test_pronation_is_limited_independently_of_flexion(self):
        arm = self.open_reset()
        self.request(arm, "forearm.L", {"elbow.L": {"pronation": 170.0, "flexion": 40.0}})
        limit = next(d.max_deg for d in self.model.joints["elbow.L"].dofs if d.name == "pronation")
        self.assert_matches(arm, "forearm.L", {"elbow.L": {"pronation": limit, "flexion": 40.0}}, "pronacion recortada")

    def test_knee_axial_rotation_has_a_static_limit_and_the_coupling_is_recorded(self):
        arm = self.open_reset()
        self.request(arm, "shin.L", {"knee.L": {"flexion": 60.0, "axial": 30.0}})
        self.assert_matches(arm, "shin.L", {"knee.L": {"flexion": 60.0, "axial": 10.0}}, "axial recortada a +-10")
        arm = self.open_reset()
        self.request(arm, "shin.R", {"knee.R": {"flexion": 60.0, "axial": 30.0}})
        self.assert_matches(arm, "shin.R", {"knee.R": {"flexion": 60.0, "axial": 10.0}}, "lado derecho: recorte a 10")
        # el acople (solo con flexion) NO lo aplica Blender: lo exige la validacion de la pose y queda anotado en el hueso
        self.assertIn("flexion", arm.pose.bones["shin.L"]["ac_coupling_axial"])
        self.assertEqual(len(arm.animation_data.drivers) if arm.animation_data else 0, 0)


if __name__ == "__main__":
    unittest.main()
