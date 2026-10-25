"""CM-1: mediciones de volumen muscular de la literatura (config/muscles/volume_measurements.json): esquema, trazabilidad y honestidad.

El archivo recoge lo encontrado, con su estado de verificacion, y NO alimenta todavia los volumenes del modelo (eso es CM-2). Las pruebas
exigen que cada cifra tenga fuente con DOI, que lo derivado se pueda recalcular, que lo no verificado este marcado y que ninguna cifra
sin verificar llegue a muscle_volumes.json."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import tendons  # noqa: E402

DATA = json.loads((ROOT / "config" / "muscles" / "volume_measurements.json").read_text(encoding="utf-8"))
VOLUMES = json.loads((ROOT / "config" / "muscles" / "muscle_volumes.json").read_text(encoding="utf-8"))
M = {m["id"]: m for m in DATA["measurements"]}


class TestVolumeMeasurements(unittest.TestCase):
    def test_every_source_has_doi_https_url_and_reliability(self):
        for k, s in DATA["sources"].items():
            self.assertRegex(s["doi"], r"^10\.\d{4,9}/\S+$", k)
            self.assertTrue(s["url"].startswith("https://"), k)
            self.assertIn(s["reliability"], ("alta", "media", "baja"), k)
            self.assertTrue(s["title"], k)

    def test_every_measurement_has_a_known_source_a_population_and_a_verification_state(self):
        for i, m in M.items():
            self.assertIn(m["source"], DATA["sources"], i)
            self.assertIn(m["verified"], (True, False), i)
            self.assertTrue(m["population"] and m["method"], i)
            if m.get("value_cm3") is not None:
                self.assertGreater(m["value_cm3"], 0, i)
                if m["sd"] is not None:
                    self.assertLess(m["sd"], m["value_cm3"], i)
            if not m["verified"]:
                self.assertTrue(m.get("derived") or "NO USAR" in m["notes"], i)  # lo no verificado lo dice

    def test_verified_values_are_the_ones_read_in_the_sources(self):
        expected = {"ritsche_vl": 636.5, "ritsche_bf": 197.4, "ritsche_gm": 224.7, "ritsche_gl": 112.6, "ritsche_ta": 119.4,
                    "kajdi_gmed_f": 270.1, "kajdi_gmed_m": 408.1, "kajdi_gmin_f": 77.2, "kajdi_gmin_m": 107.1}
        for i, v in expected.items():
            self.assertEqual((M[i]["value_cm3"], M[i]["verified"]), (v, True), i)
        self.assertEqual(M["trappe_fractions_young"]["fractions_percent"], {"rectus_femoris": 10.0, "vastus_lateralis": 33.0, "vastus_intermedius": 31.0, "vastus_medialis": 26.0})
        self.assertAlmostEqual(sum(M["trappe_fractions_young"]["fractions_percent"].values()), 100.0)

    def test_the_set_of_verified_ids_is_pinned(self):
        """Pasar una cifra a verificada exige leerla en el articulo y tocar esta lista a proposito."""
        self.assertEqual({i for i, m in M.items() if m["verified"]}, {"ritsche_vl", "ritsche_bf", "ritsche_gm", "ritsche_gl", "ritsche_ta", "trappe_fractions_young",
                                                                       "kajdi_gmed_f", "kajdi_gmed_m", "kajdi_gmin_f", "kajdi_gmin_m"})

    def test_derived_values_can_be_recomputed_and_say_they_mix_populations(self):
        fr = M["trappe_fractions_young"]["fractions_percent"]
        for i, head in (("derived_rf", "rectus_femoris"), ("derived_vi", "vastus_intermedius"), ("derived_vm", "vastus_medialis")):
            m = M[i]
            self.assertTrue(m["derived"] and not m["verified"], i)
            self.assertEqual(m["derived_from"], ["ritsche_vl", "trappe_fractions_young"])
            self.assertAlmostEqual(m["value_cm3"], M["ritsche_vl"]["value_cm3"] * fr[head] / fr["vastus_lateralis"], delta=0.06, msg=i)
            self.assertIn("estimacion", m["notes"].lower() + " " + M["derived_rf"]["notes"].lower())  # vi y vm dicen "Idem": rf lo declara
            self.assertIn("poblaciones", m["population"])

    def test_the_gluteal_values_declare_that_the_population_is_not_young_and_healthy(self):
        self.assertIn("65,0", M["kajdi_gmed_f"]["population"])
        self.assertIn("NO es un adulto joven", M["kajdi_gmed_f"]["notes"])
        for i in ("kajdi_gmed_m", "kajdi_gmin_f", "kajdi_gmin_m"):
            self.assertTrue(M[i]["population"].startswith("igual"), i)  # remiten a la poblacion declarada arriba
        self.assertGreater(M["kajdi_gmed_m"]["value_cm3"], M["kajdi_gmed_f"]["value_cm3"])  # los hombres tienen mas volumen
        self.assertGreater(M["kajdi_gmin_m"]["value_cm3"], M["kajdi_gmin_f"]["value_cm3"])

    def test_units_exist_and_the_not_found_list_is_exactly_what_has_no_verified_value(self):
        cfg = ROOT / "config" / "muscles"
        names = [u["name"] for f in tendons.FILES for u in json.loads((cfg / f"{f}.json").read_text(encoding="utf-8"))["tendons"]]
        names += [u["name"] for u in json.loads((cfg / "gluteal.json").read_text(encoding="utf-8"))["muscles"]]  # los gluteos no son unidades de tendon
        unit_names = {re.sub(r"\.[LR]$", "", n) for n in names}
        for i, m in M.items():
            if m.get("unit"):
                self.assertIn(m["unit"], unit_names, i)
        with_value = {m["unit"] for m in M.values() if m.get("unit") and m["verified"] and m.get("value_cm3")}
        listed = set(DATA["not_found"]["units"])
        self.assertEqual(listed & with_value, set())  # nada de lo listado como no encontrado tiene un valor verificado
        for u in listed:
            self.assertIn(u, unit_names, u)

    def test_nothing_unverified_reaches_the_model_volumes(self):
        measured = [m for m in VOLUMES["muscles"] if m["kind"] == "medido"]
        self.assertTrue(measured)
        self.assertEqual({m["source"] for m in measured}, {"holzbaur_2007"})  # CM-2 aun no ha aplicado nada de CM-1
        unverified = [m for m in M.values() if not m["verified"] and m.get("value_cm3")]
        self.assertTrue(unverified)
        for m in unverified:
            for v in VOLUMES["muscles"]:
                if v["unit"][:-2] == m.get("unit"):
                    self.assertEqual(v["kind"], "convencion", m["id"])

    def test_the_conventions_overestimate_what_was_measured(self):
        """Hallazgo de CM-1: las clases de convencion de la pierna estaban por encima de lo medido (el tibial anterior, mas del doble)."""
        cls = VOLUMES["size_classes_cm3"]
        by_unit = {v["unit"][:-2]: v for v in VOLUMES["muscles"] if v["unit"].endswith(".L")}
        ratios = {}
        for i in ("ritsche_vl", "ritsche_bf", "ritsche_gm", "ritsche_gl", "ritsche_ta"):
            conv = cls[by_unit[M[i]["unit"]]["size_class"]]
            ratios[i] = M[i]["value_cm3"] / conv
        self.assertLess(ratios["ritsche_ta"], 0.5)  # tibial anterior: la clase 'grande' (350) es casi el triple de lo medido (119,4)
        self.assertTrue(all(0.2 < r < 1.2 for r in ratios.values()), ratios)


if __name__ == "__main__":
    unittest.main()
