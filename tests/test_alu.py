import unittest
from alu import ALU, ALUControl


class TestALUControl(unittest.TestCase):

    def test_resolve_addi_lw_sw(self):
        # ALUOp == 0b00 -> ALU_ADD
        self.assertEqual(ALUControl.resolve(0b00, 0), ALUControl.ALU_ADD)
        self.assertEqual(ALUControl.resolve(0b00, 0x20), ALUControl.ALU_ADD)

    def test_resolve_branch(self):
        # ALUOp == 0b01 -> ALU_SUB
        self.assertEqual(ALUControl.resolve(0b01, 0), ALUControl.ALU_SUB)

    def test_resolve_r_type(self):
        # ALUOp == 0b10 -> decodificacion por campo funct
        self.assertEqual(ALUControl.resolve(0b10, ALUControl.FUNCT_ADD), ALUControl.ALU_ADD)
        self.assertEqual(ALUControl.resolve(0b10, ALUControl.FUNCT_SUB), ALUControl.ALU_SUB)
        self.assertEqual(ALUControl.resolve(0b10, ALUControl.FUNCT_AND), ALUControl.ALU_AND)
        self.assertEqual(ALUControl.resolve(0b10, ALUControl.FUNCT_OR), ALUControl.ALU_OR)
        self.assertEqual(ALUControl.resolve(0b10, ALUControl.FUNCT_NOR), ALUControl.ALU_NOR)
        self.assertEqual(ALUControl.resolve(0b10, ALUControl.FUNCT_SLT), ALUControl.ALU_SLT)
        self.assertEqual(ALUControl.resolve(0b10, ALUControl.FUNCT_NOP), ALUControl.ALU_ADD)

    def test_resolve_invalid_funct(self):
        with self.assertRaises(ValueError):
            ALUControl.resolve(0b10, 0x3F)

    def test_resolve_invalid_aluop(self):
        with self.assertRaises(ValueError):
            ALUControl.resolve(0b11, 0)


class TestALU(unittest.TestCase):

    def test_and(self):
        res, zero = ALU.execute(0b1100, 0b1010, ALUControl.ALU_AND)
        self.assertEqual(res, 0b1000)
        self.assertFalse(zero)

        res, zero = ALU.execute(0b1100, 0b0011, ALUControl.ALU_AND)
        self.assertEqual(res, 0)
        self.assertTrue(zero)

    def test_or(self):
        res, zero = ALU.execute(0b1100, 0b1010, ALUControl.ALU_OR)
        self.assertEqual(res, 0b1110)
        self.assertFalse(zero)

        res, zero = ALU.execute(0, 0, ALUControl.ALU_OR)
        self.assertEqual(res, 0)
        self.assertTrue(zero)

    def test_nor(self):
        res, zero = ALU.execute(0, 0, ALUControl.ALU_NOR)
        self.assertEqual(res, 0xFFFFFFFF)
        self.assertFalse(zero)

        res, zero = ALU.execute(0xFFFFFFFF, 0, ALUControl.ALU_NOR)
        self.assertEqual(res, 0)
        self.assertTrue(zero)

    def test_add(self):
        res, zero = ALU.execute(15, 25, ALUControl.ALU_ADD)
        self.assertEqual(res, 40)
        self.assertFalse(zero)

        # Desbordamiento a 32 bits
        res, zero = ALU.execute(0xFFFFFFFF, 1, ALUControl.ALU_ADD)
        self.assertEqual(res, 0)
        self.assertTrue(zero)

    def test_sub(self):
        res, zero = ALU.execute(40, 15, ALUControl.ALU_SUB)
        self.assertEqual(res, 25)
        self.assertFalse(zero)

        # Resta que resulta en cero
        res, zero = ALU.execute(50, 50, ALUControl.ALU_SUB)
        self.assertEqual(res, 0)
        self.assertTrue(zero)

        # Resta que da numero negativo en complemento a dos
        res, zero = ALU.execute(5, 10, ALUControl.ALU_SUB)
        self.assertEqual(res, 0xFFFFFFFB)  # -5 en 32 bits
        self.assertFalse(zero)

    def test_slt(self):
        # Con signo: 5 < 10 -> 1
        res, zero = ALU.execute(5, 10, ALUControl.ALU_SLT)
        self.assertEqual(res, 1)
        self.assertFalse(zero)

        # 10 < 5 -> 0
        res, zero = ALU.execute(10, 5, ALUControl.ALU_SLT)
        self.assertEqual(res, 0)
        self.assertTrue(zero)

        # Iguales: 5 < 5 -> 0
        res, zero = ALU.execute(5, 5, ALUControl.ALU_SLT)
        self.assertEqual(res, 0)
        self.assertTrue(zero)

        # Negativo vs positivo: -5 < 5 -> 1
        # 0xFFFFFFFB = -5, 5 = 5
        res, zero = ALU.execute(0xFFFFFFFB, 5, ALUControl.ALU_SLT)
        self.assertEqual(res, 1)
        self.assertFalse(zero)

        # Positivo vs negativo: 5 < -5 -> 0
        res, zero = ALU.execute(5, 0xFFFFFFFB, ALUControl.ALU_SLT)
        self.assertEqual(res, 0)
        self.assertTrue(zero)

        # Negativo vs negativo: -10 < -5 -> 1
        # -10 = 0xFFFFFFF6, -5 = 0xFFFFFFFB
        res, zero = ALU.execute(0xFFFFFFF6, 0xFFFFFFFB, ALUControl.ALU_SLT)
        self.assertEqual(res, 1)
        self.assertFalse(zero)

    def test_invalid_control(self):
        with self.assertRaises(ValueError):
            ALU.execute(1, 2, 0b1111)


if __name__ == "__main__":
    unittest.main()
