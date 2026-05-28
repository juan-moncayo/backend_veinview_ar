# placa/constants.py
"""
Rangos de sensores calibrados con hardware real — VeinView AR.

Calibración realizada con enfermera profesional:
  Lado A (inclinación mayor): pitch ~ -28° a -20°
  Lado B (inclinación menor): pitch ~ -16° a -10°
  Rango unificado óptimo:     pitch -28° a -10°
  Fuerza óptima confirmada:   50g – 300g (picos durante punción)

NOTA: La fuerza NO es constante — es normal que haya lecturas bajas
(sin presión) y picos altos (momento de punción). El sistema evalúa
el promedio de la sesión, no dato a dato.

Si se modifica algún rango aquí, actualizar también el firmware ESP32
(VeinView_ESP32_v3_4.ino, sección RANGOS DE SENSORES) y reflashear.
"""

# ── Ángulo pitch (grados) ─────────────────────────────────────────────────────
# Negativo porque el sensor queda invertido en la posición de canalización
ANGULO_MIN_OPTIMO    = -30.0   # un poco más amplio que el mínimo medido (-28.9°)
ANGULO_MAX_OPTIMO    = -8.0    # un poco más amplio que el máximo medido (-10.7°)
ANGULO_MIN_ACEPTABLE = -38.0   # margen extra para estudiantes en aprendizaje
ANGULO_MAX_ACEPTABLE = -4.0    # margen extra para estudiantes en aprendizaje

# ── Fuerza aplicada (gramos-fuerza) ──────────────────────────────────────────
# Confirmado con enfermera: la fuerza no es constante, hay picos en la punción
# Las lecturas bajas (0-30g) son normales cuando no está presionando
FUERZA_MIN_OPTIMA    = 50.0
FUERZA_MAX_OPTIMA    = 300.0
FUERZA_MIN_ACEPTABLE = 30.0
FUERZA_MAX_ACEPTABLE = 400.0


def tecnica_correcta(angulo_pitch: float, fuerza: float) -> bool:
    """
    Determina si la técnica es correcta según rangos óptimos.

    IMPORTANTE: No penaliza fuerza baja porque el estudiante puede estar
    en fase de preparación (sin presionar aún). Solo evalúa el ángulo
    como criterio principal cuando la fuerza es significativa.

    Usada por DatosSensor.save(), alertas_ra() y calcular_estadisticas().
    """
    angulo_ok = ANGULO_MIN_OPTIMO <= angulo_pitch <= ANGULO_MAX_OPTIMO

    # Si hay fuerza significativa, evaluar también la fuerza
    if fuerza >= FUERZA_MIN_ACEPTABLE:
        fuerza_ok = FUERZA_MIN_OPTIMA <= fuerza <= FUERZA_MAX_OPTIMA
        return angulo_ok and fuerza_ok

    # Si la fuerza es muy baja (sin presión), solo evaluar ángulo
    return angulo_ok


def evaluar_angulo(angulo_pitch: float) -> dict:
    """Evalúa el ángulo pitch y retorna dict para la respuesta de alertas."""
    en_optimo    = ANGULO_MIN_OPTIMO    <= angulo_pitch <= ANGULO_MAX_OPTIMO
    en_aceptable = ANGULO_MIN_ACEPTABLE <= angulo_pitch <= ANGULO_MAX_ACEPTABLE

    if en_optimo:
        mensaje = "Ángulo correcto"
        alerta  = False
    elif en_aceptable:
        if angulo_pitch < ANGULO_MIN_OPTIMO:
            mensaje = "Ángulo muy inclinado — levantar un poco"
        else:
            mensaje = "Ángulo poco inclinado — bajar un poco"
        alerta = True
    else:
        if angulo_pitch < ANGULO_MIN_ACEPTABLE:
            mensaje = "⚠️ DEMASIADO INCLINADO"
        else:
            mensaje = "⚠️ MUY POCO INCLINADO"
        alerta = True

    return {
        "activa":             alerta,
        "valor_actual":       round(angulo_pitch, 2),
        "en_rango_optimo":    en_optimo,
        "en_rango_aceptable": en_aceptable,
        "mensaje":            mensaje,
    }


def evaluar_fuerza(fuerza: float) -> dict:
    """
    Evalúa la fuerza y retorna dict para la respuesta de alertas.
    No alerta si la fuerza es baja — puede ser fase sin presión.
    """
    en_optimo    = FUERZA_MIN_OPTIMA    <= fuerza <= FUERZA_MAX_OPTIMA
    en_aceptable = FUERZA_MIN_ACEPTABLE <= fuerza <= FUERZA_MAX_ACEPTABLE

    # Fuerza muy baja = sin presión activa, no es error
    if fuerza < FUERZA_MIN_ACEPTABLE:
        return {
            "activa":             False,
            "valor_actual":       round(fuerza, 2),
            "en_rango_optimo":    False,
            "en_rango_aceptable": True,   # no penalizar
            "mensaje":            "Sin presión activa",
        }

    if en_optimo:
        mensaje = "Fuerza correcta"
        alerta  = False
    elif en_aceptable:
        mensaje = "Fuerza baja — presionar más" if fuerza < FUERZA_MIN_OPTIMA \
                  else "Fuerza alta — reducir presión"
        alerta  = True
    else:
        mensaje = "⚠️ FUERZA MUY ALTA — reducir presión"
        alerta  = True

    return {
        "activa":             alerta,
        "valor_actual":       round(fuerza, 2),
        "en_rango_optimo":    en_optimo,
        "en_rango_aceptable": en_aceptable,
        "mensaje":            mensaje,
    }


RANGOS_RESPUESTA = {
    "angulo_optimo":    {"min": ANGULO_MIN_OPTIMO,    "max": ANGULO_MAX_OPTIMO},
    "fuerza_optima":    {"min": FUERZA_MIN_OPTIMA,    "max": FUERZA_MAX_OPTIMA},
    "angulo_aceptable": {"min": ANGULO_MIN_ACEPTABLE, "max": ANGULO_MAX_ACEPTABLE},
    "fuerza_aceptable": {"min": FUERZA_MIN_ACEPTABLE, "max": FUERZA_MAX_ACEPTABLE},
}