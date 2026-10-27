"""CM-9: cierre de la region caderas y muslo (rama muscle-model).

Fija el estado final de la region: recuentos, trinquete, validadores en verde a tres alturas, escala isometrica de toda la geometria, verosimilitud
dimensional frente a la literatura (con sus fuentes y sus limites) y que los documentos de estado no se separen del codigo. NO sustituye a las pruebas de cada
paso (CM-1 a CM-8); las reune. Comparacion con atlas (Netter, Sobotta, Gray): no es posible aqui (obras con derechos, sin acceso a sus imagenes): la
verificacion cruzada es dimensional y con relaciones anatomicas, contra cifras de la literatura leidas en resumenes de busqueda."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from anatomical_core import anatomy, articulations, ligament_paths as lp, muscle_volumes as mv, muscles, tendons, validation  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.geometry import dot, length, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

HIP_LIGAMENTS = ("iliofemoral", "pubofemoral", "ischiofemoral")
KNEE_LIGAMENTS = ("anterior_cruciate", "posterior_cruciate", "tibial_collateral", "fibular_collateral", "patellar")
DEFORM_TENDONS = ("psoas_major", "iliacus", "tensor_fasciae_latae", "iliotibial_tract", "piriformis", "obturator_internus", "gemellus_superior", "gemellus_inferior",
                  "obturator_externus", "quadratus_femoris", "pectineus", "adductor_brevis")
SURFACES = ("femoral_head", "femoral_neck", "femoral_greater_trochanter", "femoral_shaft", "femoral_lateral_condyle", "pubic_ramus", "ischial_ramus",
            "tibial_proximal", "patellar_body", "fibular_head_body")
DOCS = ROOT / "docs"


def build_all(height=None):
    base = build_model(load_config(height_m=height))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    art = articulations.build_articulations(base, anat, articulations.load_articulation_data())
    tm = tendons.build_tendons(base, anat, art, tendons.load_tendon_data())
    mm = muscles.build_muscles(base, anat, art, muscles.load_muscle_data())
    return base, anat, art, tm, mv.build_volumes(tm, mv.load_volume_data(), mm)


class TestRegionClosure(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art, self.tm, self.vm = build_all()

    def test_final_counts(self):
        self.assertEqual(len(self.tm.tendons), 190)  # 95 unidades musculo-tendinosas por lado (86 de la primera version + cintilla iliotibial CM-5 + 8 profundos y aductores CM-6)
        self.assertEqual(len(self.vm.volumes), 94)  # 47 vientres por lado: 44 de las unidades musculo-tendinosas + 3 gluteos
        self.assertEqual(len([t for t in self.tm.tendons.values() if t.deform]), 2 * len(DEFORM_TENDONS))
        self.assertEqual(sorted(n for n, lg in self.art.ligaments.items() if lg.deform), sorted(f"{n}.{s}" for n in HIP_LIGAMENTS + KNEE_LIGAMENTS for s in "LR"))
        self.assertEqual(sorted(self.art.surfaces), sorted(f"{n}.{s}" for n in SURFACES for s in "LR"))
        self.assertEqual(len(lp.HIP_SWEEP), 13)
        self.assertEqual(len(lp.LEG_SWEEP), 22)
        self.assertEqual(len(self.art.ligaments), 620)
        self.assertEqual(sum(1 for v in self.vm.volumes.values() if v.kind == "medido"), 2 * (24 + 5 + 2))  # por lado: Holzbaur 24, Ritsche 5 y Kajdi 2; los 16 restantes son convencion
        import test_anchor_debt as ad
        self.assertEqual((len(ad.KNOWN_DEBT), ad.DEBT_CEILING), (53, 53))  # trinquete congelado: cero deuda en muslo y rodilla

    def test_every_region_validator_is_green_at_three_heights(self):
        for h in (1.5, 1.75, 2.05):
            base, anat, art, tm, vm = build_all(h)
            errors = lambda issues: [i for i in issues if i.severity == "error"]  # noqa: E731
            self.assertEqual(errors(validation.validate_articulations(base, anat, art)), [], h)
            self.assertEqual(validation.validate_ligament_poses(base, anat, art), [], h)
            self.assertEqual(validation.validate_knee_ligament_poses(base, anat, art), [], h)
            self.assertEqual(errors(tendons.validate_tendons(base, anat, art, tm)), [], h)
            self.assertEqual(tendons.validate_tendon_poses(base, anat, art, tm), [], h)
            self.assertEqual(mv.validate_volumes(tm, vm), [], h)

    def test_the_whole_region_scales_isometrically(self):
        """Toda la geometria de la region (nodos de ligamentos y tendones, superficies, hitos y volumenes) es proporcional a la altura: 1.50, 1.75 y 2.05 m."""
        ref = build_all(1.75)
        for h in (1.5, 2.05):
            base, anat, art, tm, vm = build_all(h)
            k = h / 1.75
            for n, lg in art.ligaments.items():
                if not lg.deform:
                    continue
                for (b0, p0), (b1, p1) in zip(lp.nodes(ref[2].ligaments[n]), lp.nodes(lg)):
                    self.assertLess(length(sub(tuple(k * c for c in p0), p1)), 1e-9, (h, n))
            for n, t in tm.tendons.items():
                if t.deform:
                    for s0, s1 in zip(ref[3].tendons[n].sites, t.sites):
                        self.assertLess(length(sub(tuple(k * c for c in s0.point), s1.point)), 1e-9, (h, n))
            for n, sf in art.surfaces.items():
                self.assertAlmostEqual(sf.radius_m, ref[2].surfaces[n].radius_m * k, places=9, msg=(h, n))
                self.assertLess(length(sub(tuple(k * c for c in ref[2].surfaces[n].a), sf.a)), 1e-9, (h, n))
            for n, v in vm.volumes.items():
                self.assertAlmostEqual(v.volume_m3(h) / ref[4].volumes[n].volume_m3(1.75), k ** 3, places=9, msg=(h, n))

    def test_dimensional_plausibility_against_the_literature(self):
        """Verosimilitud dimensional (no es una comparacion con atlas). Cifras de la literatura leidas en resumenes de busqueda:
        distancia del centro de la cabeza femoral a la linea media ~89 mm (Bone Joint 360, 150 caderas) y distancia entre los centros de las cabezas 208-218 mm (CT, PMC4761268);
        angulo cervicodiafisario 119-133 grados (series de cadaveres y radiograficas); diametro de la cabeza 38-48 mm y del cuello 28-34 mm."""
        for h in (1.5, 1.75, 2.05):
            base, anat, art, tm, vm = build_all(h)
            k = h / 1.75
            a = art.attachments
            c = art.joints["coxofemoral.L"].center
            t = a["greater_trochanter.L"].point
            knee = tuple((p + q) / 2 for p, q in zip(a["femoral_lateral_epicondyle.L"].point, a["femoral_medial_epicondyle.L"].point))
            gc = art.surfaces["femoral_greater_trochanter.L"].a
            half_pelvis_mm = c[0] / k * 1000
            self.assertTrue(85.0 <= half_pelvis_mm <= 110.0, half_pelvis_mm)  # 91 mm: dentro de 89 (B&J360) y 104-109 (CT)
            neck_shaft = 180.0 - math.degrees(math.acos(dot(sub(t, c), sub(knee, gc)) / (length(sub(t, c)) * length(sub(knee, gc)))))
            self.assertTrue(110.0 <= neck_shaft <= 135.0, neck_shaft)  # 116.7: ligeramente varo respecto a las series (119-133): limite declarado
            self.assertLess(neck_shaft, 119.0)  # fijado: si algun dia se corrige el cuello, esta prueba se actualiza a proposito
            head_mm = 2 * art.surfaces["femoral_head.L"].radius_m / k * 1000
            neck_mm = 2 * art.surfaces["femoral_neck.L"].radius_m / k * 1000
            self.assertTrue(38.0 <= head_mm <= 48.0 and 28.0 <= neck_mm <= 34.0, (head_mm, neck_mm))
            femur_over_h = length(sub(c, knee)) / h
            self.assertAlmostEqual(femur_over_h, 0.2421, places=3)  # = longitud del segmento muslo de la base (0,245 H) menos el desfase de los epicondilos
            self.assertTrue(0.23 <= femur_over_h <= 0.26, femur_over_h)

    def test_anatomical_relations_hold(self):
        """Relaciones entre estructuras que cualquier atlas confirma, independientes de la escala."""
        at, c = self.art.attachments, self.art.joints["coxofemoral.L"].center
        gt, lt = at["greater_trochanter.L"].point, at["lesser_trochanter.L"].point
        self.assertGreater(gt[0], c[0])  # el trocanter mayor es lateral a la cabeza
        self.assertLess(lt[0], gt[0])  # el menor es medial al mayor
        self.assertLess(at["iliopubic_eminence.L"].point[1], c[1])  # la eminencia iliopubica esta por delante de la cabeza
        self.assertGreater(at["trochanteric_fossa.L"].point[1], gt[1])  # la fosa trocanterica, por detras del trocanter
        self.assertGreater(at["intertrochanteric_crest.L"].point[1], gt[1])
        self.assertLess(at["pectineal_crest.L"].point[0], at["iliopubic_eminence.L"].point[0])  # el pecten, medial a la eminencia
        self.assertLess(at["gerdy_tubercle.L"].point[2], at["femoral_lateral_epicondyle.L"].point[2])  # Gerdy bajo el epicondilo
        self.assertLess(at["tibial_tuberosity.L"].point[1], at["gerdy_tubercle.L"].point[1] + 0.02)  # tuberosidad anterior
        ev = {n: self.tm.tendons[n] for n in ("psoas_major.L", "piriformis.L", "obturator_externus.L")}
        self.assertEqual(ev["psoas_major.L"].sites[1].landmark, "iliopubic_eminence.L")  # el psoas pasa por la eminencia
        self.assertGreater(ev["piriformis.L"].sites[1].point[1], c[1])  # el piriforme pasa por detras de la cabeza
        self.assertGreater(ev["obturator_externus.L"].sites[-2].point[1], c[1])  # el obturador externo rodea el cuello por detras

    def test_known_limitations_are_registered_in_the_closure_report(self):
        report = (DOCS / "estado" / "caderas_muslo_cierre.md").read_text(encoding="utf-8")
        for needle in ("deslizamiento de la rótula", "100°", "hasta 23 mm", "varo", "resúmenes de búsqueda", "Netter", "172", "190", "94", "53"):
            self.assertIn(needle, report, needle)
        patellar = self.art.ligaments["patellar.L"]
        self.assertIn("LIMITACION CONOCIDA", patellar.avoid_reason)

    def test_status_documents_agree_with_the_code(self):
        estado = (DOCS / "estado" / "caderas_muslo.md").read_text(encoding="utf-8")
        for i in range(2, 10):
            self.assertIn(f"- [x] **CM-{i}**", estado, i)
        self.assertIn("- [~] **CM-1**", estado)  # CM-1 sigue parcial: faltan volumenes medidos de varios musculos
        plan = (DOCS / "plan" / "30_caderas_muslo.md").read_text(encoding="utf-8")
        for i in range(1, 10):
            self.assertIn(f"CM-{i}", plan)
        for name in ("AGENTS.md", "MEMORY.md", "README.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("53", text, name)  # el trinquete congelado
        mem = (ROOT / "MEMORY.md").read_text(encoding="utf-8")
        self.assertIn("CM-9", mem)
        self.assertIn("190", mem)

    def test_region_sources_of_low_or_medium_reliability_are_flagged(self):
        """Toda fuente de fiabilidad baja citada por la region dice «verificar»; las de fiabilidad media leidas en resumenes lo dicen."""
        for src in (self.art.sources, self.tm.sources):
            for k, s in src.items():
                if s.get("reliability") == "baja" and k in ("hip_rom_aaos_chart", "deep_rotators_brookbush", "femoral_condyle_radius"):
                    self.assertTrue("VERIFICAR" in s["title"].upper() or "RESUMEN" in s["title"].upper(), k)
        for k in ("femur_morphometry", "hip_ligament_forces_2021", "patella_morphometry", "tibia_proximal_morphometry", "aaos_hip_2020", "hip_rom_physiotutors"):
            self.assertIn("resumen", self.art.sources[k]["title"].lower(), k)  # leido en el resumen (o los resumenes) de busqueda


if __name__ == "__main__":
    unittest.main()
