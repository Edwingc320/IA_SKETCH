"""CM-5: rutas del psoas-iliaco (polea en la eminencia iliopubica, insercion en el trocanter menor) y de la cintilla iliotibial (cresta iliaca ->
trocanter mayor -> epicondilo lateral -> tuberculo de Gerdy), con guias de envoltura.

Cada nodo viaja con su hueso. Los obstaculos son las `BoneSurface` del modelo (cabeza, cuello, trocanter mayor, diafisis y condilo lateral del femur,
y la rama del pubis; CONVENCION, ver sus notas) y la lamina del ilion. El barrido son 22 poses de cadera y rodilla. Las pruebas exigen que ninguna
poligonal atraviese un obstaculo ni corte la lamina, y comprueban con MUTACIONES que lo detectarian: guias quitadas o metidas en el hueso,
insercion fuera de margen y origen del iliaco por fuera de la lamina."""
import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations, ligament_paths as lp, tendons  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

UNITS = ("psoas_major", "iliacus", "iliotibial_tract", "tensor_fasciae_latae")
ILIO = ("psoas_major", "iliacus")
ITB = ("iliotibial_tract", "tensor_fasciae_latae")
NEW_SURFACES = ("femoral_greater_trochanter", "femoral_shaft", "femoral_lateral_condyle", "pubic_ramus")


