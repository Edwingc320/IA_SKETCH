"""Bateria de mutaciones de la region caderas y muslo (CM-9).

Aplica, una a una, mutaciones a los JSON de `config/` (y a `joints.json`), ejecuta las pruebas de Python puro que deberian detectarlas, y RESTAURA los bytes
exactos del archivo. Una mutacion esta "detectada" si esas pruebas fallan. Sale con codigo 1 si alguna no se detecta.

    python scripts\\mutation_battery.py            # todas
    python scripts\\mutation_battery.py -k femoral  # solo las que contienen ese texto

No forma parte de la suite (tarda varios minutos); se ejecuta al cerrar una region. Los resultados del cierre estan en docs/estado/caderas_muslo_cierre.md."""
from __future__ import annotations

import atexit
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config"
LP, LF, TL, TT = (CFG / "articulations" / "lumbar_pelvis.json", CFG / "articulations" / "leg_foot.json", CFG / "muscles" / "tendons_lower_limb.json", CFG / "muscles" / "tendons_trunk_head.json")
MV, VM, JN = CFG / "muscles" / "muscle_volumes.json", CFG / "muscles" / "volume_measurements.json", CFG / "joints.json"

HIP = ["test_hip_ligament_paths", "test_hip_rom"]
ILIO = ["test_iliopsoas_itb_paths"]
DEEP = ["test_deep_hip_muscles"]
KNEE = ["test_knee_anchors", "test_anchor_debt"]
VOL = ["test_muscle_volumes", "test_volume_measurements"]
ART = ["test_articulations", "test_lumbar_pelvis", "test_tendons"]


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def by(items, name):
    return next(x for x in items if x["name"] == name)


def mutation(file, tests):
    def deco(fn):
        MUTATIONS.append((fn.__name__, file, fn, tests))
        return fn
    return deco


MUTATIONS: list = []


# ---- volumenes
@mutation(MV, VOL)
def gmed_volume_from_the_male_cohort(d):
    next(m for m in d["muscles"] if m["unit"] == "gluteus_medius.L")["volume_cm3"] = 408.1


@mutation(MV, VOL)
def tibialis_anterior_back_to_the_convention(d):
    m = next(m for m in d["muscles"] if m["unit"] == "tibialis_anterior.L")
    m.update(kind="convencion", size_class="grande")
    for k in ("volume_cm3", "reference_height_m", "source"):
        m.pop(k, None)


@mutation(VM, VOL)
def unverified_value_marked_verified(d):
    next(m for m in d["measurements"] if m["id"] == "takahashi_addmag_posterior")["verified"] = True


@mutation(MV, VOL)
def a_derived_value_applied(d):
    m = next(m for m in d["muscles"] if m["unit"] == "rectus_femoris.L")
    m.update(kind="medido", volume_cm3=192.9, reference_height_m=1.75, source="ritsche_2025")
    m.pop("size_class", None)


# ---- ligamentos de la cadera
@mutation(LP, HIP)
def pubofemoral_without_its_wrapping_guide(d):
    by(d["ligaments"], "pubofemoral.L")["via"] = []


@mutation(LP, HIP)
def femoral_head_radius_32_mm(d):
    by(d["bone_surfaces"], "femoral_head.L")["radius_m"] = 0.032


@mutation(LP, HIP)
def iliofemoral_loses_deform(d):
    by(d["ligaments"], "iliofemoral.L").pop("deform")


@mutation(LP, HIP)
def invented_stiffness(d):
    by(d["ligaments"], "ischiofemoral.L")["mechanics"]["stiffness_N_per_mm"] = 40.0


# ---- ROM
@mutation(LP, HIP)
def published_extension_range_excludes_the_rig(d):
    next(x for x in by(d["joints"], "coxofemoral.L")["dofs"] if x["name"] == "extension")["range_deg"] = [10, 12]


@mutation(LP, HIP)
def internal_rotation_mapped_to_the_wrong_side(d):
    next(x for x in by(d["joints"], "coxofemoral.L")["dofs"] if x["name"] == "rotacion_interna")["rig"] = {"dof": "axial", "bound": "min"}


def _rig_extension_to_5(text):
    return text.replace('"min_deg": -15', '"min_deg": -5', 1)


# ---- psoas-iliaco, cintilla y rotadores profundos
@mutation(TT, ILIO)
def psoas_without_the_eminence_pulley(d):
    by(d["tendons"], "psoas_major.L")["via"] = []


