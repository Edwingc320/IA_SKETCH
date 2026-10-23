"""Pruebas dentro de Blender: generacion real, guardado, reapertura, roll, pose y visualizacion.

Las comparaciones usan numeros crudos leidos de Blender y los calculados por el modelo; no pasan
por el validador del propio proyecto. Se omiten (skip) fuera de Blender; tests/run_tests.py las
ejecuta dentro.
"""
import json
import subprocess
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

TEST_OUT = ROOT / "output" / "_test"
TOL = 1e-4  # float32 del .blend


def dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestBlenderGeneration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from anatomical_core import pipeline, scene
        cls.pipeline, cls.scene = pipeline, scene
        TEST_OUT.mkdir(parents=True, exist_ok=True)
        cls.path_a = TEST_OUT / "run_a.blend"
        cls.path_b = TEST_OUT / "run_b.blend"
        cls.msgs = []
        cls.res_a = pipeline.generate(cls.path_a, preview=False, log=cls.msgs.append)
        cls.res_b = pipeline.generate(cls.path_b, preview=False, log=cls.msgs.append)
        cls.model, cls.posed = cls.res_a.model, cls.res_a.posed

    # --- utilidades --------------------------------------------------------------------------
    def open(self, path=None, position=None):
        import bpy
        self.scene.open_blend(path or self.path_a)
        arm = bpy.data.objects["AC_Armature"]
        if position:
            arm.data.pose_position = position
        bpy.context.view_layer.update()
        return arm

    def evaluated(self, obj):
        import bpy
        return obj.evaluated_get(bpy.context.evaluated_depsgraph_get())

    # --- generacion y archivo ------------------------------------------------------------------
    def test_01_generation_completed_and_files_saved(self):
        self.assertTrue(self.path_a.is_file() and self.path_a.stat().st_size > 10_000)
        self.assertTrue(self.res_a.report_path.is_file())
        self.assertFalse([i for i in self.res_a.issues if i.severity == "error"])

    def test_02_reopened_file_matches_model(self):
        from anatomical_core import validation
        self.open()
        snap = self.scene.read_back()
        self.assertEqual(validation.validate_blend_snapshot(self.model, snap, self.posed), [])
        self.assertEqual(set(snap["bones"]), set(self.model.bones))

    def test_03_essential_elements_in_reopened_file(self):
        import bpy
        arm = self.open()
        self.assertEqual(arm.type, "ARMATURE")
        self.assertEqual(arm.data.bones["thigh.L"].parent.name, "pelvis")
        joint = json.loads(arm.data.bones["forearm.R"]["ac_joint"])
        self.assertEqual(joint["name"], "elbow.R")
        self.assertEqual({d["axis_local"] for d in joint["dofs"]}, {"x", "y"})
        pose_meta = json.loads(arm["ac_pose"])
        self.assertEqual(pose_meta["name"], "A-pose")
        self.assertEqual(pose_meta["angles_deg"]["shoulder.L"]["abduction"], 40.0)
        for col in self.scene.COLLECTIONS:
            self.assertIn(col, bpy.data.collections)
        meta = json.loads(bpy.context.scene[self.scene.META_KEY])
        self.assertEqual(meta["model_signature"], self.model.signature())
        self.assertEqual(meta["pose_signature"], self.posed.signature)
        for o in bpy.data.objects:
            if o.name.startswith(("VIS_", "JM_", "AX_")):
                self.assertEqual(o["ac_role"], "visualization_only")

    # --- roll y ejes locales ---------------------------------------------------------------------
    def test_04_rest_bones_are_the_neutral_skeleton(self):
        arm = self.open()
        for n, b in self.model.bones.items():
            bb = arm.data.bones[n]
            self.assertLess(dist(bb.head_local, b.head), TOL, n)
            self.assertLess(dist(bb.tail_local, b.tail), TOL, n)

    def test_05_roll_matches_the_model_frames_and_every_axis_is_a_local_axis(self):
        """E4: los ejes de cada articulacion son +-un eje local del hueso EN BLENDER (roll correcto)."""
        arm = self.open()
        for n, b in self.model.bones.items():
            m3 = arm.data.bones[n].matrix_local.to_3x3()
            for i in range(3):
                self.assertLess(dist(m3.col[i], b.frame[i]), TOL, f"{n} eje local {'XYZ'[i]}")
        idx = {"x": 0, "y": 1, "z": 2}
        for j in self.model.joints.values():
            m3 = arm.data.bones[j.bone].matrix_local.to_3x3()
            for d in j.dofs:
                col = m3.col[idx[d.axis_local]]
                self.assertLess(dist(tuple(d.axis_sign * c for c in col), d.axis), TOL, f"{j.name}.{d.name}")

    def test_06_left_and_right_local_axes_mirror_in_blender(self):
        arm = self.open()
        for n in self.model.bones:
            if n.endswith(".L"):
                l3 = arm.data.bones[n].matrix_local.to_3x3()
                r3 = arm.data.bones[n[:-2] + ".R"].matrix_local.to_3x3()
                self.assertLess(dist(r3.col[0], (l3.col[0][0], -l3.col[0][1], -l3.col[0][2])), TOL, n)  # x: pseudovector
                self.assertLess(dist(r3.col[1], (-l3.col[1][0], l3.col[1][1], l3.col[1][2])), TOL, n)
                self.assertLess(dist(r3.col[2], (-l3.col[2][0], l3.col[2][1], l3.col[2][2])), TOL, n)

    # --- pose: Blender frente a cinematica directa -------------------------------------------------
    def test_07_posed_bones_match_forward_kinematics(self):
        from anatomical_core.geometry import mat_vec
        arm = self.open()
        ev = self.evaluated(arm)
        for n, pb in self.posed.bones.items():
            bone = ev.pose.bones[n]
            self.assertLess(dist(bone.head, pb.head), TOL, f"{n} head")
            self.assertLess(dist(bone.tail, pb.tail), TOL, f"{n} tail")
            # orientacion: los ejes locales posados = R_b * marco neutro
            m3 = bone.matrix.to_3x3()
            for i in range(3):
                self.assertLess(dist(m3.col[i], mat_vec(pb.rotation, self.model.bones[n].frame[i])), TOL, f"{n} eje {'XYZ'[i]}")

    def test_08_pose_quaternions_roundtrip_and_pivots_are_untouched(self):
        arm = self.open()
        for n, pb in self.posed.bones.items():
            q = arm.pose.bones[n].rotation_quaternion
            self.assertLess(dist(tuple(q), pb.local_quat), 1e-6, n)
            self.assertEqual(arm.pose.bones[n].rotation_mode, "QUATERNION")
        for n in self.model.bones:  # los pivotes del reposo (datos) no se mueven por la pose
            self.assertLess(dist(arm.data.bones[n].head_local, self.model.bones[n].head), TOL, n)
        self.assertEqual(len([j for j in self.model.joints]), 19)

    def test_09_rest_position_restores_the_neutral(self):
        arm = self.open(position="REST")
        ev = self.evaluated(arm)
        for n, b in self.model.bones.items():
            self.assertLess(dist(ev.pose.bones[n].head, b.head), TOL, n)
            self.assertLess(dist(ev.pose.bones[n].tail, b.tail), TOL, n)

    def test_10_feet_are_grounded_and_flat_in_blender(self):
        arm = self.open()
        ev = self.evaluated(arm)
        for side in "LR":
            foot = ev.pose.bones[f"foot.{side}"]
            self.assertAlmostEqual(foot.head[2], self.model.ankle_height_m, delta=TOL)
            self.assertAlmostEqual(foot.tail[2], foot.head[2], delta=TOL)  # pie horizontal
        spacing = dist(ev.pose.bones["foot.L"].head, ev.pose.bones["foot.R"].head)
        self.assertAlmostEqual(spacing, 0.27193934, delta=TOL)  # separacion de tobillos calculada por FK (m)

    # --- visualizacion emparentada -----------------------------------------------------------------
    def check_visuals(self, position, expect_bone, expect_rot):
        import bpy
        from mathutils import Vector
        arm = self.open(position=position)
        for n in self.model.bones:
            o = bpy.data.objects[f"VIS_{n}"]
            self.assertEqual((o.parent, o.parent_type, o.parent_bone), (arm, "BONE", n))
            ev = self.evaluated(o)
            self.assertLess(dist(ev.matrix_world @ o.data.vertices[0].co, expect_bone(n).head), TOL, f"VIS_{n} head")
            self.assertLess(dist(ev.matrix_world @ o.data.vertices[5].co, expect_bone(n).tail), TOL, f"VIS_{n} tail")
        for jn, j in self.model.joints.items():
            carrier = j.parent_bone
            marker = bpy.data.objects[f"JM_{jn}"]
            self.assertEqual(marker.parent_bone, carrier)
            verts = marker.data.vertices
            center = sum((self.evaluated(marker).matrix_world @ v.co for v in verts), Vector()) / len(verts)
            self.assertLess(dist(center, expect_bone(j.bone).head), TOL, f"JM_{jn}")
            for d in j.dofs:
                arrow = bpy.data.objects[f"AX_{jn}_{d.name}"]
                self.assertEqual(arrow.parent_bone, carrier)
                ev = self.evaluated(arrow)
                self.assertLess(dist(ev.matrix_world.translation, expect_bone(j.bone).head), TOL, f"AX_{jn}_{d.name} pos")
                direction = ev.matrix_world.to_quaternion() @ Vector((0, 0, 1))
                self.assertLess(dist(direction, expect_rot(carrier, d.axis)), TOL, f"AX_{jn}_{d.name} dir")

    def test_11_visuals_follow_the_pose_without_double_transform(self):
        from anatomical_core.geometry import mat_vec
        self.check_visuals("POSE", lambda n: self.posed.bones[n],
                           lambda carrier, axis: mat_vec(self.posed.bones[carrier].rotation, axis))

    def test_12_visuals_match_the_neutral_in_rest_position(self):
        self.check_visuals("REST", lambda n: self.model.bones[n], lambda carrier, axis: axis)

    def test_13_axes_arrows_are_the_neutral_axes_at_rest(self):
        import bpy
        from mathutils import Vector
        self.open(position="REST")
        for j in self.model.joints.values():
            for d in j.dofs:
                arrow = bpy.data.objects[f"AX_{j.name}_{d.name}"]
                direction = self.evaluated(arrow).matrix_world.to_quaternion() @ Vector((0, 0, 1))
                self.assertLess(dist(direction, d.axis), TOL, f"{j.name}.{d.name}")

    # --- reproducibilidad y configuracion --------------------------------------------------------------
    def test_14_reproducible_scene(self):
        self.assertEqual(self.model.signature(), self.res_b.model.signature())
        self.assertEqual(self.posed.signature, self.res_b.posed.signature)
        arm = self.open(self.path_a)
        a = {n: (tuple(b.head_local), tuple(b.tail_local)) for n, b in arm.data.bones.items()}
        pa = {n: (tuple(self.evaluated(arm).pose.bones[n].head)) for n in a}
        arm = self.open(self.path_b)
        b_ = {n: (tuple(b.head_local), tuple(b.tail_local)) for n, b in arm.data.bones.items()}
        pb = {n: (tuple(self.evaluated(arm).pose.bones[n].head)) for n in b_}
        for n in a:
            for p, q in zip(a[n][0] + a[n][1] + pa[n], b_[n][0] + b_[n][1] + pb[n]):
                self.assertAlmostEqual(p, q, places=9)

    def test_15_changing_the_pose_changes_the_blend_pose_but_not_the_neutral(self):
        path = TEST_OUT / "run_pose.blend"
        res = self.pipeline.generate(path, pose_overrides={"shoulder.abduction": 25.0, "elbow.flexion": 30.0},
                                     preview=False, log=self.msgs.append)
        self.assertEqual(res.model.signature(), self.model.signature())  # mismo neutro
        self.assertNotEqual(res.posed.signature, self.posed.signature)
        arm = self.open(path)
        meta = json.loads(__import__("bpy").context.scene[self.scene.META_KEY])
        self.assertEqual(meta["model_signature"], self.model.signature())
        self.assertEqual(meta["pose_signature"], res.posed.signature)
        for n, b in self.model.bones.items():  # reposo identico
            self.assertLess(dist(arm.data.bones[n].head_local, b.head), TOL, n)
        ev = self.evaluated(arm)
        for n, pb in res.posed.bones.items():
            self.assertLess(dist(ev.pose.bones[n].tail, pb.tail), TOL, n)

    def test_16_neutral_only_leaves_the_rig_unposed(self):
        path = TEST_OUT / "run_neutral.blend"
        res = self.pipeline.generate(path, neutral_only=True, preview=False, log=self.msgs.append)
        arm = self.open(path)
        for n, pb in res.posed.bones.items():
            self.assertLess(dist(tuple(arm.pose.bones[n].rotation_quaternion), (1.0, 0.0, 0.0, 0.0)), 1e-9, n)
            self.assertLess(dist(self.evaluated(arm).pose.bones[n].tail, self.model.bones[n].tail), TOL, n)

    def test_17_changed_proportions_change_the_scene(self):
        path = TEST_OUT / "run_tall.blend"
        res = self.pipeline.generate(path, height_m=1.90, preview=False, log=self.msgs.append)
        self.assertNotEqual(res.model.signature(), self.model.signature())
        self.open(path)
        meta = json.loads(__import__("bpy").context.scene[self.scene.META_KEY])
        self.assertEqual(meta["height_m"], 1.90)

    def test_18_old_blend_v0_1_is_not_accepted_by_the_new_validation(self):
        """Compatibilidad: el .blend de v0.1 (si se conserva en output/legacy) falla la validacion nueva."""
        from anatomical_core import validation
        legacy = ROOT / "output" / "legacy" / "skeleton_core_v0.1.blend"
        if not legacy.is_file():
            self.skipTest("no hay copia legacy local (output/legacy ignorado por Git)")
        self.open(legacy)
        snap = self.scene.read_back()
        codes = {i.code for i in validation.errors(validation.validate_blend_snapshot(self.model, snap, self.posed))}
        self.assertTrue({"BLEND_SIGNATURE", "BLEND_POSE_SIGNATURE"} <= codes, codes)


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestEndToEndScript(unittest.TestCase):
    """Ejecuta scripts/generate_skeleton.py como proceso Blender independiente y revisa
    el codigo de salida y los archivos (no basta con que Blender termine)."""

    def run_script(self, *extra):
        import bpy
        cmd = [bpy.app.binary_path, "-b", "--factory-startup", "--python", str(ROOT / "scripts" / "generate_skeleton.py"), "--", *extra]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    def test_script_ok_and_outputs(self):
        out = TEST_OUT / "e2e.blend"
        if out.exists():
            out.unlink()
        r = self.run_script("--output", str(out), "--no-preview", "--pose", "shoulder.abduction=35")
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        self.assertTrue(out.is_file())
        report = json.loads(out.with_name("e2e_report.json").read_text(encoding="utf-8"))
        self.assertEqual(len(report["neutral_bones"]), 20)
        self.assertEqual(report["pose"]["angles_deg"]["shoulder.R"]["abduction"], 35.0)
        self.assertEqual([i for i in report["issues"] if i.startswith("[ERROR]")], [])

    def test_script_fails_with_nonzero_on_bad_config_or_pose(self):
        for name, args in (
            ("bad_height", ("--height", "-3")),
            ("bad_limit", ("--pose", "elbow.flexion=150")),
            ("bad_pose_syntax", ("--pose", "elbow.flexion")),
            ("bad_stance", ("--pose", "hip.abduction=40", "--pose", "ankle.inversion=-40")),
        ):
            out = TEST_OUT / f"{name}.blend"
            if out.exists():
                out.unlink()
            r = self.run_script("--output", str(out), "--no-preview", *args)
            self.assertNotEqual(r.returncode, 0, name)
            self.assertFalse(out.exists(), name)  # no se escribe un .blend invalido


if __name__ == "__main__":
    unittest.main()