def build_all(height=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    art = articulations.build_articulations(base, anat, articulations.load_articulation_data())
    return base, anat, art, tendons.build_tendons(base, anat, art, tendons.load_tendon_data())


def swap(tm, name, fn):
    """Modelo con la unidad `name` (lado izquierdo) modificada por fn(unidad)."""
    return replace(tm, tendons={**tm.tendons, name: fn(tm.tendons[name])})


def poses_codes(base, anat, art, tm):
    return {i.code for i in tendons.validate_tendon_poses(base, anat, art, tm, sides=("L",))}


class TestIliopsoasAndItbPaths(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art, self.tm = build_all()
        self.tol = 0.012 * self.base.height_m / 1.75

    def test_obstacle_surfaces_are_declared_conventions_with_a_reason(self):
        for n in NEW_SURFACES:
            for s in "LR":
                sf = self.art.surfaces[f"{n}.{s}"]
                self.assertEqual(sf.bone, f"pubis.{s}" if n == "pubic_ramus" else f"femur.{s}")
                self.assertTrue(sf.sources or sf.no_numeric_source, n)
                if sf.no_numeric_source:
                    self.assertIn("convencion", sf.notes.lower(), n)
                for src in sf.sources:
                    self.assertTrue(self.art.sources[src]["url"].startswith("https://"))
        self.assertAlmostEqual(self.art.surfaces["femoral_greater_trochanter.L"].radius_m, 0.022, places=9)
        self.assertAlmostEqual(self.art.surfaces["femoral_shaft.L"].radius_m, 0.014, places=9)
        self.assertAlmostEqual(self.art.surfaces["femoral_lateral_condyle.L"].radius_m, 0.022, places=9)
        self.assertEqual(self.art.surfaces["femoral_lateral_condyle.L"].sources, ("femoral_condyle_radius",))  # el unico con cifra publicada (resumen de busqueda)
        l, r = self.art.surfaces["femoral_shaft.L"], self.art.surfaces["femoral_shaft.R"]
        self.assertLess(length(sub(mirror_point(l.a), r.a)) + length(sub(mirror_point(l.b), r.b)), 1e-9)
        # la superficie lateral del trocanter y del condilo pasa por sus hitos oseos
        for sf, lm in (("femoral_greater_trochanter.L", "greater_trochanter.L"), ("femoral_lateral_condyle.L", "femoral_lateral_epicondyle.L")):
            self.assertAlmostEqual(self.art.surfaces[sf].signed_distance(self.art.attachments[lm].point), 0.0, places=5)  # redondeo de los datos: < 10 um

    def test_the_iliopubic_eminence_is_a_landmark_on_the_pubic_ramus(self):
        for s in "LR":
            e = self.art.attachments[f"iliopubic_eminence.{s}"]
            self.assertEqual(e.bone, f"pubis.{s}")
            self.assertLess(articulations.bone_distance(e.point, e.bone, self.base, self.anat, self.art.surfaces), self.tol)
            self.assertTrue(e.sources and all(k in self.art.sources for k in e.sources))
            self.assertIn("verificar", e.notes.lower())  # posicion aproximada
        l, r = self.art.attachments["iliopubic_eminence.L"], self.art.attachments["iliopubic_eminence.R"]
        self.assertLess(length(sub(mirror_point(l.point), r.point)), 1e-9)
        self.assertLess(l.point[0], self.art.joints["coxofemoral.L"].center[0])  # medial a la cabeza femoral
        self.assertLess(l.point[1], self.art.joints["coxofemoral.L"].center[1])  # por delante de ella

    def test_psoas_and_iliacus_go_over_the_eminence_to_the_lesser_trochanter(self):
        for n in ILIO:
            for s in "LR":
                t = self.tm.tendons[f"{n}.{s}"]
                self.assertTrue(t.deform)
                kinds = [(x.kind, x.landmark) for x in t.sites]
                self.assertEqual(kinds[1:], [("via", f"iliopubic_eminence.{s}"), ("insertion", f"lesser_trochanter.{s}")], n)
                self.assertEqual(t.sites[-1].bone, f"femur.{s}")
                for x in t.sites:  # origen, polea e insercion: a < 12 mm de su hueso incluyendo las superficies
                    self.assertLess(articulations.bone_distance(x.point, x.bone, self.base, self.anat, self.art.surfaces), self.tol, (n, x.kind))
                self.assertEqual(t.insertion_class, "medio")  # la convencion de largo del tendon no cambia
                self.assertTrue(set(t.sources) <= set(self.tm.sources) and t.sources)
                self.assertIn("verificar", t.notes.lower())
                self.assertEqual(set(t.avoid), {f"{x}.{s}" for x in ("femoral_head", "femoral_neck", "femoral_greater_trochanter", "femoral_shaft", "pubic_ramus")})
        self.assertEqual(self.tm.tendons["iliacus.L"].sites[0].landmark, "iliac_fossa.L")  # parte del hito, desplazado a la cara interna
        self.assertEqual(self.tm.tendons["psoas_major.L"].sites[0].bone, "L2")  # el origen existente no se toca

    def test_itb_and_tfl_run_over_the_trochanter_and_the_lateral_epicondyle_to_gerdy(self):
        itb = self.tm.tendons["iliotibial_tract.L"]
        self.assertEqual([(x.kind, x.bone) for x in itb.sites], [("origin", "ilium.L"), ("via", "femur.L"), ("via", "femur.L"), ("insertion", "tibia.L")])
        self.assertEqual((itb.sites[0].landmark, itb.sites[-1].landmark), ("iliac_crest.L", "gerdy_tubercle.L"))
        gt, ep = self.art.attachments["greater_trochanter.L"].point, self.art.attachments["femoral_lateral_epicondyle.L"].point
        self.assertGreater(itb.sites[1].point[0], gt[0])  # lateral al trocanter
        self.assertLess(abs(itb.sites[1].point[2] - gt[2]), 0.02)  # a su altura
        self.assertGreater(itb.sites[2].point[0], ep[0])  # lateral al epicondilo
        self.assertLess(abs(itb.sites[2].point[2] - ep[2]), 0.02)
        self.assertEqual(itb.muscles, ("tensor de la fascia lata", "gluteo mayor (fibras superficiales)"))
        tfl = self.tm.tendons["tensor_fasciae_latae.L"]
        self.assertEqual([x.point for x in tfl.sites[1:3]], [x.point for x in itb.sites[1:3]])  # mismas guias
        self.assertEqual(tfl.sites[0].landmark, "anterior_superior_iliac_spine.L")  # el origen existente no se toca
        for t in (itb, tfl):
            self.assertTrue(t.deform and t.sources and set(t.avoid) >= {"femoral_greater_trochanter.L", "femoral_shaft.L", "femoral_lateral_condyle.L"})
            for x in t.sites:
                self.assertLess(articulations.bone_distance(x.point, x.bone, self.base, self.anat, self.art.surfaces), self.tol, (t.name, x.kind))
            self.assertIn("verificar", t.notes.lower())
        self.assertIn("no confirmado", itb.sites[1].structure)  # el paso por el trocanter lo pide la especificacion; las fuentes no lo confirman
        self.assertTrue(tendons.validate_tendons(self.base, self.anat, self.art, self.tm) == [])

    def test_the_sweep_has_22_poses_inside_the_rig_limits(self):
        self.assertEqual(len(lp.LEG_SWEEP), 22)
        names = [n for n, _ in lp.LEG_SWEEP]
        self.assertEqual(len(set(names)), 22)
        self.assertTrue({"flexion_120", "extension_15", "abduction_45", "knee_135", "hip_120_knee_135"} <= set(names))
        limits = {j: {d.name: (d.min_deg, d.max_deg) for d in self.base.joints[f"{j}.L"].dofs} for j in ("hip", "knee")}
        for n, rot in lp.LEG_SWEEP:
            for joint, dofs in rot.items():
                for dof, deg in dofs.items():
                    self.assertTrue(limits[joint][dof][0] <= deg <= limits[joint][dof][1], (n, joint, dof))

    def test_no_route_penetrates_an_obstacle_or_the_iliac_plate_in_the_whole_sweep(self):
        for h in (1.5, 1.75, 2.05):
            base, anat, art, tm = build_all(h)
            self.assertEqual(tendons.validate_tendon_poses(base, anat, art, tm), [], h)
            worst = {}
            for side in "LR":
                for pose_name, posed in lp.leg_sweep_poses(base, side):
                    sf = {s.name: s for s in lp.posed_surfaces(art, base, anat, posed)}
                    for n in UNITS:
                        t = tm.tendons[f"{n}.{side}"]
                        c = lp.path_clearance(lp.posed_nodes(lp.tendon_nodes(t), base, anat, posed), [sf[a] for a in t.avoid])
                        worst[t.name] = min(worst.get(t.name, 1e9), c)
            for name, c in worst.items():
                self.assertGreater(c, 0.001 * h / 1.75, (h, name))  # con margen de 1 mm a 1.75 m (el minimo es el psoas junto a la rama del pubis en aduccion), no tangente

    def test_posed_nodes_stay_attached_to_their_bones(self):
        """Un nodo no se queda atras: su distancia con signo a los obstaculos de SU hueso no cambia con la pose (cuerpo rigido)."""
        for pose_name, posed in lp.leg_sweep_poses(self.base, "L"):
            sf = {s.name: s for s in lp.posed_surfaces(self.art, self.base, self.anat, posed)}
            for n in UNITS:
                t = self.tm.tendons[f"{n}.L"]
                path = lp.posed_nodes(lp.tendon_nodes(t), self.base, self.anat, posed)
                for site, p1 in zip(t.sites, path):
                    mine = [a for a in t.avoid if self.art.surfaces[a].bone == site.bone]
                    for a in mine:
                        self.assertAlmostEqual(self.art.surfaces[a].signed_distance(site.point), sf[a].signed_distance(p1), places=9, msg=(n, pose_name, a))
        # la cadera y la rodilla izquierdas no mueven los nodos de la pelvis ni los de la derecha
        posed = dict(lp.leg_sweep_poses(self.base, "L"))["hip_120_knee_135"]
        for n in UNITS:
            tl, tr = self.tm.tendons[f"{n}.L"], self.tm.tendons[f"{n}.R"]
            self.assertLess(length(sub(lp.posed_nodes(lp.tendon_nodes(tl), self.base, self.anat, posed)[0], tl.sites[0].point)), 1e-9, n)
            self.assertLess(max(length(sub(a, b.point)) for a, b in zip(lp.posed_nodes(lp.tendon_nodes(tr), self.base, self.anat, posed), tr.sites)), 1e-9, n)

    # ---- mutaciones: cada una debe ser detectada
    def test_mutation_psoas_without_the_eminence_pulley_penetrates(self):
        bad = swap(self.tm, "psoas_major.L", lambda t: replace(t, sites=(t.sites[0], t.sites[-1])))
        self.assertTrue({"TEN_PENETRATES"} <= {i.code for i in tendons.validate_tendons(self.base, self.anat, self.art, bad)})
        self.assertIn("TEN_PENETRATES", poses_codes(self.base, self.anat, self.art, bad))

    def test_mutation_eminence_moved_onto_the_ramus_penetrates(self):
        bad = swap(self.tm, "psoas_major.L", lambda t: replace(t, sites=(t.sites[0], replace(t.sites[1], point=self.art.surfaces["pubic_ramus.L"].a), t.sites[2])))
        self.assertIn("TEN_PENETRATES", poses_codes(self.base, self.anat, self.art, bad))

    def test_mutation_itb_without_guides_or_with_the_guide_inside_the_trochanter_is_caught(self):
        itb = self.tm.tendons["iliotibial_tract.L"]
        no_guides = swap(self.tm, "iliotibial_tract.L", lambda t: replace(t, sites=(t.sites[0], t.sites[3])))
        self.assertIn("TEN_PENETRATES", poses_codes(self.base, self.anat, self.art, no_guides))
        no_gt = swap(self.tm, "iliotibial_tract.L", lambda t: replace(t, sites=(t.sites[0], t.sites[2], t.sites[3])))
        self.assertIn("TEN_PENETRATES", poses_codes(self.base, self.anat, self.art, no_gt))
        inside = swap(self.tm, "iliotibial_tract.L", lambda t: replace(t, sites=(t.sites[0], replace(t.sites[1], point=self.art.surfaces["femoral_greater_trochanter.L"].a), *t.sites[2:])))
        self.assertIn("TEN_PENETRATES", poses_codes(self.base, self.anat, self.art, inside))
        self.assertEqual(poses_codes(self.base, self.anat, self.art, self.tm), set())
        self.assertEqual(len(itb.sites), 4)

    def test_mutation_epicondyle_guide_inside_the_condyle_is_caught(self):
        """La guia del epicondilo no es necesaria para que la poligonal no entre en el condilo (Gerdy y la guia del trocanter ya quedan por fuera), pero
        metida en el condilo si lo atraviesa: la prueba lo detecta."""
        inside = swap(self.tm, "iliotibial_tract.L", lambda t: replace(t, sites=(*t.sites[:2], replace(t.sites[2], point=self.art.surfaces["femoral_lateral_condyle.L"].a), t.sites[3])))
        self.assertIn("TEN_PENETRATES", poses_codes(self.base, self.anat, self.art, inside))
        without = swap(self.tm, "iliotibial_tract.L", lambda t: replace(t, sites=(*t.sites[:2], t.sites[3])))
        self.assertEqual(poses_codes(self.base, self.anat, self.art, without), set())  # dato honesto: sin esa guia tampoco penetra

    def test_mutation_a_displaced_guide_or_insertion_is_out_of_margin(self):
        far = tuple(c + 0.05 for c in self.tm.tendons["iliotibial_tract.L"].sites[2].point)
        bad = swap(self.tm, "iliotibial_tract.L", lambda t: replace(t, sites=(*t.sites[:2], replace(t.sites[2], point=far), t.sites[3])))
        self.assertIn("TEN_SITE_OFF_BONE", {i.code for i in tendons.validate_tendons(self.base, self.anat, self.art, bad)})
        far_ins = tuple(c + 0.10 for c in self.tm.tendons["psoas_major.L"].sites[-1].point)
        bad = swap(self.tm, "psoas_major.L", lambda t: replace(t, sites=(*t.sites[:-1], replace(t.sites[-1], point=far_ins))))
        self.assertIn("TEN_SITE_OFF_BONE", {i.code for i in tendons.validate_tendons(self.base, self.anat, self.art, bad)})
        ins = self.tm.tendons["psoas_major.L"].sites[-1]
        near = tuple(c + 0.02 for c in ins.point)  # 2 cm del trocanter menor
        bad = swap(self.tm, "psoas_major.L", lambda t: replace(t, sites=(*t.sites[:-1], replace(ins, point=near))))
        d = articulations.bone_distance(near, ins.bone, self.base, self.anat, self.art.surfaces)
        self.assertEqual("TEN_SITE_OFF_BONE" in {i.code for i in tendons.validate_tendons(self.base, self.anat, self.art, bad)}, d > self.tol)

    def test_mutation_the_iliacus_origin_on_the_outer_side_of_the_plate_crosses_it(self):
        fossa = self.art.attachments["iliac_fossa.L"].point
        bad = swap(self.tm, "iliacus.L", lambda t: replace(t, sites=(replace(t.sites[0], point=fossa), *t.sites[1:])))
        self.assertIn("TEN_CROSSES_PLATE", poses_codes(self.base, self.anat, self.art, bad))
        self.assertLess(length(sub(fossa, self.tm.tendons["iliacus.L"].sites[0].point)), 0.012)  # el desplazamiento del origen es de 10.8 mm
        self.assertGreater(length(sub(fossa, self.tm.tendons["iliacus.L"].sites[0].point)), 0.010)

    def test_validation_requires_avoid_and_known_surfaces(self):
        bad = swap(self.tm, "psoas_major.L", lambda t: replace(t, avoid=()))
        self.assertIn("TEN_AVOID_EMPTY", {i.code for i in tendons.validate_tendons(self.base, self.anat, self.art, bad)})
        bad = swap(self.tm, "psoas_major.L", lambda t: replace(t, avoid=("femoral_head.L", "no_such_surface")))
        self.assertIn("TEN_AVOID_UNKNOWN", {i.code for i in tendons.validate_tendons(self.base, self.anat, self.art, bad)})
        bad = swap(self.tm, "psoas_major.L", lambda t: replace(t, sites=tuple(replace(s, bone="L2") for s in t.sites)))
        self.assertIn("TEN_DEFORM_USELESS", {i.code for i in tendons.validate_tendons(self.base, self.anat, self.art, bad)})

    def test_surface_without_source_or_convention_note_is_rejected(self):
        from anatomical_core import validation
        sf = self.art.surfaces["femoral_shaft.L"]
        bad = replace(self.art, surfaces={**self.art.surfaces, sf.name: replace(sf, no_numeric_source=False)})
        self.assertIn("ART_SURFACE_NO_SOURCE", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)])
        bad = replace(self.art, surfaces={**self.art.surfaces, sf.name: replace(sf, notes="Capsula del femur.")})
        self.assertIn("ART_SURFACE_NOTE", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)])
        self.assertEqual([i for i in validation.validate_articulations(self.base, self.anat, self.art) if i.severity == "error"], [])

    def test_node_weights_interpolate_between_the_bones_of_the_neighbouring_sites(self):
        t = self.tm.tendons["iliotibial_tract.L"]
        for p, want in ((t.sites[0].point, {"ilium.L": 1.0}), (t.sites[1].point, {"femur.L": 1.0}), (t.sites[-1].point, {"tibia.L": 1.0})):
            w = dict(t.node_weights(p))
            self.assertAlmostEqual(sum(w.values()), 1.0)
            self.assertEqual({b for b, x in w.items() if x > 0.999}, set(want))
        mid = tuple((a + b) / 2 for a, b in zip(t.sites[2].point, t.sites[3].point))  # a mitad del tramo epicondilo -> Gerdy
        w = dict(t.node_weights(mid))
        self.assertAlmostEqual(w["femur.L"], 0.5, places=6)
        self.assertAlmostEqual(w["tibia.L"], 0.5, places=6)
        self.assertEqual(t.node_weights(t.sites[1].point)[0][0] in ("femur.L", "ilium.L"), True)

    def test_plate_helpers(self):
        o = self.anat.bones["ilium.L"].outline
        tris = lp.plate_triangles(self.anat, "ilium.L")
        self.assertEqual(len(tris), len(o) - 2)
        self.assertEqual(lp.plate_triangles(self.anat, "pubis.L"), [])  # un segmento no es lamina
        tri = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        self.assertTrue(lp.segment_hits_triangle((0.2, 0.2, -0.5), (0.2, 0.2, 0.5), tri, margin=0.001))
        self.assertFalse(lp.segment_hits_triangle((0.2, 0.2, 0.1), (0.2, 0.2, 0.5), tri))  # no llega
        self.assertFalse(lp.segment_hits_triangle((0.2, 0.2, 0.0), (0.2, 0.2, 0.5), tri))  # empieza sobre la lamina: la toca, no la atraviesa
        self.assertFalse(lp.segment_hits_triangle((2.0, 2.0, -0.5), (2.0, 2.0, 0.5), tri))  # fuera del triangulo

    def test_the_cm5_json_is_what_the_model_reads(self):
        d = json.loads((ROOT / "config" / "muscles" / "tendons_lower_limb.json").read_text(encoding="utf-8"))
        names = [u["name"] for u in d["tendons"]]
        self.assertIn("iliotibial_tract.L", names)
        self.assertEqual(sum(1 for u in d["tendons"] if u.get("deform")), 2)  # cintilla y tensor de la fascia lata


if __name__ == "__main__":
    unittest.main()
