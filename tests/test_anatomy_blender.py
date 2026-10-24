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
            if "thorax" in self._rig_ancestors(n)[1:]:  # costillas 1-6 (via T1-T6) y esternon (via T4)
                self.assertLess(dist(got, delta @ Vector(b.tail)), TOL, n)
                self.assertGreater(dist(got, b.tail), 0.005, n)
            else:
                self.assertLess(dist(got, b.tail), TOL, n)
        self.assertEqual(sorted(b.name for b in arm.data.collections_all["L1_thoracic_cage"].bones),
                         sorted(n for n, b in self.anat.bones.items() if b.region == "thoracic_cage"))

    def test_05c_hands_and_feet_follow_their_base_segment(self):
        """Girar la mano base izquierda y el pie base derecho arrastra todo su desglose (y nada mas)."""
        import bpy
        from mathutils import Euler, Vector
        arm = self.open()
        for n in ("hand.L", "foot.R"):
            pb = arm.pose.bones[n]
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = Euler((0.4, -0.3, 0.2))
        bpy.context.view_layer.update()
        ev = self.evaluated(arm)
        deltas = {n: ev.pose.bones[n].matrix @ arm.data.bones[n].matrix_local.inverted() for n in ("hand.L", "foot.R")}
        checked = {"hand.L": 0, "foot.R": 0, "quietos": 0}
        for n, b in self.anat.bones.items():
            if b.region != "hands_feet":
                continue
            root = n
            while root in self.anat.bones:
                root = self.anat.bones[root].parent
            got = ev.pose.bones[n].tail
            if root in deltas:
                self.assertLess(dist(got, deltas[root] @ Vector(b.tail)), TOL, n)
                checked[root] += 1
            else:
                self.assertLess(dist(got, b.tail), TOL, n)
                checked["quietos"] += 1
        self.assertEqual(checked, {"hand.L": 27, "foot.R": 26, "quietos": 53})
        self.assertEqual(len(arm.data.collections_all["L1_hands_feet"].bones), 106)

    def _rig_ancestors(self, n):
        out, cur = [], n
        while cur is not None:
            out.append(cur)
            cur = self.anat.bones[cur].parent if cur in self.anat.bones else self.base.bones[cur].parent
        return out

    def _check_solidary(self, driver, euler):
        """Gira el hueso `driver` en pose: todo lo que cuelga de el en el rig se mueve rigidamente; lo demas, no."""
        import bpy
        from mathutils import Euler, Vector
        arm = self.open()
        pb = arm.pose.bones[driver]
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = Euler(euler)
        bpy.context.view_layer.update()
        ev = self.evaluated(arm)
        rest = arm.data.bones[driver].matrix_local
        delta = ev.pose.bones[driver].matrix @ rest.inverted()
        moved = []
        for n, b in self.anat.bones.items():
            if n == driver:
                continue  # el propio hueso girado se mueve por definicion
            got = ev.pose.bones[n].tail
            if driver in self._rig_ancestors(n)[1:]:
                self.assertLess(dist(got, delta @ Vector(b.tail)), TOL, n)
                moved.append(n)
            else:
                self.assertLess(dist(got, b.tail), TOL, n)
        return set(moved)

    def test_05d_spine_moves_solidarily_with_the_base_carriers(self):
        """Girar el segmento base lumbar arrastra L1-L5 y TODO lo que esta por encima (toracicas, cervicales,
        craneo, mandibula, costillas, esternon, escapulas, brazos); pelvis, sacro y piernas no se mueven."""
        moved = self._check_solidary("spine_lumbar", (0.3, 0.1, -0.2))
        for n in ["L5", "L1", "T12", "T1", "C7", "C1", "cranium", "mandible", "sternum", "rib_07.L", "scapula.R", "humerus.L", "ulna.R", "index_distal.L"]:
            self.assertIn(n, moved)
        for n in ["sacrum_fused", "hip_bone.L", "femur.R", "tibia.L", "calcaneus.R"]:
            self.assertNotIn(n, moved)
        moved_neck = self._check_solidary("neck", (0.4, 0.0, 0.3))
        self.assertEqual({n for n in moved_neck if n in self.anat.bones and self.anat.bones[n].region == "spine_head"},
                         {f"C{k}" for k in range(1, 8)} | {"cranium", "mandible"})

    def test_05e_long_bones_follow_their_base_segments(self):
        moved = self._check_solidary("upper_arm.L", (0.5, 0.0, 0.4))
        self.assertTrue({"humerus.L", "radius.L", "ulna.L", "scaphoid.L", "middle_distal.L"} <= moved)
        self.assertNotIn("scapula.L", moved)  # la escapula la mueve la clavicula, no el brazo
        moved = self._check_solidary("thigh.R", (0.6, 0.0, 0.0))
        self.assertTrue({"femur.R", "patella.R", "tibia.R", "fibula.R", "talus.R", "toe_1_distal.R"} <= moved)
        self.assertNotIn("hip_bone.R", moved)
        moved = self._check_solidary("clavicle.L", (0.0, 0.0, 0.3))
        self.assertIn("scapula.L", moved)
        moved = self._check_solidary("L2", (0.2, 0.0, 0.0))  # dentro del segmento lumbar la cadena anatomica es la del rig
        self.assertEqual({n for n in moved if self.anat.bones[n].region == "spine_head"}, {"L1"})

    def test_05f_collections_and_anatomical_parent_in_blender(self):
        arm = self.open()
        cols = arm.data.collections_all
        self.assertEqual(len(cols["L1_spine_head"].bones), 26)
        self.assertEqual(len(cols["L1_long_bones"].bones), 16)
        for n, b in self.anat.bones.items():
            self.assertEqual(arm.data.bones[n]["ac_anatomical_parent"], b.anatomical_parent or b.parent, n)
        self.assertEqual(arm.data.bones["cranium"]["ac_anatomical_parent"], "C1")
        self.assertEqual(arm.data.bones["humerus.R"]["ac_anatomical_parent"], "scapula.R")

    def test_05g_union_markers_are_saved_and_follow_their_bone(self):
        """Articulaciones, ligamentos e inserciones: en el .blend, en su sitio y moviendose con su hueso."""
        import bpy
        from mathutils import Euler, Vector
        from anatomical_core import articulations, articulations_scene, validation
        art = articulations.build_articulations(self.base, self.anat, articulations.load_articulation_data())
        self.open()
        self.assertEqual(validation.validate_articulations_snapshot(art, articulations_scene.read_back_articulations()), [])
        for col in ("AC_Articulations", "AC_Ligaments", "AC_Attachments"):
            self.assertIn(col, bpy.data.collections)
        self.assertEqual(json.loads(bpy.data.objects["ART_glenohumeral.L"]["ac_dofs"])[0]["source"], "magee_rom")
        arm = self.open()
        for n, e in (("thorax", (0.3, 0.0, 0.2)), ("clavicle.L", (0.0, 0.0, 0.4)), ("upper_arm.L", (0.6, 0.0, 0.0))):
            pb = arm.pose.bones[n]
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = Euler(e)
        bpy.context.view_layer.update()
        snap = articulations_scene.read_back_articulations()
        ev = self.evaluated(arm)
        moved = lambda obj, ref: dist(snap[obj]["points"][0], ref) > 0.002  # noqa: E731
        self.assertTrue(moved("ART_costovertebral_03.L", art.joints["costovertebral_03.L"].center))  # T3 -> thorax
        self.assertFalse(moved("ART_costovertebral_09.L", art.joints["costovertebral_09.L"].center))  # T9 -> spine_thoracic
        self.assertTrue(moved("ART_acromioclavicular.L", art.joints["acromioclavicular.L"].center))  # lo lleva la clavicula
        self.assertTrue(moved("ATT_inferior_angle.L", art.attachments["inferior_angle.L"].point))  # escapula -> clavicula
        self.assertTrue(moved("ATT_greater_tubercle.L", art.attachments["greater_tubercle.L"].point))  # humero -> upper_arm
        # la clavicula derecha (sin rotacion propia) cuelga del thorax base: su marcador sigue exactamente al torax
        thorax_delta = ev.pose.bones["thorax"].matrix @ arm.data.bones["thorax"].matrix_local.inverted()
        self.assertLess(dist(snap["ART_acromioclavicular.R"]["points"][0], thorax_delta @ Vector(art.joints["acromioclavicular.R"].center)), TOL)
        # el marcador glenohumeral lo lleva la escapula (clavicula): sigue al pivote del hombro posado
        self.assertLess(dist(snap["ART_glenohumeral.L"]["points"][0], ev.pose.bones["upper_arm.L"].head), TOL)

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
