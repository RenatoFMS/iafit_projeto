import numpy as np

def calcular_angulo(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    radianos = np.arctan2(
        c[1] - b[1],
        c[0] - b[0]
    ) - np.arctan2(
        a[1] - b[1],
        a[0] - b[0]
    )

    angulo = np.abs(radianos * 180.0 / np.pi)

    if angulo > 180:
        angulo = 360 - angulo

    return angulo