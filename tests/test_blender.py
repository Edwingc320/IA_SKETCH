"""Pruebas dentro de Blender: generacion real, guardado, reapertura y reproducibilidad.

Se omiten (skip) si se ejecutan fuera de Blender; tests/run_tests.py las ejecuta dentro.
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

    def test_01_generation_completed_and_files_saved(self):
        self.assertTrue(self.path_a.is_file() and self.path_a.stat().st_size > 10_000)
        self.assertTrue(self.res_a.report_path.is_file())
        self.assertFalse([i for i in self.res_a.issues if i.severity == "error"])

    def test_02_reopened_file_matches_model(self):
        from anatomical_core import validation
        self.scene.open_blend(self.path_a)  # reabre desde disco
        snap = self.scene.read_back()
        self.assertEqual(validation.validate_blend_snapshot(self.res_a.model, snap), [])
        self.assertEqual(len(snap["bones"]), len(self.res_a.model.bones))
        self.assertEqual(set(snap["bones"]), set(self.res_a.model.bones))

    def test_03_essential_elements_in_reopened_file(self):
        import bpy
        self.scene.open_blend(self.path_a)
        arm = bpy.data.objects["AC_Armature"]
        self.assertEqual(arm.type, "ARMATURE")
        self.assertEqual(arm.data.bones["thigh.L"].parent.name, "pelvis")
        self.assertIn("ac_joint", arm.data.bones["forearm.R"].keys())
        joint = json.loads(arm.data.bones["forearm.R"]["ac_joint"])
        self.assertEqual(joint["name"], "elbow.R")
        for col in self.scene.COLLECTIONS:
            self.assertIn(col, bpy.data.collections)
        meta = json.loads(bpy.context.scene[self.scene.META_KEY])
        self.assertEqual(meta["model_signature"], self.res_a.model.signature())
        # Todo objeto de visualizacion esta marcado como tal (no se confunde con anatomia).
        for o in bpy.data.objects:
            if o.name.startswith(("VIS_", "JM_", "AX_")):
                self.assertEqual(o["ac_role"], "visualization_only")

    def test_04_axis_arrows_point_along_axes(self):
        import bpy
        from mathutils import Vector
        self.scene.open_blend(self.path_a)
        model = self.res_a.model
        for j in model.joints.values():
            for d in j.dofs:
                arrow = bpy.data.objects[f"AX_{j.name}_{d.name}"]
                direction = arrow.matrix_world.to_quaternion() @ Vector((0, 0, 1))
                self.assertLess((direction - Vector(d.axis)).length, 1e-4, f"{j.name}.{d.name}")

    def test_05_reproducible_scene(self):
        self.assertEqual(self.res_a.model.signature(), self.res_b.model.signature())
        self.scene.open_blend(self.path_a)
        snap_a = self.scene.read_back()
        self.scene.open_blend(self.path_b)
        snap_b = self.scene.read_back()
        self.assertEqual(snap_a["meta"], snap_b["meta"])
        for name, a in snap_a["bones"].items():
            b = snap_b["bones"][name]
            self.assertEqual(a["parent"], b["parent"])
            for p, q in zip(a["head"] + a["tail"], b["head"] + b["tail"]):
                self.assertAlmostEqual(p, q, places=9)

    def test_06_changed_proportions_change_the_scene(self):
        path = TEST_OUT / "run_tall.blend"
        res = self.pipeline.generate(path, height_m=1.90, preview=False, log=self.msgs.append)
        self.assertNotEqual(res.model.signature(), self.res_a.model.signature())
        self.scene.open_blend(path)
        self.assertEqual(self.scene.read_back()["meta"]["height_m"], 1.90)


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
        r = self.run_script("--output", str(out), "--no-preview")
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        self.assertTrue(out.is_file())
        report = json.loads(out.with_name("e2e_report.json").read_text(encoding="utf-8"))
        self.assertEqual(len(report["bones"]), 20)
        self.assertEqual([i for i in report["issues"] if i.startswith("[ERROR]")], [])

    def test_script_fails_with_nonzero_on_bad_config(self):
        r = self.run_script("--output", str(TEST_OUT / "bad.blend"), "--height", "-3", "--no-preview")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((TEST_OUT / "bad.blend").exists())


if __name__ == "__main__":
    unittest.main()
