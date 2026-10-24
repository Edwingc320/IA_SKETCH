"""Piernas y pies: jerarquia anatomica, cadenas de dedos a pocos mm del suelo y puntos de union (modelo oseo, sin musculos)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations, validation  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

TARSAL_PARENT = {"talus": "tibia", "calcaneus": "talus", "navicular": "talus", "cuboid": "calcaneus", "medial_cuneiform": "navicular",
                 "intermediate_cuneiform": "navicular", "lateral_cuneiform": "navicular"}
METATARSAL_TARSAL = {1: "medial_cuneiform", 2: "intermediate_cuneiform", 3: "lateral_cuneiform", 4: "cuboid", 5: "cuboid"}
FLOOR_TOL = 0.012  # las puntas de los dedos quedan a menos de 12 mm del suelo


def build_all():
    base = build_model(load_config())
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    return base, anat, articulations.build_articulations(base, anat, articulations.load_articulation_data())


class TestLegFootHierarchy(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()
        self.b = self.anat.bones

    def test_bone_counts_per_side(self):
        for s in "LR":
            legs = [f"{n}.{s}" for n in ("femur", "patella", "tibia", "fibula")]
            tarsus = [f"{n}.{s}" for n in TARSAL_PARENT]
            mt = [f"metatarsal_{k}.{s}" for k in range(1, 6)]
            toes = [f"toe_{k}_{p}.{s}" for k in range(1, 6) for p in (("proximal", "distal") if k == 1 else ("proximal", "middle", "distal"))]
            for n in legs + tarsus + mt + toes:
                self.assertIn(n, self.b, n)
            self.assertEqual(len(legs + tarsus + mt + toes), 4 + 7 + 5 + 14)

    def test_thigh_and_leg_chain(self):
        for s in "LR":
            self.assertEqual(self.b[f"femur.{s}"].anatomical_parent, f"ilium.{s}")  # coxofemoral
            for n in ("tibia", "fibula", "patella"):
                self.assertEqual(self.b[f"{n}.{s}"].anatomical_parent, f"femur.{s}", n)  # rodilla; la rotula cuelga del femur
            self.assertEqual(self.b[f"patella.{s}"].parent, f"thigh.{s}")

    def test_patella_floats_in_front_of_the_knee(self):
        knee = self.base.joints["knee.L"].pivot
        p = self.b["patella.L"]
        for pt in (p.head, p.tail):
            self.assertLess(pt[1], knee[1] - 0.03)  # delante (-Y) de la rodilla
            self.assertLess(abs(pt[2] - knee[2]), 0.06)  # a la altura de la articulacion
            self.assertLess(abs(pt[0] - knee[0]), 0.01)

    def test_tarsus_and_metatarsus_hierarchy(self):
        for s in "LR":
            for n, parent in TARSAL_PARENT.items():
                self.assertEqual(self.b[f"{n}.{s}"].anatomical_parent, f"{parent}.{s}", n)
            self.assertEqual(self.b[f"talus.{s}"].parent, f"foot.{s}")  # el rig lo mueve con el segmento base
            for k, tarsal in METATARSAL_TARSAL.items():
                self.assertEqual(self.b[f"metatarsal_{k}.{s}"].parent, f"{tarsal}.{s}", k)

    def test_talus_sits_at_the_distal_tibia_and_fibula(self):
        ankle = self.base.joints["ankle.L"].pivot
        self.assertLess(length(sub(self.b["talus.L"].head, ankle)), 0.02)
        self.assertLess(abs(self.b["tibia.L"].tail[2] - ankle[2]), 1e-12)
        self.assertGreater(self.b["fibula.L"].tail[0], self.b["tibia.L"].tail[0])  # maleolo lateral fuera del medial

    def test_toe_chains_are_exact_and_reach_near_the_floor(self):
        for s in "LR":
            for k in range(1, 6):
                phalanges = ["proximal", "distal"] if k == 1 else ["proximal", "middle", "distal"]
                prev = f"metatarsal_{k}.{s}"
                for p in phalanges:
                    bone = self.b[f"toe_{k}_{p}.{s}"]
                    self.assertEqual(bone.parent, prev, f"toe_{k}_{p}")
                    self.assertLess(length(sub(bone.head, self.b[prev].tail)), 1e-12, f"toe_{k}_{p}")
                    prev = f"toe_{k}_{p}.{s}"
                tip = self.b[f"toe_{k}_distal.{s}"].tail
                self.assertGreater(tip[2], 0.0)
                self.assertLess(tip[2], FLOOR_TOL, f"toe_{k}")  # punta a menos de 12 mm del suelo


class TestLegFootUnions(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()

    def region(self, store):
        return {n: x for n, x in store.items() if x.region == "leg_foot"}

    def test_counts_and_validation(self):
        self.assertEqual(len(self.region(self.art.joints)), 28 * 2)
        self.assertEqual(len(self.region(self.art.ligaments)), 29 * 2)
        self.assertEqual(len(self.region(self.art.attachments)), 11 * 2)
        issues = validation.validate_articulations(self.base, self.anat, self.art)
        self.assertEqual([i for i in issues if i.severity == "error"], [])

    def test_every_independent_joint_is_covered(self):
        j = self.art.joints
        names = ["tibiofemoral", "patellofemoral", "proximal_tibiofibular", "distal_tibiofibular", "talocrural", "subtalar", "talonavicular",
                 "calcaneocuboid", "cuneonavicular", "interphalangeal_1", "metatarsophalangeal_1"]
        names += [f"tarsometatarsal_{k}" for k in range(1, 6)]
        names += [f"{p}_{k}" for k in range(2, 6) for p in ("metatarsophalangeal", "proximal_interphalangeal", "distal_interphalangeal")]
        for s in "LR":
            for n in names:
                self.assertIn(f"{n}.{s}", j, n)

    def test_rig_drivers_and_centers(self):
        j = self.art.joints
        for s in "LR":
            for n, driver in (("tibiofemoral", "knee"), ("talocrural", "ankle")):
                joint = j[f"{n}.{s}"]
                self.assertEqual(joint.rig_driver, f"{driver}.{s}")
                self.assertLess(length(sub(joint.center, self.base.joints[joint.rig_driver].pivot)), 1e-12, n)
            self.assertLess(length(sub(j[f"metatarsophalangeal_3.{s}"].center, self.anat.bones[f"metatarsal_3.{s}"].tail)), 1e-12)
            self.assertLess(length(sub(j[f"distal_interphalangeal_4.{s}"].center, self.anat.bones[f"toe_4_middle.{s}"].tail)), 1e-12)

    def test_published_ranges_units_and_sources(self):
        d = lambda jn: {x.name: x for x in self.art.joints[jn].dofs}  # noqa: E731
        self.assertEqual(d("tibiofemoral.L")["flexion"].total_deg, (135, 140))
        self.assertEqual((d("tibiofemoral.R")["rotacion_interna"].total_deg, d("tibiofemoral.R")["rotacion_externa"].total_deg), ((25, 25), (18, 18)))
        self.assertEqual(d("talocrural.L")["flexion_plantar"].total_deg, (50, 50))
        self.assertEqual(d("talocrural.L")["dorsiflexion"].total_deg, (20, 40))  # las fuentes discrepan: se guarda el rango
        self.assertEqual(d("subtalar.L")["inversion"].total_deg, (30, 60))
        self.assertEqual(d("metatarsophalangeal_1.L")["extension_dorsiflexion"].total_deg, (70, 90))
        pt = d("proximal_tibiofibular.L")["traslacion"]
        self.assertEqual((pt.total_deg, pt.unit), ((1, 3), "mm"))
        self.assertIsNone(d("tarsometatarsal_2.L")["deslizamiento"].total_deg)  # sin cifra: no se inventa
        self.assertIsNone(d("metatarsophalangeal_3.L")["flexion_extension"].total_deg)
        weak = {k for k, s in self.art.sources.items() if s["reliability"] == "baja"}
        for store in (self.art.ligaments, self.art.attachments):
            for x in self.region(store).values():
                if set(x.sources) <= weak:
                    self.assertIn("verificar", x.notes.lower(), x.name)
        self.assertIn("verificar", d("talonavicular.L")["inversion_eversion_mediotarsiana"].note.lower())

    def test_ligaments_attach_where_described(self):
        lg, b = self.art.ligaments, self.anat.bones
        ends = lambda n: (lg[n].from_bone, lg[n].to_bone)  # noqa: E731
        for s in "LR":
            sign = 1 if s == "L" else -1
            self.assertEqual(ends(f"anterior_cruciate.{s}"), (f"femur.{s}", f"tibia.{s}"))
            self.assertEqual(ends(f"posterior_cruciate.{s}"), (f"femur.{s}", f"tibia.{s}"))
            self.assertEqual(ends(f"patellar.{s}"), (f"patella.{s}", f"tibia.{s}"))
            self.assertEqual(ends(f"fibular_collateral.{s}")[1], f"fibula.{s}")
            self.assertEqual(ends(f"aitfl.{s}"), (f"tibia.{s}", f"fibula.{s}"))
            for part, bone in (("tibiotalar", "talus"), ("tibionavicular", "navicular"), ("tibiocalcaneal", "calcaneus")):
                self.assertEqual(ends(f"deltoid_{part}.{s}"), (f"tibia.{s}", f"{bone}.{s}"), part)
            self.assertEqual(ends(f"atfl.{s}"), (f"fibula.{s}", f"talus.{s}"))
            self.assertEqual(ends(f"cfl.{s}"), (f"fibula.{s}", f"calcaneus.{s}"))
            self.assertEqual(ends(f"spring_ligament.{s}"), (f"calcaneus.{s}", f"navicular.{s}"))
            self.assertEqual(ends(f"lisfranc.{s}"), (f"medial_cuneiform.{s}", f"metatarsal_2.{s}"))
            self.assertEqual({lg[f"plantar_fascia_{k}.{s}"].to_bone for k in range(1, 6)}, {f"toe_{k}_proximal.{s}" for k in range(1, 6)})
            # cruzados: el anterior parte del lado lateral del femur y el posterior del medial; colaterales: lateral fuera, medial dentro
            self.assertGreater(sign * (lg[f"anterior_cruciate.{s}"].a[0] - lg[f"posterior_cruciate.{s}"].a[0]), 0.01)  # al menos 1 cm de separacion
            self.assertGreater(sign * (lg[f"fibular_collateral.{s}"].a[0] - lg[f"tibial_collateral.{s}"].a[0]), 0.03)
            # deltoideo medial; ligamento lateral del tobillo lateral
            self.assertLess(sign * lg[f"deltoid_tibiotalar.{s}"].a[0], sign * lg[f"cfl.{s}"].a[0])
            # ATFL por delante y PTFL por detras del eje del tobillo
            ankle_y = self.base.joints[f"ankle.{s}"].pivot[1]
            self.assertLess(lg[f"atfl.{s}"].b[1], ankle_y)
            self.assertGreater(lg[f"ptfl.{s}"].b[1], ankle_y - 0.001)
            # rotuliano baja de la rotula a la tuberosidad tibial
            self.assertGreater(lg[f"patellar.{s}"].a[2], lg[f"patellar.{s}"].b[2])

    def test_landmarks_sit_on_their_bones(self):
        at = self.art.attachments
        for s in "LR":
            sign = 1 if s == "L" else -1
            self.assertEqual(at[f"tibial_tuberosity.{s}"].bone, f"tibia.{s}")
            self.assertLess(at[f"tibial_tuberosity.{s}"].point[1], self.anat.bones[f"tibia.{s}"].head[1])  # anterior
            self.assertLess(sign * at[f"medial_malleolus.{s}"].point[0], sign * at[f"lateral_malleolus.{s}"].point[0])
            self.assertLess(sign * at[f"femoral_medial_epicondyle.{s}"].point[0], sign * at[f"femoral_lateral_epicondyle.{s}"].point[0])
            self.assertGreater(at[f"calcaneal_tuberosity.{s}"].point[1], at[f"navicular_tuberosity.{s}"].point[1])  # talon detras del navicular

    def test_symmetry(self):
        for store, pts in ((self.art.joints, lambda x: [x.center]), (self.art.ligaments, lambda x: [x.a, x.b]),
                           (self.art.attachments, lambda x: [x.point])):
            for n, x in self.region(store).items():
                if n.endswith(".L"):
                    for p, q in zip(pts(x), pts(store[n[:-2] + ".R"])):
                        self.assertLess(length(sub(mirror_point(p), q)), 1e-12, n)


if __name__ == "__main__":
    unittest.main()
