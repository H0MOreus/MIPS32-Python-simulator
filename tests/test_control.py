import unittest
from control import ControlUnit


class TestControlUnit(unittest.TestCase):

    def test_bubble_signals(self):
        signals = ControlUnit.make_bubble_signals()
        for k, v in signals.items():
            self.assertEqual(v, 0, f"Signal {k} should be 0 in bubble")

    def test_decode_nop_zero_instruction(self):
        signals = ControlUnit.decode(ControlUnit.OP_RTYPE, inst=0x00000000)
        self.assertEqual(signals, ControlUnit.make_bubble_signals())

    def test_decode_r_type(self):
        signals = ControlUnit.decode(ControlUnit.OP_RTYPE, inst=0x01485820)
        self.assertEqual(signals["RegDst"], 1)
        self.assertEqual(signals["ALUSrc"], 0)
        self.assertEqual(signals["MemtoReg"], 0)
        self.assertEqual(signals["RegWrite"], 1)
        self.assertEqual(signals["MemRead"], 0)
        self.assertEqual(signals["MemWrite"], 0)
        self.assertEqual(signals["Branch"], 0)
        self.assertEqual(signals["BranchNe"], 0)
        self.assertEqual(signals["Jump"], 0)
        self.assertEqual(signals["ALUOp"], 0b10)

    def test_decode_addi(self):
        signals = ControlUnit.decode(ControlUnit.OP_ADDI, inst=0x20080019)
        self.assertEqual(signals["RegDst"], 0)
        self.assertEqual(signals["ALUSrc"], 1)
        self.assertEqual(signals["MemtoReg"], 0)
        self.assertEqual(signals["RegWrite"], 1)
        self.assertEqual(signals["MemRead"], 0)
        self.assertEqual(signals["MemWrite"], 0)
        self.assertEqual(signals["ALUOp"], 0b00)

    def test_decode_lw(self):
        signals = ControlUnit.decode(ControlUnit.OP_LW, inst=0x8E0A0000)
        self.assertEqual(signals["RegDst"], 0)
        self.assertEqual(signals["ALUSrc"], 1)
        self.assertEqual(signals["MemtoReg"], 1)
        self.assertEqual(signals["RegWrite"], 1)
        self.assertEqual(signals["MemRead"], 1)
        self.assertEqual(signals["MemWrite"], 0)
        self.assertEqual(signals["ALUOp"], 0b00)

    def test_decode_sw(self):
        signals = ControlUnit.decode(ControlUnit.OP_SW, inst=0xAE090000)
        self.assertEqual(signals["ALUSrc"], 1)
        self.assertEqual(signals["MemWrite"], 1)
        self.assertEqual(signals["RegWrite"], 0)
        self.assertEqual(signals["MemRead"], 0)
        self.assertEqual(signals["ALUOp"], 0b00)

    def test_decode_beq(self):
        signals = ControlUnit.decode(ControlUnit.OP_BEQ, inst=0x112A0001)
        self.assertEqual(signals["ALUSrc"], 0)
        self.assertEqual(signals["Branch"], 1)
        self.assertEqual(signals["BranchNe"], 0)
        self.assertEqual(signals["RegWrite"], 0)
        self.assertEqual(signals["ALUOp"], 0b01)

    def test_decode_bne(self):
        signals = ControlUnit.decode(ControlUnit.OP_BNE, inst=0x152A0001)
        self.assertEqual(signals["ALUSrc"], 0)
        self.assertEqual(signals["Branch"], 0)
        self.assertEqual(signals["BranchNe"], 1)
        self.assertEqual(signals["RegWrite"], 0)
        self.assertEqual(signals["ALUOp"], 0b01)

    def test_decode_jump(self):
        signals = ControlUnit.decode(ControlUnit.OP_J, inst=0x08100004)
        self.assertEqual(signals["Jump"], 1)
        self.assertEqual(signals["RegWrite"], 0)
        self.assertEqual(signals["MemRead"], 0)
        self.assertEqual(signals["MemWrite"], 0)

    def test_decode_unsupported_opcode(self):
        with self.assertRaises(ValueError):
            ControlUnit.decode(0x3F, inst=0xFC000000)


if __name__ == "__main__":
    unittest.main()
