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
        data["bones"][0]["stations"][2]["offset_h"] = [0.0, 0.0, -0.2]  # el trocanter, 35 cm mas abajo
        _, anat, art, bad = build_all(data=data)
        d = bm.mesh_distance(art.attachments["greater_trochanter.L"].point, bad.meshes["femur.L"])
        self.assertGreater(d, 0.012)

    def test_mutation_a_thin_station_is_detected_as_a_bad_shaft(self):
        data = copy.deepcopy(bm.load_mesh_data())
        data["bones"][0]["stations"][4]["a_m"] = 0.004
        data["bones"][0]["stations"][4]["b_m"] = 0.004
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
        good = {f"BM_{n}": {"parent_bone": n, "n_verts": len(m.verts), "bbox": [tuple(min(v[i] for v in m.verts) for i in range(3)), tuple(max(v[i] for v in m.verts) for i in range(3))]}
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
        self.assertEqual(sorted(self.model.meshes), sorted(["femur.L", "femur.R", "ilium.L", "ilium.R", "ischium.L", "ischium.R", "pubis.L", "pubis.R", "sacrum", "coccyx"]))
        for n, m in self.model.meshes.items():
            self.assertEqual(euler_characteristic(list(m.verts), [list(f) for f in m.faces]), 2 - 2 * m.genus, n)
            self.assertGreater(m.volume_m3, 1e-6, n)
        self.assertEqual(self.model.meshes["sacrum"].genus, 8)  # cuatro pares de agujeros sacros, como en la imagen
        self.assertTrue(all(self.model.meshes[n].genus == 0 for n in self.model.meshes if n != "sacrum"))
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

    def test_the_ten_pelvic_and_femoral_objects_follow_their_bones_with_the_declared_shading(self):
        import bpy
        self.scene.open_blend(self.path)
        names = sorted(f"BM_{n}" for n in self.model.meshes)
        self.assertEqual(len(names), 10)
        for n in names:
            o = bpy.data.objects[n]
            self.assertEqual((o.parent.name, o.parent_bone), ("AC_Armature", n[3:]))
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
