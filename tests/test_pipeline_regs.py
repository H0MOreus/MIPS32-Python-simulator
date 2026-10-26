import unittest
from pipeline_regs import (
    PipelineRegister,
    IF_ID_Register,
    ID_EX_Register,
    EX_MEM_Register,
    MEM_WB_Register,
)
from control import ControlUnit


class TestPipelineRegisters(unittest.TestCase):

    def test_base_register_initial(self):
        reg = PipelineRegister("TEST")
        self.assertEqual(reg.name, "TEST")
        self.assertFalse(reg.valid)
        self.assertFalse(reg.stalled)
        self.assertEqual(reg.control, ControlUnit.make_bubble_signals())
        self.assertEqual(reg.data, {})

    def test_latch_and_flush(self):
        reg = PipelineRegister("TEST")
        ctrl = {"RegWrite": 1, "ALUSrc": 1}
        data = {"val": 123}

        reg.latch(valid=True, control=ctrl, data=data)
        self.assertTrue(reg.valid)
        self.assertEqual(reg.control["RegWrite"], 1)
        self.assertEqual(reg.data["val"], 123)

        # Latch con valid=False debe purgar
        reg.latch(valid=False, control=ctrl, data=data)
        self.assertFalse(reg.valid)
        self.assertEqual(reg.control, ControlUnit.make_bubble_signals())

    def test_stall(self):
        reg = PipelineRegister("TEST")
        reg.stall(True)
        reg.latch(valid=True, control={"RegWrite": 1}, data={"x": 1})
        self.assertFalse(reg.valid)  # No debe latch si esta stalled

        reg.stall(False)
        reg.latch(valid=True, control={"RegWrite": 1}, data={"x": 1})
        self.assertTrue(reg.valid)

    def test_if_id_register(self):
        reg = IF_ID_Register()
        self.assertEqual(reg.name, "IF/ID")
        self.assertIn("instr", reg.data)
        self.assertIn("pc_plus_4", reg.data)
        self.assertIn("pc", reg.data)

        reg.latch(
            valid=True,
            control=ControlUnit.make_bubble_signals(),
            data={"instr": 0x20080019, "pc_plus_4": 0x00400004, "pc": 0x00400000},
        )
        self.assertEqual(reg.data["instr"], 0x20080019)
        self.assertEqual(reg.data["pc"], 0x00400000)

    def test_id_ex_register(self):
        reg = ID_EX_Register()
        self.assertEqual(reg.name, "ID/EX")
        default_keys = ["pc", "pc_plus_4", "read_data_1", "read_data_2", "imm_ext", "rs", "rt", "rd", "funct"]
        for k in default_keys:
            self.assertIn(k, reg.data)

    def test_ex_mem_register(self):
        reg = EX_MEM_Register()
        self.assertEqual(reg.name, "EX/MEM")
        default_keys = ["pc", "branch_target", "alu_zero", "alu_result", "write_data", "rd"]
        for k in default_keys:
            self.assertIn(k, reg.data)

    def test_mem_wb_register(self):
        reg = MEM_WB_Register()
        self.assertEqual(reg.name, "MEM/WB")
        default_keys = ["pc", "read_data", "alu_result", "rd"]
        for k in default_keys:
            self.assertIn(k, reg.data)

    def test_snapshot(self):
        reg = IF_ID_Register()
        reg.latch(
            valid=True,
            control=ControlUnit.make_bubble_signals(),
            data={"instr": 0x20080019, "pc_plus_4": 0x00400004, "pc": 0x00400000},
        )
        snap = reg.snapshot()
        self.assertEqual(snap["name"], "IF/ID")
        self.assertTrue(snap["valid"])
        self.assertEqual(snap["data"]["instr"], "0x20080019")


if __name__ == "__main__":
    unittest.main()
