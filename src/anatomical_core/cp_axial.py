"""Esqueleto AXIAL parametrico `cp.*` (usa bpy): columna toracica (T12-T1), columna cervical (C7-C1), craneo y mandibula, generados desde cero como continuacion de
`cp_skeleton` (pelvis, femures y columna lumbar). Mismas reglas: objetos independientes con el prefijo `cp.`, mallas locales a su origen articular (transformaciones
aplicadas, sin vertex groups), todo en fracciones de la altura H (`--height` conserva las proporciones) y mismo tono de hueso.

Cadena de emparentamiento (Keep Transform): cp.Pelvis > cp.LumbarSpine > cp.ThoracicSpine > cp.CervicalSpine > cp.Skull > cp.Mandible.

    cp.ThoracicSpine  T12..T1 con discos; origen en el centro del disco T12/L1; cifosis (convexa hacia atras)
    cp.CervicalSpine  C7..C1 con discos; origen en el centro del disco C7/T1; lordosis (convexa hacia delante); C2 con apofisis odontoides; C1 en anillo
    cp.Skull          neurocraneo, cara (orbitas y abertura nasal en profundidad), arcos cigomaticos, mastoides y arcada dental superior; origen en el centro de los
                      condilos occipitales (articulacion atlanto-occipital)
    cp.Mandible       cuerpo, mentón, ramas, coronoides, condilos y arcada dental inferior; origen en el centro del eje de las articulaciones temporomandibulares

Los LARGOS mandan los datos antropometricos (Drillis y Contini): hombro a 0.818 H, menton a ~0.87 H, vertice a 1.0 H. La FORMA (curvas sagitales de la columna,
craneo grande con occipucio y frente, apofisis espinosas inclinadas hacia abajo en el torax) sigue la imagen de referencia `esqueleto humano.jpg`, cuya cabeza es
mas pequeña que la antropometrica: gana la antropometria (decision del usuario)."""
from __future__ import annotations

import math

import bmesh
from mathutils import Vector

from . import cp_skeleton as cp
from . import cp_skullbox, cp_vertebra

THOR_DISC_H = 0.0020
CERV_DISC_H = 0.0030
LUMBAR_TOTAL = 5 * (cp.BODY_H + cp.DISC_H) - cp.DISC_H / 2  # altura de L5-L1 desde el centro del disco L5-S1
SPINE_Y = cp.LUMBAR_Y0  # plano sagital de los extremos de cada curva (H)
KYPHOSIS, LORDOSIS = 0.016, 0.009  # flechas maximas de las curvas (H)
SKULL_BASE_TO_VERTEX = 0.075  # centro de los condilos occipitales - vertice (H)
SKULL_BASE_TO_MENTON = 0.050  # centro de los condilos occipitales - menton (H)
TMJ = (0.0, -0.032, -0.012)  # centro del eje de las ATM relativo al origen del craneo (H)

THORACIC_LEVELS = [f"T{n}" for n in range(12, 0, -1)]  # de abajo (T12) a arriba (T1)
CERVICAL_LEVELS = ["C7", "C6", "C5", "C4", "C3", "C2", "C1"]


def _lerp(a, b, t):
    return a + (b - a) * t


def _thoracic_dims(i: int) -> tuple:
    """(altura del cuerpo, semieje a, semieje b) del nivel i (0 = T12 ... 11 = T1), en H."""
    t = i / 11
    return _lerp(0.0130, 0.0098, t), _lerp(0.0112, 0.0085, t), _lerp(0.0095, 0.0075, t)


def thoracic_total() -> float:
    return sum(_thoracic_dims(i)[0] + THOR_DISC_H for i in range(12)) - THOR_DISC_H / 2


CERVICAL_BODY_H = {"C7": 0.0090, "C6": 0.0088, "C5": 0.0086, "C4": 0.0084, "C3": 0.0082}
C2_H, C1_H = 0.0170, 0.0065


def cervical_total() -> float:
    return sum(CERVICAL_BODY_H.values()) + 6 * CERV_DISC_H - CERV_DISC_H / 2 + C2_H + C1_H


def thoracic_origin_z() -> float:
    return cp.LUMBAR_Z0 + LUMBAR_TOTAL + THOR_DISC_H / 2


def cervical_origin_z() -> float:
    return thoracic_origin_z() + thoracic_total() + CERV_DISC_H / 2


def skull_origin_z() -> float:
    return cervical_origin_z() + cervical_total() + 0.0010


# --- columna (etapa B): constructores en `cp_vertebra` --------------------------------------------------------------------------------------
def _finish_local(bm):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def _column(h: float, origin: Vector, region: str, levels: list, curve, ref_name: str) -> tuple:
    """Columna de una region: jaula de vertebras y discos sobre la curva sagital, Subdivision Surface y malla local al origen."""
    spine = cp_vertebra.load_spine()
    cage = cp_vertebra.build_column(h, origin, region, levels, curve, spine["regions"][region]["disc"], spine)
    verts, faces = cp_vertebra.subdivide_column(cage)
    bm = cp.mesh_to_bm(verts, faces)
    _finish_local(bm)
    bmesh.ops.translate(bm, vec=-origin, verts=bm.verts)
    zs = [v.co.z for v in bm.verts]
    return bm, origin, max(zs) - min(zs), ref_name


