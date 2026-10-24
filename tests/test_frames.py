"""Marcos locales, ejes, signos, simetria y limites del esqueleto NEUTRO (Python puro)."""
import dataclasses
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anatomical_core import validation  # noqa: E402
from anatomical_core.config import ConfigError, load_config  # noqa: E402
from anatomical_core.geometry import (  # noqa: E402
    cross, dot, frame_from_direction, length, mat_vec, mirror_axis, mirror_frame, rotation_matrix, sub,
)
from anatomical_core.skeleton import build_model  # noqa: E402

IDX = {"x": 0, "y": 1, "z": 2}


def angle_deg(a, b):
    c = dot(a, b) / (length(a) * length(b))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


class TestFrames(unittest.TestCase):
    def setUp(self):
        self.model = build_model(load_config())

    def test_frames_are_orthonormal_right_handed_and_follow_the_bone(self):
        for b in self.model.bones.values():
            x, y, z = b.frame
            for a in b.frame:
                self.assertAlmostEqual(length(a), 1.0, places=12, msg=b.name)
            self.assertAlmostEqual(dot(x, y), 0.0, places=12, msg=b.name)
            self.assertAlmostEqual(dot(y, z), 0.0, places=12, msg=b.name)
            self.assertAlmostEqual(dot(x, z), 0.0, places=12, msg=b.name)
            self.assertLess(length(sub(cross(x, y), z)), 1e-12, b.name)  # derecho
            d = sub(b.tail, b.head)
            self.assertLess(length(sub(y, tuple(c / length(d) for c in d))), 1e-12, b.name)

    def test_right_frames_are_the_mirror_of_left_frames(self):
        for n, b in self.model.bones.items():
            if n.endswith(".L"):
                r = self.model.bones[n[:-2] + ".R"]
                for e, a in zip(mirror_frame(b.frame), r.frame):
                    self.assertLess(length(sub(e, a)), 1e-12, n)

    def test_hint_parallel_to_bone_is_rejected(self):
        with self.assertRaises(ValueError):
            frame_from_direction((1, 0, 0), (1, 0, 0))

    def test_limb_bones_are_vertical_and_straight_in_neutral(self):
        """E2: el neutro es la posicion anatomica: sin flexion de codo/muneca/rodilla ni quiebre de rodilla."""
        down = (0.0, 0.0, -1.0)
        for side in "LR":
            for seg in ("upper_arm", "forearm", "hand", "thigh", "shin"):
                b = self.model.bones[f"{seg}.{side}"]
                self.assertLess(angle_deg(sub(b.tail, b.head), down), 1e-9, f"{seg}.{side}")
            shin, foot = self.model.bones[f"shin.{side}"], self.model.bones[f"foot.{side}"]
            self.assertAlmostEqual(angle_deg(sub(shin.tail, shin.head), sub(foot.tail, foot.head)), 90.0, places=9)

    def test_structural_tilts_are_documented(self):
        """Base v2: inclinaciones estructurales del neutro. Pelvis inclinada (PT) compensada por el segmento
        lumbar; toracica, torax, cuello y cabeza como en la v0.2; clavicula del manubrio al acromion."""
        up = (0.0, 0.0, 1.0)
        tilts = {n: angle_deg(sub(self.model.bones[n].tail, self.model.bones[n].head), up)
                 for n in ("pelvis", "spine_lumbar", "spine_thoracic", "thorax", "neck", "head")}
        for n, expected in (("pelvis", 15.5), ("spine_lumbar", 8.4), ("spine_thoracic", 3.4), ("thorax", 1.1), ("neck", 6.8), ("head", 1.1)):
            self.assertAlmostEqual(tilts[n], expected, delta=0.1, msg=n)
        pel = sub(self.model.bones["pelvis"].tail, self.model.bones["pelvis"].head)
        lum = sub(self.model.bones["spine_lumbar"].tail, self.model.bones["spine_lumbar"].head)
        self.assertGreater(pel[1], 0)  # S1 detras del eje de las caderas (+Y)
        self.assertLess(lum[1], 0)  # el segmento lumbar vuelve hacia delante y compensa
        self.assertAlmostEqual(self.model.bones["spine_thoracic"].head[1], 0.004896, places=6)  # el tronco no se mueve
        cl = self.model.bones["clavicle.L"]
        v = sub(cl.tail, cl.head)
        self.assertAlmostEqual(math.degrees(math.asin(v[2] / length(v))), 22.7, delta=0.1)  # elevacion
        self.assertGreater(v[1], 0)  # del manubrio (delante) hacia atras hasta el acromion
        self.assertIn("INCLINACIONES ESTRUCTURALES", Path(__file__).resolve().parents[1].joinpath("config", "skeleton_definition.json").read_text(encoding="utf-8"))

    def test_base_v2_keeps_arms_legs_and_stature_where_they_were(self):
        """El cambio de la base solo mueve pelvis, lumbar, cuello, cabeza y clavicula: el hombro (pivote), el
        brazo, la pierna y la altura del vertex quedan exactamente donde estaban en la v0.2."""
        m = self.model
        self.assertAlmostEqual(m.joints["shoulder.L"].pivot[0], 0.182708, delta=1e-6)
        self.assertAlmostEqual(m.joints["shoulder.L"].pivot[1], -0.013356, delta=1e-6)
        self.assertAlmostEqual(m.joints["shoulder.L"].pivot[2], 1.443492, delta=1e-6)
        self.assertAlmostEqual(max(b.tail[2] for b in m.bones.values()), 1.749011, delta=1e-6)  # vertex
        self.assertAlmostEqual(m.bones["spine_lumbar"].tail[2], 1.137402, delta=1e-6)
        self.assertAlmostEqual(m.bones["neck"].length + 0.0, 0.085 * m.height_m, places=9)  # cuello C1-C7: 0.085 H
        self.assertLess(m.bones["head"].length, 0.10 * m.height_m)  # la cabeza va de los condilos al vertex


