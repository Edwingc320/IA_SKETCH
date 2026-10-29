"""IoU por REGIONES (pelvis y craneo) de las siluetas `cp.*` contra la imagen de referencia `esqueleto humano.jpg` (frente, espalda y lado). Python con PIL.

    python scripts\\compare_cp_regions.py --after output\\cp_skeleton.blend [--before antes.blend] [--out output\\reference_compare]

El comparador global (`compare_reference.py`) no sirve para `cp.*` (solo hay pelvis, femures hasta la rodilla, columna y craneo: no tiene brazos, piernas ni
costillas), asi que aqui se compara solo una BANDA de la figura: la pelvis (0.44-0.62 H) y la cabeza (0.865-1.0 H). Cada blend se renderiza con
`scripts/render_cp_silhouette.py` a la escala exacta de la referencia (coronilla = 0.998 H en la fila superior de su figura, suelo en la inferior), asi que no se
reescala nada; solo se busca el desplazamiento horizontal (+-40 px) que maximiza el IoU y se cuenta el area dentro de la banda y de una ventana horizontal.
Resultado: tabla por region y vista, y la media. Es una metrica de TENDENCIA (la imagen es un dibujo de stock con proporciones propias; gana la antropometria)."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_reference import VIEWS, reference_masks  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "esqueleto humano.jpg"
H_REF = 1.75
Z_TOP_H = 0.998
REGIONS = {  # nombre: (z inferior en H, z superior en H, semiancho de la ventana en H por vista)
    "pelvis": (0.44, 0.62, {"front": 0.13, "back": 0.13, "side": 0.13}),
    "craneo": (0.865, 1.0, {"front": 0.07, "back": 0.07, "side": 0.11}),
}
SHIFT = 40


def find_blender() -> str:
    if os.environ.get("ANATOMICAL_BLENDER") and Path(os.environ["ANATOMICAL_BLENDER"]).exists():
        return os.environ["ANATOMICAL_BLENDER"]
    for root in (os.environ.get("ProgramFiles", r"C:\Program Files"),):
        for p in sorted(Path(root, "Blender Foundation").glob("Blender *")):
            if (p / "blender.exe").exists():
                return str(p / "blender.exe")
    raise SystemExit("No se encontro Blender: define ANATOMICAL_BLENDER")


def figure_rows(path: Path = REF) -> dict:
    """Filas (coronilla, suelo) de cada figura de la imagen, medidas con el CONTORNO OSCURO (< 110) de las columnas centrales: la marca de agua (gris claro) y los
    artefactos del jpg no cuentan. (Con la mascara de relleno la coronilla salia en la fila 31, que es la marca de agua, ~40 px por encima del craneo.)"""
    im = Image.open(path).convert("L")
    _, boxes = reference_masks(path, return_boxes=True)
    px = im.load()
    out = {}
    for v, (a, b) in boxes.items():
        w = b - a
        cols = range(a + int(0.30 * w), a + int(0.70 * w))
        dark = [y for y in range(im.height) if sum(1 for x in cols if px[x, y] < 110) >= 3]
        out[v] = (dark[0], dark[-1])
    return out


def render(blend: Path, label: str, out: Path, rows: dict) -> None:
    cmd = [find_blender(), "-b", str(blend), "--python", str(ROOT / "scripts" / "render_cp_silhouette.py"), "--", str(out), label] + [f"{v}:{rows[v][0]}:{rows[v][1]}" for v in VIEWS]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or "[OK]" not in r.stdout:
        raise SystemExit(f"Fallo el render de {blend}:\n{r.stdout[-800:]}\n{r.stderr[-400:]}")


def iou(a: Image.Image, b: Image.Image) -> float:
    a, b = a.convert("1"), b.convert("1")
    inter = ImageChops.logical_and(a, b).histogram()[255]
    union = ImageChops.logical_or(a, b).histogram()[255]
    return inter / union if union else 0.0


def region_iou(ref: Image.Image, model: Image.Image, rows: tuple, view: str, region: str) -> float:
    z0, z1, halves = REGIONS[region]
    top, bottom = rows
    scale = (bottom - top) / (Z_TOP_H * H_REF)  # pixeles por metro
    r0, r1 = round(bottom - z1 * H_REF * scale), round(bottom - z0 * H_REF * scale)
    half = round(halves[view] * H_REF * scale)
    model_win = model.crop((model.width // 2 - half, r0, model.width // 2 + half, r1))
    best = 0.0
    for dx in range(-SHIFT, SHIFT + 1, 2):
        c = ref.width // 2 + dx
        best = max(best, iou(ref.crop((c - half, r0, c + half, r1)), model_win))
    return best


def run(blends: dict, out: Path) -> dict:
    refs = reference_masks(REF)
    rows = figure_rows()
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    for label, blend in blends.items():
        render(Path(blend), label, out, rows)
        rep = {}
        for region in REGIONS:
            for v in VIEWS:
                m = Image.open(out / f"{label}_{v}.png").convert("RGBA").split()[3].point(lambda p: 255 if p > 127 else 0)
                rep[f"{region}_{v}"] = round(region_iou(refs[v], m, rows[v], v, region), 4)
        rep["pelvis_mean"] = round(sum(rep[f"pelvis_{v}"] for v in VIEWS) / 3, 4)
        rep["craneo_mean"] = round(sum(rep[f"craneo_{v}"] for v in VIEWS) / 3, 4)
        rep["mean"] = round((rep["pelvis_mean"] + rep["craneo_mean"]) / 2, 4)
        report[label] = rep
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--after", required=True)
    ap.add_argument("--before")
    ap.add_argument("--out", default=str(ROOT / "output" / "reference_compare"))
    a = ap.parse_args()
    blends = ({"cp_before": a.before} if a.before else {}) | {"cp_after": a.after}
    report = run(blends, Path(a.out))
    (Path(a.out) / "report_cp_regions.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
