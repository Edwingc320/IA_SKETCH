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
    from anatomical_core import cp_skeleton as cp


def extents(o):
    xs = [v.co for v in o.data.vertices]
    return tuple(max(c[i] for c in xs) - min(c[i] for c in xs) for i in range(3))


@unittest.skipUnless(HAVE_BPY, "requiere Blender (bpy)")
class TestCpSkeleton(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.parts = cp.build_cp_skeleton(1.75)

    def test_four_independent_objects_with_the_cp_index_names(self):
        self.assertEqual(sorted(self.parts), ["cp.FemurL", "cp.FemurR", "cp.LumbarSpine", "cp.Pelvis"])
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
            cp.build_cp_skeleton(1.75, {"cp.Skull": 0.2})
        with self.assertRaises(ValueError):
            cp.cp_resize(self.parts["cp.Pelvis"], -1.0)


if __name__ == "__main__":
    unittest.main()
