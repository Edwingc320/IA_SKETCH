"""Esqueleto parametrico `cp.*` (pelvis, femures y columna lumbar): objetos independientes, origenes articulares, transformaciones aplicadas, emparentamiento Keep
Transform y redimensionado uniforme. Requiere Blender: `blender -b --python-expr "..."` (ver scripts/run.ps1) o el ejecutor de pruebas del proyecto."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import bpy
    from mathutils import Vector

    HAVE_BPY = True
except ImportError:  # pragma: no cover
    HAVE_BPY = False

if HAVE_BPY:
    from anatomical_core import cp_axial as ax
    from anatomical_core import cp_skeleton as cp


def mirror_error(o):
    """Distancia maxima (m) de un vertice espejado en x a la SUPERFICIE de la propia malla (robusto a que el Boolean triangule distinto cada lado)."""
    from mathutils.bvhtree import BVHTree

    tree = BVHTree.FromObject(o, bpy.context.evaluated_depsgraph_get())
    return max(tree.find_nearest(Vector((-v.co.x, v.co.y, v.co.z)))[3] for v in o.data.vertices)


def islands(o) -> int:
    """Numero de componentes conexas de la malla de un objeto (1 = una sola pieza cerrada, sin cascarones sueltos)."""
    import bmesh

    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    parent = list(range(len(bm.verts)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e in bm.edges:
        a, b = find(e.verts[0].index), find(e.verts[1].index)
        if a != b:
            parent[a] = b
    n = len({find(i) for i in range(len(bm.verts))})
    bm.free()
    return n


SKULL_PREFIXES = ("cp.Skull", "cp.Zygomatic", "cp.Temporal", "cp.Mastoid", "cp.Condyle", "cp.TeethUpper", "cp.Parietal", "cp.Sphenoid", "cp.Maxilla", "cp.Nasal", "cp.Lacrimal", "cp.Ethmoid")  # piezas independientes del craneo (la boveda es cp.Skull)


def skull_names(parts):
    return sorted(n for n in parts if n.startswith(SKULL_PREFIXES))


class SkullGroup:
    """El conjunto de piezas INDEPENDIENTES del craneo visto como un grupo para medirlo (comparten origen y orientacion): ray_cast y vertices del grupo, sin unirlas."""

    def __init__(self, parts, names=None):
        self.objs = [parts[n] for n in (names or skull_names(parts))]

    @property
    def matrix_world(self):
        return self.objs[0].matrix_world

    @property
    def data(self):
        return self

    @property
    def vertices(self):
        return [v for o in self.objs for v in o.data.vertices]

    def ray_cast(self, origin, direction):
        best, bd = (False, None, None, None), 1e18
        for o in self.objs:
            ok, loc, nor, idx = o.ray_cast(origin, direction)
            if ok and (loc - origin).length < bd:
                best, bd = (ok, loc, nor, idx), (loc - origin).length
        return best


def pair_mirror_error(parts, name):
    """Error de simetria de una pieza: si es de un lado (sufijo L/R), la distancia de sus vertices espejados a la SUPERFICIE de su pareja; si es central, a su propia superficie."""
    from mathutils.bvhtree import BVHTree

    if name[-1] not in "LR" or not name[:-1].endswith(("Zygomatic", "Temporal", "Condyle", "Parietal", "Sphenoid", "Maxilla", "Nasal", "Lacrimal", "Ethmoid")):
        return mirror_error(parts[name])
    other = parts[name[:-1] + ("R" if name[-1] == "L" else "L")]
    tree = BVHTree.FromObject(other, bpy.context.evaluated_depsgraph_get())
    return max(tree.find_nearest(Vector((-v.co.x, v.co.y, v.co.z)))[3] for v in parts[name].data.vertices)


def disc_centred(o, half, tol=0.006):
    """El primer disco (lente en torno al origen) esta centrado: el centroide de los vertices de su franja de altura (|z| < 1.2 half) cae a < `tol` del origen."""
    band = [v.co for v in o.data.vertices if abs(v.co.z) < 1.2 * half and abs(v.co.y) < 0.0105 * 1.75 and abs(v.co.x) < 0.0105 * 1.75]  # sin el arco ni la espinosa, que cruzan la franja por detras
    return len(band) > 80 and (sum(band, Vector()) / len(band)).length < tol


def extents(o):
    xs = [v.co for v in o.data.vertices]
    return tuple(max(c[i] for c in xs) - min(c[i] for c in xs) for i in range(3))


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestCpSkeleton(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.parts = cp.build_cp_skeleton(1.75)

    def test_four_independent_objects_with_the_cp_index_names(self):
        self.assertEqual(sorted(self.parts), sorted(set(cp.PARENTS) | {"cp.Pelvis"}))
        self.assertEqual(sorted(o.name for o in bpy.data.objects), sorted(self.parts))
        for o in self.parts.values():
            self.assertEqual(o.type, "MESH")
            self.assertGreater(len(o.data.vertices), 500)

    def test_origins_sit_on_the_articular_centres(self):
        h = 1.75
        w = {n: o.matrix_world.translation for n, o in self.parts.items()}
        self.assertLess((w["cp.FemurL"] - Vector((cp.HIP_X * h, 0, cp.HIP_Z * h))).length, 1e-6)  # centro de la cabeza femoral
        self.assertLess((w["cp.FemurR"] - Vector((-cp.HIP_X * h, 0, cp.HIP_Z * h))).length, 1e-6)
        self.assertLess((w["cp.Pelvis"] - Vector((0, 0, cp.HIP_Z * h))).length, 1e-6)  # punto medio de los centros acetabulares
        self.assertLess((w["cp.LumbarSpine"] - Vector((0, cp.LUMBAR_Y0 * h, cp.LUMBAR_Z0 * h))).length, 1e-6)  # centro del disco L5-S1
        for s in "LR":  # el origen del femur es el centro de la cabeza: la superficie mas cercana es la esfera de la cabeza
            o = self.parts[f"cp.Femur{s}"]
            on_head = [v for v in o.data.vertices if abs(v.co.length - cp.HEAD_R * h) < 1e-5]
            self.assertGreaterEqual(len(on_head), 300)  # la esfera de la cabeza (24 x 13 vertices + polos) esta centrada en el origen

    def test_the_lumbar_mesh_is_centred_on_the_l5_s1_disc_and_rises_from_the_sacrum(self):
        o = self.parts["cp.LumbarSpine"]
        h = 1.75
        zs = [v.co.z for v in o.data.vertices]
        half = cp.DISC_H / 2 * h  # el disco L5-S1 (lente) esta centrado en el origen: los vertices de su franja de altura tienen el centroide en el origen
        self.assertTrue(disc_centred(o, half), "el disco L5-S1 no esta centrado en el origen")
        self.assertAlmostEqual(min(zs), -cp.DISC_H / 2 * h, delta=0.012)  # la columna crece hacia arriba desde ese disco (la lordosis inclina el disco inferior ~17 grados)
        self.assertAlmostEqual(max(zs), (5 * (cp.BODY_H + cp.DISC_H) - cp.DISC_H / 2) * h, delta=0.012 * h)  # altura de L5-L1 con sus discos
        pelvis = self.parts["cp.Pelvis"]
        sacrum_top = max(pelvis.matrix_world @ v.co for v in pelvis.data.vertices if abs(v.co.x) < 0.02 and v.co.y > 0.02).z
        self.assertLess(abs(o.matrix_world.translation.z - sacrum_top), 0.02)  # nace del borde superior del sacro

    def test_transforms_are_applied_and_vertex_groups_are_clean(self):
        for n, o in self.parts.items():
            self.assertEqual(tuple(o.scale), (1.0, 1.0, 1.0), n)
            self.assertEqual(tuple(o.rotation_euler), (0.0, 0.0, 0.0), n)
            self.assertEqual(len(o.vertex_groups), 0, n)
        self.assertEqual(cp.validate(self.parts), [])  # mallas cerradas (manifold), volumen positivo

    def test_femurs_and_spine_are_children_of_the_pelvis_keeping_their_transform(self):
        bpy.context.view_layer.update()
        pelvis = self.parts["cp.Pelvis"]
        for n in ("cp.FemurL", "cp.FemurR", "cp.LumbarSpine"):
            o = self.parts[n]
            self.assertIs(o.parent, pelvis, n)
        self.assertIsNone(pelvis.parent)
        before = {n: o.matrix_world.translation.copy() for n, o in self.parts.items()}
        cp.unparent_keep_transform(self.parts)
        bpy.context.view_layer.update()
        for n, o in self.parts.items():
            self.assertIsNone(o.parent)
            self.assertLess((o.matrix_world.translation - before[n]).length, 1e-6, n)

    def test_the_femurs_are_mirror_images(self):
        from mathutils import kdtree

        r = self.parts["cp.FemurR"].data.vertices
        tree = kdtree.KDTree(len(r))
        for i, v in enumerate(r):
            tree.insert(v.co, i)
        tree.balance()
        l = self.parts["cp.FemurL"].data.vertices
        self.assertEqual(len(l), len(r))
        self.assertLess(max(tree.find(Vector((-v.co.x, v.co.y, v.co.z)))[2] for v in l), 1e-5)  # float32: cada vertice izquierdo espejado coincide con uno derecho

    def test_the_whole_skeleton_scales_with_the_height_keeping_proportions(self):
        ref = {n: (extents(o), o.matrix_world.translation.copy()) for n, o in self.parts.items()}  # (cada reconstruccion borra las piezas anteriores)
        for h in (1.5, 2.05):
            parts = cp.build_cp_skeleton(h)
            k = h / 1.75
            for n, o in parts.items():
                for a, b in zip(extents(o), ref[n][0]):
                    self.assertAlmostEqual(a / b, k, places=4, msg=(h, n))
                self.assertLess((o.matrix_world.translation - ref[n][1] * k).length, 1e-6, (h, n))
            self.assertAlmostEqual(parts["cp.FemurL"]["cp_ref_dim_m"], cp.THIGH_LENGTH * h, places=9)
            self.assertEqual(cp.validate(parts), [])

    def test_a_part_resizes_uniformly_keeping_structure_and_proportion(self):
        o = self.parts["cp.FemurL"]
        ref, loc = extents(o), o.matrix_world.translation.copy()
        f = cp.cp_resize(o, 0.40)
        self.assertAlmostEqual(f, 0.40 / (cp.THIGH_LENGTH * 1.75), places=9)
        self.assertAlmostEqual(o["cp_ref_dim_m"], 0.40, places=9)
        for a, b in zip(extents(o), ref):
            self.assertAlmostEqual(a / b, f, places=6)  # mismo factor en las tres direcciones: la proporcion no cambia
        self.assertLess((o.matrix_world.translation - loc).length, 1e-6)  # el origen articular no se mueve
        self.assertAlmostEqual(extents(self.parts["cp.FemurR"])[2], ref[2], places=9)  # el otro femur no se toca
        self.assertEqual(cp.validate(self.parts), [])

    def test_resizing_the_pelvis_moves_the_joint_anchors_of_its_children(self):
        pelvis = self.parts["cp.Pelvis"]
        femur_mesh, width = extents(self.parts["cp.FemurL"]), extents(pelvis)[0]
        x0 = self.parts["cp.FemurL"].matrix_world.translation.x
        cp.cp_resize(pelvis, pelvis["cp_ref_dim_m"] * 1.2)
        bpy.context.view_layer.update()
        self.assertAlmostEqual(self.parts["cp.FemurL"].matrix_world.translation.x, x0 * 1.2, places=6)  # la cadera sigue al acetabulo
        self.assertEqual(extents(self.parts["cp.FemurL"]), femur_mesh)  # la malla del femur no cambia
        self.assertAlmostEqual(extents(pelvis)[0] / width, 1.2, places=5)

    def test_dims_given_at_build_time_and_the_femur_alias(self):
        parts = cp.build_cp_skeleton(1.75, {"cp.Femur": 0.40, "cp.LumbarSpine": 0.16})
        self.assertAlmostEqual(parts["cp.FemurL"]["cp_ref_dim_m"], 0.40, places=9)
        self.assertAlmostEqual(parts["cp.FemurR"]["cp_ref_dim_m"], 0.40, places=9)
        self.assertAlmostEqual(parts["cp.LumbarSpine"]["cp_ref_dim_m"], 0.16, places=9)
        self.assertEqual(cp.validate(parts), [])

    # ---- mutaciones: las comprobaciones detectan los errores que vigilan
    def test_mutation_validate_catches_open_meshes_vertex_groups_and_unapplied_transforms(self):
        o = self.parts["cp.FemurL"]
        o.vertex_groups.new(name="residual")
        o.scale = (2.0, 1.0, 1.0)
        issues = cp.validate(self.parts)
        self.assertTrue(any("vertex groups" in i for i in issues))
        self.assertTrue(any("sin aplicar" in i for i in issues))
        o.vertex_groups.clear()
        o.scale = (1.0, 1.0, 1.0)
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[0]], context="FACES_ONLY")  # un agujero en la malla
        bm.to_mesh(o.data)
        bm.free()
        self.assertTrue(any("no manifold" in i for i in cp.validate(self.parts)))

    def test_mutation_bad_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            cp.build_cp_skeleton(0.1)
        with self.assertRaises(ValueError):
            cp.build_cp_skeleton(1.75, {"cp.Sternum": 0.2})
        with self.assertRaises(ValueError):
            cp.cp_resize(self.parts["cp.Pelvis"], -1.0)


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestCpAxial(unittest.TestCase):
    """Columna toracica y cervical, craneo y mandibula, conectados a la pelvis por la cadena de emparentamiento."""

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.parts = cp.build_cp_skeleton(1.75)
        bpy.context.view_layer.update()
        self.h = 1.75

    def world_z(self, name):
        return self.parts[name].matrix_world.translation.z

    def test_the_eight_parts_exist_and_form_one_chain_down_to_the_pelvis(self):
        self.assertEqual(sorted(self.parts), sorted(set(cp.PARENTS) | {"cp.Pelvis"}))
        for n, par in cp.PARENTS.items():
            self.assertIs(self.parts[n].parent, self.parts[par], n)
        for n, o in self.parts.items():
            while o.parent:
                o = o.parent
            self.assertEqual(o.name, "cp.Pelvis", n)  # toda pieza llega a la pelvis
        self.assertEqual(cp.validate(self.parts), [])

    def test_every_part_has_the_same_bone_tone(self):
        mats = {o.data.materials[0].name for o in self.parts.values()}
        self.assertEqual(mats, {"cp_bone"})
        self.assertEqual(tuple(round(c, 2) for c in bpy.data.materials["cp_bone"].diffuse_color[:3]), (0.95, 0.92, 0.84))

    def test_each_segment_starts_where_the_previous_one_ends(self):
        h = self.h
        lum_top = self.world_z("cp.LumbarSpine") + ax.LUMBAR_TOTAL * h
        self.assertAlmostEqual(self.world_z("cp.ThoracicSpine"), lum_top + ax.THOR_DISC_H / 2 * h, places=5)
        thor_top = self.world_z("cp.ThoracicSpine") + ax.thoracic_total() * h
        self.assertAlmostEqual(self.world_z("cp.CervicalSpine"), thor_top + ax.CERV_DISC_H / 2 * h, places=5)
        cerv_top = self.world_z("cp.CervicalSpine") + ax.cervical_total() * h
        self.assertAlmostEqual(self.world_z("cp.Skull"), cerv_top + 0.0010 * h, places=5)

    def test_origins_are_the_articular_centres(self):
        h = self.h
        for name, half in (("cp.ThoracicSpine", ax.THOR_DISC_H / 2 * h), ("cp.CervicalSpine", ax.CERV_DISC_H / 2 * h)):  # centro del disco T12/L1 y C7/T1
            self.assertTrue(disc_centred(self.parts[name], half), name)
        xs = [v.co.x for v in self.parts["cp.Skull"].data.vertices]
        self.assertAlmostEqual(max(xs) + min(xs), 0.0, delta=1e-5)  # el craneo es simetrico respecto al plano sagital del origen
        for n in (*skull_names(self.parts), "cp.Mandible", "cp.TeethLower"):  # cada pieza (o su pareja izquierda/derecha) es el espejo de si misma
            self.assertLess(pair_mirror_error(self.parts, n), 1.5e-3, n)  # 1.5 mm: el Boolean y los anillos de los tubos no triangulan igual a cada lado
        tmj = self.parts["cp.Skull"].matrix_world.translation + Vector((0.0, ax.TMJ[1], ax.TMJ[2])) * h
        self.assertLess((self.parts["cp.Mandible"].matrix_world.translation - tmj).length, 1e-5)

    def test_the_anthropometric_lengths_govern_the_axial_skeleton(self):
        h = self.h
        sk = self.parts["cp.Skull"]
        vertex = max((sk.matrix_world @ v.co).z for v in sk.data.vertices)
        menton = min((self.parts["cp.Mandible"].matrix_world @ v.co).z for v in self.parts["cp.Mandible"].data.vertices)
        self.assertAlmostEqual(vertex / h, 1.0, delta=0.006)  # vertice a 1.00 H
        self.assertAlmostEqual(menton / h, 0.870, delta=0.008)  # menton a 0.87 H (Winter)
        self.assertAlmostEqual(self.parts["cp.ThoracicSpine"]["cp_ref_dim_m"] / h, 0.18, delta=0.012)  # 12 vertebras toracicas con discos (~0.30 m)
        self.assertAlmostEqual(self.parts["cp.CervicalSpine"]["cp_ref_dim_m"] / h, 0.088, delta=0.012)
        self.assertGreater((sk.matrix_world.translation.z + ax.SKULL_BASE_TO_VERTEX * h) / h, 0.99)

    def test_the_spine_keeps_its_sagittal_curves(self):
        h = self.h

        def front_y(name, frac):  # y mas anterior (el cuerpo vertebral) en una franja a la fraccion `frac` de la altura de la pieza
            vs = self.parts[name].data.vertices
            z0, z1 = min(v.co.z for v in vs), max(v.co.z for v in vs)
            zc = z0 + (z1 - z0) * frac
            band = [v.co.y for v in vs if abs(v.co.z - zc) < 0.012 * h]
            return min(band)

        thor = [front_y("cp.ThoracicSpine", f) for f in (0.1, 0.5, 0.9)]
        self.assertGreater(thor[1] - 0.5 * (thor[0] + thor[2]), 0.5 * ax.KYPHOSIS * h)  # cifosis: el centro del torax esta mas atras que sus extremos
        cerv = [front_y("cp.CervicalSpine", f) for f in (0.1, 0.5, 0.9)]
        self.assertLess(cerv[1] - 0.5 * (cerv[0] + cerv[2]), -0.0008 * h)  # lordosis: el centro del cuello esta mas adelante (la forma de C1-C2 enmascara parte de la flecha)

    def test_the_vertebral_levels_are_recorded(self):
        self.assertEqual(self.parts["cp.ThoracicSpine"]["cp_levels"], " ".join(ax.THORACIC_LEVELS))
        self.assertEqual(self.parts["cp.CervicalSpine"]["cp_levels"], " ".join(ax.CERVICAL_LEVELS))
        self.assertEqual(len(ax.THORACIC_LEVELS), 12)
        self.assertEqual(len(ax.CERVICAL_LEVELS), 7)

    def test_skull_and_mandible_have_head_proportions(self):
        h = self.h
        sk, md = SkullGroup(self.parts), self.parts["cp.Mandible"]
        ex = lambda o, i: max(v.co[i] for v in o.data.vertices) - min(v.co[i] for v in o.data.vertices)  # noqa: E731
        self.assertTrue(0.075 * h < ex(sk, 0) < 0.100 * h, "anchura del craneo (~14.5 cm)")
        self.assertTrue(0.105 * h < ex(sk, 1) < 0.135 * h, "longitud antero-posterior: ~19 cm el neurocraneo (0.109 H) mas la arcada dental que sobresale")
        self.assertTrue(0.100 * h < ex(sk, 2) < 0.140 * h, "altura del craneo (~21 cm con la cara)")
        self.assertTrue(0.060 * h < ex(md, 0) < 0.090 * h, "anchura bicondilea de la mandibula")

    def test_resizing_a_segment_carries_the_whole_chain_above_it(self):
        z = {n: self.world_z(n) for n in ("cp.LumbarSpine", "cp.ThoracicSpine", "cp.Skull")}
        cp.cp_resize(self.parts["cp.LumbarSpine"], self.parts["cp.LumbarSpine"]["cp_ref_dim_m"] * 1.2)
        bpy.context.view_layer.update()
        self.assertAlmostEqual(self.world_z("cp.ThoracicSpine") - z["cp.LumbarSpine"], 1.2 * (z["cp.ThoracicSpine"] - z["cp.LumbarSpine"]), places=5)
        self.assertAlmostEqual(self.world_z("cp.Skull") - self.world_z("cp.ThoracicSpine"), z["cp.Skull"] - z["cp.ThoracicSpine"], places=5)  # el resto de la cadena viaja rigido
        self.assertEqual(cp.validate(self.parts), [])

    def test_the_axial_skeleton_scales_with_the_height(self):
        ref = {n: ([max(v.co[i] for v in o.data.vertices) - min(v.co[i] for v in o.data.vertices) for i in range(3)], o.matrix_world.translation.copy()) for n, o in self.parts.items()}
        parts = cp.build_cp_skeleton(2.05)
        bpy.context.view_layer.update()
        k = 2.05 / 1.75
        for n in ("cp.ThoracicSpine", "cp.CervicalSpine", "cp.Skull", "cp.Mandible"):
            o = parts[n]
            for i in range(3):
                self.assertAlmostEqual((max(v.co[i] for v in o.data.vertices) - min(v.co[i] for v in o.data.vertices)) / ref[n][0][i], k, places=4, msg=n)
            self.assertLess((o.matrix_world.translation - ref[n][1] * k).length, 1e-5, n)
        self.assertEqual(cp.validate(parts), [])

    # ---- mutaciones
    def test_mutation_a_part_cut_off_from_the_chain_is_reported(self):
        sk = self.parts["cp.Skull"]
        mw = sk.matrix_world.copy()
        sk.parent = None
        sk.matrix_world = mw
        self.assertTrue(any("no esta conectada" in i for i in cp.validate(self.parts)))

    def test_mutation_the_axial_dims_are_resizable_through_the_cli_names(self):
        parts = cp.build_cp_skeleton(1.75, {"cp.Skull": 0.20, "cp.Mandible": 0.12, "cp.ThoracicSpine": 0.30})
        self.assertAlmostEqual(parts["cp.Skull"]["cp_ref_dim_m"], 0.20, places=9)
        self.assertAlmostEqual(parts["cp.Mandible"]["cp_ref_dim_m"], 0.12, places=9)
        self.assertAlmostEqual(parts["cp.ThoracicSpine"]["cp_ref_dim_m"], 0.30, places=9)
        self.assertEqual(cp.validate(parts), [])


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestCpRefined(unittest.TestCase):
    """Pelvis y craneo de alta densidad: ala iliaca real (no plato), copa acetabular, craneo con cavidades reales y mandibula con angulo, todo anclado a los hitos."""

    PART = {"ilium": "cp.Pelvis", "ischium": "cp.Pelvis", "pubis": "cp.Pelvis", "sacrum": "cp.Pelvis", "coccyx": "cp.Pelvis", "cranium": "SKULL", "mandible": "cp.Mandible"}
    NOT_BONE = ("body_center_of_mass", "head_center_of_gravity")  # centros de masa y de gravedad: no son puntos de hueso

    @classmethod
    def setUpClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        cls.h = 1.75
        cls.parts = cp.build_cp_skeleton(cls.h)
        bpy.context.view_layer.update()

    def landmark_distances(self, h, parts):
        """{hito: mm} a la superficie de su malla cp (0 dentro del solido): hitos del nivel 1 de pelvis, femur, craneo y mandibula."""
        from mathutils.bvhtree import BVHTree
        from support import build_reference

        art = build_reference(h)[2]
        dg = bpy.context.evaluated_depsgraph_get()
        trees = {}
        out = {}
        for n, a in art.attachments.items():
            b = a.bone.split(".")[0]
            if n in self.NOT_BONE:
                continue
            name = "cp.Femur" + a.bone[-1] if b == "femur" else self.PART.get(b)
            if name is None:
                continue
            best = float("inf")
            for part in (skull_names(parts) if name == "SKULL" else [name]):  # el craneo son varias piezas independientes: vale la mas cercana
                o = parts[part]
                if part not in trees:
                    trees[part] = BVHTree.FromObject(o, dg)
                q = o.matrix_world.inverted() @ Vector(a.point)
                loc, nor, _, d = trees[part].find_nearest(q)
                best = min(best, 0.0 if (q - loc).dot(nor) < 0 else d * 1000.0)
            out[n] = best
        return out

    def test_the_meshes_are_high_density(self):
        counts = {n: len(o.data.polygons) for n, o in self.parts.items()}
        self.assertGreater(counts["cp.Pelvis"], 60000)  # alas iliacas, copas y anillo isquiopubiano
        self.assertGreater(sum(counts[n] for n in ("cp.SkullFrontal", "cp.SkullOccipital", "cp.ParietalL", "cp.ParietalR", "cp.TemporalL", "cp.TemporalR", "cp.SphenoidL", "cp.SphenoidR")), 100000)  # boveda en 5 huesos: jaula de 36 x 36 por lado + Subdivision Surface nivel 2
        self.assertGreater(counts["cp.MaxillaL"] + counts["cp.MaxillaR"], 60000)  # cara: jaula de 28 x 28 por lado + Subdivision Surface nivel 2 (maxilares)
        self.assertGreater(counts["cp.Mandible"], 2000)  # barrido en U de 21 secciones + Subdivision Surface nivel 2
        self.assertGreater(sum(counts.values()), 250000)
        for n, floor in (('cp.LumbarSpine', 5000), ('cp.ThoracicSpine', 10000), ('cp.CervicalSpine', 5000)):
            self.assertGreater(counts[n], floor, n)  # cada vertebra es una jaula (cuerpo, arco, apofisis) subdividida: no un cilindro
        for n in ("cp.Pelvis", *skull_names(self.parts), "cp.Mandible"):
            self.assertTrue(all(p.use_smooth for p in self.parts[n].data.polygons), n)  # sombreado suave
        self.assertEqual(cp.validate(self.parts), [])  # superficies cerradas (manifold) y con volumen positivo

    def test_every_pelvis_femur_skull_and_mandible_landmark_is_within_12_mm_at_three_heights(self):
        try:
            for h in (1.5, 1.75, 2.05):
                parts = cp.build_cp_skeleton(h)
                bpy.context.view_layer.update()
                d = self.landmark_distances(h, parts)
                self.assertGreaterEqual(len(d), 69, h)
                bad = {n: round(v, 1) for n, v in d.items() if v >= 12.0 * h / 1.75}
                self.assertEqual(bad, {}, h)
        finally:  # deja la escena como la encontro la clase (las demas pruebas usan self.parts), pase o falle
            cp.build_cp_skeleton(1.75)
            bpy.context.view_layer.update()
            type(self).parts = {o.name: o for o in bpy.data.objects if o.name.startswith("cp.")}

    def test_the_iliac_wing_is_a_curved_solid_sheet_not_a_flat_plate(self):
        from anatomical_core import cp_refine

        v, f = cp_refine.wing("L")
        spec = cp_refine.load_refine()["iliac_wing"]
        c0 = tuple(sum(p[i] for p in spec["outline"]) / len(spec["outline"]) for i in range(3))
        n = cp_refine._newell([tuple(p) for p in spec["outline"]])
        n = n if n[0] > 0 else tuple(-x for x in n)
        off = [sum((p[i] - c0[i]) * n[i] for i in range(3)) for p in v]  # desplazamiento lateral respecto al plano medio del ilion
        e2 = cp_refine._cross(n, cp_refine._norm(cp_refine._cross(n, (0, 0, 1))))
        e2 = e2 if e2[2] > 0 else tuple(-x for x in e2)
        height = [sum((p[i] - c0[i]) * e2[i] for i in range(3)) for p in v]
        top = [o for o, hh in zip(off, height) if hh > 0.8 * max(height)]
        mid = [o for o, hh in zip(off, height) if abs(hh) < 0.15 * max(height)]
        self.assertGreater(sum(top) / len(top) - sum(mid) / len(mid), 0.002)  # cresta acampanada: el borde superior se abre hacia lateral respecto al centro
        low = [o for o, hh in zip(off, height) if hh < 0.6 * min(height)]
        self.assertLess(sum(low) / len(low) - sum(mid) / len(mid), -0.0005)  # fosa iliaca concava: el borde inferior se cierra hacia medial
        thickness = max(off) - min(off)
        self.assertGreater(thickness, 0.012)  # no es una lamina plana: se curva ~1.2-1.8 cm
        wing = self.parts["cp.Pelvis"]
        zs = [(wing.matrix_world @ p.co).z / self.h for p in wing.data.vertices]
        self.assertGreater(max(zs), 0.60)  # la cresta llega a ~0.60 H, como el hito iliac_crest

    def test_the_iliac_wing_connects_with_the_sacrum_and_the_acetabulum(self):
        from mathutils.kdtree import KDTree

        o = self.parts["cp.Pelvis"]
        mw = o.matrix_world
        vs = [mw @ v.co for v in o.data.vertices]
        h = self.h
        sacral = [p for p in vs if abs(p.x) < 0.02 * h and 0.50 * h < p.z < 0.57 * h and p.y > 0.02 * h]  # sacro
        self.assertGreater(len(sacral), 500)
        wing_edge = [p for p in vs if 0.02 * h < p.x < 0.04 * h and 0.55 * h < p.z < 0.60 * h and p.y > 0.015 * h]  # borde sacro del ala
        self.assertGreater(len(wing_edge), 200)
        tree = KDTree(len(sacral))
        for i, p in enumerate(sacral):
            tree.insert(p, i)
        tree.balance()
        self.assertLess(min(tree.find(p)[2] for p in wing_edge), 0.003)  # el ala toca el sacro (< 3 mm)
        cup_centre = Vector((cp.HIP_X * h, 0.0, cp.HIP_Z * h))
        cup = [p for p in vs if 0.0136 * h * 0.98 < (p - cup_centre).length < 0.0215 * h * 1.02 and p.x > 0.03 * h]
        self.assertGreater(len(cup), 5000)  # copa acetabular: casquete grueso entre 13.6 y 21.5 mm de H alrededor del centro del acetabulo

    def test_the_cup_hugs_the_femoral_head_and_leaves_the_neck_free(self):
        from mathutils.bvhtree import BVHTree

        h = self.h
        c = Vector((cp.HIP_X * h, 0.0, cp.HIP_Z * h))
        pelvis, femur = self.parts["cp.Pelvis"], self.parts["cp.FemurL"]
        spec = __import__("anatomical_core.cp_refine", fromlist=["x"]).load_refine()["acetabular_cup"]
        r_in = spec["r_in"] * h
        inner = [v for v in pelvis.data.vertices if abs((pelvis.matrix_world @ v.co - c).length - r_in) < 2e-5]
        self.assertGreater(len(inner), 4000)  # cara articular: casquete esferico de 96 x 48 vertices a r_in del centro del acetabulo
        head = max((femur.matrix_world @ v.co - c).length for v in femur.data.vertices if (femur.matrix_world @ v.co - c).length < r_in)  # radio de la cabeza
        self.assertTrue(0.0005 * h < r_in - head < 0.004 * h, "holgura de interlinea entre la cabeza femoral y la copa (0.5-4 mm de H)")
        tree = BVHTree.FromObject(pelvis, bpy.context.evaluated_depsgraph_get())
        inv = pelvis.matrix_world.inverted()
        outside = [femur.matrix_world @ v.co for v in femur.data.vertices if 0.0145 * h < (femur.matrix_world @ v.co - c).length < 0.060 * h and (femur.matrix_world @ v.co - c).x > 0.004 * h]  # cuello y trocanter mayor (lado lateral); el trocanter menor roza el isquion en el modelo de nivel 1 (limite declarado)
        self.assertGreater(len(outside), 200)
        for p in outside:  # cuello y trocanteres quedan fuera del solido pelvico: la copa no se cierra sobre el cuello
            q = inv @ p
            loc, nor, _, _ = tree.find_nearest(q)
            self.assertGreater((q - loc).dot(nor), 0.0)

    def test_the_pelvis_skull_and_mandible_are_mirror_symmetric(self):
        for n in ("cp.Pelvis", *skull_names(self.parts), "cp.Mandible"):
            self.assertLess(pair_mirror_error(self.parts, n), 1.5e-3, n)  # 1.5 mm: el Boolean y los anillos de los tubos no triangulan igual a cada lado

    def test_the_obturator_foramen_and_the_symphysis_are_preserved(self):
        from mathutils.bvhtree import BVHTree

        h = self.h
        o = self.parts["cp.Pelvis"]
        tree = BVHTree.FromObject(o, bpy.context.evaluated_depsgraph_get())
        foramen = o.matrix_world.inverted() @ Vector((0.0281 * h, -0.0113 * h, 0.4959 * h))  # centro del agujero obturador
        loc, nor, _, d = tree.find_nearest(foramen)
        self.assertGreater(d, 0.004)  # a >= 4 mm de cualquier malla de la pelvis (a 1.75 m)
        self.assertGreater((foramen - loc).dot(nor), 0.0)  # fuera del solido: el agujero esta vacio
        for sign in (1, -1):  # el agujero esta vacio en ambos lados
            q = o.matrix_world.inverted() @ Vector((sign * 0.0281 * h, -0.0113 * h, 0.4959 * h))
            loc, nor, _, d = tree.find_nearest(q)
            self.assertGreater((q - loc).dot(nor), 0.0)
        symphysis = [v.co for v in o.data.vertices if abs(v.co.x) < 0.0015 * h and -0.040 * h < v.co.y + 0.0 < -0.028 * h and abs(v.co.z + (cp.HIP_Z - 0.5003) * h) < 0.006 * h]
        self.assertGreater(len(symphysis), 40)  # los dos pubis se tocan en x = 0 (sinfisis)

    def test_the_skull_has_real_orbits_and_a_piriform_aperture(self):
        h = self.h
        sk = SkullGroup(self.parts)

        def first_hit(x, z):  # primer punto de la superficie que alcanza un rayo que avanza hacia atras (+y) por (x, z)
            ok, loc, _, _ = sk.ray_cast(Vector((x * h, -0.2 * h, z * h)), Vector((0, 1, 0)))
            self.assertTrue(ok)
            return loc.y / h

        rim = first_hit(0.0183, -0.0085)  # justo bajo la orbita: el plano de la cara (maxilar)
        orbit = first_hit(0.0183, 0.0040)  # centro de la orbita
        self.assertGreater(orbit - rim, 0.010)  # la orbita esta hundida >= 0.010 H (~17 mm) respecto a su reborde
        cheek = first_hit(0.0250, -0.0120)
        nose = first_hit(0.0, -0.0135)  # centro de la abertura piriforme
        self.assertGreater(nose - first_hit(0.0, -0.0270), 0.006)  # hundida respecto a la zona nasal inferior
        self.assertGreater(nose - cheek, 0.004)
        self.assertAlmostEqual(first_hit(-0.0183, 0.0040), orbit, delta=0.0006)  # las dos orbitas son simetricas

    def test_the_skull_has_the_dimensions_of_a_human_cranium(self):
        h = self.h
        sk = SkullGroup(self.parts)
        co = [v.co for v in sk.data.vertices]
        self.assertGreater(max(p.z for p in co) / h, 0.074)  # boveda a ~0.077 H sobre los condilos occipitales (13 cm)
        cranium_width = max(p.x for p in co if p.z > 0.020 * h) - min(p.x for p in co if p.z > 0.020 * h)
        self.assertGreater(cranium_width / h, 0.078)  # anchura del neurocraneo ~14 cm
        self.assertGreater(max(p.y for p in co) / h, 0.036)  # occipucio detras de los condilos
        self.assertLess(min(p.y for p in co) / h, -0.075)  # cara adelante
        self.assertLess(max(p.y for p in co if p.z < -0.0 and abs(p.x) < 0.01 * h) / h, 0.050)

    def test_the_skull_has_marked_cheekbones_and_a_sunken_temporal_fossa(self):  # (la frente plana y el techo achatado se sustituyeron por la boveda ovoide: ver TestCpSkullParts)
        h = self.h
        sk = SkullGroup(self.parts)

        def hit(origin, direction):
            ok, loc, _, _ = sk.ray_cast(Vector(origin) * h, Vector(direction))
            self.assertTrue(ok)
            return loc / h

        co = [v.co for v in sk.data.vertices]
        face = [v.co for n2 in ("cp.MaxillaL", "cp.MaxillaR", "cp.ZygomaticL", "cp.ZygomaticR") for v in self.parts[n2].data.vertices]  # el pomulo es del maxilar (el hueso cigomatico es otra pieza)
        cheek = max(p.x for p in face if -0.010 * h < p.z < 0.0 and -0.066 * h < p.y < -0.054 * h) / h
        self.assertGreater(cheek, 0.0385)  # pomulos marcados (+9 %): 0.0397 con el relieve y 0.0371 sin el
        fossa = hit((0.2, -0.026, 0.029), (-1, 0, 0)).x
        behind = hit((0.2, -0.004, 0.029), (-1, 0, 0)).x  # misma altura, detras de la fosa
        self.assertGreater(behind - fossa, 0.0015)  # fosa temporal hundida respecto a la bobeda lateral que la rodea

    def test_the_mandible_has_angle_ascending_ramus_body_and_chin(self):
        from mathutils.bvhtree import BVHTree

        h = self.h
        md = self.parts["cp.Mandible"]
        vs = [md.matrix_world @ v.co for v in md.data.vertices]
        sk = self.parts["cp.Skull"]
        s0 = sk.matrix_world.translation

        def rel(p):  # (x, y, z) en H relativo al origen del craneo
            return ((p.x - s0.x) / h, (p.y - s0.y) / h, (p.z - s0.z) / h)

        rr = [rel(p) for p in vs]
        ramus_top = [p for p in rr if p[0] > 0 and p[2] > -0.012]  # condilo y apofisis coronoides, arriba
        angle = [p for p in rr if p[0] > 0.028 and p[2] < -0.040 and p[1] > -0.032]  # angulo mandibular, abajo y atras
        chin = [p for p in rr if abs(p[0]) < 0.010 and p[1] < -0.066 and p[2] < -0.044]  # menton
        self.assertTrue(ramus_top and angle and chin)
        self.assertLess(max(p[2] for p in ramus_top), -0.0005 + 0.0)  # los condilos no pasan del eje de las ATM
        condyle = [p for p in rr if p[0] > 0 and p[2] > -0.0100]  # cabeza del condilo, bajo la fosa glenoidea
        self.assertGreater(len(condyle), 40)
        self.assertAlmostEqual(sum(p[1] for p in condyle) / len(condyle), ax.TMJ[1], delta=0.005)  # centrada en el eje de las ATM (y = -0.032 H)
        self.assertGreater(max(p[2] for p in ramus_top) - min(p[2] for p in angle), 0.030)  # rama ascendente de ~3 cm de H (5 cm)
        self.assertGreater(min(p[1] for p in chin) , -0.085)
        self.assertLess(min(p[1] for p in chin), -0.074)  # el menton adelanta la arcada
        ramus = [p for p in rr if p[0] > 0 and -0.032 < p[2] < -0.014]  # rama ascendente recta: sin deriva lateral a lo largo de su altura
        self.assertGreater(len(ramus), 150)
        self.assertLess(max(p[0] for p in ramus) - min(p[0] for p in ramus), 0.0100)
        gonion = [p for p in rr if p[0] > 0.0 and p[2] < -0.046 and p[1] > -0.0275]  # el gonion es una esquina: el borde inferior y el posterior se cortan en angulo
        self.assertTrue(gonion)
        pivot = md.matrix_world.translation
        skull_tmj = s0 + Vector(ax.TMJ) * h
        self.assertLess((pivot - skull_tmj).length, 1e-5)  # pivote cinematico en el eje de las ATM


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestCpSpine(unittest.TestCase):
    """Etapa B: columna con vertebras propias de cada region (cuerpo en rinon con cintura, arco con foramen, apofisis reconocibles), curvas y discos."""

    @classmethod
    def setUpClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        cls.h = 1.75
        cls.parts = cp.build_cp_skeleton(cls.h)
        bpy.context.view_layer.update()
        from anatomical_core import cp_skullbox, cp_vertebra

        cls.cv, cls.sb = cp_vertebra, cp_skullbox
        cls.spine = cp_vertebra.load_spine()

    BODY_H = {"L": 0.0156, "T": 0.0115, "C": 0.0086}
    REGION = {"L": "lumbar", "T": "thoracic", "C": "cervical"}

    def vertebra(self, level):
        """Objeto de UNA vertebra aislada (en metros, origen en el centro del cuerpo) para medir su forma."""
        region = self.REGION[level[0]]
        cage = self.cv.vertebra_cage(region, level, self.cv.level_params(self.spine, region, level), self.BODY_H[level[0]])
        for v in cage.verts:
            v.co *= self.h
        verts, faces = self.sb.subdivide(cage, levels=1, scale=1.0)
        me = bpy.data.meshes.new("t_" + level)
        me.from_pydata(verts, [], faces)
        me.update()
        o = bpy.data.objects.new("t_" + level, me)
        bpy.context.scene.collection.objects.link(o)
        return o

    def release(self, o):
        m = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.meshes.remove(m)

    def test_each_region_has_its_own_vertebra_dimensions_and_shape_parameters(self):
        p = lambda r, n: self.cv.level_params(self.spine, r, n)  # noqa: E731
        self.assertGreater(p("lumbar", "L5")["bw"], p("lumbar", "L1")["bw"])  # la lumbar crece hacia el sacro
        self.assertGreater(p("thoracic", "T12")["bw"], p("thoracic", "T1")["bw"])
        self.assertGreater(p("cervical", "C7")["bw"], p("cervical", "C3")["bw"])
        self.assertGreater(p("lumbar", "L1")["bw"], p("thoracic", "T12")["bw"])  # los cuerpos lumbares son los mayores
        self.assertGreater(p("thoracic", "T1")["bw"], p("cervical", "C3")["bw"] * 1.05)
        self.assertGreater(p("thoracic", "T7")["sp"][0], p("lumbar", "L3")["sp"][0] * 1.8)  # espinosa toracica larga, lumbar corta
        self.assertGreater(p("thoracic", "T7")["sp"][1], 45.0)  # inclinada hacia abajo en T4-T9
        self.assertLess(p("lumbar", "L3")["sp"][1], 6.0)  # lumbar casi horizontal
        self.assertGreater(p("lumbar", "L3")["sp"][2], p("thoracic", "T7")["sp"][2] * 1.5)  # y alta (en hacha)
        self.assertTrue(p("cervical", "C4")["bifid"] and not p("cervical", "C7").get("bifid"))  # bifida en C3-C6, C7 prominente
        self.assertGreater(p("cervical", "C7")["sp"][0], p("cervical", "C4")["sp"][0] * 1.4)
        self.assertGreater(p("thoracic", "T6")["tp"][0], p("lumbar", "L3")["tp"][0] * 1.1)  # transversas toracicas largas
        self.assertTrue(p("thoracic", "T5")["costal"] and not p("lumbar", "L3").get("costal"))
        self.assertTrue(p("cervical", "C5")["uncinate"])
        regs = self.spine["regions"]
        self.assertEqual(len(regs["lumbar"]["levels"]) + len(regs["thoracic"]["levels"]) + len(regs["cervical"]["levels"]) + 2, 24)  # 5 + 12 + 5 + C1 + C2

    def test_the_body_is_kidney_shaped_with_a_waist_and_a_wedge(self):
        h = self.h
        for level in ("L3", "T8", "C5"):
            o = self.vertebra(level)
            p = self.cv.level_params(self.spine, self.REGION[level[0]], level)
            bh = self.BODY_H[level[0]] * h
            body = [v.co for v in o.data.vertices if v.co.y < p["bd"] * h * 1.02 and abs(v.co.x) < p["bw"] * h * 1.1]  # el cuerpo (sin el arco, que esta mas atras)
            mid = [abs(v.x) for v in body if abs(v.z) < 0.08 * bh]
            end = [abs(v.x) for v in body if 0.42 * bh < abs(v.z) < 0.52 * bh]
            self.assertGreater(max(end), max(mid) * 1.04, level)  # cintura: el platillo es mas ancho que el centro
            front_top = max(v.z for v in body if v.y < -0.6 * p["bd"] * h)
            back_top = max(v.z for v in body if 0.35 * p["bd"] * h < v.y < 0.75 * p["bd"] * h and abs(v.x) < 0.6 * p["bw"] * h)  # (sin las carillas costales, que sobresalen)
            front_top = max(v.z for v in body if v.y < -0.6 * p["bd"] * h and abs(v.x) < 0.6 * p["bw"] * h)
            if p["wedge"] > 0.02:
                self.assertGreater(front_top, back_top, level)  # cuña: mas alto delante
            posterior = [v.y for v in body if abs(v.x) < 0.1 * p["bw"] * h and v.y > 0]
            lateral = [v.y for v in body if abs(v.x) > 0.7 * p["bw"] * h and v.y > 0]
            self.assertLess(max(posterior), max(lateral), level)  # pared posterior concava (rinon): el centro entra respecto a los lados
            self.release(o)

    def test_the_vertebral_foramen_is_open_behind_the_body_and_the_arch_closes_it(self):
        h = self.h
        for level in ("L3", "T8", "C5"):
            o = self.vertebra(level)
            p = self.cv.level_params(self.spine, self.REGION[level[0]], level)
            canal_y = (p["bd"] + p["ped"][0] + p["fz"][1] * 0.45) * h
            ok_body, _, _, _ = o.ray_cast(Vector((0.0, 0.0, 0.2)), Vector((0, 0, -1)))
            ok_canal, _, _, _ = o.ray_cast(Vector((0.0, canal_y, 0.2)), Vector((0, 0, -1)))
            self.assertTrue(ok_body, level)  # por el cuerpo pasa el solido
            self.assertFalse(ok_canal, level)  # por el foramen no: el conducto esta vacio
            ok_arch, _, _, _ = o.ray_cast(Vector((0.0, canal_y, 0.0)), Vector((0, 1, 0)))
            self.assertTrue(ok_arch, level)  # y detras lo cierra el arco (laminas + espinosa)
            self.release(o)

    def test_the_spinous_and_transverse_processes_have_the_shape_of_their_region(self):
        h = self.h
        ext, slope = {}, {}
        for level in ("L3", "T7", "C4"):
            o = self.vertebra(level)
            p = self.cv.level_params(self.spine, self.REGION[level[0]], level)
            vs = [v.co.copy() for v in o.data.vertices]
            tip = max(vs, key=lambda v: v.y)  # punta de la espinosa
            apex_y = (p["bd"] + p["ped"][0] + p["fz"][1]) * h  # donde nace la espinosa (apice del arco)
            slope[level] = -tip.z / max(1e-9, tip.y - apex_y)  # inclinacion hacia abajo: 0 = horizontal, 1 = 45 grados
            ext[level] = (tip.y / h, max(abs(v.x) for v in vs) / h)
            self.release(o)
        self.assertGreater(slope["T7"], 1.0)  # espinosa toracica inclinada >= 45 grados hacia abajo (T4-T9)
        self.assertLess(slope["L3"], 0.3)  # lumbar casi horizontal (en hacha)
        self.assertGreater(ext["T7"][1], ext["C4"][1] * 1.15)  # transversas toracicas mas anchas que las cervicales
        self.assertGreater(ext["T7"][0], ext["C4"][0] * 1.15)  # y la espinosa toracica llega mas atras que la cervical (aunque baja, su proyeccion horizontal es menor que su largo)

    def test_the_spine_is_straight_in_the_frontal_plane_symmetric_and_curved_in_the_sagittal_plane(self):
        for n in ("cp.LumbarSpine", "cp.ThoracicSpine", "cp.CervicalSpine"):
            o = self.parts[n]
            xs = [v.co.x for v in o.data.vertices]
            self.assertLess(abs(sum(xs) / len(xs)), 5e-4, n)  # linea central en x = 0 (columna recta de frente)
            self.assertLess(mirror_error(o), 1.5e-3, n)  # simetria bilateral
        h = self.h

        def front_y(frac):  # y mas anterior (cuerpos) en una franja de la columna lumbar
            vs = self.parts["cp.LumbarSpine"].data.vertices
            z0, z1 = min(v.co.z for v in vs), max(v.co.z for v in vs)
            zc = z0 + (z1 - z0) * frac
            return min(v.co.y for v in vs if abs(v.co.z - zc) < 0.012 * h)

        self.assertLess(front_y(0.5) - 0.5 * (front_y(0.1) + front_y(0.9)), -0.0020)  # lordosis lumbar: el centro mas adelantado que los extremos

    def test_the_lumbar_spine_rests_on_the_sacrum_and_the_discs_are_lens_shaped(self):
        from mathutils.bvhtree import BVHTree

        h = self.h
        pelvis, lumbar = self.parts["cp.Pelvis"], self.parts["cp.LumbarSpine"]
        tree = BVHTree.FromObject(pelvis, bpy.context.evaluated_depsgraph_get())
        inv = pelvis.matrix_world.inverted()
        low = [lumbar.matrix_world @ v.co for v in lumbar.data.vertices if v.co.z < -cp.DISC_H / 2 * h * 0.8 and abs(v.co.x) < 0.01 * h]  # cara inferior del disco L5-S1
        self.assertGreater(len(low), 20)
        d = min(tree.find_nearest(inv @ p)[3] for p in low)
        self.assertLess(d, 0.006)  # el disco L5-S1 toca el sacro (< 6 mm)
        q = self.cv.level_params(self.spine, "lumbar", "L3")
        cage = self.cv.disc_cage(q["bw"], q["bd"], cp.DISC_H, 0.16, 1.05)
        hd = cp.DISC_H
        mid_r = max(abs(v.co.x) for v in cage.verts if abs(v.co.z) < 0.05 * hd)  # en la jaula (la subdivision redondea los platillos y falsearia la medida)
        end_r = max(abs(v.co.x) for v in cage.verts if abs(v.co.z) > 0.45 * hd)
        self.assertGreater(mid_r, end_r * 1.05)  # disco lenticular: mas ancho en el centro que en los platillos
        cage.free()

    def test_no_temporary_or_duplicate_objects_are_left_behind(self):
        self.assertEqual(sorted(o.name for o in bpy.data.objects), sorted(self.parts))
        self.assertEqual([m.name for m in bpy.data.meshes if m.name.startswith(("cp_tmp", "t_"))], [])
        self.assertEqual(len({o.data.name for o in bpy.data.objects}), len(bpy.data.objects))  # cada objeto con su malla

    def test_control_a_cylinder_body_fails_the_shape_checks(self):
        """Control: un cuerpo SIN cintura, cuña ni concavidad posterior no cumple las comprobaciones de forma (las comprobaciones discriminan)."""
        h = self.h
        p = self.cv.level_params(self.spine, "lumbar", "L3")
        flat = self.cv.body_cage(p["bw"], p["bd"], self.BODY_H["L"], 0.0, 0.0, 0.0)
        for v in flat.verts:
            v.co *= h
        verts, faces = self.sb.subdivide(flat, levels=1, scale=1.0)
        bh = self.BODY_H["L"] * h
        xs_mid = max(abs(v[0]) for v in verts if abs(v[2]) < 0.08 * bh)
        xs_end = max(abs(v[0]) for v in verts if 0.42 * bh < abs(v[2]) < 0.52 * bh)
        self.assertLess(xs_end, xs_mid * 1.04)  # sin cintura
        post = max(v[1] for v in verts if abs(v[0]) < 0.1 * p["bw"] * h)
        lat = max(v[1] for v in verts if abs(v[0]) > 0.7 * p["bw"] * h)
        self.assertGreaterEqual(post, lat)  # sin pared posterior concava


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestCpSkullParts(unittest.TestCase):
    """Craneo en piezas INDEPENDIENTES (bovedas, cara, cigomaticos, temporales, mastoides, condilos, dientes, mandibula): cada una una malla cerrada propia, que se tocan sin unirse
    en un solo solido; boveda ovoide conforme a las imagenes de referencia y profundidades (orbitas, fosa nasal y fosas temporales)."""

    @classmethod
    def setUpClass(cls):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        cls.h = 1.75
        cls.parts = cp.build_cp_skeleton(cls.h)
        bpy.context.view_layer.update()
        cls.sk = SkullGroup(cls.parts)

    BONES = ["cp.SkullFrontal", "cp.SkullOccipital", "cp.ParietalL", "cp.ParietalR", "cp.TemporalL", "cp.TemporalR", "cp.SphenoidL", "cp.SphenoidR"]
    FACE = [f"cp.{n}{sd}" for n in ("Maxilla", "Nasal", "Lacrimal", "Ethmoid", "Zygomatic") for sd in "LR"]
    NAMES = sorted(["cp.CondyleL", "cp.CondyleR", "cp.Skull", "cp.TeethUpper"] + BONES + FACE)

    def test_the_skull_is_made_of_independent_closed_pieces_not_one_solid(self):
        self.assertEqual(skull_names(self.parts), self.NAMES)
        for n in self.NAMES + ["cp.Mandible", "cp.TeethLower"]:
            o = self.parts[n]
            self.assertEqual(islands(o), 1, n)  # una sola pieza cerrada por objeto: nada de cascarones sueltos dentro del mismo objeto
            self.assertEqual(o.type, "MESH")
        self.assertEqual(len({self.parts[n].data.name for n in self.NAMES}), len(self.NAMES))  # cada pieza con su propia malla
        self.assertEqual(cp.validate({n: self.parts[n] for n in self.NAMES + ["cp.Mandible", "cp.TeethLower"]}), [])  # cerradas (manifold) y con volumen positivo

    def test_the_pieces_hang_from_their_bone_and_share_the_skull_origin(self):
        for n in [x for x in self.NAMES if x != "cp.Skull"]:
            self.assertIs(self.parts[n].parent, self.parts["cp.Skull"], n)
            self.assertLess((self.parts[n].matrix_world.translation - self.parts["cp.Skull"].matrix_world.translation).length, 1e-6, n)
        self.assertIs(self.parts["cp.TeethLower"].parent, self.parts["cp.Mandible"])
        self.assertIs(self.parts["cp.Skull"].parent, self.parts["cp.CervicalSpine"])

    def test_the_junctions_between_groups_touch_without_being_fused(self):
        from mathutils.bvhtree import BVHTree

        dg = bpy.context.evaluated_depsgraph_get()
        trees = {}

        def touches(a, b, lim=0.003):
            if b not in trees:
                trees[b] = BVHTree.FromObject(self.parts[b], dg)
            inv = self.parts[b].matrix_world.inverted()
            for v in list(self.parts[a].data.vertices)[::3]:
                q = inv @ (self.parts[a].matrix_world @ v.co)
                loc, nor, _, d = trees[b].find_nearest(q)
                if d < lim or (q - loc).dot(nor) < 0:
                    return True
            return False

        for a, b in (("cp.Skull", "cp.MaxillaL"), ("cp.Skull", "cp.MaxillaR"), ("cp.MaxillaL", "cp.ZygomaticL"), ("cp.MaxillaR", "cp.ZygomaticR"), ("cp.ZygomaticL", "cp.TemporalL"), ("cp.ZygomaticR", "cp.TemporalR"),
                     ("cp.MaxillaL", "cp.NasalL"), ("cp.MaxillaR", "cp.NasalR"), ("cp.MaxillaL", "cp.LacrimalL"), ("cp.MaxillaR", "cp.LacrimalR"), ("cp.LacrimalL", "cp.EthmoidL"), ("cp.LacrimalR", "cp.EthmoidR"),
                     ("cp.MaxillaL", "cp.MaxillaR"), ("cp.NasalL", "cp.NasalR"), ("cp.Skull", "cp.SkullFrontal"), ("cp.ZygomaticL", "cp.SkullFrontal"), ("cp.ZygomaticR", "cp.SkullFrontal"), ("cp.ZygomaticL", "cp.SphenoidL"), ("cp.ZygomaticR", "cp.SphenoidR"),
                     ("cp.Skull", "cp.SkullOccipital"), ("cp.Skull", "cp.ParietalL"), ("cp.Skull", "cp.ParietalR"), ("cp.Skull", "cp.TemporalL"), ("cp.Skull", "cp.TemporalR"),
                     ("cp.Skull", "cp.SphenoidL"), ("cp.Skull", "cp.CondyleL"), ("cp.Skull", "cp.CondyleR"), ("cp.MaxillaL", "cp.TeethUpper"), ("cp.Mandible", "cp.TeethLower")):
            self.assertTrue(touches(a, b) or touches(b, a), f"{a} y {b} no se tocan")
        for a, b in (("cp.SkullFrontal", "cp.NasalL"), ("cp.SkullFrontal", "cp.NasalR"), ("cp.SkullFrontal", "cp.LacrimalL"), ("cp.SkullFrontal", "cp.LacrimalR")):  # suturas con surco: a < 10 mm
            self.assertTrue(touches(a, b, 0.010) or touches(b, a, 0.010), f"{a} y {b} no estan juntos")
        self.assertEqual(sum(1 for o in bpy.data.objects if o.name.startswith(SKULL_PREFIXES)), len(self.NAMES))  # y siguen siendo objetos distintos (no se unieron)

    def test_the_vault_is_a_smooth_ovoid_like_the_reference_images(self):
        h = self.h
        vs = [v.co for v in self.parts["cp.Skull"].data.vertices]
        spec = __import__("anatomical_core.cp_skullbox", fromlist=["x"]).load_skull()["vault"]
        zc, cu, cy = spec["center"][1], spec["radius_up"], spec["center"][0]
        eq = max(abs(p.x) for p in vs if abs(p.z / h - zc) < 0.004)  # semianchura ecuatorial
        self.assertTrue(0.80 < max(abs(p.x) for p in vs if abs(p.z / h - (zc + 0.5 * cu)) < 0.003) / eq < 0.96)  # se estrecha al subir (una caja daria ~1.0)
        self.assertTrue(0.60 < max(abs(p.x) for p in vs if abs(p.z / h - (zc + 0.8 * cu)) < 0.003) / eq < 0.82)
        top = max(p.z for p in vs)
        for xf, lo, hi in ((0.5, 0.0015, 0.0060), (0.75, 0.0060, 0.0160)):  # el techo cae al alejarse de la linea media: curva de ovoide, no un plano
            zs = [p.z for p in vs if abs(abs(p.x) - xf * eq) < 0.003 * h and abs(p.y / h - cy) < 0.006 * h and p.z > 0]
            self.assertTrue(lo * h < top - max(zs) < hi * h, xf)

    def test_the_overall_proportions_follow_the_reference_images(self):
        h = self.h
        ref = __import__("json").loads((ROOT / "config" / "cp" / "skull_reference.json").read_text(encoding="utf-8"))
        md = self.parts["cp.Mandible"]
        g = [v.co for v in self.sk.data.vertices]
        jaw = [md.matrix_world @ v.co - self.parts["cp.Skull"].matrix_world.translation for v in md.data.vertices]
        top, bottom = max(p.z for p in g), min(p.z for p in jaw)
        width = max(p.x for p in g) - min(p.x for p in g)
        length = max(max(p.y for p in g), max(p.y for p in jaw)) - min(min(p.y for p in g), min(p.y for p in jaw))
        self.assertAlmostEqual(width / (top - bottom), ref["front"]["aspect_w_over_h"], delta=0.06)  # ancho / alto de frente (0.683 en la imagen)
        self.assertAlmostEqual(length / (top - bottom), ref["side"]["aspect_w_over_h"], delta=0.07)  # largo / alto de perfil (0.958 en la imagen)

    def test_resizing_the_vault_scales_the_pieces_of_the_same_bone_but_not_the_mandible(self):
        before = {n: max(v.co.x for v in self.parts[n].data.vertices) - min(v.co.x for v in self.parts[n].data.vertices) for n in ("cp.MaxillaL", "cp.ZygomaticL", "cp.Mandible")}
        f = cp.cp_resize(self.parts["cp.Skull"], self.parts["cp.Skull"]["cp_ref_dim_m"] * 1.1)
        bpy.context.view_layer.update()
        for n in ("cp.MaxillaL", "cp.ZygomaticL"):
            now = max(v.co.x for v in self.parts[n].data.vertices) - min(v.co.x for v in self.parts[n].data.vertices)
            self.assertAlmostEqual(now / before[n], f, places=4, msg=n)
        now = max(v.co.x for v in self.parts["cp.Mandible"].data.vertices) - min(v.co.x for v in self.parts["cp.Mandible"].data.vertices)
        self.assertAlmostEqual(now / before["cp.Mandible"], 1.0, places=6)  # la mandibula tiene su propia dimension
        cp.cp_resize(self.parts["cp.Skull"], self.parts["cp.Skull"]["cp_ref_dim_m"] / f)  # deshace

    @unittest.skipUnless(all((ROOT / f).exists() for f in ("craneo frontal.jpg", "craneo perfil.jpg", "craneo atras.jpg")), "faltan las imagenes de referencia (privadas, no versionadas)")
    def test_the_reference_images_are_mapped_to_the_skull_scale_and_position(self):
        from anatomical_core import cp_reference

        refs = cp_reference.add_reference_images(self.parts)
        try:
            self.assertEqual(sorted(refs), ["back", "front", "side"])
            ref = __import__("json").loads((ROOT / "config" / "cp" / "skull_reference.json").read_text(encoding="utf-8"))
            lo, hi = cp_reference._bbox(self.sk.objs + [self.parts["cp.Mandible"]])
            for v in ("front", "side"):
                x0, y0, x1, y1 = ref[v]["silhouette_bbox"]
                self.assertAlmostEqual(refs[v]["cp_m_per_px"] * (y1 - y0), hi.z - lo.z, places=6, msg=v)  # la altura de la silueta de la imagen iguala la del craneo con mandibula
            self.assertLess(refs["front"].location.y, lo.y)  # el plano frontal queda delante,
            self.assertGreater(refs["back"].location.y, hi.y)  # el posterior detras
            self.assertGreater(refs["side"].location.x, hi.x)  # y el de perfil a su lado
            self.assertTrue(all(e.hide_render and e.empty_display_type == "IMAGE" for e in refs.values()))  # no se renderizan
        finally:
            for e in refs.values():
                bpy.data.objects.remove(e, do_unlink=True)

    def test_the_five_vault_bones_are_a_suture_map_of_independent_shells(self):
        from mathutils.bvhtree import BVHTree

        for n in self.BONES:
            o = self.parts[n]
            self.assertEqual(islands(o), 1, n)  # cada hueso, una sola cascara
            self.assertGreater(len(o.data.vertices), 1000, n)
        occ = self.parts["cp.SkullOccipital"]
        zs = [v.co.z for v in occ.data.vertices]
        self.assertLess(min(zs), max(zs) - 0.04 * self.h * 0.5)  # el occipital cubre la parte trasera baja de la boveda, no un parche
        fr = self.parts["cp.SkullFrontal"]
        self.assertLess(max(v.co.y for v in fr.data.vertices), 0.0)  # el frontal queda delante de la sutura coronal
        self.assertGreater(min(v.co.y for v in self.parts["cp.ParietalL"].data.vertices), max(v.co.y for v in fr.data.vertices) - 0.035)  # la coronal en zigzag solapa unos cm en y
        self.assertGreater(min(v.co.y for v in occ.data.vertices), min(v.co.y for v in self.parts["cp.ParietalL"].data.vertices))
        for a, b in (("cp.ParietalL", "cp.ParietalR"),):  # la sutura sagital deja un surco entre los parietales
            ta = BVHTree.FromObject(self.parts[a], bpy.context.evaluated_depsgraph_get())
            d = min(ta.find_nearest(v.co)[3] for v in list(self.parts[b].data.vertices)[::7])
            self.assertGreater(d, 1e-4)
        for n in ("ParietalL", "TemporalL", "SphenoidL"):
            self.assertGreater(min(v.co.x for v in self.parts["cp." + n].data.vertices), 0.0, n)  # el lado izquierdo es +x
        for n in ("ParietalR", "TemporalR", "SphenoidR"):
            self.assertLess(max(v.co.x for v in self.parts["cp." + n].data.vertices), 0.0, n)

    def test_the_zygomatic_has_a_frontal_arm_and_a_temporal_arch(self):
        h = self.h
        for sx, n in ((1, "cp.ZygomaticL"), (-1, "cp.ZygomaticR")):
            vs = [v.co for v in self.parts[n].data.vertices]
            self.assertGreater(max(p.z for p in vs), 0.012 * h, n)  # el brazo frontal sube hasta el borde del frontal
            self.assertLess(min(p.z for p in vs), -0.008 * h, n)  # el cuerpo malar queda bajo la orbita
            self.assertGreater(max(p.y for p in vs) - min(p.y for p in vs), 0.045 * h, n)  # el arco llega hasta el temporal
            fr = min(v.co.y for v in self.parts["cp.SkullFrontal"].data.vertices)
            self.assertLess(min(p.y for p in vs), fr + 0.05 * h, n)
            self.assertGreater(max(sx * p.x for p in vs), 0.03 * h, n)  # y del lado correcto
            face_half = max(abs(v.co.x) for n2 in ("cp.MaxillaL", "cp.MaxillaR") for v in self.parts[n2].data.vertices)
            outside = sum(1 for p in vs if sx * p.x > face_half)
            self.assertGreater(outside, 100, n)  # el pomulo y el arco quedan POR FUERA del bloque de la cara, no ocultos dentro de el
            self.assertGreater(max(sx * p.x for p in vs), face_half + 0.003, n)

    def test_the_pieces_are_organised_in_section_collections(self):
        root = bpy.data.collections["CP_Skeleton"]
        for path, names in cp.SECTIONS.items():
            c = root
            for seg in path:
                c = bpy.data.collections["CP_" + seg]
                self.assertIn(c.name, [x.name for x in (root.children_recursive)], c.name)
            self.assertEqual(sorted(o.name for o in c.objects), sorted(names), path)
        every = [o for o in bpy.data.objects if o.name.startswith("cp.")]
        self.assertTrue(all(len(o.users_collection) == 1 for o in every))  # cada pieza en una sola coleccion
        self.assertEqual(len(every), sum(len(v) for v in cp.SECTIONS.values()))
        self.assertEqual(len(bpy.data.collections["CP_Neurocraneo"]["cp_huesos_esperados"].split(", ")), 8)  # los 22 huesos: 8 del neurocraneo
        self.assertEqual(len(bpy.data.collections["CP_Viscerocraneo"]["cp_huesos_esperados"].split(", ")), 14)  # y 14 del viscerocraneo
        self.assertIs(self.parts["cp.Skull"].parent, self.parts["cp.CervicalSpine"])  # el parentesco no cambia

    def test_each_temporal_bone_is_one_single_piece_with_all_its_parts(self):
        for side, sx in (("L", 1), ("R", -1)):
            n = f"cp.Temporal{side}"
            o = self.parts[n]
            self.assertEqual(islands(o), 1, n)  # escama, parte baja y mastoides fundidas: una sola componente conexa
            for gone in (f"cp.TemporalBase{side}", f"cp.Mastoid{side}"):
                self.assertNotIn(gone, self.parts, gone)  # ya no son objetos aparte
            vs = [v.co for v in o.data.vertices]
            self.assertTrue(any(p.z < -0.022 * self.h for p in vs), n)  # incluye la mastoides (baja: la parte baja sola llega a -0.017)
            self.assertTrue(any(p.z > 0.02 * self.h for p in vs), n)  # y la escama (alta)
            self.assertTrue(any(sx * p.x > 0.039 * self.h and p.y < -0.012 * self.h for p in vs), n)  # y la apofisis cigomatica (delante y por fuera)
        self.assertEqual(sum(1 for x in bpy.data.objects if x.name.startswith("cp.Temporal")), 2)

    def test_the_face_is_split_into_bones_and_the_arch_is_halved_at_the_jaw_origin_by_a_w_suture(self):
        h = self.h
        for n in self.FACE:
            self.assertEqual(islands(self.parts[n]), 1, n)  # cada hueso de la cara, una sola cascara
            self.assertGreater(len(self.parts[n].data.vertices), 300, n)
        self.assertNotIn("cp.SkullFace", self.parts)  # el bloque de la cara ya no existe: esta fragmentado
        su = dict(__import__("anatomical_core.cp_skullbox", fromlist=["x"]).load_skull()["arch_suture"], y=ax.TMJ[1])  # la sutura va donde nace la mandibula (ATM), no donde diga la configuracion
        for sx, sd in ((1, "L"), (-1, "R")):
            zy = [v.co for v in self.parts[f"cp.Zygomatic{sd}"].data.vertices]
            tp = [v.co for v in self.parts[f"cp.Temporal{sd}"].data.vertices]
            arch_t = [p for p in tp if sx * p.x > 0.039 * h and p.z < -0.004 * h]  # el arco del lado del temporal
            self.assertGreater(min(p.y for p in arch_t), (su["y"] - su["amp"] - 0.001) * h, sd)  # el temporal empieza donde nace la mandibula (y de la ATM)
            self.assertLess(max(p.y for p in zy if p.z < -0.004 * h and sx * p.x > 0.039 * h), (su["y"] + su["amp"] + 0.001) * h, sd)  # y el cigomatico acaba ahi
            bins = {}
            for p in zy:
                if p.y > (su["y"] - 0.006) * h and sx * p.x > 0.039 * h:
                    k = round(p.z / (0.0015 * h))
                    bins[k] = max(bins.get(k, -9.0), p.y)
            self.assertGreater((max(bins.values()) - min(bins.values())) / h, 0.0025, sd)  # el borde es una W (dientes), no una recta
            self.assertGreater(max(sx * p.x for p in zy), 0.0425 * h, sd)  # el cuerpo malar se une al maxilar: la mejilla es del cigomatico
        mx = [v.co for v in self.parts["cp.MaxillaL"].data.vertices]
        self.assertGreater(max(p.x for p in mx), 0.03 * h)

    def test_every_skull_piece_is_mirror_symmetric(self):
        for n in self.NAMES + ["cp.Mandible", "cp.TeethLower"]:
            self.assertLess(pair_mirror_error(self.parts, n), 1.5e-3, n)


if __name__ == "__main__":
    unittest.main()
