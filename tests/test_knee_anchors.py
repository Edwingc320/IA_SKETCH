"""CM-8: deuda de anclaje del muslo y la rodilla.

Se anaden obstaculos de la tibia proximal, la rotula y la cabeza del peroné (CONVENCION, ver sus notas) y los ligamentos de la rodilla pasan a seguir a sus
huesos en Blender (`deform`). El trinquete baja de 58 a 53 (tuberosidad tibial, ligamento rotuliano, femororrotuliana y tibioperonea proximal). Las pruebas
auditan TODOS los anclajes de femur, rotula, tibia y peroné de ligamentos, tendones, hitos y articulaciones, el barrido de cadera y rodilla (hasta 135 grados) a
tres alturas, y comprueban con MUTACIONES que una desviacion se detectaria. El ligamento rotuliano tiene una LIMITACION CONOCIDA (la rotula no se desliza): se
mide y se fija aqui."""
import copy
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    import bpy  # noqa: F401
    HAVE_BPY = True
except ImportError:
    HAVE_BPY = False

from anatomical_core import anatomy, articulations, ligament_paths as lp, pose as pose_mod, tendons, validation  # noqa: E402
from anatomical_core.config import ConfigError, PoseDef, load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

TEST_OUT = ROOT / "output" / "_test"
KNEE_BONES = ("femur", "patella", "tibia", "fibula")
KNEE_LIGAMENTS = ("anterior_cruciate", "posterior_cruciate", "tibial_collateral", "fibular_collateral", "patellar")
NEW = {"tibial_proximal": "tibia", "patellar_body": "patella", "fibular_head_body": "fibula"}