class TestJointAxes(unittest.TestCase):
    """E1 y E4: ejes ortogonales, perpendiculares al hueso y alineados con los ejes locales."""

    def setUp(self):
        self.model = build_model(load_config())

    def test_every_axis_is_plus_minus_a_local_axis_of_its_bone(self):
        n = 0
        for j in self.model.joints.values():
            bone = self.model.bones[j.bone]
            for d in j.dofs:
                col = bone.frame[IDX[d.axis_local]]
                self.assertLess(length(sub(d.axis, tuple(d.axis_sign * c for c in col))), 1e-12, f"{j.name}.{d.name}")
                n += 1
        self.assertEqual(n, 47)  # 15 centrales + 16 por lado x 2

    def test_axes_of_a_joint_are_mutually_orthogonal(self):
        for j in self.model.joints.values():
            for i, a in enumerate(j.dofs):
                for b in j.dofs[i + 1:]:
                    self.assertAlmostEqual(dot(a.axis, b.axis), 0.0, places=12, msg=f"{j.name}: {a.name}/{b.name}")

    def test_hinge_axes_are_perpendicular_to_the_bone_and_axial_axes_parallel(self):
        """E1: antes el eje de flexion de hombro/codo/muneca formaba 130/127/128 grados con el hueso."""
        for jn in ("shoulder.L", "shoulder.R", "elbow.L", "elbow.R", "wrist.L", "wrist.R", "hip.L", "knee.R", "ankle.L"):
            j = self.model.joints[jn]
            y = self.model.bones[j.bone].frame[1]
            for d in j.dofs:
                if d.positive_motion == "axial":
                    self.assertAlmostEqual(abs(dot(d.axis, y)), 1.0, places=12, msg=f"{jn}.{d.name}")
                else:
                    self.assertAlmostEqual(angle_deg(d.axis, y), 90.0, places=9, msg=f"{jn}.{d.name}")

    def test_right_axes_are_pseudovector_mirror_of_left(self):
        for n, jl in self.model.joints.items():
            if n.endswith(".L"):
                jr = self.model.joints[n[:-2] + ".R"]
                for dl, dr in zip(jl.dofs, jr.dofs):
                    self.assertLess(length(sub(mirror_axis(dl.axis), dr.axis)), 1e-12, f"{n}.{dl.name}")
                    self.assertEqual((dl.min_deg, dl.max_deg), (dr.min_deg, dr.max_deg))

    def test_validator_accepts_the_model_and_has_no_axis_errors(self):
        self.assertEqual(validation.check_frames(self.model), [])
        self.assertEqual(validation.check_joint_axes(self.model), [])


