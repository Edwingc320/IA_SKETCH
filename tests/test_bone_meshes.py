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
        self.assertEqual(sorted(self.model.meshes), ["femur.L", "femur.R"])
        for m in self.model.meshes.values():
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
