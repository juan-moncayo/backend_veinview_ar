# placa/constants.py
"""
Rangos de sensores centralizados para VeinView AR.

IMPORTANTE: Estos valores DEBEN coincidir con el firmware del ESP32
(VeinView_ESP32_v3_4_COMPLETO.ino, sección RANGOS DE SENSORES).

Si se modifica algún rango aquí, actualizar también el .ino y reflashear.
"""

# ── Ángulo pitch (grados) ─────────────────────────────────────────────────────
ANGULO_MIN_OPTIMO    = 10.0
ANGULO_MAX_OPTIMO    = 30.0
ANGULO_MIN_ACEPTABLE = 5.0
ANGULO_MAX_ACEPTABLE = 40.0

# ── Fuerza aplicada (gramos-fuerza) ──────────────────────────────────────────
FUERZA_MIN_OPTIMA    = 50.0
FUERZA_MAX_OPTIMA    = 300.0
FUERZA_MIN_ACEPTABLE = 30.0
FUERZA_MAX_ACEPTABLE = 400.0


def tecnica_correcta(angulo_pitch: float, fuerza: float) -> bool:
    """
    Determina si la técnica es correcta según rangos óptimos.
    Usada por DatosSensor.save(), alertas_ra() y calcular_estadisticas().
    """
    return (
        ANGULO_MIN_OPTIMO <= angulo_pitch <= ANGULO_MAX_OPTIMO
        and FUERZA_MIN_OPTIMA <= fuerza <= FUERZA_MAX_OPTIMA
    )


def evaluar_angulo(angulo_pitch: float) -> dict:
    """Evalúa el ángulo pitch y retorna dict para la respuesta de alertas."""
    en_optimo    = ANGULO_MIN_OPTIMO    <= angulo_pitch <= ANGULO_MAX_OPTIMO
    en_aceptable = ANGULO_MIN_ACEPTABLE <= angulo_pitch <= ANGULO_MAX_ACEPTABLE

    if en_optimo:
        mensaje = "Ángulo correcto"
        alerta  = False
    elif en_aceptable:
        mensaje = "Ángulo bajo — ajustar ligeramente" if angulo_pitch < ANGULO_MIN_OPTIMO \
                  else "Ángulo alto — ajustar ligeramente"
        alerta  = True
    else:
        mensaje = "⚠️ ÁNGULO MUY BAJO" if angulo_pitch < ANGULO_MIN_ACEPTABLE \
                  else "⚠️ ÁNGULO MUY ALTO"
        alerta  = True

    return {
        "activa":             alerta,
        "valor_actual":       round(angulo_pitch, 2),
        "en_rango_optimo":    en_optimo,
        "en_rango_aceptable": en_aceptable,
        "mensaje":            mensaje,
    }


def evaluar_fuerza(fuerza: float) -> dict:
    """Evalúa la fuerza y retorna dict para la respuesta de alertas."""
    en_optimo    = FUERZA_MIN_OPTIMA    <= fuerza <= FUERZA_MAX_OPTIMA
    en_aceptable = FUERZA_MIN_ACEPTABLE <= fuerza <= FUERZA_MAX_ACEPTABLE

    if en_optimo:
        mensaje = "Fuerza correcta"
        alerta  = False
    elif en_aceptable:
        mensaje = "Fuerza baja — presionar más" if fuerza < FUERZA_MIN_OPTIMA \
                  else "Fuerza alta — reducir presión"
        alerta  = True
    else:
        mensaje = "⚠️ FUERZA MUY BAJA" if fuerza < FUERZA_MIN_ACEPTABLE \
                  else "⚠️ FUERZA MUY ALTA"
        alerta  = True

    return {
        "activa":             alerta,
        "valor_actual":       round(fuerza, 2),
        "en_rango_optimo":    en_optimo,
        "en_rango_aceptable": en_aceptable,
        "mensaje":            mensaje,
    }


RANGOS_RESPUESTA = {
    "angulo_optimo":     {"min": ANGULO_MIN_OPTIMO,    "max": ANGULO_MAX_OPTIMO},
    "fuerza_optima":     {"min": FUERZA_MIN_OPTIMA,    "max": FUERZA_MAX_OPTIMA},
    "angulo_aceptable":  {"min": ANGULO_MIN_ACEPTABLE, "max": ANGULO_MAX_ACEPTABLE},
    "fuerza_aceptable":  {"min": FUERZA_MIN_ACEPTABLE, "max": FUERZA_MAX_ACEPTABLE},
}