# Tabla INDEPENDIENTE de la configuracion: movimiento esperado del extremo distal con angulo positivo.
# (vector en el espacio del modelo para el lado IZQUIERDO o central; el derecho refleja x si es lateral)
EXPECTED_POSITIVE_MOTION = {
    ("shoulder", "flexion"): (0, -1, 0), ("shoulder", "abduction"): (1, 0, 0),
    ("elbow", "flexion"): (0, -1, 0), ("wrist", "flexion"): (0, -1, 0), ("wrist", "deviation"): (1, 0, 0),
    ("hip", "flexion"): (0, -1, 0), ("hip", "abduction"): (1, 0, 0),
    ("knee", "flexion"): (0, 1, 0), ("ankle", "dorsiflexion"): (0, 0, 1),
    ("sternoclavicular", "elevation"): (0, 0, 1), ("sternoclavicular", "protraction"): (0, -1, 0),
    ("lumbar", "flexion"): (0, -1, 0), ("thoracic", "flexion"): (0, -1, 0), ("thorax", "flexion"): (0, -1, 0),
    ("neck", "flexion"): (0, -1, 0), ("head", "flexion"): (0, -1, 0),
    ("lumbar", "lateral_bend"): (1, 0, 0), ("thoracic", "lateral_bend"): (1, 0, 0),
    ("thorax", "lateral_bend"): (1, 0, 0), ("neck", "lateral_bend"): (1, 0, 0), ("head", "lateral_bend"): (1, 0, 0),
}
LATERAL = {("shoulder", "abduction"), ("wrist", "deviation"), ("hip", "abduction")}


class TestSigns(unittest.TestCase):
    """Sentido anatomico del movimiento positivo y negativo, calculado con rotaciones reales."""

    def setUp(self):
        self.model = build_model(load_config())

    def move(self, j, d, deg):
        tail = self.model.bones[j.bone].tail
        rel = sub(tail, j.pivot)
        return sub(mat_vec(rotation_matrix(d.axis, math.radians(deg)), rel), rel)

    def test_positive_and_negative_motion_for_every_joint_and_side(self):
        checked = 0
        for jn, j in self.model.joints.items():
            base, _, side = jn.partition(".")
            for d in j.dofs:
                key = (base, d.name)
                if key not in EXPECTED_POSITIVE_MOTION:
                    continue
                exp = EXPECTED_POSITIVE_MOTION[key]
                if side == "R" and key in LATERAL:
                    exp = (-exp[0], exp[1], exp[2])
                for limit_deg in (10.0, 30.0):
                    pos, neg = self.move(j, d, limit_deg), self.move(j, d, -limit_deg)
                    self.assertGreater(dot(pos, exp) / length(pos), 0.7, f"{jn}.{d.name} +{limit_deg}")
                    self.assertLess(dot(neg, exp) / length(neg), -0.7, f"{jn}.{d.name} -{limit_deg}")
                checked += 1
        # 10 dof centrales (5 articulaciones x flexion y lateral_bend) + 11 dof con lado x 2 lados
        self.assertEqual(checked, 10 + 11 * 2)

    def test_motion_keeps_its_sense_up_to_the_limits(self):
        """Hasta el limite del rango (acotado a 90 grados, donde el desplazamiento aun es monotono) el
        movimiento sigue el sentido anatomico: positivo hacia el declarado, negativo hacia el opuesto."""
        checked = 0
        for jn, j in self.model.joints.items():
            base, _, side = jn.partition(".")
            for d in j.dofs:
                key = (base, d.name)
                if key not in EXPECTED_POSITIVE_MOTION:
                    continue
                exp = EXPECTED_POSITIVE_MOTION[key]
                if side == "R" and key in LATERAL:
                    exp = (-exp[0], exp[1], exp[2])
                hi, lo = min(d.max_deg, 90.0), max(d.min_deg, -90.0)
                if hi > 0:
                    v = self.move(j, d, hi)
                    self.assertGreater(dot(v, exp) / length(v), 0.5, f"{jn}.{d.name} en +{hi}")
                if lo < 0:
                    v = self.move(j, d, lo)
                    self.assertLess(dot(v, exp) / length(v), -0.5, f"{jn}.{d.name} en {lo}")
                checked += 1
        self.assertEqual(checked, 10 + 11 * 2)

    def test_validator_semantics_agree_with_the_independent_table(self):
        self.assertEqual(validation.check_dof_semantics(self.model), [])

    def test_inverted_axis_sign_is_detected(self):
        j = self.model.joints["elbow.L"]
        flex = next(d for d in j.dofs if d.name == "flexion")
        flipped = dataclasses.replace(flex, axis=tuple(-c for c in flex.axis), axis_sign=-flex.axis_sign)
        bad = dataclasses.replace(j, dofs=tuple(flipped if d.name == "flexion" else d for d in j.dofs))
        m = dataclasses.replace(self.model, joints={**self.model.joints, "elbow.L": bad})
        self.assertIn("DOF_SEMANTICS", {i.code for i in validation.check_dof_semantics(m)})

    def test_non_perpendicular_or_non_local_axis_is_detected(self):
        """El defecto E1 original (eje del mundo en hueso inclinado) ahora se detecta."""
        j = self.model.joints["elbow.L"]
        bone = self.model.bones["forearm.L"]
        tilted_bone = dataclasses.replace(bone, tail=(bone.head[0] + 0.6 * bone.length, bone.head[1], bone.head[2] - 0.8 * bone.length))
        m = dataclasses.replace(self.model, bones={**self.model.bones, "forearm.L": tilted_bone})
        codes = {i.code for i in validation.check_frames(m) + validation.check_joint_axes(m)}
        self.assertIn("FRAME_Y_NOT_BONE", codes)  # el marco ya no sigue al hueso inclinado
        flex = next(d for d in j.dofs if d.name == "flexion")
        world_x = dataclasses.replace(flex, axis=(-0.8, 0.0, -0.6))  # eje que no es una columna del marco
        bad = dataclasses.replace(j, dofs=tuple(world_x if d.name == "flexion" else d for d in j.dofs))
        m2 = dataclasses.replace(self.model, joints={**self.model.joints, "elbow.L": bad})
        self.assertIn("AXIS_NOT_LOCAL", {i.code for i in validation.check_joint_axes(m2)})

    def test_non_orthonormal_frame_is_detected(self):
        b = self.model.bones["hand.L"]
        skew = dataclasses.replace(b, frame=(b.frame[0], b.frame[1], (0.0, 0.7071, 0.7071)))
        m = dataclasses.replace(self.model, bones={**self.model.bones, "hand.L": skew})
        self.assertIn("FRAME_NOT_ORTHOGONAL", {i.code for i in validation.check_frames(m)})
        left_handed = dataclasses.replace(b, frame=(b.frame[0], b.frame[1], tuple(-c for c in b.frame[2])))
        m2 = dataclasses.replace(self.model, bones={**self.model.bones, "hand.L": left_handed})
        self.assertIn("FRAME_NOT_RIGHT_HANDED", {i.code for i in validation.check_frames(m2)})


