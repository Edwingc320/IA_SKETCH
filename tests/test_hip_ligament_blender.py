"""CM-4 en Blender: al girar la cadera con el rig real, los ligamentos de la cadera siguen a sus huesos (no quedan descolgados) y no atraviesan la
cabeza ni el cuello del femur. La poligonal evaluada por Blender (modificador Armature) debe coincidir con la FK del modelo en cada pose del
barrido, y se incluye el CONTROL NEGATIVO: con el modificador silenciado el ligamento se queda atras y la prueba lo detecta."""
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

from anatomical_core import articulations, ligament_paths as lp, pose as pose_mod, validation  # noqa: E402
from anatomical_core.config import PoseDef  # noqa: E402
from anatomical_core.geometry import length, sub  # noqa: E402

TEST_OUT = ROOT / "output" / "_test"
HIP_LIGAMENTS = ("iliofemoral", "pubofemoral", "ischiofemoral")
TOL = 1e-4  # 0.1 mm


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestHipLigamentsInBlender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from anatomical_core import anatomy_pipeline, articulations_scene, scene
        cls.scene, cls.ascene = scene, articulations_scene
        TEST_OUT.mkdir(parents=True, exist_ok=True)
        cls.path = TEST_OUT / "hip_ligaments.blend"
        cls.res = anatomy_pipeline.generate(cls.path, preview=False, log=lambda *_: None)
        cls.base, cls.anat = cls.res.base, cls.res.anatomy
        cls.art = articulations.build_articulations(cls.base, cls.anat, articulations.load_articulation_data())

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

    def pose_hip(self, arm, side, rotations):
        """Gira la cadera en el rig con la rotacion que da la FK del modelo; devuelve la pose del modelo."""
        import bpy
        posed = pose_mod.apply_pose(self.base, PoseDef("t", {f"hip.{side}": rotations}))
        arm.pose.bones[f"thigh.{side}"].rotation_quaternion = posed.bones[f"thigh.{side}"].local_quat
        bpy.context.view_layer.update()
        return posed

    def evaluated_path(self, ligament):
        return [tuple(p) for p in self.ascene.read_back_articulations()[f"LIG_{ligament}"]["points"]]

    def test_the_ligaments_are_armature_deformed_meshes_not_rigid_children(self):
        import bpy
        self.scene.open_blend(self.path)
        for s in "LR":
            for n in HIP_LIGAMENTS:
                o = bpy.data.objects[f"LIG_{n}.{s}"]
                self.assertEqual((o.parent.name, o.parent_type), ("AC_Armature", "OBJECT"))
                self.assertEqual([m.type for m in o.modifiers], ["ARMATURE"])
                self.assertEqual({g.name for g in o.vertex_groups}, {b for b, _ in lp.nodes(self.art.ligaments[f"{n}.{s}"])})
                self.assertTrue(o["ac_deform"])
        rigid = bpy.data.objects["LIG_sacrotuberous.L"]  # el resto sigue siendo rigido
        self.assertEqual((rigid.parent_type, len(rigid.modifiers)), ("BONE", 0))

    def test_the_file_validates_in_rest_including_the_deformed_ligaments(self):
        self.scene.open_blend(self.path)
        snap = self.ascene.read_back_articulations()
        self.assertEqual(validation.validate_articulations_snapshot(self.art, snap), [])
        self.assertEqual(len(snap["LIG_pubofemoral.L"]["points"]), 3)  # origen, guia, insercion

    def test_blender_follows_the_model_fk_and_never_penetrates_the_femur_in_the_whole_sweep(self):
        for side in "LR":
            for pose_name, rot in lp.HIP_SWEEP:
                arm = self.open_reset()
                posed = self.pose_hip(arm, side, rot)
                surfaces = {s.name: s for s in lp.posed_surfaces(self.art, self.base, self.anat, posed)}
                for n in HIP_LIGAMENTS:
                    got = self.evaluated_path(f"{n}.{side}")
                    want = lp.posed_path(self.art.ligaments[f"{n}.{side}"], self.base, self.anat, posed)
                    self.assertEqual(len(got), len(want))
                    for g, w in zip(got, want):
                        self.assertLess(length(sub(g, w)), TOL, (side, pose_name, n))  # cada nodo esta donde la FK lo pone: no hay ligamento descolgado
                    self.assertGreaterEqual(lp.path_clearance(got, [surfaces[a] for a in self.art.ligaments[f"{n}.{side}"].avoid]), -TOL / 10, (side, pose_name, n))  # y la poligonal de Blender no entra en el hueso

    def test_the_extremes_really_move_with_the_femur(self):
        arm = self.open_reset()
        rest = {n: self.evaluated_path(f"{n}.L") for n in HIP_LIGAMENTS}
        self.pose_hip(arm, "L", {"flexion": 120.0})
        for n in HIP_LIGAMENTS:
            moved = self.evaluated_path(f"{n}.L")
            self.assertLess(length(sub(moved[0], rest[n][0])), TOL, n)  # el origen se queda en la pelvis
            self.assertGreater(length(sub(moved[-1], rest[n][-1])), 0.03, n)  # la insercion viaja varios centimetros con el femur
        arm = self.open_reset()
        before = self.evaluated_path("iliofemoral.R")
        self.pose_hip(arm, "L", {"flexion": 120.0})
        self.assertLess(max(length(sub(a, b)) for a, b in zip(before, self.evaluated_path("iliofemoral.R"))), TOL)  # la cadera derecha no se entera

    def test_negative_control_a_muted_armature_leaves_the_ligament_behind_and_the_check_notices(self):
        """Mutacion: sin el modificador (o con el ligamento emparentado rigido al hueso de origen) la insercion se queda atras y la comparacion falla."""
        import bpy
        arm = self.open_reset()
        for n in HIP_LIGAMENTS:
            bpy.data.objects[f"LIG_{n}.L"].modifiers["AC_Armature"].show_viewport = False
        posed = self.pose_hip(arm, "L", {"flexion": 90.0})
        for n in HIP_LIGAMENTS:
            got = self.evaluated_path(f"{n}.L")
            want = lp.posed_path(self.art.ligaments[f"{n}.L"], self.base, self.anat, posed)
            self.assertGreater(length(sub(got[-1], want[-1])), 0.02, n)  # la insercion queda >2 cm de donde esta el femur


if __name__ == "__main__":
    unittest.main()
