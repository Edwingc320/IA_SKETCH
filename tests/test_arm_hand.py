"""Brazo, antebrazo, muneca y mano: jerarquia anatomica, orientacion de la palma en pose A y puntos de union."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anatomical_core import anatomy, articulations, validation  # noqa: E402
from anatomical_core.config import load_config  # noqa: E402
from anatomical_core.geometry import length, mat_vec, mirror_point, sub  # noqa: E402
from anatomical_core.pose import apply_pose  # noqa: E402
from anatomical_core.skeleton import build_model  # noqa: E402

CARPAL_PARENT = {"scaphoid": "radius", "lunate": "radius", "triquetrum": "ulna", "pisiform": "triquetrum",
                 "trapezium": "scaphoid", "trapezoid": "scaphoid", "capitate": "lunate", "hamate": "triquetrum"}
METACARPAL_CARPAL = {1: "trapezium", 2: "trapezoid", 3: "capitate", 4: "hamate", 5: "hamate"}
FINGERS = {"index": 2, "middle": 3, "ring": 4, "little": 5}


def build_all(**kw):
    base = build_model(load_config(**kw))
    anat = anatomy.build_anatomy(base, anatomy.load_anatomy_config())
    return base, anat, articulations.build_articulations(base, anat, articulations.load_articulation_data())


def posed(**overrides):
    cfg = load_config(pose_overrides=overrides or None)
    model = build_model(cfg)
    return model, apply_pose(model, cfg.pose)


def palm_normal(side, **overrides):
    """Normal de la palma (anterior en el neutro, -Y) llevada a la pose A, con ajustes opcionales de la pose."""
    _, p = posed(**overrides)
    return mat_vec(p.bones[f"hand.{side}"].rotation, (0.0, -1.0, 0.0))


class TestArmHandHierarchy(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()
        self.b = self.anat.bones

    def test_bone_counts_per_side(self):
        for s in "LR":
            names = [n for n in self.b if n.endswith(f".{s}")]
            arm = [n for n in names if n.split(".")[0] in ("humerus", "radius", "ulna")]
            hand = [n for n in names if n.split(".")[0] in CARPAL_PARENT or n.startswith("metacarpal_")
                    or n.split("_")[0] in ("thumb", "index", "middle", "ring", "little")]
            self.assertEqual(len(arm), 3, s)
            self.assertEqual(len(hand), 8 + 5 + 14, s)  # carpo + metacarpo + falanges (2 del pulgar + 3 por dedo)

    def test_arm_chain(self):
        for s in "LR":
            self.assertEqual(self.b[f"humerus.{s}"].anatomical_parent, f"scapula.{s}")  # glenohumeral
            self.assertEqual(self.b[f"humerus.{s}"].parent, f"upper_arm.{s}")
            for n in ("radius", "ulna"):
                self.assertEqual(self.b[f"{n}.{s}"].anatomical_parent, f"humerus.{s}", n)  # codo

    def test_carpal_rows_and_metacarpals(self):
        for s in "LR":
            for carpal, parent in CARPAL_PARENT.items():
                self.assertEqual(self.b[f"{carpal}.{s}"].anatomical_parent, f"{parent}.{s}", carpal)
            for k, carpal in METACARPAL_CARPAL.items():
                self.assertEqual(self.b[f"metacarpal_{k}.{s}"].parent, f"{carpal}.{s}", k)

    def test_phalanx_chains_are_exact(self):
        for s in "LR":
            chains = {"thumb": (1, ["thumb_proximal", "thumb_distal"])}
            chains.update({f: (k, [f"{f}_proximal", f"{f}_middle", f"{f}_distal"]) for f, k in FINGERS.items()})
            for finger, (k, bones) in chains.items():
                prev = f"metacarpal_{k}.{s}"
                for n in bones:
                    bone = self.b[f"{n}.{s}"]
                    self.assertEqual(bone.parent, prev, n)
                    self.assertLess(length(sub(bone.head, self.b[prev].tail)), 1e-12, n)  # cabeza = cola de la anterior
                    prev = f"{n}.{s}"

    def test_distal_forearm_flanks_the_wrist(self):
        hand = self.base.bones["hand.L"]
        for n in ("radius.L", "ulna.L"):
            self.assertLess(length(sub(self.b[n].tail, hand.head)), 0.03, n)  # extremos distales junto al pivote de la muneca
        self.assertGreater(self.b["radius.L"].tail[0], self.b["ulna.L"].tail[0])  # radio lateral (pulgar), cubito medial


class TestPalmOrientationInPoseA(unittest.TestCase):
    def test_palm_faces_medially_and_slightly_forward(self):
        for side, sign in (("L", 1), ("R", -1)):
            n = palm_normal(side)
            self.assertLess(sign * n[0], -0.7, side)  # medial: hacia el cuerpo
            self.assertLess(n[1], 0.0, side)  # algo anterior
            self.assertGreater(n[1], -0.5, side)  # pero no de frente

    def test_anatomical_position_keeps_the_palm_forward(self):
        n = palm_normal("L", **{"elbow.pronation": 0.0, "elbow.flexion": 0.0, "shoulder.abduction": 0.0, "wrist.flexion": 0.0})
        self.assertLess(length(sub(n, (0.0, -1.0, 0.0))), 1e-9)

    def test_pronation_turns_about_the_forearm_axis(self):
        m, p0 = posed(**{"elbow.pronation": 0.0})
        _, p70 = posed(**{"elbow.pronation": 70.0})
        # con el codo flexionado 12 grados el eje de giro sigue siendo el del antebrazo: su punta no se mueve
        self.assertLess(length(sub(p0.bones["forearm.L"].tail, p70.bones["forearm.L"].tail)), 1e-9)
        self.assertGreater(length(sub(p0.bones["hand.L"].tail, p70.bones["hand.L"].tail)), 0.01)  # y la mano si gira

    def test_elbow_dof_order_puts_pronation_first(self):
        self.assertEqual([d.name for d in build_model(load_config()).joints["elbow.L"].dofs], ["pronation", "flexion"])


class TestArmHandUnions(unittest.TestCase):
    def setUp(self):
        self.base, self.anat, self.art = build_all()

    def region(self, store):
        return {n: x for n, x in store.items() if x.region == "arm_hand"}

    def test_counts_and_validation(self):
        self.assertEqual(len(self.region(self.art.joints)), 24 * 2)
        self.assertEqual(len(self.region(self.art.ligaments)), 42 * 2)
        self.assertEqual(len(self.region(self.art.attachments)), 8 * 2)  # solo hitos oseos; los tendones estan en muscle-model
        issues = validation.validate_articulations(self.base, self.anat, self.art)
        self.assertEqual([i for i in issues if i.severity == "error"], [])

    def test_every_independent_joint_is_covered(self):
        j = self.art.joints
        for s in "LR":
            for n in ("elbow", "proximal_radioulnar", "distal_radioulnar", "radiocarpal", "midcarpal", "carpometacarpal_1",
                      "metacarpophalangeal_thumb", "interphalangeal_thumb"):
                self.assertIn(f"{n}.{s}", j, n)
            for f, k in FINGERS.items():
                for n in (f"carpometacarpal_{k}", f"metacarpophalangeal_{f}", f"proximal_interphalangeal_{f}", f"distal_interphalangeal_{f}"):
                    self.assertIn(f"{n}.{s}", j, n)
            self.assertEqual(set(j[f"midcarpal.{s}"].bones), {f"{c}.{s}" for c in CARPAL_PARENT if c != "pisiform"})

    def test_rig_drivers_and_centers(self):
        j = self.art.joints
        for s in "LR":
            self.assertEqual((j[f"elbow.{s}"].rig_driver, j[f"radiocarpal.{s}"].rig_driver), (f"elbow.{s}", f"wrist.{s}"))
            for n in ("elbow", "radiocarpal"):
                self.assertLess(length(sub(j[f"{n}.{s}"].center, self.base.joints[j[f"{n}.{s}"].rig_driver].pivot)), 1e-12)
            self.assertIsNone(j[f"proximal_radioulnar.{s}"].rig_driver)  # la pronacion la mueve 'elbow' (sin pivote propio)
            # los centros de los dedos son exactamente las colas de los huesos proximales
            self.assertLess(length(sub(j[f"metacarpophalangeal_index.{s}"].center, self.anat.bones[f"metacarpal_2.{s}"].tail)), 1e-12)
            self.assertLess(length(sub(j[f"proximal_interphalangeal_ring.{s}"].center, self.anat.bones[f"ring_proximal.{s}"].tail)), 1e-12)

    def test_published_ranges_and_sources(self):
        d = lambda jn: {x.name: x for x in self.art.joints[jn].dofs}  # noqa: E731
        self.assertEqual(d("elbow.L")["flexion"].total_deg, (140, 150))
        self.assertEqual({k: v.total_deg for k, v in d("proximal_radioulnar.R").items()}, {"pronacion": (80, 90), "supinacion": (80, 90)})
        self.assertEqual(d("distal_radioulnar.L")["pronosupinacion_total"].total_deg, (150, 180))
        self.assertEqual(d("radiocarpal.L")["desviacion_cubital"].total_deg, (28.3, 30))
        self.assertGreater(d("radiocarpal.L")["flexion"].total_deg[0], 70)
        self.assertEqual(d("carpometacarpal_1.L")["abduccion"].total_deg, (60, 70))
        self.assertIsNone(d("carpometacarpal_3.L")["flexion_extension"].total_deg)  # sin cifra: no se inventa
        self.assertTrue(d("proximal_radioulnar.L")["pronacion"].per_side)
        # las cifras de los dedos vienen de una pagina agregadora: deben decir que hay que verificarlas
        for jn in ("metacarpophalangeal_index.L", "proximal_interphalangeal_little.R", "interphalangeal_thumb.L"):
            self.assertIn("verificar", self.art.joints[jn].notes.lower() + " ".join(x.note for x in self.art.joints[jn].dofs).lower(), jn)
        weak = {k for k, s in self.art.sources.items() if s["reliability"] == "baja"} | {"hand_rom"}
        for store in (self.art.ligaments, self.art.attachments):
            for x in self.region(store).values():
                if set(x.sources) <= weak:
                    self.assertIn("verificar", x.notes.lower(), x.name)

    def test_ligaments_attach_where_described(self):
        lg = self.art.ligaments
        ends = lambda n: (lg[n].from_bone, lg[n].to_bone)  # noqa: E731
        for s in "LR":
            self.assertEqual(ends(f"ulnar_collateral_elbow.{s}"), (f"humerus.{s}", f"ulna.{s}"))
            self.assertEqual(ends(f"radial_collateral_elbow.{s}"), (f"humerus.{s}", f"radius.{s}"))
            self.assertEqual(ends(f"interosseous_membrane.{s}"), (f"radius.{s}", f"ulna.{s}"))
            self.assertEqual(ends(f"triangular_fibrocartilage.{s}"), (f"radius.{s}", f"ulna.{s}"))
            self.assertEqual(ends(f"pisohamate.{s}"), (f"pisiform.{s}", f"hamate.{s}"))
            self.assertEqual(ends(f"anterior_oblique_cmc1.{s}"), (f"trapezium.{s}", f"metacarpal_1.{s}"))
            self.assertEqual(lg[f"annular.{s}"].joint, f"proximal_radioulnar.{s}")
            self.assertEqual(lg[f"collateral_mcp_index.{s}"].to_bone, f"index_proximal.{s}")
            # el retinaculo flexor cruza la cara palmar (-Y) del carpo
            self.assertLess(lg[f"flexor_retinaculum.{s}"].a[1], self.anat.bones[f"capitate.{s}"].head[1])
            # el colateral medial parte del epicondilo medial y el lateral del lateral
            sign = 1 if s == "L" else -1
            self.assertLess(sign * lg[f"ulnar_collateral_elbow.{s}"].a[0], sign * lg[f"radial_collateral_elbow.{s}"].a[0])

    def test_epicondyles_flank_the_distal_humerus(self):
        at = self.art.attachments
        axis_x = self.anat.bones["humerus.L"].tail[0]
        self.assertLess(at["medial_epicondyle.L"].point[0], axis_x)  # medial = hacia el cuerpo (-X en .L)
        self.assertGreater(at["lateral_epicondyle.L"].point[0], axis_x)
        self.assertEqual(at["hook_of_hamate.L"].bone, "hamate.L")
        self.assertEqual(at["scaphoid_tubercle.L"].bone, "scaphoid.L")

    def test_symmetry(self):
        for store, pts in ((self.art.joints, lambda x: [x.center]), (self.art.ligaments, lambda x: [x.a, x.b]),
                           (self.art.attachments, lambda x: [x.point])):
            for n, x in self.region(store).items():
                if n.endswith(".L"):
                    for p, q in zip(pts(x), pts(store[n[:-2] + ".R"])):
                        self.assertLess(length(sub(mirror_point(p), q)), 1e-12, n)


if __name__ == "__main__":
    unittest.main()
