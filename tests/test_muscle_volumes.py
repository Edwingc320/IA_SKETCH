"""Volumen de los vientres musculares (rama muscle-model): grandes grupos con volumen medido (miembro superior y tronco) o por convencion visual
declarada (pierna y otros), malla cerrada de volumen exacto y escala con la altura."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import bpy  # noqa: F401
    HAVE_BPY = True
except ImportError:
    HAVE_BPY = False

from anatomical_core import anatomy, articulations, muscle_volumes as mv, tendons  # noqa: E402
from anatomical_core.config import ConfigError, load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402
from anatomical_core.volumes import euler_characteristic, signed_volume  # noqa: E402

TEST_OUT = ROOT / "output" / "_test"
REQUESTED = [
    # cuadriceps, isquiotibiales, pantorrilla
    "rectus_femoris", "vastus_lateralis", "vastus_medialis", "vastus_intermedius", "biceps_femoris", "biceps_femoris_short_head", "semitendinosus", "semimembranosus",
    "gastrocnemius", "gastrocnemius_lateral", "soleus", "tibialis_anterior", "peroneus_longus", "peroneus_brevis",
    # hombro y brazo, antebrazo
    "deltoid_clavicular", "deltoid_acromial", "deltoid_spinal", "biceps_long_head", "biceps_short_head", "triceps_long_head", "triceps_lateral_head", "triceps_medial_head",
    "brachioradialis", "pronator_teres", "flexor_carpi_radialis", "flexor_carpi_ulnaris", "extensor_carpi_radialis_longus", "extensor_carpi_radialis_brevis", "extensor_carpi_ulnaris",
    # torso y cuello
    "pectoralis_major", "pectoralis_minor", "latissimus_dorsi", "trapezius_upper", "trapezius_middle", "trapezius_lower", "rectus_abdominis", "sternocleidomastoid",
]
HOLZBAUR = {  # Tabla 2 de Holzbaur et al. 2007 (cm3, media de 10 sujetos)
    "brachioradialis": 65.1, "pronator_teres": 38.4, "flexor_carpi_radialis": 34.8, "flexor_carpi_ulnaris": 37.1, "extensor_carpi_radialis_longus": 37.5,
    "extensor_carpi_radialis_brevis": 21.6, "extensor_carpi_ulnaris": 17.0, "pectoralis_major": 290.0, "latissimus_dorsi": 262.3, "brachialis": 143.7, "supraspinatus": 50.0,
    "infraspinatus": 118.6, "subscapularis": 164.5, "teres_minor": 28.0, "teres_major": 32.7, "coracobrachialis": 25.2,
}


def build_all(height=None, data=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    art = articulations.build_articulations(base, anat, articulations.load_articulation_data())
    tm = tendons.build_tendons(base, anat, art, tendons.load_tendon_data())
    return base, tm, mv.build_volumes(tm, data if data is not None else mv.load_volume_data())


class TestMuscleVolumes(unittest.TestCase):
    def setUp(self):
        self.base, self.tm, self.vm = build_all()
        self.v = self.vm.volumes

    def test_every_requested_muscle_has_a_volume_on_both_sides(self):
        for n in REQUESTED:
            for s in "LR":
                self.assertIn(f"{n}.{s}", self.v, n)
                self.assertIn(f"{n}.{s}", self.tm.tendons)  # y se apoya en una de las unidades musculo-tendinosas
        self.assertEqual(mv.validate_volumes(self.tm, self.vm), [])

    def test_measured_volumes_are_the_published_ones(self):
        for n, cm3 in HOLZBAUR.items():
            x = self.v[f"{n}.L"]
            self.assertEqual((x.kind, x.source, x.reference_height_m), ("medido", "holzbaur_2007", 1.715), n)
            self.assertAlmostEqual(x.volume_ref_cm3, cm3, places=3, msg=n)
        # los musculos con varias cabezas reparten el volumen del estudio entre ellas
        for heads, total in ((("deltoid_clavicular", "deltoid_acromial", "deltoid_spinal"), 380.5), (("biceps_long_head", "biceps_short_head"), 143.7),
                             (("triceps_long_head", "triceps_lateral_head", "triceps_medial_head"), 372.1)):
            self.assertAlmostEqual(sum(self.v[f"{h}.L"].volume_ref_cm3 for h in heads), total, places=2)
            for h in heads:
                self.assertIn("reparte", self.v[f"{h}.L"].notes)

    def test_everything_without_a_measurement_is_a_declared_convention(self):
        classes = {"pequeno": 40.0, "medio": 150.0, "grande": 350.0, "muy_grande": 700.0}
        self.assertEqual(self.vm.classes, classes)
        conv = [n for n, x in self.v.items() if x.kind == "convencion"]
        self.assertTrue(conv)
        for n in conv:
            x = self.v[n]
            self.assertEqual(x.volume_ref_cm3, classes[x.size_class])
            self.assertIn("convencion visual", x.notes.lower())
            self.assertIsNone(x.source)
        for n in ("vastus_lateralis", "soleus", "gastrocnemius", "semimembranosus", "trapezius_upper", "rectus_abdominis", "sternocleidomastoid", "pectoralis_minor"):
            self.assertEqual(self.v[f"{n}.L"].kind, "convencion", n)  # sin volumen medido consultado
        self.assertEqual(self.v["vastus_lateralis.L"].size_class, "muy_grande")
        self.assertGreater(self.v["vastus_lateralis.L"].volume_ref_cm3, self.v["peroneus_brevis.L"].volume_ref_cm3 * 10)

    def test_each_belly_mesh_is_closed_and_has_exactly_the_declared_volume(self):
        for n, x in self.v.items():
            if n.endswith(".R"):
                continue
            verts, faces = mv.mesh_for(self.tm, x)
            self.assertEqual(euler_characteristic(verts, faces), 2, n)
            target = x.volume_m3(self.base.height_m)
            self.assertAlmostEqual(signed_volume(verts, faces) / target, 1.0, places=9, msg=n)
        # a 1.75 m los volumenes medidos son los de sus sujetos (1.715 m) escalados por (1.75/1.715)^3
        self.assertAlmostEqual(self.v["pectoralis_major.L"].volume_m3(1.75) * 1e6, 290.0 * (1.75 / 1.715) ** 3, places=6)

    def test_volume_scales_with_the_cube_of_the_height_and_the_shape_linearly(self):
        _, tm2, vm2 = build_all(1.5)
        k = 1.5 / self.base.height_m
        for n in ("vastus_lateralis.L", "pectoralis_major.L", "biceps_long_head.R", "soleus.L"):
            a, b = self.v[n], vm2.volumes[n]
            va, vb = signed_volume(*mv.mesh_for(self.tm, a)), signed_volume(*mv.mesh_for(tm2, b))
            self.assertAlmostEqual(vb / va, k ** 3, places=8, msg=n)
            (pa, _), (pb, _) = mv.mesh_for(self.tm, a), mv.mesh_for(tm2, b)
            for p, q in zip(pa, pb):  # la forma escala linealmente, vertice a vertice
                self.assertLess(length(sub(tuple(k * c for c in p), q)), 1e-9, n)

    def test_symmetry(self):
        for n, a in self.v.items():
            if n.endswith(".L"):
                pa, _ = mv.mesh_for(self.tm, a)
                pb, _ = mv.mesh_for(self.tm, self.v[n[:-2] + ".R"])
                self.assertEqual(len(pa), len(pb))  # el orden de los vertices de un anillo se invierte al reflejar: se busca el vertice espejo mas cercano
                grid = {}
                for q in pb:  # rejilla de 1e-6: cada punto se busca solo en las celdas vecinas
                    grid.setdefault(tuple(int(c // 1e-6) for c in q), []).append(q)
                for p in pa:
                    m = mirror_point(p)
                    cell = tuple(int(c // 1e-6) for c in m)
                    near = [q for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1) for q in grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), ())]
                    self.assertTrue(near and min(length(sub(m, q)) for q in near) < 1e-9, n)

    def test_flat_muscles_have_a_wide_cross_section(self):
        path = ((0.0, 0.0, 1.0), (0.0, 0.0, 0.7))
        round_v, _ = mv.belly_mesh(path, 3e-4, 1.0)
        flat_v, flat_f = mv.belly_mesh(path, 3e-4, 4.0)
        self.assertAlmostEqual(signed_volume(flat_v, flat_f), 3e-4, places=12)  # el aplanamiento conserva el volumen
        mid = lambda v: v[(mv.RINGS // 2 - 1) * mv.SIDES:(mv.RINGS // 2) * mv.SIDES]  # noqa: E731
        ext = lambda ring, i: max(p[i] for p in ring) - min(p[i] for p in ring)  # noqa: E731
        self.assertAlmostEqual(ext(mid(round_v), 0), ext(mid(round_v), 1), places=9)
        self.assertAlmostEqual(ext(mid(flat_v), 0) / ext(mid(flat_v), 1), 4.0, places=6)  # ancho en X, grosor en Y (antero-posterior)
        self.assertGreater(self.v["pectoralis_major.L"].aspect, 1.0)
        self.assertGreater(self.v["latissimus_dorsi.L"].aspect, 1.0)

    def test_the_belly_is_fusiform_thin_at_both_ends_and_widest_near_the_middle(self):
        verts, _ = mv.belly_mesh(((0.0, 0.0, 1.0), (0.0, 0.0, 0.7)), 3e-4, 1.0)
        radius = lambda i: max(abs(p[0]) for p in verts[i * mv.SIDES:(i + 1) * mv.SIDES])  # noqa: E731
        widest = max(range(mv.RINGS - 1), key=radius)
        self.assertTrue(mv.RINGS // 2 - 3 <= widest <= mv.RINGS // 2 + 1, widest)  # maximo hacia el centro
        self.assertLess(radius(0), 0.5 * radius(widest))  # los extremos se afinan hacia la insercion y el origen
        self.assertLess(radius(mv.RINGS - 2), 0.5 * radius(widest))
        self.assertTrue(all(radius(i) < radius(i + 1) for i in range(widest)) and all(radius(i) > radius(i + 1) for i in range(widest, mv.RINGS - 2)))

    def test_bad_data_is_rejected(self):
        data = mv.load_volume_data()
        for edit, msg in ((lambda d: d["muscles"][0].update(kind="medido", source=None), "medido"), (lambda d: d["muscles"][-1].update(size_class="enorme"), "clase"),
                          (lambda d: d["muscles"][0].update(aspect=9.0), "aspect"), (lambda d: d["muscles"][0].update(unit="no_such_unit.L"), "unidad"),
                          (lambda d: d["muscles"].append(copy.deepcopy(d["muscles"][0])), "duplicado")):
            bad = copy.deepcopy(data)
            edit(bad)
            with self.assertRaises(ConfigError, msg=msg):
                build_all(data=bad)
        bad = copy.deepcopy(data)
        bad["muscles"][-1]["notes"] = "Vastus."  # convencion sin decirlo
        _, tm, vm = build_all(data=bad)
        self.assertIn("VOL_CONVENTION_NOTE", [i.code for i in mv.validate_volumes(tm, vm)])
        bad = copy.deepcopy(data)
        bad["sources"]["holzbaur_2007"]["url"] = "http://x"
        _, tm, vm = build_all(data=bad)
        self.assertIn("VOL_SOURCE", [i.code for i in mv.validate_volumes(tm, vm)])


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestMuscleVolumesInBlender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from anatomical_core import anatomy_pipeline, muscle_volumes_scene, scene
        cls.scene, cls.vscene = scene, muscle_volumes_scene
        TEST_OUT.mkdir(parents=True, exist_ok=True)
        cls.path = TEST_OUT / "muscle_volumes_a.blend"
        cls.res = anatomy_pipeline.generate(cls.path, preview=False, log=lambda *_: None)

    def test_file_validates_and_the_volumes_follow_their_origin_bone(self):
        import bpy
        from mathutils import Euler
        self.scene.open_blend(self.path)
        snap = self.vscene.read_back_muscle_volumes()
        base, tm, vm = build_all()
        self.assertEqual(mv.validate_volumes_snapshot(tm, vm, snap), [])
        self.assertEqual(len(snap), len(vm.volumes))
        self.assertTrue(all(o.data.polygons[0].use_smooth for o in bpy.data.objects if o.name.startswith("MUV_")))
        # al girar la cadera izquierda el vasto lateral izquierdo (nace en el trocanter) se mueve y el derecho no
        pb = bpy.data.objects["AC_Armature"].pose.bones["thigh.L"]
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = Euler((0.7, 0.0, 0.0))
        bpy.context.view_layer.update()
        after = self.vscene.read_back_muscle_volumes()
        centre = lambda s, n: [(a + b) / 2 for a, b in zip(*s[n]["bbox"])]  # noqa: E731
        move = lambda n: length(sub(tuple(centre(after, n)), tuple(centre(snap, n))))  # noqa: E731
        self.assertGreater(move("MUV_vastus_lateralis.L"), 0.02)  # el centro del vasto se desplaza varios centimetros
        self.assertLess(move("MUV_vastus_lateralis.R"), 1e-4)


if __name__ == "__main__":
    unittest.main()
