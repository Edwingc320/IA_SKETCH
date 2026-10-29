"""Mascaras de silueta de las tres imagenes de referencia del craneo (`craneo frontal.jpg`, `craneo perfil.jpg`, `craneo atras.jpg`, en la raiz del proyecto; referencias
PRIVADAS, no se versionan: ver .gitignore). Python con PIL, sin numpy.

    python scripts\\skull_reference.py [carpeta_de_salida]      # escribe skull_ref_<vista>.png y skull_ref_profiles.json

Cada imagen es distinta (un dibujo con etiquetas sobre fondo blanco, una lamina con marca de agua y una fotografia sobre fondo negro con la columna cervical), asi que la
silueta se aisla por vista: umbral contra el fondo, APERTURA morfologica (borra las etiquetas, las lineas guia y los trazos de las marcas de agua) y la componente
conexa mayor. De la vista posterior se descartan las filas por debajo de la base del craneo (columna cervical). Las siluetas sirven de forma, NO de medida absoluta:
cada imagen tiene su propia escala, asi que se comparan normalizadas a la caja del craneo."""
import json
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
FILES = {"front": "craneo frontal.jpg", "side": "craneo perfil.jpg", "back": "craneo atras.jpg"}
BACK_BASE_ROW = 352  # fila (de 657) bajo la que empieza la columna cervical en la vista posterior


def largest_component(mask: Image.Image) -> Image.Image:
    w, h = mask.size
    px = mask.load()
    seen = bytearray(w * h)
    best, best_pts = 0, None
    for y0 in range(h):
        for x0 in range(w):
            if px[x0, y0] and not seen[y0 * w + x0]:
                q, pts = deque([(x0, y0)]), []
                seen[y0 * w + x0] = 1
                while q:
                    x, y = q.popleft()
                    pts.append((x, y))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < w and 0 <= ny < h and px[nx, ny] and not seen[ny * w + nx]:
                            seen[ny * w + nx] = 1
                            q.append((nx, ny))
                if len(pts) > best:
                    best, best_pts = len(pts), pts
    out = Image.new("L", (w, h), 0)
    o = out.load()
    for x, y in best_pts or []:
        o[x, y] = 255
    return out


def fill_holes(mask: Image.Image) -> Image.Image:
    """Rellena los huecos interiores (orbitas, fosa nasal, dientes): la silueta es el contorno exterior."""
    w, h = mask.size
    inv = mask.point(lambda v: 0 if v else 255)
    px = inv.load()
    outside = bytearray(w * h)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if px[x, y] and not outside[y * w + x]:
                outside[y * w + x] = 1
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if px[x, y] and not outside[y * w + x]:
                outside[y * w + x] = 1
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and px[nx, ny] and not outside[ny * w + nx]:
                outside[ny * w + nx] = 1
                q.append((nx, ny))
    out = Image.new("L", (w, h), 255)
    o = out.load()
    for y in range(h):
        for x in range(w):
            if outside[y * w + x]:
                o[x, y] = 0
    return out


def opening(mask: Image.Image, size: int) -> Image.Image:
    return mask.filter(ImageFilter.MinFilter(size)).filter(ImageFilter.MaxFilter(size))


def silhouette(view: str, root: Path = ROOT) -> Image.Image:
    im = Image.open(root / FILES[view]).convert("L")
    if view == "back":
        im = im.crop((0, 0, im.width, BACK_BASE_ROW))
        m = im.point(lambda v: 255 if v > 45 else 0)  # craneo claro sobre fondo negro
        m = opening(m, 7)
    elif view == "front":
        m = opening(im.point(lambda v: 255 if v < 251 else 0), 9)  # etiquetas y lineas guia (<9 px) desaparecen; la mandibula y los dientes son casi blancos
    else:
        m = opening(im.point(lambda v: 255 if v < 238 else 0), 9)  # marca de agua y logotipo
    return fill_holes(largest_component(m))


def normalised(mask: Image.Image) -> Image.Image:
    box = mask.getbbox()
    return mask.crop(box)


def width_profile(mask: Image.Image, rows: int = 40) -> list:
    """Anchura relativa (a la altura de la caja) de la silueta en `rows` filas equidistantes, de arriba abajo."""
    m = normalised(mask)
    w, h = m.size
    px = m.load()
    out = []
    for i in range(rows):
        y = min(h - 1, int((i + 0.5) * h / rows))
        xs = [x for x in range(w) if px[x, y]]
        out.append(round((max(xs) - min(xs) + 1) / h, 4) if xs else 0.0)
    return out


def main(out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    prof = {}
    for v in FILES:
        m = silhouette(v)
        m.save(out / f"skull_ref_{v}.png")
        box = m.getbbox()
        prof[v] = {"bbox": box, "aspect_w_over_h": round((box[2] - box[0]) / (box[3] - box[1]), 4), "width_profile": width_profile(m)}
        print(f"[ref] {v}: caja {box}, ancho/alto = {prof[v]['aspect_w_over_h']}")
    (out / "skull_ref_profiles.json").write_text(json.dumps(prof, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "output" / "reference_compare"))
