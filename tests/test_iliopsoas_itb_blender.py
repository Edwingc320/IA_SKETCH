"""CM-5 en Blender: con el rig real, el psoas-iliaco, la cintilla iliotibial y el tensor de la fascia lata (tubos deformados por la armadura) siguen a sus
huesos y no atraviesan los obstaculos del femur y la pelvis en el barrido de 22 poses de cadera y rodilla. Cada anillo de los tubos evaluado por Blender
debe coincidir con la cinematica directa del modelo; incluye el CONTROL NEGATIVO (modificador silenciado: la ruta se queda atras)."""
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

from anatomical_core import articulations, ligament_paths as lp, pose as pose_mod, tendons, validation  # noqa: E402
from anatomical_core.config import PoseDef  # noqa: E402
from anatomical_core.geometry import add, length, scale, sub  # noqa: E402

TEST_OUT = ROOT / "output" / "_test"
UNITS = ("psoas_major", "iliacus", "iliotibial_tract", "tensor_fasciae_latae")
TOL = 1e-4  # 0.1 mm
PARTS = ("origin", "belly", "insertion")  # en el orden del recorrido, del origen a la insercion


def expected_rings(t, pts, posed, base, anat):
    """Centros de los anillos de un tubo, posados: mezcla lineal de las poses de los huesos de los dos sitios que rodean a cada punto."""
    out = []
    for a, b in zip(pts, pts[1:]):
        if length(sub(a, b)) < 1e-9:
            continue
        for p in (a, b):
            q = (0.0, 0.0, 0.0)
            for bone, w in t.node_weights(p):
                q = add(q, scale(posed.bones[lp.rig_bone(bone, base, anat)].apply(p), w))
            out.append(q)
    return out


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestIliopsoasAndItbInBlender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from anatomical_core import anatomy_pipeline, scene, tendons_scene
        cls.scene, cls.tscene = scene, tendons_scene
        TEST_OUT.mkdir(parents=True, exist_ok=True)
        cls.path = TEST_OUT / "iliopsoas_itb.blend"
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
        """Gira la cadera y la rodilla en el rig con las rotaciones de la FK del modelo; devuelve la pose del modelo."""
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
            chain = []
            for obj, pts in self.parts_of(t):
                got = snap[obj]["rings"]
                want = expected_rings(t, pts, posed, self.base, self.anat)
                self.assertEqual(len(got), len(want), obj)
                for g, w in zip(got, want):
                    self.assertLess(length(sub(g, w)), TOL, (side, pose_name, obj))  # cada anillo esta donde la FK lo pone: nada descolgado
                chain += got
            self.assertGreaterEqual(lp.path_clearance(chain, [surfaces[a] for a in t.avoid], samples=4), -TOL / 10, (side, pose_name, n))  # y no entra en el hueso

    def test_the_tubes_of_the_wrapped_units_are_armature_deformed_and_the_rest_stay_rigid(self):
        import bpy
        self.scene.open_blend(self.path)
        for n in UNITS:
            for s in "LR":
                t = self.tm.tendons[f"{n}.{s}"]
                for obj, _ in self.parts_of(t):
                    o = bpy.data.objects[obj]
                    self.assertEqual((o.parent.name, o.parent_type), ("AC_Armature", "OBJECT"), obj)
                    self.assertEqual([m.type for m in o.modifiers], ["ARMATURE"], obj)
                    self.assertEqual({g.name for g in o.vertex_groups}, {x.bone for x in t.sites}, obj)
                    self.assertTrue(o["ac_deform"])
        rigid = bpy.data.objects["TEN_belly_biceps_femoris.L"]
        self.assertEqual((rigid.parent_type, len(rigid.modifiers)), ("BONE", 0))

    def test_the_file_validates_in_rest(self):
        self.scene.open_blend(self.path)
        self.assertEqual(tendons.validate_tendons_snapshot(self.tm, self.tscene.read_back_tendons()), [])
        self.assertEqual(tendons.validate_tendon_poses(self.base, self.anat, self.art, self.tm), [])
        self.assertEqual([i for i in validation.validate_articulations(self.base, self.anat, self.art) if i.severity == "error"], [])

    def test_blender_follows_the_model_fk_and_never_penetrates_in_the_left_sweep(self):
        for pose_name, rotations in lp.LEG_SWEEP:
            self.check_pose("L", pose_name, rotations)

    def test_blender_follows_the_model_fk_and_never_penetrates_on_the_right_side(self):
        sweep = dict(lp.LEG_SWEEP)
        for pose_name in ("flexion_120", "extension_15", "abduction_45", "knee_135", "hip_120_knee_135", "hip_30_abduction_45_knee_30"):
            self.check_pose("R", pose_name, sweep[pose_name])

    def test_the_far_ends_travel_with_their_bones(self):
        arm = self.open_reset()
        rest = self.tscene.read_back_tendons()
        self.pose_leg(arm, "L", {"hip": {"flexion": 90.0}, "knee": {"flexion": 90.0}})
        moved = self.tscene.read_back_tendons()
        itb = "TEN_insertion_iliotibial_tract.L"  # acaba en Gerdy, en la tibia: viaja con la rodilla y la cadera
        self.assertGreater(length(sub(moved[itb]["points"][1], rest[itb]["points"][1])), 0.2)
        psoas = "TEN_insertion_psoas_major.L"
        self.assertGreater(length(sub(moved[psoas]["points"][1], rest[psoas]["points"][1])), 0.03)  # el trocanter menor sigue al femur
        self.assertLess(length(sub(moved["TEN_belly_iliacus.L"]["points"][0], rest["TEN_belly_iliacus.L"]["points"][0])), TOL)  # el origen se queda en la pelvis
        for k in rest:  # la pierna derecha no se entera
            if k.endswith(".R") and any(u in k for u in UNITS):
                self.assertLess(max(length(sub(a, b)) for a, b in zip(moved[k]["rings"], rest[k]["rings"])), TOL, k)

    def test_negative_control_a_muted_armature_leaves_the_route_behind(self):
        import bpy
        arm = self.open_reset()
        for o in bpy.data.objects:
            if o.name.startswith("TEN_") and o.name.endswith("iliotibial_tract.L"):
                o.modifiers["AC_Armature"].show_viewport = False
        posed = self.pose_leg(arm, "L", {"hip": {"flexion": 90.0}, "knee": {"flexion": 90.0}})
        snap = self.tscene.read_back_tendons()
        t = self.tm.tendons["iliotibial_tract.L"]
        obj, pts = self.parts_of(t)[-1]
        got, want = snap[obj]["rings"], expected_rings(t, pts, posed, self.base, self.anat)
        self.assertGreater(max(length(sub(g, w)) for g, w in zip(got, want)), 0.1)  # la comparacion lo detecta


if __name__ == "__main__":
    unittest.main()
