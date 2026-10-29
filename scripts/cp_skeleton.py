"""Genera el esqueleto parametrico `cp.*` (pelvis, femures y columna lumbar) en un .blend.

    blender -b --python scripts\cp_skeleton.py -- [--height 1.75] [--dim cp.FemurL=0.46] [--dim cp.Pelvis=0.30] [--no-parent] [--reference-images] [--out output\cp_skeleton.blend]

`--dim PIEZA=metros` redimensiona la pieza de forma uniforme (misma estructura y proporcion); `cp.Femur` aplica a los dos femures. Dimensiones de referencia:
cp.Pelvis = ancho biiliaco, cp.Femur* = longitud cabeza-rodilla, cp.LumbarSpine / cp.ThoracicSpine / cp.CervicalSpine = altura, cp.Skull = longitud antero-posterior,
cp.Mandible = anchura bicondilea. Cadena: Pelvis > Lumbar > Toracica > Cervical > Craneo > Mandibula (redimensionar una pieza arrastra la cadena que cuelga de ella)."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import bpy  # noqa: E402

from anatomical_core import cp_skeleton as cp  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--height", type=float, default=cp.REF_HEIGHT_M)
ap.add_argument("--dim", action="append", default=[], metavar="PIEZA=METROS")
ap.add_argument("--no-parent", action="store_true")
ap.add_argument("--reference-images", action="store_true", help="anade las imagenes de referencia del craneo como planos alineados (coleccion CP_Reference)")
ap.add_argument("--out", default=str(ROOT / "output" / "cp_skeleton.blend"))
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
bpy.ops.wm.read_factory_settings(use_empty=True)
dims = dict(d.split("=", 1) for d in a.dim)
parts = cp.build_cp_skeleton(a.height, dims, parent=not a.no_parent)
issues = cp.validate(parts)
if a.reference_images:
    from anatomical_core import cp_reference

    refs = cp_reference.add_reference_images(parts)
    print(f"[cp] planos de referencia: {sorted(refs) or 'ninguno (faltan las imagenes en la raiz)'}")
out = Path(a.out) if Path(a.out).is_absolute() else ROOT / a.out
out.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out))
for n, o in parts.items():
    print(f"[cp] {n:15s} origen {tuple(round(c, 4) for c in o.matrix_world.translation)}  {o['cp_ref_dim_name']} = {o['cp_ref_dim_m']:.4f} m  vertices {len(o.data.vertices)}")
print("[cp] problemas:", issues or "ninguno")
print(f"[OK] {out}")
sys.exit(1 if issues else 0)
