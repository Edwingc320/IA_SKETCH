"""F1 (esqueleto solido, docs/plan/70_esqueleto_referencia.md): mallas oseas solidas como lofts de secciones elipticas, ajustadas a los hitos del modelo.

Primer hueso: el femur. Las pruebas fijan que cada malla es cerrada (Euler 2) y de volumen positivo, simetrica L/R, isometrica con --height (1.50, 1.75 y 2.05 m),
que los hitos del femur quedan a < 12 mm de su superficie, que sigue al rig en Blender y que MUTACIONES de los datos se detectan."""
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

from anatomical_core import anatomy, articulations, bone_meshes as bm, pose as pose_mod, validation  # noqa: E402
from anatomical_core.config import ConfigError, PoseDef, load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402
from anatomical_core.volumes import euler_characteristic  # noqa: E402

TEST_OUT = ROOT / "output" / "_test"
FEMUR_LANDMARKS = ("greater_trochanter", "lesser_trochanter", "femoral_lateral_epicondyle", "femoral_medial_epicondyle", "gluteal_tuberosity", "trochanteric_fossa", "intertrochanteric_crest")


def build_all(height=None, data=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    art = articulations.build_articulations(base, anat, articulations.load_articulation_data())
    return base, anat, art, bm.build_bone_meshes(base, anat, data if data is not None else bm.load_mesh_data())


class TestLoft(unittest.TestCase):
    def test_a_capsule_is_closed_positive_and_has_the_analytic_volume(self):
        r, L = 0.02, 0.10
        st = (bm.Station((0, 0, 0), r, r), bm.Station((0, 0, -L), r, r))
        verts, faces = bm.loft(st, sides=32, cap_start=r, cap_end=r)
        self.assertEqual(euler_characteristic(verts, [list(f) for f in faces]), 2)
        from anatomical_core.volumes import signed_volume
        vol = signed_volume(verts, faces)
        self.assertAlmostEqual(vol / (math.pi * r * r * L + 4 / 3 * math.pi * r ** 3), 1.0, delta=0.03)  # cilindro + dos medias esferas
        self.assertGreater(vol, 0)

    def test_an_elliptical_tube_keeps_its_semi_axes_and_the_frame_does_not_twist(self):
        st = (bm.Station((0, 0, 0), 0.03, 0.01), bm.Station((0, 0, -0.2), 0.03, 0.01), bm.Station((0, 0, -0.4), 0.03, 0.01))
        verts, _ = bm.loft(st, sides=24)
        xs = [v[0] for v in verts if abs(v[2] + 0.2) < 1e-3]
        ys = [v[1] for v in verts if abs(v[2] + 0.2) < 1e-3]
        self.assertAlmostEqual(max(xs) - min(xs), 0.06, delta=0.002)  # anchura a lo largo de x
        self.assertAlmostEqual(max(ys) - min(ys), 0.02, delta=0.002)  # profundidad a lo largo de y
        bent = (bm.Station((0, 0, 0), 0.03, 0.01), bm.Station((0, 0, -0.2), 0.03, 0.01), bm.Station((0.1, 0, -0.35), 0.03, 0.01))  # trayectoria curva: sigue siendo cerrada y sin giros
        verts2, faces2 = bm.loft(bent, sides=24)
        self.assertEqual(euler_characteristic(verts2, [list(f) for f in faces2]), 2)
        self.assertTrue(all(math.isfinite(c) for v in verts2 for c in v))

    def test_a_loft_needs_two_stations_and_sane_semi_axes(self):
        with self.assertRaises(ConfigError):
            bm.loft((bm.Station((0, 0, 0), 0.01, 0.01),))
        data = bm.load_mesh_data()
        bad = copy.deepcopy(data)
        bad["bones"][0]["stations"][0]["a_m"] = 0.5
        with self.assertRaises(ConfigError):
            build_all(data=bad)
        bad = copy.deepcopy(data)
        bad["bones"][0]["stations"] = bad["bones"][0]["stations"][:1]
        with self.assertRaises(ConfigError):
            build_all(data=bad)
        bad = copy.deepcopy(data)
        bad["bones"][0]["name"] = "no_such_bone.L"
        with self.assertRaises(ConfigError):
            build_all(data=bad)


class TestFemurMesh(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art, self.model = build_all()

    def test_both_femurs_are_closed_positive_and_valid(self):
        self.assertEqual([n for n in sorted(self.model.meshes) if n.startswith("femur")], ["femur.L", "femur.R"])
        for m in (self.model.meshes["femur.L"], self.model.meshes["femur.R"]):
            self.assertEqual(euler_characteristic(list(m.verts), [list(f) for f in m.faces]), 2, m.name)
            self.assertGreater(m.volume_m3, 3.0e-4)  # ~514 cm3 a 1.75 m
            self.assertLess(m.volume_m3, 8.0e-4)
        self.assertEqual(bm.validate_bone_meshes(self.base, self.anat, self.model), [])

    def test_right_is_the_exact_mirror_of_left(self):
        l, r = self.model.meshes["femur.L"], self.model.meshes["femur.R"]
        self.assertEqual(len(l.verts), len(r.verts))
        key = lambda v: tuple(round(c, 9) for c in v)  # noqa: E731  (el orden de los vertices de un anillo se invierte al reflejar)
        self.assertEqual(sorted(key(mirror_point(p)) for p in l.verts), sorted(key(q) for q in r.verts))

    def test_the_mesh_has_the_shape_of_a_femur(self):
        l = self.model.meshes["femur.L"]
        zs = [v[2] for v in l.verts]
        self.assertAlmostEqual(max(zs) - min(zs), 0.45, delta=0.01)  # 45 cm: cabeza a condilos
        c = self.art.joints["coxofemoral.L"].center
        self.assertEqual(bm.mesh_distance(c, l), 0.0)  # el centro de la cabeza esta dentro
        self.assertGreater(l.stations[0].a * 2, 0.040)  # cabeza de 44 mm
        self.assertLess(l.stations[4].a * 2, 0.034)  # diafisis de unos 29 mm: mas fina que la cabeza y que los condilos
        self.assertLess(l.stations[4].a, l.stations[-1].a / 2 + 0.001)
        self.assertEqual([x.point[0] > c[0] for x in l.stations[1:3]], [True, True])  # el cuello y el trocanter van lateral a la cabeza
        xs = [v[0] for v in l.verts]
        self.assertGreater(max(xs), self.art.attachments["greater_trochanter.L"].point[0] - 0.002)  # la malla llega al trocanter mayor

    def test_every_femur_landmark_is_within_12_mm_of_the_surface_at_three_heights(self):
        for h in (1.5, 1.75, 2.05):
            base, anat, art, model = build_all(h)
            tol = 0.012 * h / 1.75
            for n in FEMUR_LANDMARKS:
                for s in "LR":
                    d = bm.mesh_distance(art.attachments[f"{n}.{s}"].point, model.meshes[f"femur.{s}"])
                    self.assertLess(d, tol, (h, n, s))

    def test_isometric_scaling(self):
        ref = self.model.meshes["femur.L"]
        for h in (1.5, 2.05):
            _, _, _, m2 = build_all(h)
            k = h / 1.75
            self.assertAlmostEqual(m2.meshes["femur.L"].volume_m3 / ref.volume_m3, k ** 3, places=8)
            for p, q in zip(ref.verts, m2.meshes["femur.L"].verts):
                self.assertLess(length(sub(tuple(k * c for c in p), q)), 1e-9)

    def test_the_femur_mesh_contains_the_obstacle_surface_axes_of_the_model(self):
        """La malla es coherente con los obstaculos de convencion (CM-4 a CM-8): el eje del cuello y de la diafisis queda dentro."""
        l = self.model.meshes["femur.L"]
        for name in ("femoral_neck.L", "femoral_shaft.L"):
            s = self.art.surfaces[name]
            mid = tuple((a + b) / 2 for a, b in zip(s.a, s.b))
            self.assertEqual(bm.mesh_distance(mid, l), 0.0, name)

    # ---- mutaciones
    def test_mutation_a_station_moved_far_away_breaks_the_landmark_contract(self):
        data = copy.deepcopy(bm.load_mesh_data())
        data["bones"][0]["stations"][3]["offset_h"] = [0.0, 0.0, -0.2]  # el trocanter, 35 cm mas abajo
        _, anat, art, bad = build_all(data=data)
        d = bm.mesh_distance(art.attachments["greater_trochanter.L"].point, bad.meshes["femur.L"])
        self.assertGreater(d, 0.012)

    def test_mutation_a_thin_station_is_detected_as_a_bad_shaft(self):
        data = copy.deepcopy(bm.load_mesh_data())
        data["bones"][0]["stations"][5]["a_m"] = 0.004
        data["bones"][0]["stations"][5]["b_m"] = 0.004
        _, _, _, thin = build_all(data=data)
        good = self.model.meshes["femur.L"]
        self.assertLess(thin.meshes["femur.L"].volume_m3, 0.9 * good.volume_m3)

    def test_mutation_an_open_mesh_or_an_asymmetric_pair_is_caught(self):
        l = self.model.meshes["femur.L"]
        holed = replace(l, faces=l.faces[:-5])
        bad = bm.BoneMeshModel({**self.model.meshes, "femur.L": holed}, self.model.height_m)
        self.assertIn("BMESH_NOT_CLOSED", [i.code for i in bm.validate_bone_meshes(self.base, self.anat, bad)])
        shifted = replace(l, verts=tuple((v[0] + 0.01, v[1], v[2]) for v in l.verts))
        bad = bm.BoneMeshModel({**self.model.meshes, "femur.L": shifted}, self.model.height_m)
        self.assertIn("BMESH_ASYMMETRIC", [i.code for i in bm.validate_bone_meshes(self.base, self.anat, bad)])
        inverted = replace(l, faces=tuple(tuple(reversed(f)) for f in l.faces))
        bad = bm.BoneMeshModel({**self.model.meshes, "femur.L": inverted}, self.model.height_m)
        self.assertIn("BMESH_VOLUME", [i.code for i in bm.validate_bone_meshes(self.base, self.anat, bad)])
        stray = bm.BoneMeshModel({**self.model.meshes, "tail_bone.L": l}, self.model.height_m)
        self.assertIn("BMESH_BONE_UNKNOWN", [i.code for i in bm.validate_bone_meshes(self.base, self.anat, stray)])

    def test_snapshot_validator_catches_a_wrong_parent_a_missing_object_and_a_changed_shape(self):
        l = self.model.meshes["femur.L"]
        lo, hi = tuple(min(v[i] for v in l.verts) for i in range(3)), tuple(max(v[i] for v in l.verts) for i in range(3))
        good = {f"BM_{n}": {"parent_bone": m.parent_bone, "n_verts": len(m.verts), "bbox": [tuple(min(v[i] for v in m.verts) for i in range(3)), tuple(max(v[i] for v in m.verts) for i in range(3))]}
                for n, m in self.model.meshes.items()}
        self.assertEqual(bm.validate_bone_meshes_snapshot(self.model, good), [])
        bad = {**good, "BM_femur.L": {**good["BM_femur.L"], "parent_bone": "thigh.L"}}
        self.assertIn("BMESH_BLEND_PARENT", [i.code for i in bm.validate_bone_meshes_snapshot(self.model, bad)])
        bad = {k: v for k, v in good.items() if k != "BM_femur.R"}
        self.assertIn("BMESH_BLEND_MISSING", [i.code for i in bm.validate_bone_meshes_snapshot(self.model, bad)])
        bad = {**good, "BM_femur.L": {**good["BM_femur.L"], "bbox": [(lo[0] + 0.01, lo[1], lo[2]), hi]}}
        self.assertIn("BMESH_BLEND_SHAPE", [i.code for i in bm.validate_bone_meshes_snapshot(self.model, bad)])
        bad = {**good, "BM_extra.L": good["BM_femur.L"]}
        self.assertIn("BMESH_BLEND_EXTRA", [i.code for i in bm.validate_bone_meshes_snapshot(self.model, bad)])


PELVIS = ("ilium", "ischium", "pubis", "sacrum", "coccyx")
SKIP_LANDMARKS = ("body_center_of_mass", "head_center_of_gravity")  # no son puntos de hueso


def pelvis_landmarks(art):
    return [(n, a) for n, a in art.attachments.items() if a.region == "lumbar_pelvis" and a.bone.split(".")[0] in PELVIS and n not in SKIP_LANDMARKS and not n.endswith(".R")]


def pelvis_contract(base, anat, art, model, tol=None):
    """Violaciones del contrato de F2: huecos, anillo pelvico cerrado, hitos a < 12 mm y generos."""
    tol = tol if tol is not None else 0.012 * base.height_m / 1.75
    bad = []
    if model.meshes["sacrum"].genus != 8:
        bad.append("sacrum: no tiene los 8 agujeros sacros")
    for n, a in pelvis_landmarks(art):
        if bm.mesh_distance(a.point, model.meshes[a.bone]) >= tol:
            bad.append(f"hito {n} a mas de 12 mm de {a.bone}")
    m = model.meshes
    touch = lambda a, b: min(min(length(sub(p, q)) for q in b.verts) for p in a.verts)  # noqa: E731
    k = base.height_m / 1.75
    if touch(m["pubis.L"], m["pubis.R"]) > 0.004 * k:
        bad.append("sinfisis abierta: los pubis no se tocan")
    ramus = replace(m["ischium.L"], verts=tuple(v for v in m["ischium.L"].verts if v[1] < -0.045 * k))  # extremo anterior de la rama (lejos del acetabulo)
    if not ramus.verts or touch(ramus, m["pubis.L"]) > 0.004 * k:
        bad.append("anillo abierto: la rama isquiopubiana no llega al pubis")
    if touch(m["sacrum"], m["ilium.L"]) > 0.010 * k:  # declarado: la interlinea sacroiliaca del modelo es de ~8 mm (real 2-4 mm)
        bad.append("sacroiliaca abierta")
    foramen = (0.056 * k, -0.015 * k, 0.866 * k)
    if any(bm.mesh_distance(foramen, m[f"{n}.L"]) == 0.0 for n in ("ilium", "ischium", "pubis")):
        bad.append("el agujero obturador esta tapado")
    return bad


class TestPelvisMeshes(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art, self.model = build_all()

    def test_ten_meshes_closed_with_the_declared_openings(self):
        self.assertEqual(sorted(self.model.meshes), sorted(["femur.L", "femur.R", "ilium.L", "ilium.R", "ischium.L", "ischium.R", "pubis.L", "pubis.R", "sacrum", "coccyx",
                                                            "acetabulum.L", "acetabulum.R", "acetabular_roof.L", "acetabular_roof.R", "obturator_frame.L", "obturator_frame.R", "pubic_symphysis"]))
        for n, m in self.model.meshes.items():
            self.assertEqual(euler_characteristic(list(m.verts), [list(f) for f in m.faces]), 2 - 2 * m.genus, n)
            self.assertGreater(m.volume_m3, 1e-6, n)
        self.assertEqual(self.model.meshes["sacrum"].genus, 8)  # cuatro pares de agujeros sacros, como en la imagen
        self.assertEqual({n: m.genus for n, m in self.model.meshes.items() if m.genus}, {"sacrum": 8, "obturator_frame.L": 1, "obturator_frame.R": 1})  # los marcos obturadores son anillos
        self.assertEqual(bm.validate_bone_meshes(self.base, self.anat, self.model), [])

    def test_the_sacral_foramina_are_real_holes_in_two_columns_of_four(self):
        sacrum = self.model.meshes["sacrum"]
        data = [b for b in bm.load_mesh_data()["bones"] if b["name"] == "sacrum"][0]
        self.assertEqual(len(data["holes"]), 8)
        from anatomical_core.anatomy import _eval, _point_spec
        centres = [_eval(_point_spec(h["center"], "h"), self.base, self.anat.bones) for h in data["holes"]]
        for c in centres:
            d = bm.mesh_distance(c, sacrum)
            self.assertAlmostEqual(d, 0.0045, delta=0.001)  # el centro del agujero esta a un radio de la pared: vacio
        left = sorted((c for c in centres if c[0] > 0), key=lambda c: -c[2])
        right = sorted((c for c in centres if c[0] < 0), key=lambda c: -c[2])
        self.assertEqual((len(left), len(right)), (4, 4))
        for a, b in zip(left, right):
            self.assertAlmostEqual(a[0], -b[0], places=9)  # simetricos
            self.assertAlmostEqual(a[2], b[2], places=9)

    def test_the_pelvic_ring_closes_with_the_symphysis_the_obturator_foramen_and_the_sacroiliac(self):
        self.assertEqual(pelvis_contract(self.base, self.anat, self.art, self.model), [])

    def test_every_pelvic_landmark_is_within_12_mm_of_its_mesh_at_three_heights_both_sides(self):
        for h in (1.5, 1.75, 2.05):
            base, anat, art, model = build_all(h)
            tol = 0.012 * h / 1.75
            lm = pelvis_landmarks(art)
            self.assertGreaterEqual(len(lm), 17)
            for n, a in lm:
                self.assertLess(bm.mesh_distance(a.point, model.meshes[a.bone]), tol, (h, n))
                if n.endswith(".L"):
                    r = art.attachments[n[:-2] + ".R"]
                    self.assertLess(bm.mesh_distance(r.point, model.meshes[r.bone]), tol, (h, n, "R"))
            self.assertEqual(pelvis_contract(base, anat, art, model), [], h)

    def test_the_pelvis_scales_isometrically(self):
        ref = {n: m.volume_m3 for n, m in self.model.meshes.items()}
        for h in (1.5, 2.05):
            _, _, _, m2 = build_all(h)
            for n, v in ref.items():
                self.assertAlmostEqual(m2.meshes[n].volume_m3 / v, (h / 1.75) ** 3, places=7, msg=(h, n))

    def test_symmetry_and_the_slab_style(self):
        key = lambda v: tuple(round(c, 9) for c in v)  # noqa: E731
        for n in ("ilium", "ischium", "pubis"):
            l, r = self.model.meshes[f"{n}.L"], self.model.meshes[f"{n}.R"]
            self.assertEqual(sorted(key(mirror_point(p)) for p in l.verts), sorted(key(q) for q in r.verts), n)
        s = self.model.meshes["sacrum"]
        # el sacro es simetrico respecto a x = 0 salvo el empuje lateral de 2-4 mm de algunos puntos intermedios del contorno (declarado)
        far = max(min(length(sub(mirror_point(p), q)) for q in s.verts) for p in s.verts)
        self.assertLess(far, 0.006)
        self.assertFalse(self.model.meshes["ilium.L"].smooth or s.smooth)  # laminas: sombreado plano
        self.assertTrue(self.model.meshes["pubis.L"].smooth)

    def test_the_regions_ligaments_and_muscle_origins_were_not_touched(self):
        """F2 no modifica ligamentos ni origenes musculares: los hitos y ligamentos de la region siguen exactamente donde estaban (valores de CM-1 a CM-10)."""
        a = self.art.attachments
        self.assertEqual(tuple(round(c, 4) for c in a["ischial_tuberosity.L"].point), (0.0613, 0.021, 0.8225))
        self.assertEqual(tuple(round(c, 4) for c in a["iliopubic_eminence.L"].point), (0.0449, -0.0415, 0.9009))
        self.assertEqual(tuple(round(c, 4) for c in self.art.ligaments["iliofemoral.L"].a), (0.1067, -0.0262, 0.9581))
        self.assertEqual(len(self.art.ligaments), 620)

    # ---- mutaciones de F2
    def test_mutation_a_sacral_hole_removed_is_caught(self):
        data = copy.deepcopy(bm.load_mesh_data())
        next(b for b in data["bones"] if b["name"] == "sacrum")["holes"].pop()
        base, anat, art, bad = build_all(data=data)
        self.assertEqual(bad.meshes["sacrum"].genus, 7)
        self.assertIn("sacrum: no tiene los 8 agujeros sacros", pelvis_contract(base, anat, art, bad))

    def test_mutation_an_open_ring_or_a_covered_foramen_or_a_displaced_ilium_is_caught(self):
        data = copy.deepcopy(bm.load_mesh_data())
        isch = next(b for b in data["bones"] if b["name"] == "ischium.L")
        isch["stations"][0]["offset_h"] = [x + d for x, d in zip(isch["stations"][0]["offset_h"], (0.0, 0.0, -0.06))]  # el extremo de la rama, 10 cm mas abajo
        base, anat, art, bad = build_all(data=data)
        self.assertTrue(any("anillo abierto" in v for v in pelvis_contract(base, anat, art, bad)))
        data = copy.deepcopy(bm.load_mesh_data())
        for p in next(b for b in data["bones"] if b["name"] == "ilium.L")["outline"]:
            p["offset_h"][2] += 0.03  # toda la lamina 5 cm mas arriba: los hitos del ilion quedan fuera
        base, anat, art, bad = build_all(data=data)
        self.assertTrue(any("hito" in v for v in pelvis_contract(base, anat, art, bad)))
        data = copy.deepcopy(bm.load_mesh_data())
        for st in next(b for b in data["bones"] if b["name"] == "pubis.L")["stations"]:
            st["a_m"], st["b_m"] = 0.07, 0.07  # pubis enorme: tapa el agujero obturador
        base, anat, art, bad = build_all(data=data)
        self.assertTrue(any("obturador" in v for v in pelvis_contract(base, anat, art, bad)))

    def test_mutation_a_degenerate_slab_outline_is_rejected(self):
        data = copy.deepcopy(bm.load_mesh_data())
        next(b for b in data["bones"] if b["name"] == "ilium.L")["outline"] = [{"at": "pelvis.head"}, {"at": "pelvis.tail"}]
        with self.assertRaises(ConfigError):
            build_all(data=data)
        data = copy.deepcopy(bm.load_mesh_data())
        next(b for b in data["bones"] if b["name"] == "ilium.L")["thickness_m"] = 0.5
        with self.assertRaises(ConfigError):
            build_all(data=data)


class TestSlabPrimitive(unittest.TestCase):
    def test_a_slab_with_holes_has_the_analytic_volume_and_euler_two_minus_two_holes(self):
        sq = [(0, 0, 0), (0.1, 0, 0), (0.1, 0.1, 0), (0, 0.1, 0)]
        verts, faces = bm.slab(sq, 0.01)
        from anatomical_core.volumes import signed_volume
        self.assertAlmostEqual(signed_volume(verts, faces), 1e-4, places=12)
        r1, r2 = 0.02, 0.01
        verts, faces = bm.slab(sq, 0.01, [{"center": (0.05, 0.05, 0), "radius": r1}, {"center": (0.02, 0.02, 0), "radius": r2}])
        self.assertEqual(euler_characteristic(verts, [list(f) for f in faces]), -2)
        poly = lambda r: 0.5 * 12 * r * r * math.sin(2 * math.pi / 12)  # noqa: E731
        self.assertAlmostEqual(signed_volume(verts, faces), 0.01 * (0.01 - poly(r1) - poly(r2)), places=12)

    def test_a_slab_does_not_accept_a_crossing_outline(self):
        with self.assertRaises(ConfigError):
            bm.slab([(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)], 0.01)  # corbata: area neta nula


JOINTS = ("acetabulum.L", "acetabulum.R")
HIP_NEW = ("acetabulum.L", "acetabulum.R", "acetabular_roof.L", "acetabular_roof.R", "obturator_frame.L", "obturator_frame.R", "pubic_symphysis")
PELVIC_MASSES = ("ilium", "ischium", "pubis", "obturator_frame", "acetabulum", "acetabular_roof")


def _touches(a, b, lim):
    """True si algun vertice de `a` esta a menos de `lim` de algun vertice de `b` (rejilla de celdas `lim`: rapido)."""
    grid = {}
    for q in b.verts:
        grid.setdefault(tuple(int(c // lim) for c in q), []).append(q)
    for p in a.verts:
        c = tuple(int(x // lim) for x in p)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if any(length(sub(p, q)) < lim for q in grid.get((c[0] + dx, c[1] + dy, c[2] + dz), ())):
                        return True
    return False


def _closest(points, mesh, n=24):
    """Los `n` puntos mas cercanos a los vertices de `mesh` (por vertice: barato); sobre ellos se mide despues la distancia exacta a la superficie."""
    return sorted(points, key=lambda p: min((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2 for q in mesh.verts))[:n]


def _surface_distance(p, mesh, reach=0.006):
    """Distancia de un punto a la superficie de la malla: como `mesh_distance` (sin el caso interior) pero descartando los triangulos lejanos."""
    from anatomical_core.anatomy import point_triangle_distance

    best = float("inf")
    verts = mesh.verts
    for f in mesh.faces:
        for i in range(1, len(f) - 1):
            a, b, c = verts[f[0]], verts[f[i]], verts[f[i + 1]]
            if min(length(sub(p, a)), length(sub(p, b)), length(sub(p, c))) > best + reach:
                continue
            best = min(best, point_triangle_distance(p, a, b, c))
    return best


def hip_contract(base, model):
    """Violaciones del contrato de la articulacion coxofemoral (F2b): copa que abraza la cabeza sin tocarla, cuello libre, copa fundida con la pelvis, marco del
    agujero obturador con el agujero vacio y sinfisis que une los dos pubis."""
    from anatomical_core.volumes import point_inside

    k = base.height_m / 1.75
    m = model.meshes
    bad = []
    for side in "LR":
        C = base.bones[f"thigh.{side}"].head
        cup, fem = m[f"acetabulum.{side}"], m[f"femur.{side}"]
        cv, cf = list(cup.verts), [list(f) for f in cup.faces]
        near = [v for v in fem.verts if length(sub(v, C)) < 0.05 * k]
        if any(point_inside(v, cv, cf) for v in near):
            bad.append(f"{side}: la cabeza o el cuello del femur penetra la copa")
        head = [v for v in near if length(sub(v, C)) < 0.026 * k]
        gap = min(_surface_distance(v, cup) for v in _closest(head, cup))
        if not 0.0005 * k <= gap <= 0.0035 * k:
            bad.append(f"{side}: holgura cabeza-copa de {gap * 1000:.1f} mm (esperado 0.5-3.5 mm)")
        neck = [v for v in near if length(sub(v, C)) > 0.032 * k]
        if min(_surface_distance(v, cup) for v in _closest(neck, cup)) < 0.002 * k:
            bad.append(f"{side}: el cuello roza el borde de la copa")
        roof = m.get(f"acetabular_roof.{side}")  # sin techo, la copa queda separada de la lamina del ilion
        for other in (f"ilium.{side}", f"ischium.{side}", f"pubis.{side}"):
            if not (_touches(cup, m[other], 0.004 * k) or (roof and _touches(roof, m[other], 0.004 * k))):
                bad.append(f"{side}: la copa no esta fundida con {other}")
        if not (roof and _touches(roof, cup, 0.002 * k)):
            bad.append(f"{side}: el techo no toca la copa")
        fr = m[f"obturator_frame.{side}"]
        if fr.genus != 1:
            bad.append(f"{side}: el marco obturador no tiene el agujero")
        if not (_touches(fr, m[f"ischium.{side}"], 0.004 * k) and _touches(fr, m[f"pubis.{side}"], 0.004 * k)):
            bad.append(f"{side}: el marco obturador no esta empotrado en el hueso")
    fo = (0.0491 * k, -0.0198 * k, 0.8678 * k)
    for n, mm in m.items():
        if n.split(".")[0] in PELVIC_MASSES and n.endswith(".L") and bm.mesh_distance(fo, mm) < 0.015 * k:
            bad.append(f"el agujero obturador esta tapado o invadido por {n}")
    sy = m["pubic_symphysis"]
    if not (_touches(sy, m["pubis.L"], 0.001 * k) and _touches(sy, m["pubis.R"], 0.001 * k)):
        bad.append("la sinfisis no une los dos pubis")
    return bad


class TestHipJoint(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art, self.model = build_all()
        self.m = self.model.meshes

    def test_the_new_meshes_are_closed_and_have_their_tones_and_parent_bones(self):
        for n in HIP_NEW:
            x = self.m[n]
            self.assertEqual(euler_characteristic(list(x.verts), [list(f) for f in x.faces]), 2 - 2 * x.genus, n)
            self.assertGreater(x.volume_m3, 1e-6, n)
        self.assertEqual({n: self.m[n].tone for n in HIP_NEW}, {"acetabulum.L": "joint", "acetabulum.R": "joint", "acetabular_roof.L": "bone", "acetabular_roof.R": "bone",
                                                              "obturator_frame.L": "grey", "obturator_frame.R": "grey", "pubic_symphysis": "grey"})
        self.assertEqual(self.m["acetabulum.R"].parent_bone, "ilium.R")
        self.assertEqual(self.m["obturator_frame.L"].parent_bone, "ischium.L")
        self.assertEqual(self.m["pubic_symphysis"].parent_bone, "pubis.L")
        self.assertEqual({n: x.tone for n, x in self.m.items() if x.tone == "bone" and n.split(".")[0] in ("ilium", "ischium", "pubis", "sacrum", "coccyx")}.keys(),
                         {n for n in self.m if n.split(".")[0] in ("ilium", "ischium", "pubis", "sacrum", "coccyx")})  # la pelvis es hueso claro
        self.assertEqual({n for n, x in self.m.items() if x.tone == "joint"}, set(JOINTS))  # solo la union articular va en rojo
        self.assertEqual(self.m["femur.L"].tone, "grey")
        self.assertEqual(bm.validate_bone_meshes(self.base, self.anat, self.model), [])

    def test_the_cup_hugs_the_femoral_head_and_leaves_the_neck_free(self):
        self.assertEqual(hip_contract(self.base, self.model), [])
        C = self.base.bones["thigh.L"].head
        self.assertAlmostEqual(min(length(sub(v, C)) for v in self.m["acetabulum.L"].verts), 0.0235, places=6)  # cara articular a 23.5 mm: 1.5 mm de interlinea sobre la cabeza de 22 mm
        self.assertAlmostEqual(max(length(sub(v, C)) for v in self.m["acetabulum.L"].verts), 0.0315, places=6)

    def test_the_cup_is_fused_with_the_pelvis_and_the_ring_stays_closed(self):
        for s in "LR":
            self.assertTrue(_touches(self.m[f"acetabular_roof.{s}"], self.m[f"ilium.{s}"], 0.004))
            self.assertTrue(_touches(self.m[f"acetabulum.{s}"], self.m[f"ischium.{s}"], 0.004))
            self.assertTrue(_touches(self.m[f"acetabulum.{s}"], self.m[f"pubis.{s}"], 0.004))
        self.assertEqual(pelvis_contract(self.base, self.anat, self.art, self.model), [])

    def test_the_hip_contract_holds_at_three_heights_with_both_sides_symmetric(self):
        for h in (1.5, 1.75, 2.05):
            base, anat, art, model = build_all(h)
            self.assertEqual(hip_contract(base, model), [], h)
            self.assertEqual(bm.validate_bone_meshes(base, anat, model), [], h)
            self.assertAlmostEqual(model.meshes["acetabulum.L"].volume_m3 / self.m["acetabulum.L"].volume_m3, (h / 1.75) ** 3, places=7)
        key = lambda v: tuple(round(c, 9) for c in v)  # noqa: E731
        for n in ("acetabulum", "acetabular_roof", "obturator_frame"):
            self.assertEqual(sorted(key(mirror_point(p)) for p in self.m[f"{n}.L"].verts), sorted(key(q) for q in self.m[f"{n}.R"].verts), n)
        sy = self.m["pubic_symphysis"]
        self.assertLess(max(min(length(sub(mirror_point(p), q)) for q in sy.verts) for p in sy.verts), 1e-6)  # simetrica respecto a x = 0

    def test_the_head_neck_transition_is_gradual(self):
        fem = next(b for b in bm.load_mesh_data()["bones"] if b["name"] == "femur.L")["stations"]
        self.assertEqual(fem[1]["note"], "union cabeza-cuello")
        radii = [s["a_m"] for s in fem[:3]]
        self.assertTrue(radii[0] > radii[1] > radii[2])
        self.assertLessEqual(max(a - b for a, b in zip(radii, radii[1:])), 0.0065)  # sin escalones bruscos entre cabeza (22 mm), union (20.5) y cuello (15.5)

    def test_hip_landmarks_stay_within_12_mm_of_their_meshes_at_three_heights(self):
        names = ("anterior_inferior_iliac_spine", "inferior_gluteal_line", "ischial_spine", "obturator_margin", "iliopubic_eminence", "trochanteric_fossa", "intertrochanteric_crest",
                 "lesser_trochanter", "greater_trochanter", "pubic_body", "ischial_tuberosity", "pectineal_crest")
        for h in (1.5, 1.75, 2.05):
            base, anat, art, model = build_all(h)
            for n in names:
                for s in "LR":
                    a = art.attachments[f"{n}.{s}"]
                    self.assertLess(bm.mesh_distance(a.point, model.meshes[a.bone]), 0.012 * h / 1.75, (h, n, s))

    def test_the_regions_ligaments_and_muscle_origins_were_not_touched_by_the_joint_meshes(self):
        a = self.art.attachments
        self.assertEqual(tuple(round(c, 4) for c in a["ischial_tuberosity.L"].point), (0.0613, 0.021, 0.8225))
        self.assertEqual(tuple(round(c, 4) for c in self.art.ligaments["iliofemoral.L"].a), (0.1067, -0.0262, 0.9581))
        self.assertEqual(len(self.art.ligaments), 620)

    # ---- mutaciones
    def _built(self, edit):
        data = copy.deepcopy(bm.load_mesh_data())
        edit(data["bones"])
        return build_all(data=data)

    def test_mutation_a_cup_that_is_too_large_or_too_small_is_caught(self):
        for r_in in (0.0200, 0.0300):
            base, _, _, bad = self._built(lambda bones, r=r_in: next(b for b in bones if b["name"] == "acetabulum.L").update(r_in_m=r, r_out_m=r + 0.008))
            self.assertNotEqual(hip_contract(base, bad), [], r_in)

    def test_mutation_a_cup_turned_round_or_displaced_is_caught(self):
        base, _, _, bad = self._built(lambda bones: next(b for b in bones if b["name"] == "acetabulum.L").update(axis=[0.84, -0.20, -0.50]))
        self.assertTrue(any("penetra" in v or "holgura" in v for v in hip_contract(base, bad)))
        base, _, _, bad = self._built(lambda bones: next(b for b in bones if b["name"] == "acetabulum.L")["center"].update(offset_h=[0.0, 0.0, 0.03]))
        self.assertNotEqual(hip_contract(base, bad), [])

    def test_mutation_a_cup_that_closes_over_the_neck_or_loses_its_roof_is_caught(self):
        base, _, _, bad = self._built(lambda bones: next(b for b in bones if b["name"] == "acetabulum.L").update(theta_max_deg=165.0))
        self.assertTrue(any("cuello" in v or "penetra" in v for v in hip_contract(base, bad)))
        data = copy.deepcopy(bm.load_mesh_data())
        data["bones"] = [b for b in data["bones"] if b["name"] != "acetabular_roof.L"]  # sin techo la copa queda separada de la lamina del ilion
        base, _, _, bad = build_all(data=data)
        self.assertTrue(any("fundida" in v for v in hip_contract(base, bad)))

    def test_mutation_a_blocked_foramen_or_a_floating_frame_or_a_split_symphysis_is_caught(self):
        base, _, _, bad = self._built(lambda bones: next(b for b in bones if b["name"] == "obturator_frame.L").update(holes=[]))
        self.assertTrue(any("marco" in v or "agujero" in v for v in hip_contract(base, bad)))
        def float_frame(bones):  # el marco entero (contorno y borde del agujero) 17 cm hacia atras: queda fuera del hueso
            f = next(b for b in bones if b["name"] == "obturator_frame.L")
            for p in f["outline"] + f["holes"][0]["loop"]:
                p["offset_h"][1] += 0.1
        base, _, _, bad = self._built(float_frame)
        self.assertTrue(any("empotrado" in v or "invadido" in v for v in hip_contract(base, bad)))
        base, _, _, bad = self._built(lambda bones: [s["offset_h"].__setitem__(2, s["offset_h"][2] + 0.03) for s in next(b for b in bones if b["name"] == "pubic_symphysis")["stations"]])
        self.assertTrue(any("sinfisis" in v for v in hip_contract(base, bad)))

    def test_mutation_invalid_cup_and_tone_data_are_rejected(self):
        for edit in (lambda b: b.update(tone="rojo"), lambda b: b.update(theta_max_deg=5.0), lambda b: b.update(r_in_m=0.04, r_out_m=0.03), lambda b: b.update(bone="no_such_bone.L")):
            data = copy.deepcopy(bm.load_mesh_data())
            edit(next(b for b in data["bones"] if b["name"] == "acetabulum.L"))
            with self.assertRaises(ConfigError):
                build_all(data=data)


class TestCupPrimitive(unittest.TestCase):
    def test_a_cup_has_the_analytic_volume_and_is_a_closed_genus_zero_shell(self):
        r_in, r_out, th = 0.02, 0.03, math.radians(90)
        verts, faces = bm.cup((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), r_in, r_out, th, n_theta=24, n_phi=48)
        self.assertEqual(euler_characteristic(verts, [list(f) for f in faces]), 2)
        from anatomical_core.volumes import signed_volume
        exact = 2 * math.pi / 3 * (r_out ** 3 - r_in ** 3)  # semiesfera hueca
        self.assertAlmostEqual(signed_volume(verts, faces) / exact, 1.0, delta=0.01)

    def test_a_cup_rejects_bad_radii_and_angles(self):
        for args in ((0.03, 0.02, 1.5), (0.0, 0.02, 1.5), (0.02, 0.03, 0.05), (0.02, 0.03, 3.1)):
            with self.assertRaises(ConfigError):
                bm.cup((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), *args)


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestBoneMeshesInBlender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from anatomical_core import anatomy_pipeline, bone_meshes_scene, scene
        cls.scene, cls.bscene = scene, bone_meshes_scene
        TEST_OUT.mkdir(parents=True, exist_ok=True)
        cls.path = TEST_OUT / "bone_meshes.blend"
        cls.res = anatomy_pipeline.generate(cls.path, preview=False, log=lambda *_: None)
        cls.base, cls.anat = cls.res.base, cls.res.anatomy
        cls.model = bm.build_bone_meshes(cls.base, cls.anat, bm.load_mesh_data())

    def test_the_objects_exist_follow_their_bone_and_carry_the_style(self):
        import bpy
        self.scene.open_blend(self.path)
        for s in "LR":
            o = bpy.data.objects[f"BM_femur.{s}"]
            self.assertEqual((o.parent.name, o.parent_type, o.parent_bone), ("AC_Armature", "BONE", f"femur.{s}"))
            self.assertEqual([m.type for m in o.modifiers], ["SOLIDIFY"])  # contorno oscuro (casco invertido)
            self.assertEqual(len(o.data.materials), 2)
            fill = o.data.materials[0].diffuse_color
            self.assertTrue(all(0.8 < c < 0.9 for c in fill[:3]))  # gris claro de la imagen
            self.assertTrue(o.data.materials[1].use_backface_culling)
        self.assertEqual(bm.validate_bone_meshes_snapshot(self.model, self.bscene.read_back_bone_meshes()), [])

    def test_the_seventeen_pelvic_and_femoral_objects_follow_their_bones_with_the_declared_tones_and_shading(self):
        import bpy
        self.scene.open_blend(self.path)
        names = sorted(f"BM_{n}" for n in self.model.meshes)
        self.assertEqual(len(names), 17)
        for n in names:
            o = bpy.data.objects[n]
            self.assertEqual((o.parent.name, o.parent_bone), ("AC_Armature", self.model.meshes[n[3:]].parent_bone))
            self.assertEqual(o.get("ac_tone"), self.model.meshes[n[3:]].tone)
            self.assertEqual(tuple(round(c, 2) for c in o.data.materials[0].diffuse_color[:3]), {"grey": (0.86, 0.86, 0.85), "bone": (0.95, 0.92, 0.84), "joint": (0.8, 0.1, 0.1)}[self.model.meshes[n[3:]].tone], n)
            smooth = self.model.meshes[n[3:]].smooth
            self.assertEqual(all(p.use_smooth for p in o.data.polygons), smooth, n)  # laminas planas, lofts suaves
            self.assertEqual(len(o.data.polygons) > 0, True)
        self.assertEqual(len(bpy.data.objects["BM_sacrum"].data.vertices), len(self.model.meshes["sacrum"].verts))
        self.assertFalse(bpy.data.objects["BM_ilium.L"].hide_render)
        self.assertEqual(bm.validate_bone_meshes_snapshot(self.model, self.bscene.read_back_bone_meshes()), [])

    def test_the_femur_mesh_moves_with_the_hip(self):
        import bpy
        from anatomical_core.config import PoseDef  # noqa: F811
        self.scene.open_blend(self.path)
        arm = bpy.data.objects["AC_Armature"]
        for pb in arm.pose.bones:
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        rest = self.bscene.read_back_bone_meshes()["BM_femur.L"]["bbox"]
        posed = pose_mod.apply_pose(self.base, PoseDef("t", {"hip.L": {"flexion": 90.0}}))
        arm.pose.bones["thigh.L"].rotation_quaternion = posed.bones["thigh.L"].local_quat
        bpy.context.view_layer.update()
        o = bpy.data.objects["BM_femur.L"]
        ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
        world = [ev.matrix_world @ v.co for v in o.data.vertices]
        self.assertAlmostEqual(min(w.z for w in world), 0.93, delta=0.06)  # tras 90 grados de flexion el femur esta horizontal: su punto mas bajo (antes en los condilos, a 0.50 m) sube a ~0.93 m
        self.assertGreater(rest[1][2] - rest[0][2], 0.4)
        # el centro de la cabeza (pivote de la cadera) no se mueve
        pivot = self.base.joints["hip.L"].pivot
        head = min(world, key=lambda w: (w - __import__("mathutils").Vector(pivot)).length)
        self.assertLess((head - __import__("mathutils").Vector(pivot)).length, 0.025)  # algun vertice de la cabeza sigue junto al pivote


if __name__ == "__main__":
    unittest.main()
