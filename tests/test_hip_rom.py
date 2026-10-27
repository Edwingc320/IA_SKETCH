"""CM-7: auditoria y armonizacion de los rangos de movimiento (ROM) de la cadera.

Los seis rangos publicados de `coxofemoral` (flexion, extension, abduccion, aduccion, rotacion interna y externa) son ahora el RANGO ENTRE FUENTES
(StatPearls, medias normativas de la AAOS de 2020, hoja con los valores redondeados de la AAOS y Physiotutors) y cada uno dice a que limite del rig
corresponde (`rig`). La validacion exige que el limite del rig caiga dentro de su rango. Decision sobre la extension (15 grados del rig frente a los 10
de StatPearls): se MANTIENE 15, porque queda dentro del rango entre fuentes (10-30) y cerca de la media medida (17); por eso no cambia ni `joints.json`,
ni las restricciones Limit Rotation, ni el golden. Las pruebas fijan esa decision, comprueban con mutaciones que una discrepancia se detectaria y repiten
los barridos de poses (incluida una extension de 10 grados) con todos los ligamentos y tendones con envoltura."""
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

from anatomical_core import anatomy, articulations, ligament_paths as lp, pose as pose_mod, tendons, validation  # noqa: E402
from anatomical_core.config import ConfigError, PoseDef, load_config  # noqa: E402
from anatomical_core.geometry import length, mat_vec, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

TEST_OUT = ROOT / "output" / "_test"
# dof publicado -> (limite del rig, rango entre fuentes)
EXPECTED = {"flexion": (("flexion", "max"), (110.0, 128.0)), "extension": (("flexion", "min"), (10.0, 30.0)), "abduccion": (("abduction", "max"), (30.0, 50.0)),
            "aduccion": (("abduction", "min"), (14.0, 30.0)), "rotacion_interna": (("axial", "max"), (15.0, 45.0)), "rotacion_externa": (("axial", "min"), (35.0, 60.0))}
SP = {"flexion": 120.0, "extension": 10.0, "abduccion": 45.0, "aduccion": 25.0, "rotacion_interna": 15.0, "rotacion_externa": 35.0}  # StatPearls
RIG_LIMITS = {"flexion": (-15.0, 120.0), "abduction": (-30.0, 45.0), "axial": (-40.0, 45.0)}
HIP_LIGAMENTS = ("iliofemoral", "pubofemoral", "ischiofemoral")
DEFORM_TENDONS = ("psoas_major", "iliacus", "tensor_fasciae_latae", "iliotibial_tract", "piriformis", "obturator_internus", "gemellus_superior", "gemellus_inferior",
                  "obturator_externus", "quadratus_femoris", "pectineus", "adductor_brevis")


