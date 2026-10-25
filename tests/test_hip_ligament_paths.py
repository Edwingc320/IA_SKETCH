"""CM-4: trayectoria de los ligamentos de la cadera (iliofemoral, pubofemoral, isquiofemoral) con guias de envoltura.

Cada nodo del ligamento viaja con su hueso; la cabeza y el cuello del femur son obstaculos analiticos (esfera y capsula, CONVENCION con radios
tomados del centro de los rangos publicados). Las pruebas barren la cadera (flexion 0-120, extension 15, abduccion 45, aduccion, rotaciones y
combinaciones), exigen que ninguna poligonal atraviese el femur, y comprueban con MUTACIONES que la prueba lo detectaria: el extremo en el eje del
cuello (geometria antigua) o la guia de envoltura quitada."""
import copy
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations, ligament_paths as lp, validation  # noqa: E402
from anatomical_core.config import ConfigError, load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

HIP_LIGAMENTS = ("iliofemoral", "pubofemoral", "ischiofemoral")


def build_all(height=None, data=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    return base, anat, articulations.build_articulations(base, anat, data if data is not None else articulations.load_articulation_data())


class TestHipLigamentPaths(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()
        self.tol = 0.012 * self.base.height_m / 1.75

    def test_surfaces_are_the_head_sphere_and_the_neck_capsule_on_both_sides(self):
        self.assertEqual(sorted(self.art.surfaces), ["femoral_head.L", "femoral_head.R", "femoral_neck.L", "femoral_neck.R"])
        for s in "LR":
            head, neck = self.art.surfaces[f"femoral_head.{s}"], self.art.surfaces[f"femoral_neck.{s}"]
            center = self.art.joints[f"coxofemoral.{s}"].center
            self.assertEqual((head.kind, neck.kind, head.bone, neck.bone), ("sphere", "capsule", f"femur.{s}", f"femur.{s}"))
            self.assertLess(length(sub(head.a, center)), 1e-9)
            self.assertLess(length(sub(neck.a, center)), 1e-9)
            self.assertEqual(head.a, head.b)
            self.assertAlmostEqual(head.radius_m, 0.022, places=9)  # diametro 44 mm: centro del rango publicado 38-48
            self.assertAlmostEqual(neck.radius_m, 0.015, places=9)  # diametro 30 mm: centro del rango publicado 28-34
            self.assertTrue(head.sources and neck.sources)
            for src in head.sources:
                self.assertIn(src, self.art.sources)
                self.assertTrue(self.art.sources[src]["url"].startswith("https://"))
        l, r = self.art.surfaces["femoral_neck.L"], self.art.surfaces["femoral_neck.R"]
        self.assertLess(length(sub(mirror_point(l.b), r.b)), 1e-9)
        neck_len = length(sub(l.b, l.a))
        self.assertTrue(0.04 < neck_len < 0.06, neck_len)  # el cuello mide unos 5 cm hasta el trocanter

    def test_surfaces_scale_with_the_height(self):
        for h in (1.5, 2.05):
            _, _, art = build_all(h)
            k = h / 1.75
            self.assertAlmostEqual(art.surfaces["femoral_head.L"].radius_m, 0.022 * k, places=9)
            self.assertAlmostEqual(length(sub(art.surfaces["femoral_neck.L"].b, art.surfaces["femoral_neck.L"].a)),
                                   length(sub(self.art.surfaces["femoral_neck.L"].b, self.art.surfaces["femoral_neck.L"].a)) * k, places=9)

    def test_the_three_ligaments_follow_their_bones_and_declare_the_mechanics_as_a_convention(self):
        for s in "LR":
            for n in HIP_LIGAMENTS:
                lg = self.art.ligaments[f"{n}.{s}"]
                self.assertTrue(lg.deform, n)
                self.assertEqual(lg.to_bone, f"femur.{s}")
                self.assertEqual(lg.mechanics["status"], "convencion_parametrica_declarada")
                self.assertIsNone(lg.mechanics["stiffness_N_per_mm"])
                self.assertIsNone(lg.mechanics["slack_length_m"])
                for src in ("femur_morphometry", "hip_ligament_forces_2021"):
                    self.assertIn(src, lg.sources)
            self.assertEqual(len(self.art.ligaments[f"pubofemoral.{s}"].via), 1)  # pasa bajo la cabeza: necesita una guia
            self.assertEqual(self.art.ligaments[f"pubofemoral.{s}"].via[0].bone, f"femur.{s}")
            self.assertEqual(self.art.ligaments[f"iliofemoral.{s}"].via, ())  # la recta ya queda fuera en todo el barrido
            self.assertEqual(self.art.ligaments[f"ischiofemoral.{s}"].via, ())

    def test_every_node_is_within_12_mm_of_its_host_bone_and_the_insertions_sit_on_the_neck_surface(self):
        for n, lg in self.art.ligaments.items():
            if not lg.deform:
                continue
            for bone, p in lp.nodes(lg):
                self.assertLess(articulations.bone_distance(p, bone, self.base, self.anat, self.art.surfaces), self.tol, n)
            side = n[-1]
            surfaces = [x for x in self.art.surfaces.values() if x.bone == f"femur.{side}"]
            sd = min(x.signed_distance(lg.b) for x in surfaces)
            self.assertTrue(0.0 < sd < 0.0015, (n, sd))  # 1 mm por fuera de la superficie, no dentro del hueso
        for n in ("iliofemoral.L", "pubofemoral.L"):  # la geometria antigua dejaba el extremo en el eje del cuello, dentro del hueso: ya no
            self.assertGreater(min(x.signed_distance(self.art.ligaments[n].b) for x in self.art.surfaces.values() if x.bone == "femur.L"), 0.0)

    def test_the_sweep_covers_the_requested_range_and_stays_inside_the_rig_limits(self):
        names = dict(lp.HIP_SWEEP)
        self.assertEqual(names["flexion_120"], {"flexion": 120.0})
        self.assertEqual(names["extension_15"], {"flexion": -15.0})
        self.assertEqual(names["abduction_45"], {"abduction": 45.0})
        self.assertTrue({"flexion_30", "flexion_60", "flexion_90"} <= set(names))
        limits = {d.name: (d.min_deg, d.max_deg) for d in self.base.joints["hip.L"].dofs}
        for n, rot in lp.HIP_SWEEP:
            for dof, deg in rot.items():
                self.assertTrue(limits[dof][0] <= deg <= limits[dof][1], (n, dof))  # el rig no recorta ninguna pose del barrido

    def test_no_hip_ligament_penetrates_the_femur_in_any_pose_at_several_heights(self):
        for h in (1.5, 1.75, 2.05):
            base, anat, art = build_all(h)
            for s in "LR":
                for n in HIP_LIGAMENTS:
                    sweep = lp.sweep_clearance(art, base, anat, f"{n}.{s}", s)
                    self.assertEqual(len(sweep), len(lp.HIP_SWEEP))
                    worst = min(sweep, key=sweep.get)
                    self.assertGreaterEqual(sweep[worst], 0.0, (h, n, s, worst))
                    self.assertGreater(sweep[worst], 0.0004 * h / 1.75, (h, n, s, worst))  # con margen, no tangente
        self.assertEqual(validation.validate_ligament_poses(self.base, self.anat, self.art), [])

    def test_posed_nodes_stay_attached_to_their_bones(self):
        """Un nodo no se queda atras: su distancia con signo al obstaculo de SU hueso no cambia con la pose (cuerpo rigido), y el origen no se mueve."""
        for name, posed in lp.hip_sweep_poses(self.base, "L"):
            surfaces = {x.name: x for x in lp.posed_surfaces(self.art, self.base, self.anat, posed)}
            for n in HIP_LIGAMENTS:
                lg = self.art.ligaments[f"{n}.L"]
                path = lp.posed_path(lg, self.base, self.anat, posed)
                self.assertLess(length(sub(path[0], lg.a)), 1e-9, (n, name))  # el origen esta en la pelvis, que no se mueve
                for (bone, p0), p1 in list(zip(lp.nodes(lg), path))[1:]:
                    rest = min(x.signed_distance(p0) for x in self.art.surfaces.values() if x.bone == bone)
                    now = min(x.signed_distance(p1) for x in surfaces.values())
                    self.assertAlmostEqual(rest, now, places=9, msg=(n, name))

    def test_the_old_straight_geometry_with_the_end_on_the_neck_axis_would_be_caught(self):
        """Mutacion: el extremo del pubofemoral y del isquiofemoral en el eje del cuello (geometria anterior a CM-4) atraviesa el femur."""
        for n in ("pubofemoral.L", "ischiofemoral.L", "iliofemoral.L"):
            lg = self.art.ligaments[n]
            neck = self.art.surfaces["femoral_neck.L"]
            on_axis = tuple(neck.a[i] + 0.6 * (neck.b[i] - neck.a[i]) for i in range(3))
            bad = replace(self.art, ligaments={**self.art.ligaments, n: replace(lg, b=on_axis, via=())})
            sweep = lp.sweep_clearance(bad, self.base, self.anat, n)
            self.assertLess(min(sweep.values()), -0.005, n)  # varios milimetros dentro del hueso
            codes = [i.code for i in validation.validate_ligament_poses(self.base, self.anat, bad, sides=("L",))]
            self.assertIn("LIG_PENETRATES", codes, n)

    def test_removing_the_wrapping_guide_of_the_pubofemoral_is_caught(self):
        lg = self.art.ligaments["pubofemoral.L"]
        bad = replace(self.art, ligaments={**self.art.ligaments, "pubofemoral.L": replace(lg, via=())})
        sweep = lp.sweep_clearance(bad, self.base, self.anat, "pubofemoral.L")
        self.assertLess(min(sweep.values()), 0.0)  # sin la guia, la recta atraviesa la cabeza
        self.assertIn("LIG_PENETRATES", [i.code for i in validation.validate_ligament_poses(self.base, self.anat, bad, sides=("L",))])
        self.assertGreaterEqual(min(lp.sweep_clearance(self.art, self.base, self.anat, "pubofemoral.L").values()), 0.0)

    def test_moving_the_guide_into_the_head_is_caught_at_rest_and_in_the_sweep(self):
        lg = self.art.ligaments["pubofemoral.L"]
        c = self.art.joints["coxofemoral.L"].center
        bad_via = replace(lg.via[0], point=c)  # la guia en el centro de la cabeza
        bad = replace(self.art, ligaments={**self.art.ligaments, "pubofemoral.L": replace(lg, via=(bad_via,))})
        codes = [i.code for i in validation.validate_articulations(self.base, self.anat, bad)]
        self.assertIn("ART_LIGAMENT_PENETRATES", codes)
        self.assertEqual([i.code for i in validation.validate_articulations(self.base, self.anat, self.art) if i.severity == "error"], [])

    def test_validation_rejects_a_guide_far_from_its_bone_invented_mechanics_and_unsourced_surfaces(self):
        lg = self.art.ligaments["pubofemoral.L"]
        far = replace(lg.via[0], point=tuple(c + 0.05 for c in lg.via[0].point))
        bad = replace(self.art, ligaments={**self.art.ligaments, "pubofemoral.L": replace(lg, via=(far,))})
        self.assertIn("ART_VIA_OFF_BONE", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)])
        invented = replace(lg, mechanics={"status": "convencion_parametrica_declarada", "stiffness_N_per_mm": 35.0, "slack_length_m": None})
        bad = replace(self.art, ligaments={**self.art.ligaments, "pubofemoral.L": invented})
        self.assertIn("ART_MECHANICS_INVENTED", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)])
        undeclared = replace(lg, mechanics={"status": "inventado"})
        bad = replace(self.art, ligaments={**self.art.ligaments, "pubofemoral.L": undeclared})
        self.assertIn("ART_MECHANICS_STATUS", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)])
        measured_without_source = replace(lg, mechanics={"status": "medido", "stiffness_N_per_mm": 35.0})
        bad = replace(self.art, ligaments={**self.art.ligaments, "pubofemoral.L": measured_without_source})
        self.assertIn("ART_MECHANICS_NO_SOURCE", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)])
        nosrc = replace(self.art.surfaces["femoral_head.L"], sources=())
        bad = replace(self.art, surfaces={**self.art.surfaces, "femoral_head.L": nosrc})
        self.assertIn("ART_SURFACE_NO_SOURCE", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)])

    def test_bad_surface_data_is_rejected(self):
        data = articulations.load_articulation_data()
        for edit, msg in ((lambda s: s.update(kind="cubo"), "kind"), (lambda s: s.update(radius_m=0.5), "radio"), (lambda s: s.update(radius_m=-1.0), "radio")):
            bad = copy.deepcopy(data)
            for d in bad:
                for sf in d.get("bone_surfaces", []):
                    edit(sf)
            with self.assertRaises(ConfigError, msg=msg):
                build_all(data=bad)

    def test_rig_bone_resolves_level_1_bones_to_the_base(self):
        self.assertEqual(lp.rig_bone("femur.L", self.base, self.anat), "thigh.L")
        self.assertEqual(lp.rig_bone("ilium.R", self.base, self.anat), "pelvis")
        self.assertEqual(lp.rig_bone("thigh.L", self.base, self.anat), "thigh.L")
        with self.assertRaises(KeyError):
            lp.rig_bone("no_such_bone", self.base, self.anat)

    def test_other_ligaments_are_unchanged_rigid_two_node_paths(self):
        rigid = [lg for lg in self.art.ligaments.values() if not lg.deform]
        self.assertGreater(len(rigid), 600)
        self.assertTrue(all(lg.via == () for lg in rigid))
        self.assertEqual(sorted(n for n, lg in self.art.ligaments.items() if lg.deform), sorted(f"{n}.{s}" for n in HIP_LIGAMENTS for s in "LR"))


if __name__ == "__main__":
    unittest.main()
