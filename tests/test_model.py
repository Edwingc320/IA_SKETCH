"""Pruebas del modelo de datos (Python puro: no requieren Blender)."""
import dataclasses
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anatomical_core import validation  # noqa: E402
from anatomical_core.config import ConfigError, load_config  # noqa: E402
from anatomical_core.joints import Dof, Joint  # noqa: E402
from anatomical_core.skeleton import REQUIRED_BONES, Bone, SkeletonModel, build_model  # noqa: E402


def make_model(**kw):
    return build_model(load_config(**kw))


def codes(issues):
    return {i.code for i in validation.errors(issues)}


def synthetic_snapshot(model, posed):
    """Snapshot ideal (lo que read_back deberia devolver) construido solo desde los datos del modelo."""
    from anatomical_core.geometry import mat_vec

    visuals = {}
    for n, pb in posed.bones.items():
        visuals[f"VIS_{n}"] = {"head": pb.head, "tail": pb.tail, "parent_bone": n}
    for jn, j in model.joints.items():
        if j.parent_bone is None:
            continue
        visuals[f"JM_{jn}"] = {"center": posed.bones[j.bone].head, "parent_bone": j.parent_bone}
        for d in j.dofs:
            visuals[f"AX_{jn}_{d.name}"] = {
                "location": posed.bones[j.bone].head,
                "direction": mat_vec(posed.bones[j.parent_bone].rotation, d.axis),
                "parent_bone": j.parent_bone,
            }
    return {
        "armature_object": "AC_Armature",
        "armature_transform_identity": True,
        "pose_position": "POSE",
        "bones": {n: {"parent": b.parent, "head": b.head, "tail": b.tail, "length": b.length, "frame": list(b.frame)} for n, b in model.bones.items()},
        "pose_bones": {n: {"head": pb.head, "tail": pb.tail} for n, pb in posed.bones.items()},
        "visuals": visuals,
        "collections": ["AC_Skeleton", "AC_BoneVisuals", "AC_JointMarkers", "AC_JointAxes"],
        "counts": {
            "joint_markers": len(model.joints),
            "joint_axes": sum(len(j.dofs) for j in model.joints.values()),
            "bone_visuals": len(model.bones),
        },
        "meta": {"model_signature": model.signature(), "pose_signature": posed.signature},
    }


class TestValidModel(unittest.TestCase):
    def setUp(self):
        self.model = make_model()

    def test_01_required_bones_exist(self):
        for name in REQUIRED_BONES:
            self.assertIn(name, self.model.bones)
        self.assertEqual(validation.check_required_bones(self.model), [])

    def test_02_no_dangling_references(self):
        self.assertEqual(validation.check_references(self.model), [])
        for b in self.model.bones.values():
            self.assertTrue(b.parent is None or b.parent in self.model.bones)

    def test_03_hierarchy_valid_single_root_no_cycles(self):
        self.assertEqual(validation.check_hierarchy(self.model), [])
        self.assertEqual([b.name for b in self.model.bones.values() if b.parent is None], ["pelvis"])

    def test_04_lengths_positive_and_finite(self):
        self.assertEqual(validation.check_lengths(self.model), [])
        for b in self.model.bones.values():
            self.assertGreater(b.length, 0)
            self.assertTrue(math.isfinite(b.length))

    def test_05_pivots_and_axes_valid(self):
        self.assertEqual(validation.check_pivots_and_axes(self.model), [])
        self.assertGreaterEqual(len(self.model.joints), 19)

    def test_06_symmetry_and_grounding(self):
        self.assertEqual(validation.check_symmetry(self.model), [])
        self.assertEqual(validation.check_ground_neutral(self.model), [])
        # El apoyo del pie lo define el pivote del tobillo (ankle_height_fraction), no el punto mas bajo.
        self.assertAlmostEqual(self.model.ankle_height_m, 0.039 * 1.75, places=12)
        for side in "LR":
            foot = self.model.bones[f"foot.{side}"]
            self.assertAlmostEqual(foot.head[2], self.model.ankle_height_m, places=12)
            self.assertAlmostEqual(foot.tail[2], foot.head[2], places=12)  # pie horizontal
        lowest = min(min(b.head[2], b.tail[2]) for b in self.model.bones.values())
        self.assertGreaterEqual(lowest, self.model.ankle_height_m - 1e-9)

    def test_07_full_validation_has_no_errors(self):
        issues = validation.validate_model(self.model)
        self.assertEqual(validation.errors(issues), [], [str(i) for i in issues])

    def test_08_reproducible(self):
        a, b = make_model(), make_model()
        self.assertEqual(a.signature(), b.signature())
        self.assertEqual(a.config_signature, b.config_signature)

    def test_09_configurable_proportions(self):
        taller = make_model(height_m=1.90)
        self.assertNotEqual(taller.signature(), self.model.signature())
        self.assertAlmostEqual(taller.bones["thigh.L"].length / self.model.bones["thigh.L"].length, 1.90 / 1.75, places=6)
        longer = make_model(length_overrides={"thigh": 0.30})
        self.assertAlmostEqual(longer.bones["thigh.R"].length, 0.30 * 1.75, places=6)
        self.assertEqual(validation.errors(validation.validate_model(longer)), [])

    def test_10_bad_config_is_rejected(self):
        with self.assertRaises(ConfigError):
            load_config(height_m=-1)
        with self.assertRaises(ConfigError):
            load_config(length_overrides={"no_existe": 0.1})

    def test_11_mirrored_axes_are_pseudovector_mirrors(self):
        l, r = self.model.joints["shoulder.L"], self.model.joints["shoulder.R"]
        abd_l = next(d for d in l.dofs if d.name == "abduction").axis
        abd_r = next(d for d in r.dofs if d.name == "abduction").axis
        self.assertEqual(abd_l, (0.0, -1.0, 0.0))
        self.assertEqual(abd_r, (0.0, 1.0, 0.0))


