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


def extents(o):
    xs = [v.co for v in o.data.vertices]
    return tuple(max(c[i] for c in xs) - min(c[i] for c in xs) for i in range(3))


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestCpSkeleton(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.parts = cp.build_cp_skeleton(1.75)

    def test_four_independent_objects_with_the_cp_index_names(self):
        self.assertEqual(sorted(self.parts), ["cp.CervicalSpine", "cp.FemurL", "cp.FemurR", "cp.LumbarSpine", "cp.Mandible", "cp.Pelvis", "cp.Skull", "cp.ThoracicSpine"])
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
        half = cp.DISC_H / 2 * h  # los centros de las dos caras del disco L5-S1 estan a media altura del origen, uno frente al otro
        poles = [v.co.copy() for v in o.data.vertices if abs(v.co.length - half) < 1e-5]
        self.assertTrue(any((a + b).length < 1e-5 for a in poles for b in poles if a is not b), "el disco L5-S1 no esta centrado en el origen")
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
        self.assertEqual(sorted(self.parts), ["cp.CervicalSpine", "cp.FemurL", "cp.FemurR", "cp.LumbarSpine", "cp.Mandible", "cp.Pelvis", "cp.Skull", "cp.ThoracicSpine"])
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
            poles = [v.co.copy() for v in self.parts[name].data.vertices if abs(v.co.length - half) < 1e-5]
            self.assertTrue(any((a + b).length < 1e-5 for a in poles for b in poles if a is not b), name)
        xs = [v.co.x for v in self.parts["cp.Skull"].data.vertices]
        self.assertAlmostEqual(max(xs) + min(xs), 0.0, delta=1e-5)  # el craneo es simetrico respecto al plano sagital del origen
        for n in ("cp.Skull", "cp.Mandible"):  # cada vertice espejado en x coincide con otro vertice de la misma malla (hasta 0.5 mm)
            self.assertLess(mirror_error(self.parts[n]), 1.5e-3, n)  # 1.5 mm: el Boolean y los anillos de los tubos no triangulan igual a cada lado
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
        sk, md = self.parts["cp.Skull"], self.parts["cp.Mandible"]
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

    PART = {"ilium": "cp.Pelvis", "ischium": "cp.Pelvis", "pubis": "cp.Pelvis", "sacrum": "cp.Pelvis", "coccyx": "cp.Pelvis", "cranium": "cp.Skull", "mandible": "cp.Mandible"}
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
        from test_bone_meshes import build_all

        _, _, art, _ = build_all(h)
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
            o = parts[name]
            if name not in trees:
                trees[name] = BVHTree.FromObject(o, dg)
            q = o.matrix_world.inverted() @ Vector(a.point)
            loc, nor, _, d = trees[name].find_nearest(q)
            out[n] = 0.0 if (q - loc).dot(nor) < 0 else d * 1000.0
        return out

    def test_the_meshes_are_high_density(self):
        counts = {n: len(o.data.polygons) for n, o in self.parts.items()}
        self.assertGreater(counts["cp.Pelvis"], 60000)  # alas iliacas, copas y anillo isquiopubiano
        self.assertGreater(counts["cp.Skull"], 60000)
        self.assertGreater(counts["cp.Mandible"], 20000)
        self.assertGreater(sum(counts.values()), 240000)
        for n in ("cp.Pelvis", "cp.Skull", "cp.Mandible"):
            self.assertTrue(all(p.use_smooth for p in self.parts[n].data.polygons), n)  # sombreado suave
        self.assertEqual(cp.validate(self.parts), [])  # superficies cerradas (manifold) y con volumen positivo

    def test_every_pelvis_femur_skull_and_mandible_landmark_is_within_12_mm_at_three_heights(self):
        for h in (1.5, 1.75, 2.05):
            parts = cp.build_cp_skeleton(h)
            bpy.context.view_layer.update()
            d = self.landmark_distances(h, parts)
            self.assertGreaterEqual(len(d), 69, h)
            bad = {n: round(v, 1) for n, v in d.items() if v >= 12.0 * h / 1.75}
            self.assertEqual(bad, {}, h)
        cp.build_cp_skeleton(1.75)  # deja la escena como la encontro la clase (las demas pruebas usan self.parts)
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
        h = self.h
        c = Vector((cp.HIP_X * h, 0.0, cp.HIP_Z * h))
        pelvis, femur = self.parts["cp.Pelvis"], self.parts["cp.FemurL"]
        cup = [pelvis.matrix_world @ v.co for v in pelvis.data.vertices if (pelvis.matrix_world @ v.co - c).length < 0.0215 * h * 1.01 and (pelvis.matrix_world @ v.co - c).length > 0.0136 * h * 0.99
               and (pelvis.matrix_world @ v.co).x > 0.03 * h]
        inner = min((p - c).length for p in cup)
        self.assertAlmostEqual(inner, 0.0136 * h, delta=0.0003)  # cara articular a 13.6 mm de H del centro
        head = max((femur.matrix_world @ v.co - c).length for v in femur.data.vertices if (femur.matrix_world @ v.co - c).length < 0.0132 * h)  # radio de la cabeza (0.0126 H)
        self.assertTrue(0.0005 * h < inner - head < 0.004 * h, "holgura de interlinea entre la cabeza femoral y la copa (0.5-4 mm de H)")
        neck = [femur.matrix_world @ v.co for v in femur.data.vertices if 0.026 * h < (femur.matrix_world @ v.co - c).length < 0.045 * h]
        self.assertGreater(min((p - c).length for p in neck if True), 0.0136 * h)  # ningun vertice del cuello entra en la copa
        from mathutils.kdtree import KDTree

        tree = KDTree(len(cup))
        for i, p in enumerate(cup):
            tree.insert(p, i)
        tree.balance()
        self.assertGreater(min(tree.find(p)[2] for p in neck), 0.001)  # el cuello no roza el borde de la copa

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
        sk = self.parts["cp.Skull"]

        def first_hit(x, z):  # primer punto de la superficie que alcanza un rayo que avanza hacia atras (+y) por (x, z)
            ok, loc, _, _ = sk.ray_cast(Vector((x * h, -0.2 * h, z * h)), Vector((0, 1, 0)))
            self.assertTrue(ok)
            return loc.y / h

        rim = first_hit(0.0183, 0.0160)  # por encima de la orbita: reborde / frente
        orbit = first_hit(0.0183, 0.0040)  # centro de la orbita
        self.assertGreater(orbit - rim, 0.010)  # la orbita esta hundida >= 0.010 H (~17 mm) respecto a su reborde
        cheek = first_hit(0.0250, -0.0120)
        nose = first_hit(0.0, -0.0135)  # centro de la abertura piriforme
        self.assertGreater(nose - first_hit(0.0, -0.0270), 0.006)  # hundida respecto a la zona nasal inferior
        self.assertGreater(nose - cheek, 0.004)
        self.assertAlmostEqual(first_hit(-0.0183, 0.0040), orbit, delta=0.0006)  # las dos orbitas son simetricas

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
        self.assertGreater(max(p[2] for p in ramus_top) - min(p[2] for p in angle), 0.030)  # rama ascendente de ~3 cm de H (5 cm)
        self.assertGreater(min(p[1] for p in chin) , -0.085)
        self.assertLess(min(p[1] for p in chin), -0.074)  # el menton adelanta la arcada
        pivot = md.matrix_world.translation
        skull_tmj = s0 + Vector(ax.TMJ) * h
        self.assertLess((pivot - skull_tmj).length, 1e-5)  # pivote cinematico en el eje de las ATM


if __name__ == "__main__":
    unittest.main()
