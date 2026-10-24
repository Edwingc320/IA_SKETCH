"""Puntos de union del torax y la cintura escapular (articulaciones, ligamentos, inserciones). Python puro."""
import collections
import dataclasses
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from anatomical_core import anatomy, articulations, validation  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.geometry import length, mirror_point, sub  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

H = 1.75


def build_all(**kw):
    base = build_model(load_config(**kw))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    return base, anat, articulations.build_articulations(base, anat, articulations.load_articulation_data())


def codes(issues, severity="error"):
    return [i.code for i in issues if i.severity == severity]


def mid(b):
    return tuple((x + y) / 2 for x, y in zip(b.head, b.tail))


class TestArticulationData(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()

    def region(self, store):
        return {n: x for n, x in store.items() if x.region == "thorax_shoulder"}

    def test_counts(self):
        per_side = 4 + 12 + 10 + 7 + 3  # cintura escapular + costovertebrales + costotransversas + esternocostales + intercondrales
        central = 2 + 13  # manubrioesternal, xifoesternal + 13 segmentos intervertebrales C7/T1..T12/L1
        self.assertEqual(len(self.region(self.art.joints)), 2 * per_side + central)
        self.assertEqual(len(self.region(self.art.ligaments)), 2 * 5 + 1)  # 5 por lado + interclavicular
        self.assertEqual(len(self.region(self.art.attachments)), 36)  # 18 hitos oseos por lado; los musculos estan en muscle-model

    def test_validation_has_no_errors_and_no_warnings_on_the_corrected_base(self):
        """Base v2: la clavicula va del manubrio al acromion, asi que ya no hay huecos ni ligamentos de longitud
        absurda (antes: 4 avisos de hueco esternoclavicular/acromioclavicular y 2 de ligamento costoclavicular)."""
        issues = validation.validate_articulations(self.base, self.anat, self.art)
        self.assertEqual(codes(issues), [])
        self.assertEqual(collections.Counter(codes(issues, "warning")), {})
        j, lg = self.art.joints, self.art.ligaments
        for s in "LR":
            self.assertLess(length(sub(j[f"sternoclavicular.{s}"].center, self.anat.bones["sternum"].head)), 0.025)  # antes 86 mm
            self.assertLess(length(sub(j[f"acromioclavicular.{s}"].center, self.base.bones[f"clavicle.{s}"].tail)), 1e-9)  # antes 30 mm
            self.assertLess(length(sub(lg[f"costoclavicular.{s}"].a, lg[f"costoclavicular.{s}"].b)), 0.030)  # antes 89 mm (real ~15)
        self.assertTrue(all(not x.known_limitation for x in j.values() if x.region == "thorax_shoulder"))

    def test_every_number_has_a_source_and_every_source_is_used(self):
        used = set()
        for j in self.art.joints.values():
            used |= set(j.sources)
            for d in j.dofs:
                if d.total_deg is not None:
                    self.assertIn(d.source, self.art.sources, f"{j.name}.{d.name}")
                    used.add(d.source)
        for x in list(self.art.ligaments.values()) + list(self.art.attachments.values()):
            used |= set(x.sources)
        self.assertEqual(used, set(self.art.sources))
        for k, s in self.art.sources.items():
            self.assertTrue(s["url"].startswith("https://"), k)
            self.assertIn(s["reliability"], ("alta", "media", "baja"))
        weak = {k for k, s in self.art.sources.items() if s["reliability"] == "baja"}
        for a in self.art.attachments.values():  # lo que solo se apoya en fuentes debiles lo dice en la nota
            if set(a.sources) <= weak:
                self.assertIn("verificar", a.notes.lower(), a.name)

    def test_rig_drivers_coincide_with_the_base_pivots(self):
        j = self.art.joints
        for s in "LR":
            self.assertEqual(j[f"glenohumeral.{s}"].rig_driver, f"shoulder.{s}")
            self.assertLess(length(sub(j[f"glenohumeral.{s}"].center, self.base.joints[f"shoulder.{s}"].pivot)), 1e-12)
            self.assertEqual(j[f"sternoclavicular.{s}"].rig_driver, f"sternoclavicular.{s}")
            self.assertLess(length(sub(j[f"sternoclavicular.{s}"].center, self.base.joints[f"sternoclavicular.{s}"].pivot)), 1e-12)
        self.assertLess(length(sub(j["intervertebral_C7_T1"].center, self.base.joints["neck"].pivot)), 1e-12)
        self.assertLess(length(sub(j["intervertebral_T12_L1"].center, self.base.joints["thoracic"].pivot)), 1e-12)
        drivers = sorted(n for n, x in self.region(j).items() if x.rig_driver)
        self.assertEqual(len(drivers), 6)  # el resto aun no tiene motor en la base (poses futuras)

    def test_published_ranges(self):
        j = self.art.joints
        sc = {d.name: d.total_deg for d in j["sternoclavicular.L"].dofs}
        self.assertEqual(sc, {"elevacion_depresion": (60.0, 60.0), "protraccion_retraccion": (35.0, 35.0), "rotacion_axial": (40.0, 40.0)})
        gh = {d.name: (d.total_deg, d.source) for d in j["glenohumeral.R"].dofs}
        self.assertEqual(gh["abduccion"], ((170.0, 180.0), "magee_rom"))
        self.assertEqual(gh["abduccion_solo_glenohumeral"], ((120.0, 120.0), "wjg_shr"))  # ritmo 2:1
        st = {d.name: d.total_deg for d in j["scapulothoracic.L"].dofs}
        self.assertEqual(st["rotacion_superior_inferior"], (60.0, 60.0))
        self.assertIsNone(st["protraccion_retraccion"])  # sin cifra en las fuentes: no se inventa
        wilke = lambda name: {d.name: d.total_deg for d in j[name].dofs}  # noqa: E731
        self.assertEqual(wilke("intervertebral_T1_T2")["flexion_extension"], (14.0, 14.0))
        self.assertEqual(wilke("intervertebral_T6_T7")["inclinacion_lateral"], (10.0, 12.0))  # T1-T7
        self.assertEqual(wilke("intervertebral_T7_T8")["inclinacion_lateral"], (8.0, 9.0))  # T7-T12
        self.assertEqual(wilke("intervertebral_T9_T10")["rotacion_axial"], (10.0, 12.0))  # T1-T10
        self.assertEqual(wilke("intervertebral_T10_T11")["rotacion_axial"], (7.0, 8.0))  # T10-T12
        cv_upper = {d.name: d.total_deg for d in j["costovertebral_03.L"].dofs}
        self.assertEqual(cv_upper["bomba_eje_transversal"], (10.0, 16.0))
        self.assertIsNone({d.name: d.total_deg for d in j["costovertebral_10.L"].dofs}["asa_de_cubo_eje_anteroposterior"])
        self.assertEqual(j["manubriosternal"].dofs, ())  # movimiento minimo: sin rango

    def test_sternum_landmarks_follow_the_sources(self):
        A = self.anat.bones
        st = A["sternum"]
        self.assertAlmostEqual(st.head[2], A["T2"].head[2], places=9)  # escotadura yugular: disco T2-T3
        self.assertAlmostEqual(st.tail[2], mid(A["T10"])[2], places=9)  # punta del xifoides: T10
        ms = self.art.joints["manubriosternal"].center
        self.assertAlmostEqual(ms[2], A["T4"].head[2], places=9)  # angulo esternal: disco T4-T5
        self.assertAlmostEqual(self.art.joints["xiphisternal"].center[2], mid(A["T9"])[2], places=9)
        rib2_cartilage = A["rib_02.L"].outline[-1]
        self.assertLess(abs(rib2_cartilage[2] - ms[2]), 1e-3)  # la 2a costilla llega al angulo esternal
        self.assertLess(st.head[1], A["T2"].head[1] - 0.05 * H)  # el esternon queda delante (-Y)

    def test_joint_centers_and_scapular_landmarks(self):
        A, j, at = self.anat.bones, self.art.joints, self.art.attachments
        for k in range(1, 13):
            self.assertLess(length(sub(j[f"costovertebral_{k:02d}.L"].center, A[f"rib_{k:02d}.L"].head)), 1e-12)
        glen = A["scapula.L"].head
        self.assertGreater(at["supraglenoid_tubercle.L"].point[2], glen[2])
        self.assertLess(at["infraglenoid_tubercle.L"].point[2], glen[2])
        self.assertLess(at["coracoid_process.L"].point[1], glen[1])  # coracoides anterior
        self.assertLess(abs(at["superior_angle.L"].point[2] - mid(A["T2"])[2]), 0.01)  # angulo superior ~ T2
        self.assertLess(abs(at["inferior_angle.L"].point[2] - mid(A["T7"])[2]), 0.01)  # angulo inferior ~ T7
        for n in ("acromion", "greater_tubercle", "deltoid_tuberosity"):
            self.assertGreater(at[f"{n}.L"].point[0], 0)
            self.assertLess(at[f"{n}.R"].point[0], 0)

    def test_symmetry(self):
        for store, pts in ((self.art.joints, lambda x: [x.center]), (self.art.ligaments, lambda x: [x.a, x.b]),
                           (self.art.attachments, lambda x: [x.point])):
            pairs = 0
            for n, x in store.items():
                if ".L" in n:
                    for p, q in zip(pts(x), pts(store[n.replace(".L", ".R")])):
                        self.assertLess(length(sub(mirror_point(p), q)), 1e-12, n)
                    pairs += 1
            self.assertGreater(pairs, 0)

    def test_scales_with_the_base(self):
        base, anat, art = build_all(height_m=1.90)
        self.assertEqual(codes(validation.validate_articulations(base, anat, art)), [])
        self.assertLess(length(sub(art.joints["glenohumeral.L"].center, base.joints["shoulder.L"].pivot)), 1e-12)


class TestScapulaDoesNotCollide(unittest.TestCase):
    def test_clearance_and_detection(self):
        base, anat, _ = build_all()
        for s in "LR":
            self.assertGreater(anatomy.scapula_rib_clearance(anat, s), validation.SCAPULA_RIB_CLEARANCE_M)
        sc = anat.bones["scapula.L"]
        rib = anat.bones["rib_06.L"]
        pushed = dataclasses.replace(sc, tail=rib.outline[1])  # angulo inferior metido en una costilla
        bad = dataclasses.replace(anat, bones={**anat.bones, "scapula.L": pushed})
        self.assertIn("ANAT_SCAPULA_RIB_COLLISION", codes(validation.validate_anatomy(base, bad)))


class TestArticulationValidatorDetectsProblems(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()

    def with_joint(self, name, **ch):
        return dataclasses.replace(self.art, joints={**self.art.joints, name: dataclasses.replace(self.art.joints[name], **ch)})

    def check(self, art, code):
        self.assertIn(code, codes(validation.validate_articulations(self.base, self.anat, art)))

    def test_detections(self):
        gh = self.art.joints["glenohumeral.L"]
        self.check(self.with_joint("glenohumeral.L", center=(gh.center[0] + 0.05, gh.center[1], gh.center[2])), "ART_JOINT_FAR")
        self.check(self.with_joint("glenohumeral.L", center=(gh.center[0] + 0.004, gh.center[1], gh.center[2])), "ART_RIG_DRIVER_PIVOT")
        self.check(self.with_joint("glenohumeral.L", sources=("no_existe",)), "ART_SOURCE_UNKNOWN")
        self.check(self.with_joint("glenohumeral.L", bones=("humerus.L", "fantasma")), "ART_BONE_UNKNOWN")
        d0 = gh.dofs[0]
        self.check(self.with_joint("glenohumeral.L", dofs=(dataclasses.replace(d0, source=None),) + gh.dofs[1:]), "ART_DOF_NO_SOURCE")
        self.check(self.with_joint("glenohumeral.L", dofs=(dataclasses.replace(d0, total_deg=(200.0, 10.0)),) + gh.dofs[1:]), "ART_DOF_RANGE")
        a = self.art.attachments["supraglenoid_tubercle.L"]
        far = dataclasses.replace(a, point=(a.point[0], a.point[1] - 0.2, a.point[2]))
        self.check(dataclasses.replace(self.art, attachments={**self.art.attachments, a.name: far}), "ART_ATTACHMENT_OFF_BONE")
        r = self.art.attachments["supraglenoid_tubercle.R"]
        asym = dataclasses.replace(r, point=(r.point[0], r.point[1], r.point[2] + 0.01))
        self.check(dataclasses.replace(self.art, attachments={**self.art.attachments, r.name: asym}), "ART_ASYMMETRIC")

    def test_config_rejects_numbers_without_flag(self):
        data = json.loads((ROOT / "config" / "articulations" / "thorax_shoulder.json").read_text(encoding="utf-8"))
        st = next(j for j in data["joints"] if j["name"] == "scapulothoracic.L")
        bad = next(d for d in st["dofs"] if d["total_deg"] is None)
        del bad["no_numeric_source"]
        from anatomical_core.config import ConfigError
        with self.assertRaises(ConfigError):
            articulations.build_articulations(self.base, self.anat, [data])


class TestBoneModelHasNoMuscles(unittest.TestCase):
    """main es el modelo de estructura osea: los puntos 'attachments' son hitos oseos; los musculos viven en la rama muscle-model."""

    MUSCLE_WORDS = ("origen", "insercion", "tendon", "musculo", "braquial", "trapecio", "deltoides", "triceps", "biceps")

    def test_attachments_are_bone_landmarks_only(self):
        art = articulations.build_articulations(*(lambda b: (b, anatomy.build_anatomy(b, anatomy.load_anatomy_config())))(build_model(load_config())),
                                                articulations.load_articulation_data())
        self.assertTrue(art.attachments)
        for n, a in art.attachments.items():
            self.assertTrue(all(s.startswith("hito") for s in a.structures), n)
            self.assertFalse(any(w in " ".join(a.structures).lower() for w in self.MUSCLE_WORDS), n)


if __name__ == "__main__":
    unittest.main()
