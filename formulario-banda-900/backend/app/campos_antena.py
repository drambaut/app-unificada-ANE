"""
Fuente unica de verdad para los rangos y tooltips de los campos de antena,
tal como se definieron en el documento "Rangos / Tooltip".

Se usa tanto para validar en el backend (schemas.py) como para exponerse
al frontend via /api/config/campos-antena, de forma que el formulario web
y el panel admin muestren siempre el mismo texto de ayuda y los mismos limites.
"""

CAMPOS_ANTENA = {
    "acimut": {
        "label": "Acimut",
        "min": 0,
        "min_inclusive": True,
        "max": 359,
        "max_inclusive": True,
        "tooltip": (
            "Es la direccion hacia donde apunta la antena, medida en grados desde "
            "el norte geografico. Valor entre 0 y 359."
        ),
    },
    "tilt": {
        "label": "Tilt",
        "min": -40,
        "min_inclusive": True,
        "max": 10,
        "max_inclusive": True,
        "tooltip": (
            "Es el angulo de inclinacion en grados de la antena hacia arriba o "
            "hacia abajo, un valor positivo indica inclinacion hacia arriba, "
            "mientras que un valor negativo indica inclinacion hacia abajo, el "
            "valor 0 indica que la antena no se encuentra inclinada. Valor entre "
            "-40 y 10."
        ),
    },
    "ganancia": {
        "label": "Ganancia",
        "min": 0,
        "min_inclusive": True,
        "max": 30,
        "max_inclusive": True,
        "tooltip": (
            "Indica la capacidad de la antena para concentrar la senal en una "
            "direccion determinada, se mide en dBi, el valor de la ganancia se "
            "encuentra en la hoja de especificaciones de la antena. Valor entre "
            "0 y 30."
        ),
    },
    "angulo_apertura": {
        "label": "Angulo de apertura",
        "min": 0,
        "min_inclusive": False,
        "max": 360,
        "max_inclusive": True,
        "tooltip": (
            "Es el angulo en grados en el que la antena radia la mayor parte de "
            "la potencia, este parametro puede ser consultado en la hoja de "
            "especificaciones tecnicas de la antena. Valor entre 0 y 360."
        ),
    },
    "altura_suelo": {
        "label": "Altura al suelo",
        "min": 1,
        "min_inclusive": False,
        "max": 20,
        "max_inclusive": True,
        "tooltip": (
            "Es la distancia vertical en metros desde el suelo hasta la posicion "
            "donde se instalara la antena. Valor entre 1 y 20."
        ),
    },
}


def validar_campo(nombre: str, valor: float) -> str | None:
    """Devuelve un mensaje de error si el valor esta fuera de rango, o None si es valido."""
    c = CAMPOS_ANTENA[nombre]
    ok_min = valor >= c["min"] if c["min_inclusive"] else valor > c["min"]
    ok_max = valor <= c["max"] if c["max_inclusive"] else valor < c["max"]
    if ok_min and ok_max:
        return None
    # Mensaje simple e igual al que ve el usuario en el frontend, sin
    # lenguaje matematico ("mayor o igual", etc.)
    return f"{c['label']}: valor entre {c['min']} y {c['max']}"
