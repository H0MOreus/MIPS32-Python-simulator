import unittest
from lib_bits import (
    to_unsigned32,
    to_signed32,
    sign_extend_16_32,
    zero_extend_16_32,
    get_bits,
    MASK_32,
    SIGNO_BIT_32,
    MASK_16,
    SIGNO_BIT_16,
)


class TestLibBits(unittest.TestCase):

    def test_to_unsigned32(self):
        self.assertEqual(to_unsigned32(0), 0)
        self.assertEqual(to_unsigned32(42), 42)
        self.assertEqual(to_unsigned32(0xFFFFFFFF), 0xFFFFFFFF)
        self.assertEqual(to_unsigned32(0x100000000), 0)
        self.assertEqual(to_unsigned32(-1), 0xFFFFFFFF)
        self.assertEqual(to_unsigned32(-4), 0xFFFFFFFC)

    def test_to_signed32(self):
        self.assertEqual(to_signed32(0), 0)
        self.assertEqual(to_signed32(100), 100)
        self.assertEqual(to_signed32(0x7FFFFFFF), 2147483647)
        self.assertEqual(to_signed32(0x80000000), -2147483648)
        self.assertEqual(to_signed32(0xFFFFFFFF), -1)
        self.assertEqual(to_signed32(0xFFFFFFFC), -4)

    def test_sign_extend_16_32(self):
        # Inmediatos positivos (bit 15 == 0)
        self.assertEqual(sign_extend_16_32(0), 0)
        self.assertEqual(sign_extend_16_32(0x0001), 1)
        self.assertEqual(sign_extend_16_32(0x7FFF), 32767)

        # Inmediatos negativos (bit 15 == 1)
        # -1 en 16 bits es 0xFFFF -> en 32 bits debe ser 0xFFFFFFFF
        self.assertEqual(sign_extend_16_32(0xFFFF), 0xFFFFFFFF)
        self.assertEqual(sign_extend_16_32(0xFFFC), 0xFFFFFFFC)
        # 0x8000 (-32768) -> 0xFFFF8000
        self.assertEqual(sign_extend_16_32(0x8000), 0xFFFF8000)

        # Con bits superiores sucios deben ser enmascarados
        self.assertEqual(sign_extend_16_32(0x1234FFFF), 0xFFFFFFFF)
        self.assertEqual(sign_extend_16_32(0x12340005), 5)

    def test_zero_extend_16_32(self):
        self.assertEqual(zero_extend_16_32(0), 0)
        self.assertEqual(zero_extend_16_32(0xFFFF), 0x0000FFFF)
        self.assertEqual(zero_extend_16_32(0x8000), 0x00008000)
        self.assertEqual(zero_extend_16_32(0x12345678), 0x5678)

    def test_get_bits(self):
        # 32 bits: 0x12345678 = 0001 0010 0011 0100 0101 0110 0111 1000
        val = 0x12345678

        # Extraer nibbles individuales
        self.assertEqual(get_bits(val, 3, 0), 0x8)
        self.assertEqual(get_bits(val, 7, 4), 0x7)
        self.assertEqual(get_bits(val, 11, 8), 0x6)
        self.assertEqual(get_bits(val, 15, 12), 0x5)
        self.assertEqual(get_bits(val, 31, 28), 0x1)

        # Extraer campos de instruccion MIPS
        # Opcode [31:26]
        # Ej: 0x20080019 -> opcode es bits 31..26
        # 0x20080019 = 0010 0000 0000 1000 ... -> opcode = 001000 = 8 (ADDI)
        instr = 0x20080019
        opcode = get_bits(instr, 31, 26)
        rs = get_bits(instr, 25, 21)
        rt = get_bits(instr, 20, 16)
        imm = get_bits(instr, 15, 0)

        self.assertEqual(opcode, 0x08)
        self.assertEqual(rs, 0)
        self.assertEqual(rt, 8)
        self.assertEqual(imm, 25)

        # Extraer un solo bit
        self.assertEqual(get_bits(val, 0, 0), 0)  # el bit 0 de 8 es 0 (1000)
        self.assertEqual(get_bits(val, 3, 3), 1)  # el bit 3 de 8 es 1 (1000)


if __name__ == "__main__":
    unittest.main()