class TestValidatorDetectsProblems(unittest.TestCase):
    """La validacion debe FALLAR ante datos corruptos (no solo aprobar datos buenos)."""

    def setUp(self):
        self.model = make_model()

    def with_bones(self, **changes):
        bones = dict(self.model.bones)
        for name, b in changes.items():
            n = name.replace("__", ".")
            if b is None:
                bones.pop(n)
            else:
                bones[n] = b
        return dataclasses.replace(self.model, bones=bones)

    def test_missing_bone(self):
        m = self.with_bones(head=None)
        self.assertIn("MISSING_BONE", codes(validation.validate_model(m)))

    def test_unknown_parent(self):
        b = self.model.bones["hand.L"]
        m = self.with_bones(hand__L=dataclasses.replace(b, parent="fantasma"))
        self.assertIn("UNKNOWN_PARENT", codes(validation.validate_model(m)))

    def test_cycle(self):
        m = self.with_bones(
            spine_lumbar=dataclasses.replace(self.model.bones["spine_lumbar"], parent="head"),
        )
        self.assertIn("CYCLE", codes(validation.validate_model(m)))

    def test_two_roots(self):
        m = self.with_bones(neck=dataclasses.replace(self.model.bones["neck"], parent=None))
        self.assertIn("ROOT_COUNT", codes(validation.validate_model(m)))

    def test_non_positive_and_nan_length(self):
        b = self.model.bones["shin.L"]
        self.assertIn("LENGTH_NOT_POSITIVE", codes(validation.validate_model(self.with_bones(shin__L=dataclasses.replace(b, length=0.0)))))
        self.assertIn("NON_FINITE", codes(validation.validate_model(self.with_bones(shin__L=dataclasses.replace(b, length=float("nan"))))))
        self.assertIn("NON_FINITE", codes(validation.validate_model(self.with_bones(shin__L=dataclasses.replace(b, tail=(0, float("inf"), 0))))))

    def test_length_mismatch(self):
        b = self.model.bones["shin.L"]
        m = self.with_bones(shin__L=dataclasses.replace(b, length=b.length * 2))
        self.assertIn("LENGTH_MISMATCH", codes(validation.validate_model(m)))

    def _with_joint(self, jname, joint):
        joints = dict(self.model.joints)
        joints[jname] = joint
        return dataclasses.replace(self.model, joints=joints)

    def test_bad_axis_pivot_limits(self):
        j = self.model.joints["knee.L"]
        d0 = j.dofs[0]
        bad_axis = dataclasses.replace(j, dofs=(dataclasses.replace(d0, axis=(2.0, 0, 0)),))
        self.assertIn("AXIS_INVALID", codes(validation.validate_model(self._with_joint("knee.L", bad_axis))))
        bad_pivot = dataclasses.replace(j, pivot=(9.0, 9.0, 9.0))
        self.assertIn("PIVOT_OFF_BONE", codes(validation.validate_model(self._with_joint("knee.L", bad_pivot))))
        bad_limits = dataclasses.replace(j, dofs=(dataclasses.replace(d0, min_deg=10, max_deg=5),))
        self.assertIn("LIMITS_INVALID", codes(validation.validate_model(self._with_joint("knee.L", bad_limits))))
        rest_out = dataclasses.replace(j, dofs=(dataclasses.replace(d0, min_deg=10, max_deg=50),))
        self.assertIn("REST_OUTSIDE_LIMITS", codes(validation.validate_model(self._with_joint("knee.L", rest_out))))
        parallel = dataclasses.replace(j, dofs=(d0, dataclasses.replace(d0, name="otro")))
        self.assertIn("AXES_PARALLEL", codes(validation.validate_model(self._with_joint("knee.L", parallel))))

    def test_joint_unknown_bone(self):
        j = dataclasses.replace(self.model.joints["knee.L"], bone="no_existe")
        self.assertIn("JOINT_UNKNOWN_BONE", codes(validation.validate_model(self._with_joint("knee.L", j))))

    def test_asymmetry(self):
        b = self.model.bones["hand.R"]
        m = self.with_bones(hand__R=dataclasses.replace(b, tail=(b.tail[0] + 0.1, b.tail[1], b.tail[2])))
        self.assertTrue({"ASYMMETRIC", "LENGTH_MISMATCH"} & codes(validation.validate_model(m)))

    def test_blend_snapshot_comparison(self):
        from anatomical_core import pose as pose_mod
        posed = pose_mod.apply_pose(self.model, load_config().pose)
        snap = synthetic_snapshot(self.model, posed)
        self.assertEqual(validation.validate_blend_snapshot(self.model, snap, posed), [])
        broken = dict(snap, bones={k: v for k, v in snap["bones"].items() if k != "head"})
        self.assertIn("BLEND_MISSING_BONE", codes(validation.validate_blend_snapshot(self.model, broken, posed)))
        self.assertIn("NO_ARMATURE", codes(validation.validate_blend_snapshot(self.model, dict(snap, armature_object=None), posed)))
        # el snapshot detecta: roll incorrecto, pose distinta de la FK, visual sin emparentar o desplazada
        bad_roll = dict(snap, bones={**snap["bones"], "forearm.L": dict(snap["bones"]["forearm.L"], frame=[(0, 1, 0), (1, 0, 0), (0, 0, 1)])})
        self.assertIn("BLEND_FRAME", codes(validation.validate_blend_snapshot(self.model, bad_roll, posed)))
        bad_pose = dict(snap, pose_bones={**snap["pose_bones"], "hand.L": {"head": (0, 0, 0), "tail": (0, 0, 1)}})
        self.assertIn("BLEND_POSE_POSITION", codes(validation.validate_blend_snapshot(self.model, bad_pose, posed)))
        unparented = dict(snap, visuals={**snap["visuals"], "VIS_hand.L": dict(snap["visuals"]["VIS_hand.L"], parent_bone=None)})
        self.assertIn("VIS_PARENT", codes(validation.validate_blend_snapshot(self.model, unparented, posed)))
        displaced = dict(snap, visuals={**snap["visuals"], "JM_elbow.L": dict(snap["visuals"]["JM_elbow.L"], center=(0, 0, 0))})
        self.assertIn("VIS_POSITION", codes(validation.validate_blend_snapshot(self.model, displaced, posed)))
        wrong_sig = dict(snap, meta=dict(snap["meta"], pose_signature="x"))
        self.assertIn("BLEND_POSE_SIGNATURE", codes(validation.validate_blend_snapshot(self.model, wrong_sig, posed)))


if __name__ == "__main__":
    unittest.main()
