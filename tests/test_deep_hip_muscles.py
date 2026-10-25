"""CM-6: musculos profundos de la cadera y aductores que faltaban (piriforme, obturadores interno y externo, gemelos superior e inferior, cuadrado femoral,
pectineo y aductor corto) y los hitos nuevos (pectineal_crest, obturator_margin, trochanteric_fossa, intertrochanteric_crest).

Cada nodo viaja con su hueso. Obstaculos: cabeza, cuello y diafisis del femur, rama del pubis y el isquion (CONVENCION, ver sus notas) y las laminas del
ilion y del sacro. El barrido son 22 poses de cadera y rodilla. Las pruebas exigen anclajes a < 12 mm, ninguna penetracion con margen, y comprueban con
MUTACIONES que lo detectarian (guias quitadas o lejos, extremos metidos en el hueso)."""
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations, ligament_paths as lp, tendons, validation  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

LANDMARKS = {"pectineal_crest": "pubis", "obturator_margin": "ischium", "trochanteric_fossa": "femur", "intertrochanteric_crest": "femur"}
UNITS = ("piriformis", "obturator_internus", "gemellus_superior", "gemellus_inferior", "obturator_externus", "quadratus_femoris", "pectineus", "adductor_brevis")
ORIGINS = {"piriformis": "sacral_lateral_mass", "obturator_internus": "obturator_margin", "gemellus_superior": "ischial_spine", "gemellus_inferior": "ischial_tuberosity",
           "obturator_externus": "obturator_margin", "quadratus_femoris": "ischial_tuberosity", "pectineus": "pectineal_crest", "adductor_brevis": "pubic_body"}
AVOID = {"piriformis": ("femoral_head", "femoral_neck", "ischial_ramus"), "obturator_internus": ("femoral_head", "femoral_neck", "ischial_ramus"),
         "gemellus_superior": ("femoral_head", "femoral_neck", "ischial_ramus"), "gemellus_inferior": ("femoral_head", "femoral_neck", "ischial_ramus"),
         "obturator_externus": ("femoral_head", "femoral_neck", "ischial_ramus"), "quadratus_femoris": ("femoral_head", "femoral_neck", "ischial_ramus", "femoral_shaft"),
         "pectineus": ("femoral_head", "femoral_neck", "femoral_shaft", "pubic_ramus"), "adductor_brevis": ("femoral_head", "femoral_neck", "femoral_shaft", "pubic_ramus")}
VIAS = {"piriformis": ["ischium.L"], "obturator_internus": ["ischium.L"], "obturator_externus": ["ischium.L", "femur.L"]}


