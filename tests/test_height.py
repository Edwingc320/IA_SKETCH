"""Altura como entrada reutilizable: unidades (m, cm, pies y pulgadas) y escala de todo el modelo oseo con la altura."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations, validation  # noqa: E402
from anatomical_core.config import ConfigError, load_config, parse_height  # noqa: E402
from anatomical_core.geometry import length, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402


def build_all(height):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    return base, anat, articulations.build_articulations(base, anat, articulations.load_articulation_data())


class TestParseHeight(unittest.TestCase):
    def test_units(self):
        for text, meters in (("1.70", 1.70), ("1,70", 1.70), ("1.70m", 1.70), ("170cm", 1.70), ("170 CM", 1.70), ("1700mm", 1.70),
                             ("5ft7in", 1.7018), ("5 ft 7 in", 1.7018), ("5'7\"", 1.7018), ("5'7", 1.7018), ("5ft", 1.524),
                             ("67in", 1.7018), ("6 feet", 1.8288)):
            self.assertAlmostEqual(parse_height(text), meters, places=4, msg=text)
        self.assertEqual(parse_height(1.8), 1.8)

    def test_ambiguous_or_invalid_values_are_rejected(self):
        for bad in ("170", 170, "5.7", "abc", "", "0", "-1.7", "nan", "5ft7in8", "9 m"):
            with self.assertRaises(ConfigError, msg=repr(bad)):
                parse_height(bad)

    def test_load_config_accepts_text(self):
        self.assertAlmostEqual(build_model(load_config(height_m="5ft7in")).height_m, 1.7018, places=4)


class TestWholeBoneModelScalesWithHeight(unittest.TestCase):
    """Todo lo oseo (base, nivel 1, articulaciones, ligamentos y hitos) se deduce de la altura y sigue siendo valido."""

    def test_valid_at_several_heights(self):
        for height in ("1.50m", "5ft7in", "1.70", "1.90m", "2.05m"):
            base, anat, art = build_all(height)
            issues = validation.validate_model(base) + validation.validate_anatomy(base, anat) + validation.validate_articulations(base, anat, art)
            self.assertEqual([i for i in issues if i.severity == "error"], [], height)

    def test_every_point_scales_linearly(self):
        base0, anat0, art0 = build_all("1.75m")
        base1, anat1, art1 = build_all("5ft7in")
        k = base1.height_m / base0.height_m
        self.assertAlmostEqual(k, 1.7018 / 1.75, places=6)
        for n, b in anat0.bones.items():
            self.assertLess(length(sub(tuple(k * c for c in b.head), anat1.bones[n].head)), 1e-9, n)
            self.assertLess(length(sub(tuple(k * c for c in b.tail), anat1.bones[n].tail)), 1e-9, n)
        for store0, store1, pts in ((art0.joints, art1.joints, lambda x: [x.center]), (art0.ligaments, art1.ligaments, lambda x: [x.a, x.b]),
                                    (art0.attachments, art1.attachments, lambda x: [x.point])):
            for n, x in store0.items():
                for p, q in zip(pts(x), pts(store1[n])):
                    self.assertLess(length(sub(tuple(k * c for c in p), q)), 1e-9, n)

    def test_ranges_do_not_scale_with_height(self):
        """Los angulos publicados son los mismos a cualquier altura (solo se escalan longitudes y tolerancias)."""
        _, _, a0 = build_all("1.60m")
        _, _, a1 = build_all("1.95m")
        for n, j in a0.joints.items():
            self.assertEqual([(d.name, d.total_deg) for d in j.dofs], [(d.name, d.total_deg) for d in a1.joints[n].dofs], n)
        for n, j in a0.joints.items():
            self.assertAlmostEqual(a1.joints[n].tolerance_m / j.tolerance_m, 1.95 / 1.60, places=6, msg=n)


if __name__ == "__main__":
    unittest.main()
