"""Deuda de anclaje: puntos del modelo antiguo que aun quedan a mas de 12 mm de la superficie de su hueso.

La regla (AGENTS.md) es que todo hito, extremo de ligamento y centro de articulacion quede a menos de 12 mm (a 1.75 m, escala con la
altura) de su hueso. Los anclajes de esta lista vienen de las secciones anteriores, cuyos huesos no tienen anchura (craneo lateral,
vertebras, hueso largo sin accidentes) y estan pendientes de corregirse. El test es un TRINQUETE: la lista solo puede disminuir. Un
anclaje nuevo fuera de 12 mm falla; uno corregido debe quitarse de la lista (si no, tambien falla)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

# (tipo, nombre del lado .L o sin lado, hueso). ATT = hito, LIG = extremo de ligamento (.a origen / .b insercion), JNT = centro de articulacion.
KNOWN_DEBT = {
    ("ATT", "coronoid_process.L", "mandible"),
    ("ATT", "mastoid_process.L", "cranium"),
    ("ATT", "superior_nuchal_line.L", "cranium"),
    ("ATT", "tibial_tuberosity.L", "tibia.L"),
    ("ATT", "ulnar_coronoid_process.L", "ulna.L"),
    ("JNT", "calcaneocuboid.L", "calcaneus.L"),
    ("JNT", "costotransverse_01.L", "T1"),
    ("JNT", "costotransverse_02.L", "T2"),
    ("JNT", "costotransverse_03.L", "T3"),
    ("JNT", "costotransverse_04.L", "T4"),
    ("JNT", "costotransverse_05.L", "T5"),
    ("JNT", "costotransverse_06.L", "T6"),
    ("JNT", "costotransverse_07.L", "T7"),
    ("JNT", "costotransverse_08.L", "T8"),
    ("JNT", "costotransverse_09.L", "T9"),
    ("JNT", "costotransverse_10.L", "T10"),
    ("JNT", "costovertebral_01.L", "T1"),
    ("JNT", "costovertebral_02.L", "T2"),
    ("JNT", "costovertebral_03.L", "T3"),
    ("JNT", "costovertebral_04.L", "T4"),
    ("JNT", "costovertebral_05.L", "T5"),
    ("JNT", "costovertebral_06.L", "T6"),
    ("JNT", "costovertebral_07.L", "T7"),
    ("JNT", "costovertebral_08.L", "T8"),
    ("JNT", "costovertebral_09.L", "T9"),
    ("JNT", "costovertebral_10.L", "T10"),
    ("JNT", "costovertebral_11.L", "T11"),
    ("JNT", "costovertebral_12.L", "T12"),
    ("JNT", "cuneonavicular.L", "lateral_cuneiform.L"),
    ("JNT", "distal_radioulnar.L", "radius.L"),
    ("JNT", "distal_tibiofibular.L", "fibula.L"),
    ("JNT", "distal_tibiofibular.L", "tibia.L"),
    ("JNT", "elbow.L", "radius.L"),
    ("JNT", "elbow.L", "ulna.L"),
    ("JNT", "midcarpal.L", "hamate.L"),
    ("JNT", "midcarpal.L", "trapezium.L"),
    ("JNT", "midcarpal.L", "triquetrum.L"),
    ("JNT", "patellofemoral.L", "femur.L"),
    ("JNT", "patellofemoral.L", "patella.L"),
    ("JNT", "pisotriquetral.L", "triquetrum.L"),
    ("JNT", "proximal_radioulnar.L", "radius.L"),
    ("JNT", "proximal_radioulnar.L", "ulna.L"),
    ("JNT", "proximal_tibiofibular.L", "fibula.L"),
    ("JNT", "proximal_tibiofibular.L", "tibia.L"),
    ("JNT", "radiocarpal.L", "radius.L"),
    ("JNT", "radiocarpal.L", "scaphoid.L"),
    ("JNT", "scapulothoracic.L", "rib_05.L"),
    ("JNT", "subtalar.L", "calcaneus.L"),
    ("JNT", "subtalar.L", "talus.L"),
    ("JNT", "talocrural.L", "fibula.L"),
    ("LIG", "aitfl.L.a", "tibia.L"),
    ("LIG", "annular.L.a", "ulna.L"),
    ("LIG", "annular.L.b", "ulna.L"),
    ("LIG", "anterior_cruciate.L.a", "femur.L"),
    ("LIG", "cfl.L.b", "calcaneus.L"),
    ("LIG", "nuchal.a", "C7"),
    ("LIG", "patellar.L.b", "tibia.L"),
    ("LIG", "pitfl.L.a", "tibia.L"),
    ("LIG", "posterior_atlanto_occipital_membrane.a", "C1"),
    ("LIG", "posterior_cruciate.L.a", "femur.L"),
    ("LIG", "sphenomandibular.L.b", "mandible"),
    ("LIG", "transverse_atlas.a", "C1"),
    ("LIG", "transverse_atlas.b", "C1"),
    ("LIG", "ulnar_collateral_elbow.L.b", "ulna.L"),
}
NOT_ON_BONE = {"body_center_of_mass", "head_center_of_gravity"}


def violations():
    base = build_model(load_config())
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    art = articulations.build_articulations(base, anat, articulations.load_articulation_data())
    tol = 0.012 * base.height_m / 1.75
    out = set()
    for n, x in art.attachments.items():
        if not n.endswith(".R") and n not in NOT_ON_BONE and articulations.bone_distance(x.point, x.bone, base, anat) > tol:
            out.add(("ATT", n, x.bone))
    for n, x in art.ligaments.items():
        if n.endswith(".R"):
            continue
        for end, bone, p in (("a", x.from_bone, x.a), ("b", x.to_bone, x.b)):
            if articulations.bone_distance(p, bone, base, anat) > tol:
                out.add(("LIG", f"{n}.{end}", bone))
    for n, x in art.joints.items():
        if n.endswith(".R"):
            continue
        for bone in x.bones:
            if articulations.bone_distance(x.center, bone, base, anat) > tol:
                out.add(("JNT", n, bone))
    return out


class TestAnchorDebtOnlyShrinks(unittest.TestCase):
    def test_no_new_anchor_beyond_12_mm(self):
        new = sorted(violations() - KNOWN_DEBT)
        self.assertEqual(new, [], "anclajes nuevos a mas de 12 mm de su hueso")

    def test_corrected_anchors_leave_the_list(self):
        fixed = sorted(KNOWN_DEBT - violations())
        self.assertEqual(fixed, [], "ya estan a menos de 12 mm: quitalos de KNOWN_DEBT")


if __name__ == "__main__":
    unittest.main()