@mutation(TT, ILIO)
def iliacus_origin_back_on_the_outer_side_of_the_plate(d):
    by(d["tendons"], "iliacus.L")["origin"].pop("offset_h")


@mutation(LP, ILIO)
def trochanter_sphere_radius_40_mm(d):
    by(d["bone_surfaces"], "femoral_greater_trochanter.L")["radius_m"] = 0.04


@mutation(TL, ILIO)
def itb_guide_pushed_into_the_trochanter(d):
    by(d["tendons"], "iliotibial_tract.L")["via"][0]["offset_h"] = [0.0715, 0.0, 0.0]


@mutation(TL, DEEP)
def obturator_externus_without_its_neck_guide(d):
    by(d["tendons"], "obturator_externus.L")["via"] = by(d["tendons"], "obturator_externus.L")["via"][:1]


@mutation(TL, DEEP)
def piriformis_loses_its_avoid_list(d):
    by(d["tendons"], "piriformis.L")["avoid"] = []


@mutation(TL, DEEP)
def pectineus_insertion_moved(d):
    by(d["tendons"], "pectineus.L")["insertion"]["offset_h"] = [0.0, 0.0, 0.0]


@mutation(LP, DEEP)
def ischial_obstacle_radius_12_mm(d):
    by(d["bone_surfaces"], "ischial_ramus.L")["radius_m"] = 0.012


@mutation(LP, DEEP)
def obturator_margin_landmark_far_from_the_bone(d):
    by(d["attachments"], "obturator_margin.L")["point"]["offset_h"] = [0.0, -0.03, 0.0]


@mutation(TL, DEEP)
def piriformis_cites_an_unknown_source(d):
    by(d["tendons"], "piriformis.L")["sources"] = ["no_such_source"]


# ---- rodilla
@mutation(LF, KNEE)
def tibial_proximal_obstacle_removed(d):
    d["bone_surfaces"] = [s for s in d["bone_surfaces"] if s["name"] != "tibial_proximal.L"]


@mutation(LF, KNEE)
def patella_obstacle_5_mm(d):
    by(d["bone_surfaces"], "patellar_body.L")["radius_m"] = 0.005


@mutation(LF, KNEE)
def patellar_ligament_back_to_rigid(d):
    by(d["ligaments"], "patellar.L").pop("deform")


@mutation(LF, KNEE)
def tibial_collateral_anchor_displaced(d):
    by(d["ligaments"], "tibial_collateral.L")["from"]["point"]["offset_h"] = [0.03, 0.0, 0.0]


@mutation(LF, KNEE)
def fibular_head_obstacle_removed(d):
    d["bone_surfaces"] = [s for s in d["bone_surfaces"] if s["name"] != "fibular_head_body.L"]


def run_one(name, file, fn, tests):
    original = file.read_bytes()
    atexit.register(file.write_bytes, original)  # si el proceso termina a medias, los bytes originales se restauran
    try:
        if fn is None:
            file.write_bytes(_rig_extension_to_5(original.decode("utf-8")).encode("utf-8"))
        else:
            data = json.loads(original.decode("utf-8"))
            fn(data)
            file.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        cmd = [sys.executable, "-B", "-m", "unittest", *tests]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src") + ";" + str(ROOT / "tests")})
        return r.returncode != 0
    finally:
        file.write_bytes(original)


def main(argv) -> int:
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "config"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if dirty:
        print("Hay cambios sin confirmar en config/; confirmalos o descartalos antes (asi no se mezclan con las mutaciones):")
        print(dirty)
        return 2
    pattern = argv[argv.index("-k") + 1] if "-k" in argv else ""
    items = [(n, f, fn, t) for n, f, fn, t in MUTATIONS if pattern in n]
    if not pattern:
        items.append(("rig_extension_limit_lowered_to_5_degrees", JN, None, ["test_hip_rom", "test_base_frozen"]))
    missed, t0 = [], time.time()
    for n, f, fn, tests in items:
        detected = run_one(n, f, fn, tests)
        print(f"{'DETECTADA ' if detected else 'NO DETECTADA'}  {n}  ({f.name}; {', '.join(tests)})", flush=True)
        if not detected:
            missed.append(n)
    print(f"\nMutaciones: {len(items)}; detectadas: {len(items) - len(missed)}; sin detectar: {len(missed)}; {time.time() - t0:.0f} s")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
