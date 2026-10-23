"""Nivel 1 en Blender: huesos anatomicos como hijos de la base, en un archivo propio.

Compara numeros crudos de Blender con el modelo. Se omite fuera de Blender.
"""
import json
import shutil
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
TOL = 1e-4


def dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestAnatomyInBlender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from anatomical_core import anatomy_pipeline, anatomy_scene, scene
        cls.scene, cls.anatomy_scene, cls.pipeline = scene, anatomy_scene, anatomy_pipeline
        TEST_OUT.mkdir(parents=True, exist_ok=True)
        cls.path = TEST_OUT / "anatomy_a.blend"
        cls.res = anatomy_pipeline.generate(cls.path, preview=False, log=lambda *_: None)
        cls.base, cls.anat = cls.res.base, cls.res.anatomy

    def open(self):
        import bpy
        self.scene.open_blend(self.path)
        bpy.context.view_layer.update()
        return bpy.data.objects["AC_Armature"]

    def evaluated(self, obj):
        import bpy
        return obj.evaluated_get(bpy.context.evaluated_depsgraph_get())

    def test_01_file_validates_base_and_level_1(self):
        from anatomical_core import validation
        self.open()
        snap = self.scene.read_back()
        base_part = self.pipeline.base_part_of_snapshot(snap, self.base)
        from anatomical_core import pose
        from anatomical_core.config import PoseDef
        neutral = pose.apply_pose(self.base, PoseDef("neutral", {}))
        self.assertEqual(validation.validate_blend_snapshot(self.base, base_part, neutral), [])
        self.assertEqual(validation.validate_anatomy_snapshot(self.anat, self.anatomy_scene.read_back_anatomy()), [])

    def test_02_level_1_bones_are_children_of_base_segments(self):
        arm = self.open()
        bones = arm.data.bones
        for n, b in self.anat.bones.items():
            self.assertEqual(bones[n].parent.name, b.parent, n)
            self.assertEqual(bones[n].get("ac_layer"), "anatomy_L1")
        self.assertEqual(bones["hip_bone.L"].parent.name, "pelvis")
        self.assertEqual(bones["sacrum_fused"].parent.name, "pelvis")
        # la base sigue siendo la misma: 20 huesos sin marca de nivel 1, en la coleccion L0_base
        base_bones = [b for b in bones if b.get("ac_layer") is None]
        self.assertEqual(sorted(b.name for b in base_bones), sorted(self.base.bones))
        self.assertEqual(sorted(b.name for b in arm.data.collections_all["L0_base"].bones), sorted(self.base.bones))
        self.assertEqual(sorted(b.name for b in arm.data.collections_all["L1_pelvic_girdle"].bones),
                         sorted(n for n, b in self.anat.bones.items() if b.region == "pelvic_girdle"))

    def test_03_rest_positions_and_roll_match_the_model(self):
        arm = self.open()
        for n, b in self.anat.bones.items():
            bb = arm.data.bones[n]
            self.assertLess(dist(bb.head_local, b.head), TOL, n)
            self.assertLess(dist(bb.tail_local, b.tail), TOL, n)
            m3 = bb.matrix_local.to_3x3()
            for i in range(3):
                self.assertLess(dist(m3.col[i], b.frame[i]), TOL, f"{n} eje {'XYZ'[i]}")
        for n, b in self.base.bones.items():  # la base no se movio al anadir el nivel 1
            self.assertLess(dist(arm.data.bones[n].head_local, b.head), TOL, n)
            self.assertLess(dist(arm.data.bones[n].tail_local, b.tail), TOL, n)

    def test_04_level_1_follows_its_base_parent_rigidly(self):
        """'Hijos' de verdad: mover/girar la pelvis base arrastra sacro, coxis y coxales (y su visualizacion)."""
        import bpy
        from mathutils import Euler, Vector
        arm = self.open()
        pb = arm.pose.bones["pelvis"]
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = Euler((0.3, -0.2, 0.4))
        pb.location = Vector((0.05, -0.02, 0.10))
        bpy.context.view_layer.update()
        ev = self.evaluated(arm)
        rest = arm.data.bones["pelvis"].matrix_local
        delta = ev.pose.bones["pelvis"].matrix @ rest.inverted()
        moved = 0
        for n in ("sacrum_fused", "coccyx_fused", "hip_bone.L", "hip_bone.R"):
            b = self.anat.bones[n]
            self.assertLess(dist(ev.pose.bones[n].head, delta @ Vector(b.head)), TOL, n)
            self.assertLess(dist(ev.pose.bones[n].tail, delta @ Vector(b.tail)), TOL, n)
            vis = bpy.data.objects[f"ANA_{n}"]
            self.assertLess(dist(self.evaluated(vis).matrix_world @ vis.data.vertices[0].co, delta @ Vector(b.head)), TOL, n)
            moved += dist(delta @ Vector(b.head), b.head) > 0.01
        self.assertEqual(moved, 4)  # la prueba no es vacua: todo se desplazo

    def test_05_femoral_head_stays_in_the_acetabulum_when_the_thigh_moves(self):
        import bpy
        from mathutils import Euler
        arm = self.open()
        for s in "LR":
            pbt = arm.pose.bones[f"thigh.{s}"]
            pbt.rotation_mode = "XYZ"
            pbt.rotation_euler = Euler((0.6, 0.2, -0.3))
        bpy.context.view_layer.update()
        ev = self.evaluated(arm)
        for s in "LR":
            self.assertLess(dist(ev.pose.bones[f"thigh.{s}"].head, ev.pose.bones[f"hip_bone.{s}"].tail), TOL)
            self.assertGreater(dist(ev.pose.bones[f"thigh.{s}"].tail, self.base.bones[f"thigh.{s}"].tail), 0.05)

    def test_05b_ribs_follow_the_base_segment_of_their_level(self):
        """Costillas 1-6 y esternon son hijos de thorax; 7-12 de spine_thoracic: girar solo thorax
        mueve las superiores y deja quietas las inferiores."""
        import bpy
        from mathutils import Euler, Vector
        arm = self.open()
        pb = arm.pose.bones["thorax"]
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = Euler((0.35, 0.0, 0.25))
        bpy.context.view_layer.update()
        ev = self.evaluated(arm)
        delta = ev.pose.bones["thorax"].matrix @ arm.data.bones["thorax"].matrix_local.inverted()
        for n, b in self.anat.bones.items():
            if b.region != "thoracic_cage":
                continue
            got = ev.pose.bones[n].tail
            if b.parent == "thorax":
                self.assertLess(dist(got, delta @ Vector(b.tail)), TOL, n)
                self.assertGreater(dist(got, b.tail), 0.005, n)
            else:
                self.assertLess(dist(got, b.tail), TOL, n)
        self.assertEqual(sorted(b.name for b in arm.data.collections_all["L1_thoracic_cage"].bones),
                         sorted(n for n, b in self.anat.bones.items() if b.region == "thoracic_cage"))

    def test_06_visuals_and_outlines_are_parented_without_double_transform(self):
        import bpy
        self.open()
        for n, b in self.anat.bones.items():
            vis = bpy.data.objects[f"ANA_{n}"]
            self.assertEqual(vis.parent_bone, n)
            self.assertLess(dist(self.evaluated(vis).matrix_world @ vis.data.vertices[5].co, b.tail), TOL, n)
            if b.outline:
                o = bpy.data.objects[f"ANA_outline_{n}"]
                self.assertEqual((o.parent_bone, o["ac_role"]), (n, "reference_geometry"))
        self.assertIn("AC_Anatomy_Outlines", bpy.data.collections)

    def test_07_base_file_is_not_touched(self):
        """El nivel 1 vive en su propio archivo: la base de skeleton_core.blend no contiene huesos de nivel 1."""
        base_blend = ROOT / "output" / "skeleton_core.blend"
        if not base_blend.is_file():
            self.skipTest("no hay skeleton_core.blend generado")
        import bpy
        self.scene.open_blend(base_blend)
        names = {b.name for b in bpy.data.objects["AC_Armature"].data.bones}
        self.assertEqual(names, set(self.base.bones))


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestAnatomyScript(unittest.TestCase):
    def run_script(self, *extra):
        import bpy
        cmd = [bpy.app.binary_path, "-b", "--factory-startup", "--python", str(ROOT / "scripts" / "generate_anatomy.py"), "--", *extra]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    def test_script_ok(self):
        out = TEST_OUT / "anatomy_e2e.blend"
        if out.exists():
            out.unlink()
        r = self.run_script("--output", str(out), "--no-preview")
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        report = json.loads(out.with_name("anatomy_e2e_report.json").read_text(encoding="utf-8"))
        self.assertIn("pelvic_girdle", report["regions"])
        self.assertEqual(report["bones"]["hip_bone.L"]["parent"], "pelvis")

    def test_script_fails_when_an_anchor_is_broken(self):
        bad_dir = TEST_OUT / "anatomy_bad_config"
        if bad_dir.exists():
            shutil.rmtree(bad_dir)
        shutil.copytree(ROOT / "config" / "anatomy", bad_dir)
        p = bad_dir / "pelvic_girdle.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        hb = next(b for b in data["bones"] if b["name"] == "hip_bone.L")
        hb["tail"] = {"at": "thigh.L.head", "offset_h": [0.01, 0, 0]}  # cabeza femoral fuera del acetabulo
        p.write_text(json.dumps(data), encoding="utf-8")
        out = TEST_OUT / "anatomy_bad.blend"
        if out.exists():
            out.unlink()
        r = self.run_script("--output", str(out), "--no-preview", "--anatomy-dir", str(bad_dir))
        self.assertEqual(r.returncode, 2, r.stdout[-2000:])
        self.assertIn("ANAT_ANCHOR", r.stdout)
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