def build_all(height=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    art = articulations.build_articulations(base, anat, articulations.load_articulation_data())
    return base, anat, art, tendons.build_tendons(base, anat, art, tendons.load_tendon_data())


def with_dof(art, joint, name, **kw):
    j = art.joints[joint]
    return replace(art, joints={**art.joints, joint: replace(j, dofs=tuple(replace(d, **kw) if d.name == name else d for d in j.dofs))})


class TestHipRomAudit(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art, self.tm = build_all()

    def test_the_six_published_ranges_are_ranges_between_sources_mapped_to_a_rig_limit(self):
        for s in "LR":
            dofs = {d.name: d for d in self.art.joints[f"coxofemoral.{s}"].dofs}
            self.assertEqual(set(dofs), set(EXPECTED))
            for n, (rig, rng) in EXPECTED.items():
                d = dofs[n]
                self.assertEqual((d.rig, d.range_deg), (rig, rng), n)
                self.assertEqual(d.total_deg, (SP[n], SP[n]), n)  # el valor de StatPearls no se toca
                self.assertEqual(d.source, "statpearls_hip")
                self.assertEqual(set(d.other_sources), {"aaos_hip_2020", "hip_rom_aaos_chart", "hip_rom_physiotutors"}, n)
                self.assertIn("CM-7", d.note)
                for k in (d.source, *d.other_sources):
                    self.assertTrue(self.art.sources[k]["url"].startswith("https://"), k)
        # la hoja que redondea los valores de la AAOS es una fuente secundaria: baja, con «verificar»
        self.assertEqual(self.art.sources["hip_rom_aaos_chart"]["reliability"], "baja")
        self.assertIn("VERIFICAR", self.art.sources["hip_rom_aaos_chart"]["title"])

    def test_every_rig_limit_lies_inside_its_published_range(self):
        for s in "LR":
            hip = self.base.joints[f"hip.{s}"]
            self.assertEqual({d.name: (d.min_deg, d.max_deg) for d in hip.dofs}, RIG_LIMITS)  # el rig no cambia: joints.json y el golden siguen igual
            for d in self.art.joints[f"coxofemoral.{s}"].dofs:
                bd = next(x for x in hip.dofs if x.name == d.rig[0])
                limit = abs(bd.min_deg if d.rig[1] == "min" else bd.max_deg)
                self.assertTrue(d.range_deg[0] <= limit <= d.range_deg[1], (d.name, limit, d.range_deg))
        self.assertEqual([i for i in validation.validate_articulations(self.base, self.anat, self.art) if i.severity == "error"], [])

    def test_the_extension_decision_keeps_15_degrees_and_says_why(self):
        d = {x.name: x for x in self.art.joints["coxofemoral.L"].dofs}["extension"]
        self.assertEqual(abs(self.base.joints["hip.L"].dofs[0].min_deg), 15.0)
        self.assertTrue(d.range_deg[0] < 15.0 < d.range_deg[1])  # 15 esta dentro del rango entre fuentes (StatPearls 10, AAOS 2020 17, hoja 30)
        self.assertGreater(15.0, 10.0)  # y por encima de StatPearls: el rig es un TECHO, no el valor tipico
        self.assertIn("se mantiene", d.note)
        self.assertIn("17", d.note)

    def test_internal_rotation_is_positive_axial_and_external_negative(self):
        """Comprobado con la FK: axial positivo lleva la punta del pie hacia medial (rotacion interna); por eso rotacion_interna <-> axial max."""
        foot = lambda deg: pose_mod.apply_pose(self.base, PoseDef("t", {"hip.L": {"axial": deg}})).bones["foot.L"].tail  # noqa: E731
        self.assertLess(foot(30.0)[0], foot(0.0)[0])  # medial = hacia x menor en el lado izquierdo
        self.assertGreater(foot(-30.0)[0], foot(0.0)[0])
        dofs = {d.name: d for d in self.art.joints["coxofemoral.L"].dofs}
        self.assertEqual(dofs["rotacion_interna"].rig, ("axial", "max"))
        self.assertEqual(dofs["rotacion_externa"].rig, ("axial", "min"))

    # ---- mutaciones: una discrepancia entre el rig y la literatura se detecta
    def test_mutation_a_published_range_that_excludes_the_rig_limit_is_caught(self):
        for dof, new in (("extension", (10.0, 12.0)), ("extension", (20.0, 30.0)), ("flexion", (100.0, 110.0)), ("aduccion", (10.0, 25.0)), ("rotacion_interna", (15.0, 40.0))):
            bad = with_dof(self.art, "coxofemoral.L", dof, range_deg=new)
            self.assertIn("ART_ROM_RIG_OUTSIDE", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)], (dof, new))
        ok = with_dof(self.art, "coxofemoral.L", "extension", range_deg=(10.0, 15.0))  # el limite exacto es valido
        self.assertEqual([i.code for i in validation.validate_articulations(self.base, self.anat, ok) if i.severity == "error"], [])

    def test_mutation_unknown_rig_dof_or_missing_range_or_source_is_caught(self):
        bad = with_dof(self.art, "coxofemoral.L", "extension", rig=("no_such_dof", "min"))
        self.assertIn("ART_ROM_RIG_UNKNOWN", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)])
        bad = with_dof(self.art, "coxofemoral.L", "extension", range_deg=None, rig=("flexion", "min"))
        self.assertIn("ART_ROM_RIG_UNKNOWN", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)])
        bad = with_dof(self.art, "coxofemoral.L", "extension", other_sources=("no_such_source",))
        self.assertIn("ART_SOURCE_UNKNOWN", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)])

    def test_bad_rig_spec_in_the_data_is_rejected(self):
        data = articulations.load_articulation_data()
        import copy
        for rig in ({"dof": "flexion", "bound": "medio"}, {"bound": "min"}, "flexion"):
            bad = copy.deepcopy(data)
            for d in bad:
                for j in d.get("joints", []):
                    for x in j.get("dofs", []):
                        if j["name"] == "coxofemoral.L" and x["name"] == "extension":
                            x["rig"] = rig
            with self.assertRaises(ConfigError):
                articulations.build_articulations(self.base, self.anat, bad)

    # ---- la pose valida el techo del rig
    def test_the_pose_validator_accepts_the_rig_limits_and_rejects_beyond(self):
        for rot, ok in (({"flexion": -15.0}, True), ({"flexion": -16.0}, False), ({"flexion": 120.0}, True), ({"flexion": 121.0}, False),
                        ({"abduction": 45.0}, True), ({"abduction": -31.0}, False), ({"axial": 45.0}, True), ({"axial": -41.0}, False)):
            posed = pose_mod.apply_pose(self.base, PoseDef("t", {"hip.L": rot}))
            codes = [i.code for i in validation.validate_pose(self.base, posed)]
            self.assertEqual("POSE_OUT_OF_LIMITS" in codes, not ok, rot)

    # ---- barridos
    def test_every_wrapped_ligament_and_tendon_is_covered_by_the_sweeps(self):
        deform_lig = sorted(n for n, lg in self.art.ligaments.items() if lg.deform)
        deform_ten = sorted(n for n, t in self.tm.tendons.items() if t.deform)
        knee = ("anterior_cruciate", "posterior_cruciate", "tibial_collateral", "fibular_collateral", "patellar")  # CM-8
        self.assertEqual(deform_lig, sorted(f"{n}.{s}" for n in HIP_LIGAMENTS + knee for s in "LR"))
        self.assertEqual(deform_ten, sorted(f"{n}.{s}" for n in DEFORM_TENDONS for s in "LR"))  # si se anade uno nuevo con envoltura, esta lista y su barrido se actualizan
        self.assertEqual(len(lp.LEG_SWEEP), 22)

    def test_sweeps_pass_at_three_heights_with_no_penetration_and_every_node_within_12_mm(self):
        for h in (1.5, 1.75, 2.05):
            base, anat, art, tm = build_all(h)
            tol = 0.012 * h / 1.75
            self.assertEqual(validation.validate_ligament_poses(base, anat, art), [], h)
            self.assertEqual(tendons.validate_tendon_poses(base, anat, art, tm), [], h)
            for n in (*[f"{x}.{s}" for x in HIP_LIGAMENTS for s in "LR"],):
                for bone, p in lp.nodes(art.ligaments[n]):  # ningun nodo descolgado: todos a < 12 mm de su hueso (rigidos, asi que igual en cualquier pose)
                    self.assertLess(articulations.bone_distance(p, bone, base, anat, art.surfaces), tol, (h, n))
            for n in (f"{x}.{s}" for x in DEFORM_TENDONS for s in "LR"):
                for site in tm.tendons[n].sites:
                    self.assertLess(articulations.bone_distance(site.point, site.bone, base, anat, art.surfaces), tol, (h, n))

    def test_a_10_degree_extension_ceiling_would_also_be_covered(self):
        """Si el techo bajara a 10 grados (valor de StatPearls), toda pose con menos extension esta dentro del barrido ya probado: se prueban 5, 10 y 15."""
        for h in (1.5, 1.75, 2.05):
            base, anat, art, tm = build_all(h)
            for side in "LR":
                for ext in (-5.0, -10.0, -15.0):
                    posed = pose_mod.apply_pose(base, PoseDef("t", {f"hip.{side}": {"flexion": ext}}))
                    sf = {s.name: s for s in lp.posed_surfaces(art, base, anat, posed)}
                    for n in HIP_LIGAMENTS:
                        lg = art.ligaments[f"{n}.{side}"]
                        self.assertGreater(lp.path_clearance(lp.posed_path(lg, base, anat, posed), [sf[a] for a in lg.avoid]), 0.0, (h, side, ext, n))
                    for n in DEFORM_TENDONS:
                        t = tm.tendons[f"{n}.{side}"]
                        self.assertGreater(lp.path_clearance(lp.posed_nodes(lp.tendon_nodes(t), base, anat, posed), [sf[a] for a in t.avoid]), 0.0, (h, side, ext, n))


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestHipLimitRotationInBlender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from anatomical_core import anatomy_pipeline, scene
        cls.scene = scene
        TEST_OUT.mkdir(parents=True, exist_ok=True)
        cls.path = TEST_OUT / "hip_rom.blend"
        cls.res = anatomy_pipeline.generate(cls.path, preview=False, log=lambda *_: None)
        cls.base = cls.res.base

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

    def evaluated(self, arm, bone):
        import bpy
        return arm.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones[bone].matrix.to_3x3()

    def expected(self, side, rot):
        posed = pose_mod.apply_pose(self.base, PoseDef("t", {f"hip.{side}": rot})).bones[f"thigh.{side}"]
        return [mat_vec(posed.rotation, self.base.bones[f"thigh.{side}"].frame[i]) for i in range(3)]

    def test_the_hip_constraints_carry_the_audited_limits_on_both_sides(self):
        import math

        import bpy
        self.scene.open_blend(self.path)
        arm = bpy.data.objects["AC_Armature"]
        for s in "LR":
            joint = self.base.joints[f"hip.{s}"]
            cons = [c for c in arm.pose.bones[f"thigh.{s}"].constraints if c.type == "LIMIT_ROTATION"]
            self.assertEqual(len(cons), 1)
            limits = {}
            for axis in "xyz":
                if getattr(cons[0], f"use_limit_{axis}"):
                    limits[axis] = (round(math.degrees(getattr(cons[0], f"min_{axis}")), 6), round(math.degrees(getattr(cons[0], f"max_{axis}")), 6))
            norm = lambda lo, hi: tuple(sorted((round(abs(lo), 3), round(abs(hi), 3))))  # noqa: E731  (el eje y el signo dependen del dof: se comparan magnitudes)
            want = sorted(norm(d.min_deg, d.max_deg) for d in joint.dofs)
            got = sorted(norm(lo, hi) for lo, hi in limits.values())
            self.assertEqual(got, want, s)  # las magnitudes de los limites del rig coinciden con joints.json (15/120, 30/45, 40/45)
            self.assertEqual(len(limits), 3)

    def test_the_extension_ceiling_is_15_degrees_in_blender_too(self):
        import bpy
        for want, ask in (({"flexion": -15.0}, {"flexion": -15.0}), ({"flexion": -15.0}, {"flexion": -25.0})):  # pedir 25 queda recortado a 15
            self.open_reset()
            arm = bpy.data.objects["AC_Armature"]
            posed = pose_mod.apply_pose(self.base, PoseDef("t", {"hip.L": ask})).bones["thigh.L"]
            arm.pose.bones["thigh.L"].rotation_quaternion = posed.local_quat
            bpy.context.view_layer.update()
            m3 = self.evaluated(arm, "thigh.L")
            for i, col in enumerate(self.expected("L", want)):
                self.assertLess(length(sub(tuple(m3.col[i]), col)), 1e-4, (ask, i))


if __name__ == "__main__":
    unittest.main()
