"""Generación de códigos de barras EAN-13 (SVG) sin dependencias externas."""

_L_STRUCTURE = {
    0: "LLLLLLRRRRRR",
    1: "LLGLGG RRRRRR".replace(" ", ""),
    2: "LLGGLG RRRRRR".replace(" ", ""),
    3: "LLGGGL RRRRRR".replace(" ", ""),
    4: "LGLLGG RRRRRR".replace(" ", ""),
    5: "LGGLLG RRRRRR".replace(" ", ""),
    6: "LGGGLL RRRRRR".replace(" ", ""),
    7: "LGLGLG RRRRRR".replace(" ", ""),
    8: "LGLGGL RRRRRR".replace(" ", ""),
    9: "LGGLGL RRRRRR".replace(" ", ""),
}

# Codificaciones de 7 bits por dígito
_L_CODES = {
    0: "0001101", 1: "0011001", 2: "0010011", 3: "0111101", 4: "0100011",
    5: "0110001", 6: "0101111", 7: "0111011", 8: "0110111", 9: "0001011",
}
_G_CODES = {
    0: "0100111", 1: "0110011", 2: "0011011", 3: "0100001", 4: "0011101",
    5: "0111001", 6: "0000101", 7: "0010001", 8: "0001001", 9: "0010111",
}
_R_CODES = {
    0: "1110010", 1: "1100110", 2: "1101100", 3: "1000010", 4: "1011100",
    5: "1001110", 6: "1010000", 7: "1000100", 8: "1001000", 9: "1110100",
}


def digito_control_ean13(digitos12: str) -> int:
    """Calcula el dígito de verificación a partir de los 12 primeros dígitos."""
    suma = 0
    for i, ch in enumerate(digitos12):
        d = int(ch)
        suma += d * (1 if i % 2 == 0 else 3)
    mod = suma % 10
    return (10 - mod) % 10


def ean13_completo(digitos) -> str:
    """Normaliza a 13 dígitos EAN-13 con dígito de verificación (si hacen falta)."""
    solo = "".join(ch for ch in str(digitos) if ch.isdigit())
    if len(solo) >= 13:
        return solo[:13]
    base = solo.zfill(12)
    return base + str(digito_control_ean13(base))


def _bits_ean13(codigo13: str) -> str:
    estructura = _L_STRUCTURE[int(codigo13[0])]
    bits = "101"  # guarda izquierda
    for i in range(1, 13):
        digito = int(codigo13[i])
        pat = estructura[i - 1]
        tabla = {"L": _L_CODES, "G": _G_CODES, "R": _R_CODES}[pat]
        bits += tabla[digito]
        if i == 6:
            bits += "01010"  # separador central
    bits += "101"
    return bits


def svg_ean13(codigo13: str, altura: int = 40, ancho: int = 170, mostrar=False) -> str:
    bits = _bits_ean13(codigo13)
    n = len(bits)
    barra = ancho / n
    path = []
    rects = []
    corte = "evenodd"
    for i, b in enumerate(bits):
        x = i * barra
        if b == "1":
            path.append(f"M{x:.2f} 0 v{altura} h{barra:.2f} v-{altura} Z")
    texto = ""
    if mostrar:
        texto = (
            f'<text x="{ancho / 2}" y="{altura + 12}" text-anchor="middle" '
            f'font-size="11" font-family="monospace">{codigo13}</text>'
        )
    altura_total = altura + (16 if mostrar else 0)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {altura_total}" '
        f'width="100%" height="100%" shape-rendering="crispEdges">'
        f'<path fill="#000" fill-rule="{corte}" d="' + "".join(path) + f'"/>{texto}</svg>'
    )


def codigo_para_producto(producto_id: int, codigo_barras=None) -> str:
    """Reduce a un EAN-13 válido: usa el código existente o el ID del producto."""
    if codigo_barras:
        return ean13_completo(codigo_barras)
    return ean13_completo(str(producto_id).zfill(12))