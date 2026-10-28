"""CM-10: deslizamiento (tracking) de la rotula con la flexion de la rodilla.

La rotula se mueve respecto al femur segun patella_tracking.patella_transform (pitch = 0.9 x flexion y acercamiento radial de 0.04 mm por grado, parametros
AJUSTADOS a la geometria del modelo; la relacion con la flexion de la rodilla no se pudo verificar en la literatura). Las pruebas fijan: la cinematica, que la
rotula no entre en el femur y quede a < 12 mm de los condilos, que el ligamento rotuliano mantenga su longitud (antes de 27 a 81 mm, ahora de 27 a 29 mm) y que
el tendon cuadricipital rodee la troclea; en las 22 poses de barrido a 1.50, 1.75 y 2.05 m, en el modelo y en Blender (restricciones, sin drivers), con
MUTACIONES que se detectan."""
import copy
import math
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import bpy  # noqa: F401
    HAVE_BPY = True
except ImportError:
    HAVE_BPY = False

from anatomical_core import anatomy, articulations, ligament_paths as lp, patella_tracking as pt, pose as pose_mod, tendons, validation  # noqa: E402
from anatomical_core.config import ConfigError, PoseDef, load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

TEST_OUT = ROOT / "output" / "_test"
QUADRICEPS = ("rectus_femoris", "vastus_lateralis", "vastus_medialis", "vastus_intermedius")