def build_all(height=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    art = articulations.build_articulations(base, anat, articulations.load_articulation_data())
    return base, anat, art, tendons.build_tendons(base, anat, art, tendons.load_tendon_data())


def knee_anchors(art, tm):
    """(nombre, tipo, hueso, punto) de todo anclaje de femur, rotula, tibia o peroné."""
    out = []
    for n, lg in art.ligaments.items():
        for k, (bone, p) in enumerate(lp.nodes(lg)):
            if bone.startswith(KNEE_BONES):
                out.append((n, f"ligamento[{k}]", bone, p))
    for n, t in tm.tendons.items():
        for s in t.sites:
            if s.bone.startswith(KNEE_BONES):
                out.append((n, f"tendon {s.kind}", s.bone, s.point))
    for n, a in art.attachments.items():
        if a.bone.startswith(KNEE_BONES):
            out.append((n, "hito", a.bone, a.point))
    for n, j in art.joints.items():
        for b in j.bones:
            if b.startswith(KNEE_BONES):
                out.append((n, "articulacion", b, j.center))
    return out


class TestKneeAnchors(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art, self.tm = build_all()
        self.tol = 0.012 * self.base.height_m / 1.75

    def test_new_obstacles_are_declared_conventions_with_sources_or_a_reason(self):
        for n, bone in NEW.items():
            for s in "LR":
                sf = self.art.surfaces[f"{n}.{s}"]
                self.assertEqual(sf.bone, f"{bone}.{s}")
                self.assertTrue(sf.sources or sf.no_numeric_source, n)
                for k in sf.sources:
                    self.assertTrue(self.art.sources[k]["url"].startswith("https://"), k)
        t, p, f = (self.art.surfaces[f"{n}.L"] for n in NEW)
        self.assertEqual((t.kind, p.kind, f.kind), ("capsule", "capsule", "sphere"))
        self.assertAlmostEqual(t.radius_m, 0.023, places=9)  # profundidad anteroposterior de 46 mm
        self.assertAlmostEqual(p.radius_m, 0.011, places=9)  # grosor de la rotula de 22 mm (publicado: 19-22)
        self.assertAlmostEqual(f.radius_m, 0.010, places=9)
        self.assertTrue(f.no_numeric_source and "convencion" in f.notes.lower())
        self.assertEqual((t.sources, p.sources), (("tibia_proximal_morphometry",), ("patella_morphometry",)))
        self.assertLess(length(sub(mirror_point(t.a), self.art.surfaces["tibial_proximal.R"].a)), 1e-9)

    def test_the_five_fixed_anchors_are_now_on_the_bone_surfaces(self):
        a, j, lg = self.art.attachments, self.art.joints, self.art.ligaments
        bd = lambda p, b: articulations.bone_distance(p, b, self.base, self.anat, self.art.surfaces)  # noqa: E731
        self.assertLess(bd(a["tibial_tuberosity.L"].point, "tibia.L"), self.tol)
        self.assertLess(bd(lg["patellar.L"].b, "tibia.L"), self.tol)
        self.assertLess(bd(j["patellofemoral.L"].center, "patella.L"), self.tol)
        self.assertLess(bd(j["proximal_tibiofibular.L"].center, "tibia.L"), self.tol)
        self.assertLess(bd(j["proximal_tibiofibular.L"].center, "fibula.L"), self.tol)
        # sin las nuevas superficies seguian a 16-25 mm: el obstaculo es lo que las sana
        wire = lambda p, b: articulations.bone_distance(p, b, self.base, self.anat)  # noqa: E731
        for p, b in ((a["tibial_tuberosity.L"].point, "tibia.L"), (j["patellofemoral.L"].center, "patella.L"), (j["proximal_tibiofibular.L"].center, "fibula.L")):
            self.assertGreater(wire(p, b), self.tol, (b,))

    def test_every_thigh_and_knee_anchor_is_within_12_mm_at_three_heights(self):
        for h in (1.5, 1.75, 2.05):
            base, anat, art, tm = build_all(h)
            tol = 0.012 * h / 1.75
            anchors = knee_anchors(art, tm)
            self.assertGreater(len(anchors), 150)
            worst = 0.0
            import test_anchor_debt as ad
            for n, kind, bone, p in anchors:
                if n.startswith(("body_center", "head_center")):
                    continue
                if n.startswith(ad.ANKLE_NAMES):  # deuda del tobillo (pierna y pie): sigue en el trinquete, no es del muslo ni de la rodilla
                    self.assertTrue(any(k[1].startswith(n[:-2]) for k in ad.KNOWN_DEBT), n)
                    continue
                d = articulations.bone_distance(p, bone, base, anat, art.surfaces)
                worst = max(worst, d / (h / 1.75))
                self.assertLessEqual(d, tol + 1e-9, (h, n, kind, bone))  # el trinquete cuenta como deuda lo que supera los 12 mm; en el limite exacto no

    def test_the_knee_ligaments_follow_their_bones_and_say_what_they_avoid(self):
        for s in "LR":
            for n in KNEE_LIGAMENTS:
                lg = self.art.ligaments[f"{n}.{s}"]
                self.assertTrue(lg.deform, n)
                self.assertEqual(lg.tolerance_m, 0.012 * self.base.height_m / 1.75)  # el limite de 12 mm, ya no 30-40 mm
                self.assertTrue(lg.avoid or lg.avoid_reason, n)
                self.assertIn("CM-8", lg.notes)
            self.assertEqual(self.art.ligaments[f"tibial_collateral.{s}"].avoid, (f"femoral_lateral_condyle.{s}", f"femoral_shaft.{s}"))
            self.assertEqual(self.art.ligaments[f"fibular_collateral.{s}"].avoid, (f"femoral_shaft.{s}",))
            for n in ("anterior_cruciate", "posterior_cruciate"):
                self.assertIn("intraarticular", self.art.ligaments[f"{n}.{s}"].avoid_reason)
            self.assertIn("LIMITACION CONOCIDA", self.art.ligaments[f"patellar.{s}"].avoid_reason)
        self.assertEqual([i for i in validation.validate_articulations(self.base, self.anat, self.art) if i.severity == "error"], [])

    def test_the_knee_sweep_up_to_135_degrees_has_no_penetration_at_three_heights(self):
        names = [n for n, _ in lp.LEG_SWEEP]
        self.assertIn("knee_135", names)
        self.assertIn("hip_120_knee_135", names)
        for h in (1.5, 1.75, 2.05):
            base, anat, art, tm = build_all(h)
            self.assertEqual(validation.validate_knee_ligament_poses(base, anat, art), [], h)
            for side in "LR":
                for pose_name, posed in lp.leg_sweep_poses(base, side):
                    sf = {s.name: s for s in lp.posed_surfaces(art, base, anat, posed)}
                    for n in ("tibial_collateral", "fibular_collateral"):
                        lg = art.ligaments[f"{n}.{side}"]
                        self.assertGreater(lp.path_clearance(lp.posed_path(lg, base, anat, posed), [sf[a] for a in lg.avoid]), 0.001 * h / 1.75, (h, side, pose_name, n))

    def test_known_limitation_the_patellar_ligament_without_patellar_gliding(self):
        """Medido: sin deslizamiento de la rotula el ligamento rotuliano pasa de 27 mm a 81 mm a 135 grados y atraviesa el condilo/diafisis a partir de ~100 grados.
        Si algun dia la rotula se desliza, esta prueba debe cambiar (y el ligamento pasar a evitar el femur)."""
        lg = self.art.ligaments["patellar.L"]

        def at(deg):
            posed = pose_mod.apply_pose(self.base, PoseDef("t", {"knee.L": {"flexion": float(deg)}}))
            sf = {s.name: s for s in lp.posed_surfaces(self.art, self.base, self.anat, posed)}
            path = lp.posed_path(lg, self.base, self.anat, posed)
            return lp.path_length(path), lp.path_clearance(path, [sf["femoral_lateral_condyle.L"], sf["femoral_shaft.L"]], 30)
        l0, c0 = at(0)
        l135, c135 = at(135)
        self.assertAlmostEqual(l0, 0.0267, places=3)
        self.assertGreater(l135 / l0, 2.5)  # un ligamento real casi no cambia de longitud: es el sintoma de que falta el deslizamiento
        self.assertGreater(c0, 0.010)
        self.assertLess(c135, -0.005)
        first = next(d for d in range(0, 136, 5) if at(d)[1] < 0)
        self.assertGreaterEqual(first, 100)  # hasta ~100 grados no atraviesa

    # ---- mutaciones
    def test_mutation_removing_a_new_obstacle_brings_the_debt_back(self):
        a, j = self.art.attachments["tibial_tuberosity.L"], self.art.joints["patellofemoral.L"]
        for name, p, bone in (("tibial_proximal.L", a.point, "tibia.L"), ("patellar_body.L", j.center, "patella.L"), ("fibular_head_body.L", self.art.joints["proximal_tibiofibular.L"].center, "fibula.L")):
            without = {k: v for k, v in self.art.surfaces.items() if k != name}
            self.assertGreater(articulations.bone_distance(p, bone, self.base, self.anat, without), self.tol, name)

    def test_mutation_the_debt_ratchet_detects_a_reintroduced_anchor(self):
        import test_anchor_debt as ad
        self.assertEqual(ad.violations() - ad.KNOWN_DEBT, set())
        moved = replace(self.art.attachments["tibial_tuberosity.L"], point=tuple(c + 0.03 for c in self.art.attachments["tibial_tuberosity.L"].point))
        d = articulations.bone_distance(moved.point, "tibia.L", self.base, self.anat, self.art.surfaces)
        self.assertGreater(d, self.tol)  # un anclaje desplazado 3 cm sale del margen: el trinquete lo cazaria como nuevo
        self.assertLessEqual(len(ad.KNOWN_DEBT), ad.DEBT_CEILING)

    def test_mutation_a_collateral_end_inside_the_femur_is_caught_in_the_sweep(self):
        lg = self.art.ligaments["tibial_collateral.L"]
        shaft = self.art.surfaces["femoral_shaft.L"]
        bad_lg = replace(lg, a=tuple((p + q) / 2 for p, q in zip(shaft.a, shaft.b)))
        bad = replace(self.art, ligaments={**self.art.ligaments, lg.name: bad_lg})
        self.assertIn("LIG_PENETRATES", [i.code for i in validation.validate_knee_ligament_poses(self.base, self.anat, bad, sides=("L",))])
        self.assertIn("ART_LIGAMENT_PENETRATES", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)])

    def test_mutation_a_displaced_knee_anchor_is_out_of_margin(self):
        for n in KNEE_LIGAMENTS:
            lg = self.art.ligaments[f"{n}.L"]
            bad_lg = replace(lg, b=tuple(c + 0.05 for c in lg.b))
            bad = replace(self.art, ligaments={**self.art.ligaments, lg.name: bad_lg})
            self.assertIn("ART_LIGAMENT_OFF_BONE", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)], n)

    def test_mutation_deform_without_avoid_or_reason_is_rejected(self):
        lg = self.art.ligaments["fibular_collateral.L"]
        bad = replace(self.art, ligaments={**self.art.ligaments, lg.name: replace(lg, avoid=())})
        self.assertIn("ART_AVOID_EMPTY", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)])
        bad = replace(self.art, ligaments={**self.art.ligaments, lg.name: replace(lg, avoid=("no_such_surface",))})
        self.assertIn("ART_AVOID_UNKNOWN", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)])

    def test_bad_new_surface_data_is_rejected(self):
        data = articulations.load_articulation_data()
        bad = copy.deepcopy(data)
        for d in bad:
            for sf in d.get("bone_surfaces", []):
                if sf["name"] == "patellar_body.L":
                    sf["radius_m"] = 0.5
        with self.assertRaises(ConfigError):
            articulations.build_articulations(self.base, self.anat, bad)


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestKneeLigamentsInBlender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from anatomical_core import anatomy_pipeline, articulations_scene, scene
        cls.scene, cls.ascene = scene, articulations_scene
        TEST_OUT.mkdir(parents=True, exist_ok=True)
        cls.path = TEST_OUT / "knee_anchors.blend"
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

    def pose_leg(self, arm, side, rotations):
        import bpy
        posed = pose_mod.apply_pose(self.base, PoseDef("t", {f"{j}.{side}": dict(r) for j, r in rotations.items()}))
        for j in rotations:
            bone = self.base.joints[f"{j}.{side}"].bone
            arm.pose.bones[bone].rotation_quaternion = posed.bones[bone].local_quat
        bpy.context.view_layer.update()
        return posed

    def test_the_knee_ligaments_are_armature_deformed(self):
        import bpy
        self.scene.open_blend(self.path)
        for s in "LR":
            for n in KNEE_LIGAMENTS:
                o = bpy.data.objects[f"LIG_{n}.{s}"]
                self.assertEqual((o.parent.name, o.parent_type, [m.type for m in o.modifiers]), ("AC_Armature", "OBJECT", ["ARMATURE"]), n)
                self.assertEqual({g.name for g in o.vertex_groups}, {b for b, _ in lp.nodes(self.art.ligaments[f"{n}.{s}"])}, n)
        self.assertEqual(validation.validate_articulations_snapshot(self.art, self.ascene.read_back_articulations()), [])

    def test_both_ends_follow_their_bones_through_the_knee_sweep_and_stay_within_12_mm(self):
        for side in "LR":
            for pose_name, rot in lp.LEG_SWEEP:
                arm = self.open_reset()
                posed = self.pose_leg(arm, side, rot)
                snap = self.ascene.read_back_articulations()
                for n in KNEE_LIGAMENTS:
                    lg = self.art.ligaments[f"{n}.{side}"]
                    got = [tuple(p) for p in snap[f"LIG_{n}.{side}"]["points"]]
                    want = lp.posed_path(lg, self.base, self.anat, posed)
                    for g, w in zip(got, want):
                        self.assertLess(length(sub(g, w)), 1e-4, (side, pose_name, n))  # el extremo tibial acompaña a la tibia: nada descolgado
                    # y cada extremo conserva su distancia a las superficies de SU hueso (cuerpo rigido): lo que estaba a < 12 mm en reposo sigue estandolo
                    posed_sf = {s.name: s for s in lp.posed_surfaces(self.art, self.base, self.anat, posed)}
                    for (bone, p0), g in zip(lp.nodes(lg), got):
                        for name, sf in self.art.surfaces.items():
                            if sf.bone == bone:
                                self.assertAlmostEqual(sf.signed_distance(p0), posed_sf[name].signed_distance(g), places=4, msg=(side, pose_name, n, name))

    def test_negative_control_the_old_rigid_parenting_leaves_the_tibial_end_behind(self):
        import bpy
        arm = self.open_reset()
        for n in KNEE_LIGAMENTS:
            bpy.data.objects[f"LIG_{n}.L"].modifiers["AC_Armature"].show_viewport = False
        posed = self.pose_leg(arm, "L", {"knee": {"flexion": 90.0}})
        snap = self.ascene.read_back_articulations()
        for n in KNEE_LIGAMENTS:
            lg = self.art.ligaments[f"{n}.L"]
            got = [tuple(p) for p in snap[f"LIG_{n}.L"]["points"]]
            want = lp.posed_path(lg, self.base, self.anat, posed)
            self.assertGreater(max(length(sub(g, w)) for g, w in zip(got, want)), 0.005 if "cruciate" in n else 0.02, n)  # el extremo se queda atras (los cruzados, cortos y junto al eje, >5 mm)


if __name__ == "__main__":
    unittest.main()
