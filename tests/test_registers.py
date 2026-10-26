import unittest
from registers import RegisterFile, ProgramCounter


class TestRegisterFile(unittest.TestCase):

    def setUp(self):
        self.rf = RegisterFile()

    def test_initial_state(self):
        for i in range(32):
            self.assertEqual(self.rf.read(i), 0)

    def test_read_write(self):
        self.rf.write(8, 0x12345678)
        self.assertEqual(self.rf.read(8), 0x12345678)

        # Truncamiento a 32 bits en la escritura
        self.rf.write(9, 0x100000005)
        self.assertEqual(self.rf.read(9), 0x00000005)

    def test_reg_write_false(self):
        self.rf.write(8, 100, reg_write=False)
        self.assertEqual(self.rf.read(8), 0)

    def test_zero_register_invariance(self):
        # El registro $zero ($0) nunca debe cambiar de valor
        self.assertEqual(self.rf.read(0), 0)
        self.rf.write(0, 999, reg_write=True)
        self.assertEqual(self.rf.read(0), 0)

    def test_out_of_bounds(self):
        with self.assertRaises(ValueError):
            self.rf.read(-1)
        with self.assertRaises(ValueError):
            self.rf.read(32)
        with self.assertRaises(ValueError):
            self.rf.write(-1, 10)
        with self.assertRaises(ValueError):
            self.rf.write(32, 10)

    def test_resolve_name(self):
        self.assertEqual(RegisterFile.resolve_name("$zero"), 0)
        self.assertEqual(RegisterFile.resolve_name("$0"), 0)
        self.assertEqual(RegisterFile.resolve_name("$at"), 1)
        self.assertEqual(RegisterFile.resolve_name("$v0"), 2)
        self.assertEqual(RegisterFile.resolve_name("$a0"), 4)
        self.assertEqual(RegisterFile.resolve_name("$t0"), 8)
        self.assertEqual(RegisterFile.resolve_name("$8"), 8)
        self.assertEqual(RegisterFile.resolve_name("$s0"), 16)
        self.assertEqual(RegisterFile.resolve_name("$16"), 16)
        self.assertEqual(RegisterFile.resolve_name("$sp"), 29)
        self.assertEqual(RegisterFile.resolve_name("$ra"), 31)

        # Insensibilidad a mayusculas y espacios
        self.assertEqual(RegisterFile.resolve_name("  $T0  "), 8)
        self.assertEqual(RegisterFile.resolve_name("$ZERO"), 0)

        # Nombres invalidos
        with self.assertRaises(ValueError):
            RegisterFile.resolve_name("$invalid")
        with self.assertRaises(ValueError):
            RegisterFile.resolve_name("$32")

    def test_reset(self):
        self.rf.write(8, 42)
        self.rf.write(16, 100)
        self.rf.reset()
        self.assertEqual(self.rf.read(8), 0)
        self.assertEqual(self.rf.read(16), 0)

    def test_dump(self):
        self.rf.write(8, 0x1A)
        # dump cond=True incluye $zero y los no nulos
        d_cond = self.rf.dump(cond=True)
        self.assertIn("$zero ($0)", d_cond)
        self.assertIn("$t0 ($8)", d_cond)
        self.assertEqual(d_cond["$t0 ($8)"], "0x0000001A")
        self.assertNotIn("$t1 ($9)", d_cond)

        # dump cond=False incluye los 32 registros
        d_all = self.rf.dump(cond=False)
        self.assertEqual(len(d_all), 32)


class TestProgramCounter(unittest.TestCase):

    def setUp(self):
        self.pc = ProgramCounter()

    def test_initial_value(self):
        self.assertEqual(self.pc.value, ProgramCounter.INITIAL_PC)
        self.assertEqual(self.pc.value, 0x00400000)

    def test_write_and_read(self):
        self.pc.write(0x00400004)
        self.assertEqual(self.pc.value, 0x00400004)

        # Escritura condicional deshabilitada
        self.pc.write(0x00400008, pc_write=False)
        self.assertEqual(self.pc.value, 0x00400004)

        # Truncamiento a 32 bits
        self.pc.write(0x100400008)
        self.assertEqual(self.pc.value, 0x00400008)

    def test_reset(self):
        self.pc.write(0x00401000)
        self.pc.reset()
        self.assertEqual(self.pc.value, ProgramCounter.INITIAL_PC)


if __name__ == "__main__":
    unittest.main()
