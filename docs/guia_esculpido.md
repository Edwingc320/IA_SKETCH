# Guía de esculpido del cráneo `cp.*` (redondez y terminación)

Criterio acordado con el usuario para todos los huesos del cráneo. Las láminas de referencia se miran a ojo y **no se colocan en el modelo**.

1. **Una pieza continua por hueso.** Cada hueso es una sola malla cerrada (una isla). Si nace de varias partes (cuerpo + brazos, escama + base), se funden por Boolean y se **pulen las uniones** para que no se vean costuras, escalones ni «bloques pegados».
2. **Redondez, no cajas.** Nada de vigas, losas ni cubos con aristas duras en superficies que en el hueso real son curvas: se modelan con barridos redondeados / Subdivision Surface, o recortando la bóveda curva con contornos poligonales. Referencia medible: ángulo entre caras vecinas < 30–45° en las superficies visibles.
3. **Pulido que conserva el volumen.** Se alisa con suavizado Taubin (λ|μ), que no encoge la pieza; el volumen y la tridimensionalidad actuales se mantienen (tolerancia: caja y volumen ±3 %), y los contactos con los huesos vecinos se conservan.
4. **Bordes de sutura.** Polígonos simples y W/triángulos; un surco de una fila de caras entre huesos; sin cortes fractales.
5. **Verificar mirando.** Renderizar el hueso solo y compararlo con la lámina antes de dar el cambio por bueno; luego prueba automática solo de lo modificado y mutación de lo nuevo.
