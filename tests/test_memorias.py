import unittest
from memorias import (
    Memory,
    AlignmentError,
    SegmentationFault,
)


class TestMemory(unittest.TestCase):

    def setUp(self):
        self.mem = Memory(strict_text_protection=True)

    def test_load_and_fetch_program(self):
        program = [0x20080019, 0x2109000F, 0xAE090000]
        self.mem.load_program(program, Memory.TEXT_BASE)

        self.assertEqual(self.mem.fetch_instruction(0x00400000), 0x20080019)
        self.assertEqual(self.mem.fetch_instruction(0x00400004), 0x2109000F)
        self.assertEqual(self.mem.fetch_instruction(0x00400008), 0xAE090000)

    def test_data_read_write_word(self):
        addr = Memory.DATA_BASE  # 0x10000000
        self.mem.write_word(addr, 0x12345678)
        self.assertEqual(self.mem.read_word(addr), 0x12345678)

        self.mem.write_word(addr + 4, 42)
        self.assertEqual(self.mem.read_word(addr + 4), 42)

    def test_data_read_write_byte(self):
        addr = Memory.DATA_BASE
        self.mem.write_byte(addr, 0xAB)
        self.mem.write_byte(addr + 1, 0x12)
        # Lectura sin signo (lbu): no extiende signo
        self.assertEqual(self.mem.read_byte(addr, signed=False), 0xAB)
        self.assertEqual(self.mem.read_byte(addr + 1, signed=False), 0x12)
        # Lectura con signo (lb): extiende el bit mas significativo (0xAB es negativo -> 0xFFFFFFAB)
        self.assertEqual(self.mem.read_byte(addr, signed=True), 0xFFFFFFAB)
        self.assertEqual(self.mem.read_byte(addr + 1, signed=True), 0x12)

    def test_word_alignment_error(self):
        # En .data
        with self.assertRaises(AlignmentError):
            self.mem.read_word(Memory.DATA_BASE + 1)
        with self.assertRaises(AlignmentError):
            self.mem.read_word(Memory.DATA_BASE + 2)
        with self.assertRaises(AlignmentError):
            self.mem.read_word(Memory.DATA_BASE + 3)
        with self.assertRaises(AlignmentError):
            self.mem.write_word(Memory.DATA_BASE + 1, 100)

        # En .text
        with self.assertRaises(AlignmentError):
            self.mem.fetch_instruction(Memory.TEXT_BASE + 1)

    def test_strict_text_protection(self):
        # Escribir en .text debe lanzar SegmentationFault si strict_text_protection=True
        with self.assertRaises(SegmentationFault):
            self.mem.write_word(Memory.TEXT_BASE, 0x12345678)

    def test_segmentation_fault_out_of_bounds(self):
        # Fuera de rango inferior
        with self.assertRaises(SegmentationFault):
            self.mem.read_word(0x00000000)

        # Entre .text y .data
        with self.assertRaises(SegmentationFault):
            self.mem.read_word(0x00500000)

        # Fuera de rango superior de .data
        with self.assertRaises(SegmentationFault):
            self.mem.read_word(Memory.DATA_BASE + Memory.DATA_SIZE + 4)

        # Fetch fuera de .text
        with self.assertRaises(SegmentationFault):
            self.mem.fetch_instruction(Memory.DATA_BASE)

    def test_reset(self):
        self.mem.load_program([0x12345678], Memory.TEXT_BASE)
        self.mem.write_word(Memory.DATA_BASE, 0x99999999)
        self.mem.reset()
        self.assertEqual(self.mem.fetch_instruction(Memory.TEXT_BASE), 0)
        self.assertEqual(self.mem.read_word(Memory.DATA_BASE), 0)


if __name__ == "__main__":
    unittest.main()
