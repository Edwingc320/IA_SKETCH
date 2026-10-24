# Músculos glúteos (rama `muscle-model`)

Capa **muscular** construida sobre el modelo óseo: no existe en `main`. Cada músculo tiene sitios de **origen** e **inserción**, y una **fibra** por cada pareja origen → inserción. Todos los sitios nacen de un **hito óseo** del modelo óseo (`config/articulations/lumbar_pelvis.json`, `leg_foot.json`) y quedan a **menos de 12 mm de la superficie de su hueso** (la cara de una lámina cerrada cuenta como superficie). Datos: `config/muscles/gluteal.json`; código: `src/anatomical_core/muscles.py` y `muscles_scene.py`; pruebas: `tests/test_muscles.py`.

| Músculo | Orígenes (hito óseo) | Inserciones (hito óseo) |
|---|---|---|
| **Glúteo mayor** | cara externa del ilion por detrás de la línea glútea posterior (`posterior_gluteal_line`), masa lateral del sacro (`sacral_lateral_mass`), aponeurosis toracolumbar → cresta ilíaca (`iliac_crest`) | tuberosidad glútea del fémur (`gluteal_tuberosity`) y cintilla iliotibial → tubérculo de Gerdy (`gerdy_tubercle`, en la tibia) |
| **Glúteo mediano** | cara externa del ilion entre las líneas glúteas posterior y anterior | cara lateral del trocánter mayor (`greater_trochanter` +4 mm lateral) |
| **Glúteo menor** | cara externa del ilion entre las líneas glúteas anterior e inferior | cara anterior del trocánter mayor (`greater_trochanter`, 6 mm por delante) |

Fuentes: [Wikipedia](https://en.wikipedia.org/wiki/Gluteal_muscles), [Radiopaedia](https://www.radiopaedia.org/articles/gluteal-muscles), [WikiMSK](https://wikimsk.org/wiki/Gluteus_Medius), [AnatomyZone](https://anatomyzone.com/lower-limb/pelvic-girdle-and-gluteal-region/gluteus-medius/) y [ABMP](https://www.abmp.com/massage-and-bodywork-magazine/issues/julyaugust-2015/maximus-medius-and-minimus), todas de fiabilidad media. Las fuentes discrepan en el detalle del origen del mayor (cóccix, ligamento sacrotuberoso): se modelan los sitios comunes.

**Aclaraciones**
- La **aponeurosis toracolumbar** y la **cintilla iliotibial** son fascia, no hueso: se anclan al hueso donde terminan (cresta ilíaca y tubérculo de Gerdy). El tubérculo de Gerdy como destino de la cintilla no figuraba en las fuentes consultadas: **verificar en un atlas**.
- No hay ningún vector hacia coordenadas libres: cada fibra une dos sitios sobre huesos. Los marcadores (`MUS_site_*`) y las fibras (`MUS_fiber_*`) están emparentados al hueso de su origen o su inserción, de modo que al girar la cadera el sitio del trocánter sigue al fémur y el del ilion se queda (probado en Blender). Son datos: la fibra no se estira todavía.
- Cada músculo se pide como los demás datos: las posiciones se reflejan al lado derecho y escalan con la altura.
