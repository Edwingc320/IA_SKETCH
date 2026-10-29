"""Compara las siluetas del craneo `cp.*` con las de las imagenes de referencia (`craneo frontal/perfil/atras.jpg`): IoU de FORMA (ambas siluetas normalizadas a su caja), error del
perfil de anchura y una imagen de superposicion (verde = coinciden, rojo = solo el modelo, azul = solo la referencia). Python con PIL.

    python scripts\\compare_skull_reference.py --blend output\\cp_skeleton.blend [--label skull] [--out output\\reference_compare]

Renderiza el blend con `scripts/render_skull_views.py` (Blender): frente y perfil con TODO el craneo y la mandibula; atras solo con la boveda (la cara queda tras ella). Las imagenes
son laminas anatomicas con su propia escala y proporcion, asi que se compara la FORMA (no medidas): la antropometria sigue mandando en los largos."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skull_reference import silhouette, width_profile  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ("front", "side", "back")
NORM_H = 500


def find_blender() -> str:
    if os.environ.get("ANATOMICAL_BLENDER") and Path(os.environ["ANATOMICAL_BLENDER"]).exists():
        return os.environ["ANATOMICAL_BLENDER"]
    for p in sorted(Path(os.environ.get("ProgramFiles", r"C:\Program Files"), "Blender Foundation").glob("Blender *")):
        if (p / "blender.exe").exists():
            return str(p / "blender.exe")
    raise SystemExit("No se encontro Blender: define ANATOMICAL_BLENDER")


def render(blend: Path, label: str, out: Path, view_set: str, mode: str) -> None:
    cmd = [find_blender(), "-b", str(blend), "--python", str(ROOT / "scripts" / "render_skull_views.py"), "--", str(out), f"{label}_{view_set}", "--set", view_set, "--mode", mode]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or "[OK]" not in r.stdout:
        raise SystemExit(f"Fallo el render:\n{r.stdout[-600:]}\n{r.stderr[-300:]}")


def model_mask(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA").split()[3].point(lambda v: 255 if v > 127 else 0)


def normalise(mask: Image.Image) -> Image.Image:
    m = mask.crop(mask.getbbox())
    return m.resize((max(1, round(m.width * NORM_H / m.height)), NORM_H), Image.NEAREST)


def compare(ref: Image.Image, mod: Image.Image) -> dict:
    a, b = normalise(ref), normalise(mod)
    w = max(a.width, b.width) + 20
    ca, cb = Image.new("L", (w, NORM_H), 0), Image.new("L", (w, NORM_H), 0)
    ca.paste(a, ((w - a.width) // 2, 0))
    cb.paste(b, ((w - b.width) // 2, 0))
    pa, pb = ca.load(), cb.load()
    inter = union = 0
    over = Image.new("RGB", (w, NORM_H), (255, 255, 255))
    po = over.load()
    for y in range(NORM_H):
        for x in range(w):
            ia, ib = pa[x, y] > 0, pb[x, y] > 0
            inter += ia and ib
            union += ia or ib
            po[x, y] = (0, 160, 0) if ia and ib else (230, 60, 60) if ib else (60, 60, 230) if ia else (255, 255, 255)
    wa, wb = width_profile(ref), width_profile(mod)
    return {"iou": round(inter / union, 4), "width_profile_error": round(sum(abs(x - y) for x, y in zip(wa, wb)) / len(wa), 4),
            "aspect_reference": round(a.width / NORM_H, 4), "aspect_model": round(b.width / NORM_H, 4), "_overlay": over}


def run(blend: Path, label: str, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    render(blend, label, out, "all", "silhouette")
    render(blend, label, out, "vault", "silhouette")
    report, tiles = {}, []
    for v in VIEWS:
        src = out / f"{label}_{'vault' if v == 'back' else 'all'}_{v}.png"
        res = compare(silhouette(v), model_mask(src))
        over = res.pop("_overlay")
        over.save(out / f"{label}_overlay_{v}.png")
        tiles.append(over)
        report[v] = res
    report["mean_iou"] = round(sum(report[v]["iou"] for v in VIEWS) / 3, 4)
    sheet = Image.new("RGB", (sum(t.width for t in tiles) + 20, NORM_H), (255, 255, 255))
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0))
        x += t.width + 10
    sheet.save(out / f"{label}_overlay.png")
    (out / f"{label}_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--label", default="skull")
    ap.add_argument("--out", default=str(ROOT / "output" / "reference_compare"))
    a = ap.parse_args()
    print(json.dumps(run(Path(a.blend), a.label, Path(a.out)), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
