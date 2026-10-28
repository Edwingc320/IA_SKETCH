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
    from mathutils import kdtree

    vs = o.data.vertices
    tree = kdtree.KDTree(len(vs))
    for i, v in enumerate(vs):
        tree.insert(v.co, i)
    tree.balance()
    return max(tree.find(Vector((-v.co.x, v.co.y, v.co.z)))[2] for v in vs)


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
            self.assertLess(mirror_error(self.parts[n]), 1e-3, n)  # 0.5 mm: los anillos de los tubos espejados giran su fase
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
        self.assertTrue(0.105 * h < ex(sk, 1) < 0.125 * h, "longitud antero-posterior (~19 cm con arcada dental)")
        self.assertTrue(0.100 * h < ex(sk, 2) < 0.140 * h, "altura del craneo (~21 cm con la cara)")
        self.assertTrue(0.060 * h < ex(md, 0) < 0.090 * h, "anchura bicondilea de la mandibula")
        profile = [v.co for v in sk.data.vertices if abs(v.co.x - 0.0175 * h) < 0.0025 * h and abs(v.co.z - 0.012 * h) < 0.0025 * h and v.co.y < -0.060 * h]
        self.assertTrue(profile, "orbitas con reborde")
        self.assertGreaterEqual(ax.ORBIT_DEPTH, 0.010)  # las orbitas y la abertura nasal se hunden (profundidad), no solo se marcan con un reborde
        self.assertGreaterEqual(ax.NASAL_DEPTH, 0.006)
        import bmesh

        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=0.05)
        before = [(v.co.copy(), v.co.y) for v in bm.verts]
        ax.dent(bm, (0.0, -0.05, 0.0), 0.02, 0.01, (0, 1, 0))  # el vertice central se hunde casi la profundidad completa y los lejanos no se mueven
        centre = Vector((0.0, -0.05, 0.0))
        moved = [(v.co.y - y0, (p0 - centre).length) for v, (p0, y0) in zip(bm.verts, before)]
        self.assertGreater(max(d for d, _ in moved), 0.004)
        self.assertTrue(all(abs(d) < 1e-12 for d, dist in moved if dist >= 0.02))
        bm.free()

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


if __name__ == "__main__":
    unittest.main()