def build_thoracic(h: float) -> tuple:
    """(bmesh, origen mundo, dimension de referencia, nombre): T12-T1 con discos y cifosis; vertebras torácicas (cuerpo en corazon con carillas costales, apofisis espinosa larga
    e inclinada, transversas largas); origen en el centro del disco T12/L1."""
    origin = Vector((0.0, cp.LUMBAR_Y0, thoracic_origin_z())) * h
    total = thoracic_total()
    levels = [(name, _thoracic_dims(i)[0], THOR_DISC_H) for i, name in enumerate(THORACIC_LEVELS)]
    curve = lambda s: KYPHOSIS * math.sin(math.pi * min(max(s / total, 0.0), 1.0))  # noqa: E731 (convexa hacia atras: +y)
    return _column(h, origin, "thoracic", levels, curve, "thoracic_height")


def build_cervical(h: float) -> tuple:
    """(bmesh, origen mundo, dimension de referencia, nombre): C7-C1 con lordosis; C3-C7 con ganchos uncinados y espinosa corta (bifida en C3-C6), C2 con odontoides, C1 en anillo;
    origen en el centro del disco C7/T1."""
    origin = Vector((0.0, cp.LUMBAR_Y0, cervical_origin_z())) * h
    total = cervical_total()
    levels = [(name, CERVICAL_BODY_H[name], CERV_DISC_H) for name in ("C7", "C6", "C5", "C4", "C3")] + [("C2", C2_H, CERV_DISC_H), ("C1", C1_H, 0.0)]
    curve = lambda s: -LORDOSIS * math.sin(math.pi * min(max(s / total, 0.0), 1.0))  # noqa: E731 (convexa hacia delante: -y)
    return _column(h, origin, "cervical", levels, curve, "cervical_height")


# --- craneo y mandibula ----------------------------------------------------------------------------------------------------------------------
def skull_origin(h: float) -> Vector:
    return Vector((0.0, cp.LUMBAR_Y0, skull_origin_z())) * h


SKULL_GROUP_PREFIXES = ("cp.Skull", "cp.Zygomatic", "cp.Temporal", "cp.Parietal", "cp.Sphenoid", "cp.Mastoid", "cp.Condyle", "cp.TeethUpper")  # piezas independientes del craneo (la boveda es cp.Skull)


def build_skull_parts(h: float) -> dict:
    """{nombre del objeto: (bmesh, origen mundo, dimension de referencia, nombre de la dimension)} de las PIEZAS INDEPENDIENTES del craneo (`cp_skullbox`): boveda (cp.Skull),
    cara, cigomaticos, temporales, mastoides, condilos occipitales y arcada dental superior; cada una es una malla cerrada propia (no se unen en un solo solido). Todas comparten
    el origen del craneo (centro de los condilos occipitales) y sus mallas son locales a el. La referencia de la boveda es su longitud antero-posterior."""
    out = {}
    for name, (verts, faces) in cp_skullbox.skull_parts().items():
        bm = cp.mesh_to_bm(verts, faces, h)
        _finish_local(bm)
        ext = [max(v.co[i] for v in bm.verts) - min(v.co[i] for v in bm.verts) for i in range(3)]
        out[f"cp.{name}"] = (bm, skull_origin(h), ext[1] if name == "Skull" else max(ext), "skull_length" if name == "Skull" else "part_extent")
    return out


def build_mandible(h: float) -> tuple:
    """(bmesh, origen mundo, dimension de referencia, nombre): mandibula por box modeling (barrido en U de secciones rectangulares: condilo, rama recta, gonion en esquina,
    cuerpo y menton plano; Subdivision Surface nivel 2 con creases) con origen en el centro del eje de las ATM; referencia = anchura bicondilea. Sin dientes (cp.TeethLower)."""
    verts, faces = cp_skullbox.box_mandible()
    bm = cp.mesh_to_bm(verts, faces, h, offset=tuple(-c * h for c in TMJ))
    _finish_local(bm)
    xs = [v.co.x for v in bm.verts]
    return bm, skull_origin(h) + Vector(TMJ) * h, max(xs) - min(xs), "mandible_width"


def build_teeth_lower(h: float) -> tuple:
    """(bmesh, origen mundo, dimension, nombre): arcada dental inferior, pieza independiente que cuelga de la mandibula (mismo origen: el eje de las ATM)."""
    verts, faces = cp_skullbox.teeth_lower()
    bm = cp.mesh_to_bm(verts, faces, h, offset=tuple(-c * h for c in TMJ))
    _finish_local(bm)
    ext = max(max(v.co[i] for v in bm.verts) - min(v.co[i] for v in bm.verts) for i in range(3))
    return bm, skull_origin(h) + Vector(TMJ) * h, ext, "part_extent"
