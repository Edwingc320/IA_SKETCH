"""Pose A (cinematica directa) sobre el esqueleto neutro (Python puro)."""
import dataclasses
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anatomical_core import pose, validation  # noqa: E402
from anatomical_core.config import ConfigError, PoseDef, load_config  # noqa: E402
from anatomical_core.geometry import (  # noqa: E402
    IDENTITY, dot, length, mat_mul, mat_transpose, mat_vec, mirror_point, normalize, rotation_matrix, sub,
)
from anatomical_core.skeleton import build_model  # noqa: E402


def angle_deg(a, b):
    c = dot(a, b) / (length(a) * length(b))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def quat_to_matrix(q):
    w, x, y, z = q
    return (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
    )


def seg(model_or_posed, name, posed=False):
    b = model_or_posed.bones[name]
    return sub(b.tail, b.head)


class PoseBase(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()
        self.model = build_model(self.cfg)
        self.posed = pose.apply_pose(self.model, self.cfg.pose)


class TestPoseDoesNotTouchTheNeutral(PoseBase):
    def test_modifying_the_pose_does_not_change_the_neutral_structure(self):
        before = (self.model.signature(), {n: (b.head, b.tail, b.length, b.frame) for n, b in self.model.bones.items()},
                  {n: j.pivot for n, j in self.model.joints.items()})
        for override in ({"shoulder.abduction": 10.0}, {"elbow.flexion": 90.0, "elbow.pronation": 20.0}, {"hip.flexion": 30.0}):
            cfg = load_config(pose_overrides=override)
            m2 = build_model(cfg)
            pose.apply_pose(m2, cfg.pose)
            self.assertEqual(m2.signature(), before[0])  # el neutro es identico
            self.assertNotEqual(cfg.pose_signature, self.cfg.pose_signature)
            self.assertEqual(cfg.signature, self.cfg.signature)
        pose.apply_pose(self.model, PoseDef("x", {"shoulder": {"abduction": 80.0}}))
        after = (self.model.signature(), {n: (b.head, b.tail, b.length, b.frame) for n, b in self.model.bones.items()},
                 {n: j.pivot for n, j in self.model.joints.items()})
        self.assertEqual(before, after)  # apply_pose no muta el modelo

    def test_changing_a_length_changes_the_neutral_and_the_pose(self):
        cfg = load_config(length_overrides={"upper_arm": 0.18})
        self.assertNotEqual(cfg.signature, self.cfg.signature)
        m2 = build_model(cfg)
        self.assertNotEqual(pose.apply_pose(m2, cfg.pose).signature, self.posed.signature)

    def test_neutral_pose_is_the_identity(self):
        posed = pose.apply_pose(self.model, PoseDef("neutral", {}))
        for c in posed.root_translation:
            self.assertAlmostEqual(c, 0.0, places=12)  # ruido de coma flotante (~1e-17), no un desplazamiento
        for n, b in self.model.bones.items():
            self.assertLess(length(sub(posed.bones[n].head, b.head)), 1e-12)
            self.assertLess(length(sub(posed.bones[n].tail, b.tail)), 1e-12)


class TestForwardKinematics(PoseBase):
    def test_pose_reproduces_the_configured_angles(self):
        """Los angulos MEDIDOS en la pose coinciden con los parametros de pose_a.json."""
        down = (0.0, 0.0, -1.0)
        for side in "LR":
            ua = seg(self.posed, f"upper_arm.{side}")
            fa = seg(self.posed, f"forearm.{side}")
            ha = seg(self.posed, f"hand.{side}")
            self.assertAlmostEqual(angle_deg(ua, down), 40.0, places=9, msg="abduccion de hombro")
            self.assertAlmostEqual(angle_deg(ua, fa), 12.0, places=9, msg="flexion de codo")
            self.assertAlmostEqual(angle_deg(fa, ha), 6.0, places=9, msg="flexion de muneca")
            th = seg(self.posed, f"thigh.{side}")
            sh = seg(self.posed, f"shin.{side}")
            self.assertAlmostEqual(angle_deg(th, down), 3.0, places=9, msg="abduccion de cadera")
            self.assertAlmostEqual(angle_deg(th, sh), 0.0, places=6, msg="la rodilla no tiene quiebre (E3)")
            # abduccion: los brazos se separan del cuerpo (lateral)
            self.assertGreater(ua[0] * (1 if side == "L" else -1), 0)

    def test_lengths_and_connections_are_preserved(self):
        for n, b in self.model.bones.items():
            pb = self.posed.bones[n]
            self.assertAlmostEqual(length(sub(pb.tail, pb.head)), b.length, places=12, msg=n)
            if b.parent and length(sub(self.model.bones[b.parent].tail, b.head)) < 1e-9:  # hueso conectado
                self.assertLess(length(sub(self.posed.bones[b.parent].tail, pb.head)), 1e-9, n)

    def test_pivots_are_not_duplicated_or_displaced(self):
        self.assertEqual(len(self.model.joints), 19)
        for jn, j in self.model.joints.items():
            posed_pivot = self.posed.bones[j.bone].head
            parent = self.posed.bones[j.parent_bone]
            self.assertLess(length(sub(posed_pivot, parent.apply(j.pivot))), 1e-12, jn)  # = A_padre(pivote neutro)
        self.assertEqual([i for i in validation.validate_pose(self.model, self.posed) if i.severity == "error"], [])

    def test_left_right_symmetry_of_the_pose(self):
        for n in self.model.bones:
            if n.endswith(".L"):
                a, b = self.posed.bones[n], self.posed.bones[n[:-2] + ".R"]
                self.assertLess(length(sub(mirror_point(a.head), b.head)), 1e-12, n)
                self.assertLess(length(sub(mirror_point(a.tail), b.tail)), 1e-12, n)

    def test_fk_matches_an_independent_two_bone_computation(self):
        """Comprobacion independiente (a mano) de la cadena hombro -> codo -> muneca del brazo izquierdo.
        Se comparan vectores RELATIVOS entre huesos (la traslacion de raiz que apoya los pies no influye)."""
        m = self.model
        abd = next(d for d in m.joints["shoulder.L"].dofs if d.name == "abduction").axis
        flex = next(d for d in m.joints["elbow.L"].dofs if d.name == "flexion").axis
        r_sh = rotation_matrix(abd, math.radians(40.0))
        ua, fa = m.bones["upper_arm.L"], m.bones["forearm.L"]
        # brazo: el vector hombro->codo es el del neutro girado 40 grados sobre el eje de abduccion
        upper_posed = sub(self.posed.bones["forearm.L"].head, self.posed.bones["upper_arm.L"].head)
        self.assertLess(length(sub(upper_posed, mat_vec(r_sh, sub(ua.tail, ua.head)))), 1e-9)
        # antebrazo: el eje de flexion viaja con el brazo (r_sh) y gira 12 grados; el vector codo->muneca lo refleja
        r_el = mat_mul(r_sh, rotation_matrix(flex, math.radians(12.0)))
        fore_posed = sub(self.posed.bones["hand.L"].head, self.posed.bones["forearm.L"].head)
        self.assertLess(length(sub(fore_posed, mat_vec(r_el, sub(fa.tail, fa.head)))), 1e-9)

    def test_hinge_axes_stay_perpendicular_to_adjacent_posed_segments(self):
        """E1 en la pose: el eje de flexion del codo (arrastrado por el brazo) es perpendicular al brazo
        y al antebrazo posados; igual para la rodilla."""
        for side in "LR":
            for jn, upper, lower in ((f"elbow.{side}", f"upper_arm.{side}", f"forearm.{side}"), (f"knee.{side}", f"thigh.{side}", f"shin.{side}")):
                j = self.model.joints[jn]
                flex = next(d for d in j.dofs if d.name == "flexion")
                axis_posed = mat_vec(self.posed.bones[j.parent_bone].rotation, flex.axis)
                for name in (upper, lower):
                    self.assertAlmostEqual(angle_deg(axis_posed, seg(self.posed, name)), 90.0, places=6, msg=f"{jn}/{name}")

    def test_local_quaternions_reproduce_the_world_rotation(self):
        """Los cuaterniones locales que se asignan a Blender (ejes locales del hueso) equivalen a R_b."""
        for n, b in self.model.bones.items():
            if not b.parent:
                continue
            pb, par = self.posed.bones[n], self.posed.bones[b.parent]
            f_cols = b.frame  # ejes del marco = columnas de F
            F = tuple(tuple(f_cols[j][i] for j in range(3)) for i in range(3))  # columnas -> matriz
            local = quat_to_matrix(pb.local_quat)
            rl_world = mat_mul(mat_mul(F, local), mat_transpose(F))
            expected = mat_mul(par.rotation, rl_world)
            for i in range(3):
                self.assertLess(length(sub(expected[i], pb.rotation[i])), 1e-9, n)

    def test_root_translation_grounds_the_feet_exactly(self):
        for side in "LR":
            self.assertAlmostEqual(self.posed.bones[f"foot.{side}"].head[2], self.model.ankle_height_m, places=12)
        self.assertLess(self.posed.root_translation[2], 0.0)  # abducir acorta la pierna en altura: la pelvis baja
        self.assertAlmostEqual(self.posed.root_translation[0], 0.0)
        self.assertAlmostEqual(self.posed.root_translation[1], 0.0)


class TestStanceAndFeet(PoseBase):
    def test_ankle_spacing_and_feet_support_of_the_provisional_3_degrees(self):
        """D4: los 3 grados de abduccion de cadera son provisionales; se calculan y validan separacion y apoyo."""
        m = pose.metrics(self.model, self.posed)
        hip = 2 * 0.052 * 1.75
        self.assertAlmostEqual(m["hip_spacing_m"], hip, places=12)
        leg = self.model.bones["thigh.L"].length + self.model.bones["shin.L"].length
        expected_ankle_x = 0.052 * 1.75 + leg * math.sin(math.radians(3.0))  # calculo independiente
        self.assertAlmostEqual(m["ankle_spacing_m"] / 2, expected_ankle_x, places=9)
        self.assertGreaterEqual(m["ankle_spacing_over_hip_spacing"], validation.STANCE_WARN[0])
        self.assertLessEqual(m["ankle_spacing_over_hip_spacing"], validation.STANCE_WARN[1])
        for side in "LR":
            self.assertLess(m[f"foot_{side}_tilt_deg"], 1e-6)  # pie plano
            self.assertAlmostEqual(m[f"foot_{side}_ankle_height_error_m"], 0.0, places=12)
        self.assertAlmostEqual(m["ankle_level_diff_m"], 0.0, places=12)
        self.assertEqual(validation.validate_pose(self.model, self.posed), [])  # sin errores ni avisos

    def test_abduction_without_ankle_compensation_tilts_the_foot_and_is_rejected(self):
        cfg = load_config(pose_overrides={"hip.abduction": 8.0})  # ankle.inversion sigue en -3
        posed = pose.apply_pose(build_model(cfg), cfg.pose)
        self.assertEqual(posed.angles["ankle.L"]["inversion"], -3.0)
        issues = validation.validate_pose(build_model(cfg), posed)
        self.assertIn("POSE_FOOT_TILTED", {i.code for i in validation.errors(issues)})
        # con la compensacion correcta (-8) vuelve a ser valida
        cfg2 = load_config(pose_overrides={"hip.abduction": 8.0, "ankle.inversion": -8.0})
        posed2 = pose.apply_pose(build_model(cfg2), cfg2.pose)
        self.assertEqual(validation.errors(validation.validate_pose(build_model(cfg2), posed2)), [])
        self.assertLess(pose.metrics(build_model(cfg2), posed2)["foot_L_tilt_deg"], 1e-6)

    def test_extreme_stance_is_rejected(self):
        cfg = load_config(pose_overrides={"hip.abduction": 40.0, "ankle.inversion": -40.0})
        m = build_model(cfg)
        posed = pose.apply_pose(m, cfg.pose)
        self.assertIn("POSE_STANCE", {i.code for i in validation.errors(validation.validate_pose(m, posed))})

    def test_one_sided_pose_keeps_feet_on_the_ground_or_is_flagged(self):
        cfg = load_config(pose_overrides={"hip.L.flexion": 60.0})  # solo la pierna izquierda
        m = build_model(cfg)
        posed = pose.apply_pose(m, cfg.pose)
        self.assertIn("POSE_FEET_NOT_LEVEL", {i.code for i in validation.errors(validation.validate_pose(m, posed))})


class TestPoseLimitsAndConfig(PoseBase):
    def test_values_outside_the_limits_are_rejected(self):
        for override in ({"elbow.flexion": 150.0}, {"elbow.flexion": -5.0}, {"shoulder.abduction": 200.0}, {"knee.flexion": -1.0}):
            cfg = load_config(pose_overrides=override)
            m = build_model(cfg)
            posed = pose.apply_pose(m, cfg.pose)
            self.assertIn("POSE_OUT_OF_LIMITS", {i.code for i in validation.errors(validation.validate_pose(m, posed))}, override)

    def test_limit_edges_are_accepted(self):
        cfg = load_config(pose_overrides={"elbow.flexion": 145.0, "shoulder.abduction": 180.0, "knee.flexion": 0.0})
        m = build_model(cfg)
        posed = pose.apply_pose(m, cfg.pose)
        self.assertNotIn("POSE_OUT_OF_LIMITS", {i.code for i in validation.errors(validation.validate_pose(m, posed))})

    def test_unknown_joint_or_dof_is_a_config_error(self):
        with self.assertRaises(ConfigError):
            pose.apply_pose(self.model, PoseDef("x", {"no_existe": {"flexion": 1.0}}))
        with self.assertRaises(ConfigError):
            pose.apply_pose(self.model, PoseDef("x", {"elbow": {"no_dof": 1.0}}))
        with self.assertRaises(ConfigError):
            load_config(pose_overrides={"abduction": 5.0})  # falta la articulacion
        with self.assertRaises(ConfigError):
            load_config(pose_overrides={"shoulder.abduction": float("nan")})

    def test_side_specific_key_overrides_the_general_one(self):
        posed = pose.apply_pose(self.model, PoseDef("x", {"shoulder": {"abduction": 30.0}, "shoulder.R": {"abduction": 50.0}}))
        self.assertEqual(posed.angles["shoulder.L"]["abduction"], 30.0)
        self.assertEqual(posed.angles["shoulder.R"]["abduction"], 50.0)
        down = (0.0, 0.0, -1.0)
        self.assertAlmostEqual(angle_deg(seg(posed, "upper_arm.R"), down), 50.0, places=9)

    def test_multiple_dofs_compose_in_the_listed_order(self):
        """Documentado: dof compuestos en el orden listado sobre ejes locales fijos (extrinseco)."""
        j = self.model.joints["shoulder.L"]
        fl = next(d for d in j.dofs if d.name == "flexion").axis
        ab = next(d for d in j.dofs if d.name == "abduction").axis
        posed = pose.apply_pose(self.model, PoseDef("x", {"shoulder.L": {"flexion": 30.0, "abduction": 40.0}}))
        r_expected = mat_mul(rotation_matrix(ab, math.radians(40.0)), rotation_matrix(fl, math.radians(30.0)))  # flexion primero
        self.assertLess(length(sub(mat_vec(posed.bones["upper_arm.L"].rotation, (0, 0, 1)), mat_vec(r_expected, (0, 0, 1)))), 1e-9)


if __name__ == "__main__":
    unittest.main()