class TestLimits(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()
        self.model = build_model(self.cfg)

    def test_limits_are_measured_from_the_neutral_and_contain_zero(self):
        for j in self.model.joints.values():
            for d in j.dofs:
                self.assertLessEqual(d.min_deg, 0.0, f"{j.name}.{d.name}")
                self.assertGreaterEqual(d.max_deg, 0.0, f"{j.name}.{d.name}")

    def test_limit_values_are_unchanged_from_v0_1_and_a_pose_fits_inside(self):
        """D1/limites: los valores numericos no cambian; la geometria del neutro es la que se corrigio."""
        j = self.model.joints
        lim = lambda n, dof: next((d.min_deg, d.max_deg) for d in j[n].dofs if d.name == dof)  # noqa: E731
        self.assertEqual(lim("elbow.L", "flexion"), (0, 145))
        self.assertEqual(lim("knee.R", "flexion"), (0, 140))
        self.assertEqual(lim("ankle.L", "dorsiflexion"), (-50, 20))
        self.assertEqual(lim("shoulder.L", "abduction"), (-50, 180))
        self.assertEqual(lim("hip.R", "abduction"), (-30, 45))

    def test_schema_1_is_rejected_with_a_clear_message(self):
        import json
        import shutil
        import tempfile

        src = Path(__file__).resolve().parents[1] / "config"
        with tempfile.TemporaryDirectory(dir=str(Path(__file__).resolve().parents[1] / "output")) as tmp:
            for f in src.glob("*.json"):
                shutil.copy(f, tmp)
            p = Path(tmp) / "proportions.json"
            data = json.loads(p.read_text(encoding="utf-8"))
            data["schema_version"] = 1
            p.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ConfigError) as cm:
                load_config(tmp)
            self.assertIn("schema_version 1", str(cm.exception))
            self.assertIn("v0.1.0", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