def build_all(height=None, anatomy_dir=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    art = articulations.build_articulations(base, anat, articulations.load_articulation_data())
    return base, anat, art, tendons.build_tendons(base, anat, art, tendons.load_tendon_data())


def with_tracking(anat, side="L", **kw):
    b = anat.bones[f"patella.{side}"]
    return replace(anat, bones={**anat.bones, b.name: replace(b, tracking={**b.tracking, **kw})})


class TestPatellaKinematics(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art, self.tm = build_all()
        self.patella = self.anat.bones["patella.L"]

    def test_the_tracking_spec_is_declared_on_both_patellae_as_a_fitted_convention(self):
        for s in "LR":
            t = self.anat.bones[f"patella.{s}"].tracking
            self.assertEqual((t["driver_joint"], t["driver_dof"], t["pitch_ratio"], t["radial_mm_per_deg"]), ("knee", "flexion", 0.9, -0.04))
            self.assertIn("NO se pudo verificar", t["notes"])
            self.assertIn("Convencion", t["notes"])
        self.assertIsNone(self.anat.bones["femur.L"].tracking)  # solo la rotula se desliza

    def test_bad_tracking_specs_are_rejected(self):
        good = {"driver_joint": "knee", "driver_dof": "flexion", "pitch_ratio": 0.9, "radial_mm_per_deg": -0.04}
        self.assertEqual(anatomy._tracking_spec(good, "t"), good)
        for bad in ({**good, "pitch_ratio": 0.0}, {**good, "pitch_ratio": 2.0}, {**good, "radial_mm_per_deg": 5.0}, {k: v for k, v in good.items() if k != "driver_dof"}, "no es un objeto"):
            with self.assertRaises(ConfigError):
                anatomy._tracking_spec(bad, "t")

    def test_the_transform_is_the_identity_at_zero_flexion_and_pitches_c_times_the_flexion(self):
        t0 = pt.patella_transform(self.patella, self.base, 0.0)
        for p in (self.patella.head, self.patella.tail, (0.1, -0.05, 0.6)):
            self.assertLess(length(sub(t0.apply(p), p)), 1e-12)
        for f in (30.0, 90.0, 135.0):
            t = pt.patella_transform(self.patella, self.base, f)
            self.assertAlmostEqual(t.pitch_deg, 0.9 * f)
            # el pivote solo se desplaza por el deslizamiento radial (5.4 mm a 135 grados)
            self.assertAlmostEqual(length(sub(t.apply(t.pivot), t.pivot)), 0.04e-3 * f, places=9)
            # rotacion alrededor del eje de la rodilla (x): la coordenada x no cambia
            p = self.patella.head
            self.assertAlmostEqual(t.apply(p)[0], p[0], places=9)

    def test_left_and_right_are_mirror_images_and_the_transform_scales_with_height(self):
        for f in (45.0, 135.0):
            l = pt.patella_transform(self.patella, self.base, f)
            r = pt.patella_transform(self.anat.bones["patella.R"], self.base, f)
            p = self.patella.head
            self.assertLess(length(sub(mirror_point(l.apply(p)), r.apply(mirror_point(p)))), 1e-12)
        base2, anat2, _, _ = build_all(2.05)
        k = 2.05 / 1.75
        t1, t2 = pt.patella_transform(self.patella, self.base, 100.0), pt.patella_transform(anat2.bones["patella.L"], base2, 100.0)
        p = self.patella.tail
        self.assertLess(length(sub(tuple(k * c for c in t1.apply(p)), t2.apply(tuple(k * c for c in p)))), 1e-9)

    def test_the_patella_descends_in_front_of_and_below_the_condyles_at_deep_flexion(self):
        centre = tuple((a + b) / 2 for a, b in zip(self.patella.head, self.patella.tail))
        piv = self.base.joints["knee.L"].pivot
        t = pt.patella_transform(self.patella, self.base, 135.0).apply(centre)
        self.assertLess(t[2], piv[2] - 0.03)  # a mas de 3 cm bajo el eje de la rodilla
        self.assertLess(t[1] - piv[1], 0.02)  # y no por detras de los condilos mas de 2 cm
        self.assertAlmostEqual(math.degrees(math.atan2(t[2] - piv[2], t[1] - piv[1])) % 360.0, (math.degrees(math.atan2(centre[2] - piv[2], centre[1] - piv[1])) + 0.9 * 135.0) % 360.0, delta=3.0)


class TestPatellaSweep(unittest.TestCase):
    def test_validator_is_green_and_the_numbers_hold_at_three_heights(self):
        for h in (1.5, 1.75, 2.05):
            base, anat, art, tm = build_all(h)
            k = h / 1.75
            self.assertEqual(validation.validate_patella_tracking(base, anat, art), [], h)
            for side in "LR":
                body = art.surfaces[f"patellar_body.{side}"]
                lig = art.ligaments[f"patellar.{side}"]
                gaps, lengths, lig_clear, pitch_at = [], [], [], {}
                for pose_name, posed in lp.leg_sweep_poses(base, side):
                    sf = {s.name: s for s in lp.posed_surfaces(art, base, anat, posed)}
                    b = sf[body.name]
                    samples = [tuple(b.a[i] + (b.b[i] - b.a[i]) * j / 20 for i in range(3)) for j in range(21)]
                    cond, shaft = sf[f"femoral_lateral_condyle.{side}"], sf[f"femoral_shaft.{side}"]
                    gaps.append((min(cond.signed_distance(p) for p in samples) - b.radius_m, min(shaft.signed_distance(p) for p in samples) - b.radius_m))
                    path = lp.posed_path(lig, base, anat, posed)
                    lengths.append(lp.path_length(path))
                    lig_clear.append(lp.path_clearance(path, [sf[a] for a in lig.avoid]))
                    pitch_at[pose_name] = pt.patella_transform(anat.bones[f"patella.{side}"], base, pt.knee_flexion(posed, anat.bones[f"patella.{side}"])).pitch_deg
                self.assertTrue(all(0.002 * k < g[0] < 0.012 * k and g[1] > 0.005 * k for g in gaps), (h, side))  # sin penetrar y a < 12 mm del condilo
                self.assertLess(max(lengths) / min(lengths), 1.15, (h, side))  # antes 3.04
                self.assertAlmostEqual(min(lengths), 0.0267 * k, places=3)
                self.assertAlmostEqual(max(lengths), 0.0292 * k, places=3)  # 26.7 -> 29.2 mm a 1.75 m
                self.assertGreater(min(lig_clear), 0.010 * k, (h, side))  # el ligamento esta a > 10 mm del femur en todo el barrido
                self.assertAlmostEqual(pitch_at["knee_135"], 121.5)  # inclinacion a 135 grados
                self.assertAlmostEqual(pitch_at["hip_120_knee_135"], 121.5)  # solo depende de la rodilla
                self.assertEqual(pitch_at["flexion_120"], 0.0)  # la cadera no mueve la rotula respecto al femur
                for pose_name in ("knee_120", "knee_135", "hip_120_knee_135"):  # en flexion profunda (> 100 grados) ajusta posicion e inclinacion sin entrar en el femur
                    self.assertGreater(pitch_at[pose_name], 100.0)

    def test_the_quadriceps_wraps_the_trochlea_and_ends_on_the_gliding_patella(self):
        for h in (1.5, 1.75, 2.05):
            base, anat, art, tm = build_all(h)
            self.assertEqual(tendons.validate_tendon_poses(base, anat, art, tm), [], h)
            for n in QUADRICEPS:
                for s in "LR":
                    t = tm.tendons[f"{n}.{s}"]
                    self.assertTrue(t.deform and t.avoid, n)
                    self.assertEqual(t.sites[-1].bone, f"patella.{s}")
                    self.assertEqual([x.bone for x in t.sites[1:-1]], [f"femur.{s}", f"femur.{s}"])  # dos guias troclears
                    for x in t.sites:
                        self.assertLess(articulations.bone_distance(x.point, x.bone, base, anat, art.surfaces), 0.012 * h / 1.75, (n, x.kind))

    def test_the_insertion_of_the_quadriceps_travels_with_the_patella(self):
        base, anat, art, tm = build_all()
        rf = tm.tendons["rectus_femoris.L"]
        ins = rf.sites[-1]
        rest = lp.pose_point(ins.bone, ins.point, base, anat, pose_mod.apply_pose(base, PoseDef("t", {})))
        deep = lp.pose_point(ins.bone, ins.point, base, anat, pose_mod.apply_pose(base, PoseDef("t", {"knee.L": {"flexion": 135.0}})))
        self.assertGreater(length(sub(deep, rest)), 0.05)  # la insercion baja varios centimetros con la rotula
        # sin el deslizamiento (rotula rigida al femur) no se movia nada
        rigid = replace(anat, bones={**anat.bones, "patella.L": replace(anat.bones["patella.L"], tracking=None)})
        still = lp.pose_point(ins.bone, ins.point, base, rigid, pose_mod.apply_pose(base, PoseDef("t", {"knee.L": {"flexion": 135.0}})))
        self.assertLess(length(sub(still, rest)), 1e-12)

    # ---- mutaciones
    def test_mutation_without_the_glide_the_cm8_limitation_returns(self):
        base, anat, art, tm = build_all()
        rigid = replace(anat, bones={**anat.bones, "patella.L": replace(anat.bones["patella.L"], tracking=None)})
        codes = {i.code for i in validation.validate_patella_tracking(base, rigid, art, sides=("L",))}
        self.assertEqual(codes, set())  # sin tracking el validador no tiene nada que comprobar...
        lg = art.ligaments["patellar.L"]
        posed = pose_mod.apply_pose(base, PoseDef("t", {"knee.L": {"flexion": 135.0}}))
        sf = {s.name: s for s in lp.posed_surfaces(art, base, rigid, posed)}
        path = lp.posed_path(lg, base, rigid, posed)
        self.assertGreater(lp.path_length(path) / 0.0267, 3.0)  # ...pero la rotula rigida estira el ligamento 3x
        self.assertLess(lp.path_clearance(path, [sf[a] for a in lg.avoid]), -0.005)  # y lo mete en el femur

    def test_mutation_wrong_ratio_or_radial_glide_is_caught_by_the_validator(self):
        base, anat, art, tm = build_all()
        for kw, code in (({"pitch_ratio": 0.5}, "PATELLA_LIGAMENT_LENGTH"), ({"pitch_ratio": 1.0, "radial_mm_per_deg": 0.3}, "PATELLA_GAP"),
                         ({"radial_mm_per_deg": -0.5}, "PATELLA_PENETRATES"), ({"pitch_ratio": 0.3, "radial_mm_per_deg": 0.0}, "PATELLA_LIGAMENT_LENGTH")):
            bad = with_tracking(anat, **kw)
            self.assertIn(code, {i.code for i in validation.validate_patella_tracking(base, bad, art, sides=("L",))}, kw)
        self.assertEqual(validation.validate_patella_tracking(base, anat, art), [])

    def test_mutation_quadriceps_without_its_trochlear_guides_penetrates(self):
        base, anat, art, tm = build_all()
        for n in QUADRICEPS:
            t = tm.tendons[f"{n}.L"]
            bad = replace(tm, tendons={**tm.tendons, t.name: replace(t, sites=(t.sites[0], t.sites[-1]))})
            self.assertIn("TEN_PENETRATES", {i.code for i in tendons.validate_tendon_poses(base, anat, art, bad, sides=("L",))}, n)

    def test_mutation_a_guide_inside_the_condyle_is_caught(self):
        base, anat, art, tm = build_all()
        t = tm.tendons["vastus_lateralis.L"]
        inside = replace(t.sites[2], point=art.surfaces["femoral_lateral_condyle.L"].a)
        bad = replace(tm, tendons={**tm.tendons, t.name: replace(t, sites=(t.sites[0], t.sites[1], inside, t.sites[3]))})
        self.assertIn("TEN_PENETRATES", {i.code for i in tendons.validate_tendon_poses(base, anat, art, bad, sides=("L",))})


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestPatellaTrackingInBlender(unittest.TestCase):
    """Con el rig real (sin drivers): el hueso auxiliar gira la rotula con Copy Rotation y una restriccion Transformation la desplaza; la rotula evaluada por
    Blender debe coincidir con la cinematica del modelo en las 22 poses y a tres alturas, y el ligamento rotuliano y el tendon cuadricipital la siguen."""

    @classmethod
    def setUpClass(cls):
        from anatomical_core import anatomy_pipeline, scene, tendons_scene, articulations_scene
        cls.scene, cls.tscene, cls.ascene = scene, tendons_scene, articulations_scene
        TEST_OUT.mkdir(parents=True, exist_ok=True)
        cls.runs = {}
        for h in (1.5, 1.75, 2.05):
            path = TEST_OUT / f"patella_{int(h * 100)}.blend"
            res = anatomy_pipeline.generate(path, preview=False, log=lambda *_: None, height_m=h)
            art = articulations.build_articulations(res.base, res.anatomy, articulations.load_articulation_data())
            cls.runs[h] = (path, res.base, res.anatomy, art, tendons.build_tendons(res.base, res.anatomy, art, tendons.load_tendon_data()))

    def pose_and_read(self, run, side, rotations):
        import bpy
        path, base, anat, art, tm = run
        arm = bpy.data.objects["AC_Armature"]
        for pb in arm.pose.bones:
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            pb.location = (0.0, 0.0, 0.0)
        posed = pose_mod.apply_pose(base, PoseDef("t", {f"{j}.{side}": dict(r) for j, r in rotations.items()}))
        for j in rotations:
            bone = base.joints[f"{j}.{side}"].bone
            arm.pose.bones[bone].rotation_quaternion = posed.bones[bone].local_quat
        bpy.context.view_layer.update()
        ev = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return posed, ev

    def test_the_rig_uses_constraints_not_drivers_and_a_helper_bone(self):
        import bpy
        for h, run in self.runs.items():
            path, base, anat, art, tm = run
            self.scene.open_blend(path)
            arm = bpy.data.objects["AC_Armature"]
            self.assertFalse(arm.animation_data and arm.animation_data.drivers)  # sin drivers
            for s in "LR":
                carrier = arm.pose.bones[pt.carrier_name(f"patella.{s}")]
                self.assertEqual([c.type for c in carrier.constraints], ["COPY_ROTATION"])
                self.assertAlmostEqual(carrier.constraints[0].influence, 0.9)
                self.assertEqual([c.type for c in arm.pose.bones[f"patella.{s}"].constraints], ["TRANSFORM"])
                self.assertEqual(arm.data.bones[f"patella.{s}"].parent.name, carrier.name)
                self.assertEqual(arm.data.bones[carrier.name].parent.name, f"thigh.{s}")
                self.assertEqual(arm.data.bones[carrier.name]["ac_layer"], "rig_helper")
            break

    def test_the_evaluated_patella_matches_the_model_in_the_22_poses_at_three_heights(self):
        import bpy
        for h, run in self.runs.items():
            path, base, anat, art, tm = run
            self.scene.open_blend(path)
            for side in "LR":
                b = anat.bones[f"patella.{side}"]
                for pose_name, rot in lp.LEG_SWEEP:
                    posed, ev = self.pose_and_read(run, side, rot)
                    pb = ev.pose.bones[f"patella.{side}"]
                    # cabeza y cola del hueso de la rotula: posicion mundial = pose del femur sobre la transformacion de deslizamiento
                    for rest, got in ((b.head, tuple(pb.head)), (b.tail, tuple(pb.tail))):
                        want = lp.pose_point(b.name, rest, base, anat, posed)
                        self.assertLess(length(sub(got, want)), 2e-4 * h / 1.75, (h, side, pose_name))

    def test_patellar_ligament_and_quadriceps_follow_the_gliding_patella_in_blender(self):
        import bpy
        for h, run in self.runs.items():
            path, base, anat, art, tm = run
            self.scene.open_blend(path)
            for pose_name in ("rest", "knee_60", "knee_135", "hip_120_knee_135", "flexion_90_abduction_30"):
                rot = dict(lp.LEG_SWEEP)[pose_name]
                posed, ev = self.pose_and_read(run, "L", rot)
                snap = self.ascene.read_back_articulations()
                lg = art.ligaments["patellar.L"]
                got = [tuple(p) for p in snap["LIG_patellar.L"]["points"]]
                for g, w in zip(got, lp.posed_path(lg, base, anat, posed)):
                    self.assertLess(length(sub(g, w)), 2e-4 * h / 1.75, (h, pose_name, "rotuliano"))
                tsnap = self.tscene.read_back_tendons()
                for n in QUADRICEPS:
                    t = tm.tendons[f"{n}.L"]
                    ring_end = tsnap[f"TEN_insertion_{n}.L"]["points"][1]
                    want = lp.pose_point(t.sites[-1].bone, t.sites[-1].point, base, anat, posed)
                    self.assertLess(length(sub(tuple(ring_end), want)), 2e-4 * h / 1.75, (h, pose_name, n))  # el extremo del tendon esta en la rotula

    def test_negative_control_without_the_constraints_the_patella_stays_rigid(self):
        import bpy
        path, base, anat, art, tm = self.runs[1.75]
        self.scene.open_blend(path)
        arm = bpy.data.objects["AC_Armature"]
        for s in "L":
            for pbname in (pt.carrier_name(f"patella.{s}"), f"patella.{s}"):
                for c in arm.pose.bones[pbname].constraints:
                    c.mute = True
        posed, ev = self.pose_and_read((path, base, anat, art, tm), "L", {"knee": {"flexion": 135.0}})
        pb = ev.pose.bones["patella.L"]
        want = lp.pose_point("patella.L", anat.bones["patella.L"].head, base, anat, posed)
        self.assertGreater(length(sub(tuple(pb.head), want)), 0.03)  # sin restricciones la rotula queda >3 cm de donde debe


if __name__ == "__main__":
    unittest.main()