def build_all(height=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    art = articulations.build_articulations(base, anat, articulations.load_articulation_data())
    return base, anat, art, tendons.build_tendons(base, anat, art, tendons.load_tendon_data())


def swap(tm, name, fn):
    return replace(tm, tendons={**tm.tendons, name: fn(tm.tendons[name])})


def codes(base, anat, art, tm):
    return ({i.code for i in tendons.validate_tendons(base, anat, art, tm)} | {i.code for i in tendons.validate_tendon_poses(base, anat, art, tm, sides=("L",))}) - {"TEN_ASYMMETRIC"}


class TestDeepHipMuscles(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art, self.tm = build_all()
        self.tol = 0.012 * self.base.height_m / 1.75

    def test_the_four_new_landmarks_are_within_12_mm_of_their_bone_faces(self):
        for n, bone in LANDMARKS.items():
            for s in "LR":
                a = self.art.attachments[f"{n}.{s}"]
                self.assertEqual(a.bone, f"{bone}.{s}" if bone != "pubis" else f"pubis.{s}")
                self.assertLess(articulations.bone_distance(a.point, a.bone, self.base, self.anat, self.art.surfaces), self.tol, n)
                self.assertTrue(a.sources and all(k in self.art.sources and self.art.sources[k]["url"].startswith("https://") for k in a.sources), n)
                self.assertIn("verificar", a.notes.lower(), n)  # posicion aproximada
            l, r = self.art.attachments[f"{n}.L"], self.art.attachments[f"{n}.R"]
            self.assertLess(length(sub(mirror_point(l.point), r.point)), 1e-9, n)
        self.assertEqual([i for i in validation.validate_articulations(self.base, self.anat, self.art) if i.severity == "error"], [])

    def test_landmarks_sit_where_anatomy_says(self):
        at, c = self.art.attachments, self.art.joints["coxofemoral.L"].center
        # fosa trocanterica: detras y medial al trocanter mayor; cresta intertrocanterea: entre los dos trocanteres y por detras
        fossa, ic, gt, lt = (at[f"{n}.L"].point for n in ("trochanteric_fossa", "intertrochanteric_crest", "greater_trochanter", "lesser_trochanter"))
        self.assertGreater(fossa[1], gt[1] + 0.01)
        self.assertLess(fossa[0], gt[0])
        self.assertTrue(lt[0] < ic[0] < gt[0] and ic[1] > gt[1] + 0.01)
        # pecten del pubis: medial a la eminencia iliopubica y por delante; margen obturador: bajo la cabeza, hacia delante del isquion
        pect, em, om = (at[f"{n}.L"].point for n in ("pectineal_crest", "iliopubic_eminence", "obturator_margin"))
        self.assertLess(pect[0], em[0])
        self.assertLess(pect[1], c[1])
        self.assertLess(om[2], c[2] - 0.04)
        self.assertLess(om[0], c[0])

    def test_the_ischial_obstacle_is_a_declared_convention(self):
        for s in "LR":
            sf = self.art.surfaces[f"ischial_ramus.{s}"]
            self.assertEqual((sf.bone, sf.kind, sf.no_numeric_source), (f"ischium.{s}", "capsule", True))
            self.assertAlmostEqual(sf.radius_m, 0.005, places=9)
            self.assertIn("convencion", sf.notes.lower())

    def test_eight_units_per_side_with_the_expected_origins_routes_and_insertions(self):
        for n in UNITS:
            for s in "LR":
                t = self.tm.tendons[f"{n}.{s}"]
                self.assertTrue(t.deform and t.avoid and t.sources and t.muscles, n)
                self.assertEqual(t.sites[0].landmark, f"{ORIGINS[n]}.{s}", n)
                self.assertEqual(t.sites[-1].bone, f"femur.{s}", n)
                self.assertEqual([x.bone for x in t.sites[1:-1]], [b.replace(".L", f".{s}") for b in VIAS.get(n, [])], n)
                self.assertTrue(all(k in self.tm.sources for k in t.sources))
                self.assertIn("verificar", t.notes.lower(), n)
                self.assertEqual(t.origin_class, None)
                self.assertIn(t.insertion_class, ("corto", "medio"), n)
                self.assertTrue({f"{x}.{s}" for x in AVOID[n]} <= set(t.avoid), n)  # cada unidad dice que obstaculos evita
                for x in t.sites:
                    self.assertLess(articulations.bone_distance(x.point, x.bone, self.base, self.anat, self.art.surfaces), self.tol, (n, x.kind))
        self.assertEqual(self.tm.tendons["obturator_internus.L"].sites[-1].landmark, "trochanteric_fossa.L")
        self.assertEqual(self.tm.tendons["obturator_externus.L"].sites[-1].landmark, "trochanteric_fossa.L")
        self.assertEqual(self.tm.tendons["quadratus_femoris.L"].sites[-1].landmark, "intertrochanteric_crest.L")
        self.assertEqual(self.tm.tendons["gemellus_superior.L"].sites[0].landmark, "ischial_spine.L")  # el gemelo superior nace de la espina, el inferior de la tuberosidad
        self.assertEqual(self.tm.tendons["gemellus_inferior.L"].sites[0].landmark, "ischial_tuberosity.L")
        self.assertEqual(tendons.validate_tendons(self.base, self.anat, self.art, self.tm), [])

    def test_the_obturator_guides_go_around_the_foramen_frame_and_the_lesser_sciatic_notch(self):
        oi, oe = self.tm.tendons["obturator_internus.L"], self.tm.tendons["obturator_externus.L"]
        spine, tub = self.art.attachments["ischial_spine.L"].point, self.art.attachments["ischial_tuberosity.L"].point
        notch = oi.sites[1].point
        self.assertTrue(tub[2] < notch[2] < spine[2])  # la escotadura ciatica menor esta entre la espina y la tuberosidad
        self.assertGreater(notch[1], max(spine[1], tub[1]) - 0.001)  # y por detras del isquion
        om = self.art.attachments["obturator_margin.L"].point
        self.assertLess(oi.sites[0].point[0], om[0])  # el interno nace en la cara interna (medial)
        self.assertGreater(oe.sites[0].point[0], om[0])  # el externo en la externa (lateral)
        self.assertLess(length(sub(oi.sites[0].point, om)), 0.0025)
        # el externo rodea por debajo el cuello del femur: la ultima guia esta en la cara posteroinferior del cuello
        wrap = oe.sites[2].point
        self.assertLess(self.art.surfaces["femoral_neck.L"].signed_distance(wrap), 0.002)
        self.assertGreater(self.art.surfaces["femoral_neck.L"].signed_distance(wrap), 0.0)
        self.assertGreater(wrap[1], self.art.joints["coxofemoral.L"].center[1])  # detras de la cabeza

    def test_no_route_penetrates_an_obstacle_or_a_plate_in_the_whole_sweep(self):
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
            self.assertEqual(len(worst), 16)
            for name, c in worst.items():
                self.assertGreater(c, 0.0005 * h / 1.75, (h, name))  # margen de 0.5 mm a 1.75 m (el minimo es el obturador externo bajo el cuello)

    def test_posed_nodes_stay_attached_to_their_bones(self):
        for pose_name, posed in lp.leg_sweep_poses(self.base, "L"):
            sf = {s.name: s for s in lp.posed_surfaces(self.art, self.base, self.anat, posed)}
            for n in UNITS:
                t = self.tm.tendons[f"{n}.L"]
                path = lp.posed_nodes(lp.tendon_nodes(t), self.base, self.anat, posed)
                for site, p1 in zip(t.sites, path):
                    for a in (a for a in t.avoid if self.art.surfaces[a].bone == site.bone):
                        self.assertAlmostEqual(self.art.surfaces[a].signed_distance(site.point), sf[a].signed_distance(p1), places=9, msg=(n, pose_name, a))
        posed = dict(lp.leg_sweep_poses(self.base, "L"))["flexion_120"]
        for n in UNITS:  # el origen en la pelvis no se mueve; la pierna derecha no se entera
            tl, tr = self.tm.tendons[f"{n}.L"], self.tm.tendons[f"{n}.R"]
            self.assertLess(length(sub(lp.posed_nodes(lp.tendon_nodes(tl), self.base, self.anat, posed)[0], tl.sites[0].point)), 1e-9, n)
            self.assertLess(max(length(sub(a, b.point)) for a, b in zip(lp.posed_nodes(lp.tendon_nodes(tr), self.base, self.anat, posed), tr.sites)), 1e-9, n)

    # ---- mutaciones
    def test_mutation_guides_removed_are_caught(self):
        drop = lambda t, k: replace(t, sites=tuple(s for i, s in enumerate(t.sites) if i != k))  # noqa: E731
        cases = (("piriformis.L", (1,)), ("obturator_internus.L", (1,)), ("obturator_externus.L", (1,)), ("obturator_externus.L", (2,)))
        for name, ks in cases:
            bad = swap(self.tm, name, lambda t, ks=ks: drop(t, ks[0]))
            self.assertIn("TEN_PENETRATES", codes(self.base, self.anat, self.art, bad), (name, ks))
        no_guides = swap(self.tm, "obturator_externus.L", lambda t: replace(t, sites=(t.sites[0], t.sites[-1])))
        self.assertIn("TEN_PENETRATES", codes(self.base, self.anat, self.art, no_guides))
        self.assertIn("TEN_CROSSES_PLATE", codes(self.base, self.anat, self.art, swap(self.tm, "piriformis.L", lambda t: drop(t, 1))))  # sin la escotadura corta la lamina
        self.assertEqual(codes(self.base, self.anat, self.art, self.tm), set())

    def test_mutation_endpoints_inside_a_bone_are_caught(self):
        sh, isc, ram = self.art.surfaces["femoral_shaft.L"], self.art.surfaces["ischial_ramus.L"], self.art.surfaces["pubic_ramus.L"]
        mid = lambda s: tuple((a + b) / 2 for a, b in zip(s.a, s.b))  # noqa: E731
        setp = lambda t, k, p: replace(t, sites=tuple(replace(x, point=p) if i == k else x for i, x in enumerate(t.sites)))  # noqa: E731
        for name, k, p in (("quadratus_femoris.L", 1, mid(sh)), ("adductor_brevis.L", 1, mid(sh)), ("gemellus_inferior.L", 0, mid(isc)), ("pectineus.L", 0, ram.b)):
            bad = swap(self.tm, name, lambda t, k=k, p=p: setp(t, k, p))
            self.assertIn("TEN_PENETRATES", codes(self.base, self.anat, self.art, bad), name)

    def test_mutation_a_displaced_guide_or_insertion_is_out_of_margin(self):
        far = lambda p, d: tuple(c + d for c in p)  # noqa: E731
        setp = lambda t, k, p: replace(t, sites=tuple(replace(x, point=p) if i == k else x for i, x in enumerate(t.sites)))  # noqa: E731
        bad = swap(self.tm, "obturator_internus.L", lambda t: setp(t, 1, far(t.sites[1].point, 0.05)))
        self.assertIn("TEN_SITE_OFF_BONE", codes(self.base, self.anat, self.art, bad))
        bad = swap(self.tm, "quadratus_femoris.L", lambda t: setp(t, 1, far(t.sites[1].point, 0.10)))
        self.assertIn("TEN_SITE_OFF_BONE", codes(self.base, self.anat, self.art, bad))
        bad = swap(self.tm, "pectineus.L", lambda t: setp(t, 1, far(t.sites[1].point, -0.10)))
        self.assertIn("TEN_SITE_OFF_BONE", codes(self.base, self.anat, self.art, bad))

    def test_mutation_a_landmark_moved_more_than_12_mm_is_caught(self):
        for n in LANDMARKS:
            a = self.art.attachments[f"{n}.L"]
            moved = replace(a, point=tuple(c + 0.08 for c in a.point))
            bad = replace(self.art, attachments={**self.art.attachments, a.name: moved})
            self.assertIn("ART_ATTACHMENT_OFF_BONE", [i.code for i in validation.validate_articulations(self.base, self.anat, bad)], n)

    def test_mutation_unit_without_avoid_or_on_one_bone_is_rejected(self):
        bad = swap(self.tm, "piriformis.L", lambda t: replace(t, avoid=()))
        self.assertIn("TEN_AVOID_EMPTY", {i.code for i in tendons.validate_tendons(self.base, self.anat, self.art, bad)})
        bad = swap(self.tm, "piriformis.L", lambda t: replace(t, avoid=t.avoid + ("femoral_head.X",)))
        self.assertIn("TEN_AVOID_UNKNOWN", {i.code for i in tendons.validate_tendons(self.base, self.anat, self.art, bad)})

    def test_both_plates_are_checked(self):
        self.assertTrue(lp.plate_triangles(self.anat, "sacrum"))  # el origen del piriforme esta en la lamina del sacro, que tambien se vigila
        t = self.tm.tendons["piriformis.L"]
        self.assertEqual(t.sites[0].bone, "sacrum")


if __name__ == "__main__":
    unittest.main()
