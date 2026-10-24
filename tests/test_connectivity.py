"""Pivotes y conectividad: el pivote de cada articulacion esta en la cabeza del hueso hijo y ningun hueso del nivel 1 queda
separado de su padre anatomico sin una articulacion natural que lo explique (salvo excepciones documentadas)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations  # noqa: E402
from anatomical_core.anatomy import point_segment_distance  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.geometry import length, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

CONTACT_M = 0.005  # a menos de 5 mm el hueso esta en contacto con su padre anatomico (a 1.75 m)

# Huesos que la jerarquia pedida cuelga de un padre con el que NO comparten articulacion natural. Cada uno debe
# articularse con otros huesos (se comprueba) y su razon queda documentada aqui.
NO_DIRECT_JOINT = {
    "sternum": "cuelga de T4 por la jerarquia del tronco, pero se une al esqueleto por las articulaciones esternocostales y esternoclaviculares",
    "fibula": "cuelga del femur por la jerarquia pedida (rodilla), pero se articula con la tibia (tibioperoneas proximal y distal)",
}


def build_all():
    base = build_model(load_config())
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    return base, anat, articulations.build_articulations(base, anat, articulations.load_articulation_data())


def segment_of(name, base, anat):
    return anat.bones.get(name) or base.bones[name]


class TestPivotsAndConnectivity(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()

    def test_every_base_pivot_is_exactly_the_head_of_the_child_bone(self):
        for name, joint in self.base.joints.items():
            self.assertEqual(length(sub(joint.pivot, self.base.bones[joint.bone].head)), 0.0, name)
            parent = self.base.bones[joint.bone].parent
            self.assertEqual(joint.parent_bone, parent, name)

    def test_base_bone_heads_touch_their_parent_segment(self):
        """Ningun hueso de la base se desconecta de su padre: su cabeza esta sobre el segmento del padre. Solo hay tres
        desfases, todos laterales por diseno (el padre es el eje medio del cuerpo y la articulacion es par)."""
        lateral = {"clavicle": "esternoclavicular: a un lado del eje del torax", "thigh": "cadera: a un lado del eje de la pelvis",
                   "upper_arm": "hombro: en el extremo acromial de la clavicula, fuera de su segmento"}
        for name, bone in self.base.bones.items():
            if bone.parent is None:
                continue
            parent = self.base.bones[bone.parent]
            gap = point_segment_distance(bone.head, parent.head, parent.tail)
            key = name.split(".")[0]
            if key in lateral:
                self.assertGreater(gap, 0.0, name)
                self.assertLess(gap, 0.06 * self.base.height_m, name)  # desfase lateral acotado
            else:
                self.assertLess(gap, 1e-9, name)

    def test_level1_bones_connect_to_their_anatomical_parent(self):
        joint_pairs = {frozenset((a, b)) for j in self.art.joints.values() for a in j.bones for b in j.bones if a != b}
        undocumented = []
        for name, bone in self.anat.bones.items():
            parent = bone.anatomical_parent or bone.parent
            seg = segment_of(parent, self.base, self.anat)
            gap = point_segment_distance(bone.head, seg.head, seg.tail)
            if gap <= CONTACT_M * self.base.height_m / 1.75:
                continue
            if frozenset((name, parent)) in joint_pairs:
                continue  # separado, pero una articulacion natural los une (p. ej. la rotula, la escapula, las costillas)
            if name.split(".")[0] in NO_DIRECT_JOINT:
                continue
            undocumented.append((name, parent, round(gap * 1000, 1)))
        self.assertEqual(undocumented, [], "huesos separados de su padre sin articulacion natural ni excepcion documentada")

    def test_documented_exceptions_are_still_articulated(self):
        """Una excepcion solo vale mientras el hueso siga articulado con algo."""
        for name, reason in NO_DIRECT_JOINT.items():
            self.assertTrue(reason)
            for side in ("", ".L", ".R"):
                bone = name + side
                if bone not in self.anat.bones:
                    continue
                self.assertTrue(any(bone in j.bones for j in self.art.joints.values()), bone)

    def test_floating_bones_are_linked_by_their_own_joint(self):
        """La rotula y la escapula no se tocan con su padre, pero cada una tiene su articulacion (femororrotuliana; AC, glenohumeral y escapulotoracica)."""
        for side in "LR":
            self.assertTrue(any(f"patella.{side}" in j.bones and f"femur.{side}" in j.bones for j in self.art.joints.values()))
            for other in (f"clavicle.{side}", f"humerus.{side}"):
                self.assertTrue(any(f"scapula.{side}" in j.bones and other in j.bones for j in self.art.joints.values()), other)

    def test_every_level1_bone_is_in_at_least_one_natural_joint_or_is_a_known_rigid_bone(self):
        articulated = {b for j in self.art.joints.values() for b in j.bones}
        loose = sorted(n for n in self.anat.bones if n not in articulated)
        # los huesos largos y vertebras estan siempre en alguna articulacion; solo quedan sin ella los que se articulan con
        # estructuras no modeladas como hueso (nada en esta lista de 185 huesos): debe estar vacia
        self.assertEqual(loose, [])


if __name__ == "__main__":
    unittest.main()
