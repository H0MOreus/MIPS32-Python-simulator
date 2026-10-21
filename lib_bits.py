"""
Primitivas de hardware para manipulacion de palabras de 32 bits
conversion en complemento a dos y extraccion de campos de instruccion
"""

MASK_32 = 0xFFFFFFFF
SIGNO_BIT_32 = 0x80000000
MASK_16 = 0xFFFF
SIGNO_BIT_16 = 0x8000

# Numeros representables
def to_unsigned32(x: int)-> int:
    return x & MASK_32

"""
Primero solo aceptamos numeros de 32 bits
0x80000000 == 1000 0000 0000 0000; basicamente el bit de signo
el AND con el bit de signo significa que es negativo.
"""

def to_signed32(x: int) -> int:
    ui = x & MASK_32
    if ui & SIGNO_BIT_32:
        return ui - 0x100000000
    # si es positivo
    return ui

"""
nos aseguramos que el inm sea de 16 bits
si es negativo (bit de signo = 1):
    hacemos la extension de signo, rellenamos con 1, no pasa nada y mantenemos el mismo numero
    la comparacion con la mascara 32 no es necesaria porque  ya he comparado inm antes de entrar
"""
# signo_extendido_16_32, estaba usando nombres castellano, pero para subirlo a github
# y sentirme mejor lo he puesto en ingles
def sign_extend_16_32(inm: int) -> int:
    inm = inm & MASK_16
    if inm & SIGNO_BIT_16:
        return (inm | 0xFFFF0000) & MASK_32
    return inm

"""
0xFFFF == 1111 1111 1111 1111 
al hacer el AND con 16 bits, limpia y deja el resto a 0
Ej: 0x12345 & 0xFFFF =>
1111 0010 0011 0100 0101
     1111 1111 1111 1111
AND  -------------------
0000 0010 0011 0100 0101 -> resultado inmediato "extendido a 32"
Este es un concepto explotado en otros metodos, python no guarda bits y luego los interpretan
directamente son enteros, entonces lo unico que nos aseguramos es de eliminar bits sobrantes en caso de que existan.
"""
# extension_zero
def zero_extend_16_32(inm: int)->int:
    return inm & MASK_16
"""
Obtiene el rango de bits [hi:lo], incluidos.
Empieza en 0
"""
"""
Ej: instruccion 32 bits, OpCode [31, 26]
l = 6 (31 - 26 +1), la cantidad de bits
mask = (1 << l) 0100 0000; desplazar un uno para tener a continuacion
(1 << l) -1 == 0011 1111; obtenemos una mascara de 6 unos
word >> lo => entero de 32 bits desplazado a la derecha nos queda el campo que queremos
y con el & mask eliminamos bits sobrantes si hubiera


l = hi - lo + 1;            6 = 31 - 26 +1
mask = (1 << l) - 1         mask = 0011 1111
return (word >> lo) & mask   return (instruccion >> 26)
"""
# extraer_bits
def get_bits(word: int, hi: int, lo: int)->int:
    l = hi - lo + 1
    mask = (1 << l) - 1
    return (word >> lo) & mask