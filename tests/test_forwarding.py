import unittest
from forwarding import ForwardingUnit, HazardDetectionUnit
from pipeline_regs import IF_ID_Register, ID_EX_Register, EX_MEM_Register
from control import ControlUnit


class TestForwardingUnit(unittest.TestCase):

    def setUp(self):
        self.fu = ForwardingUnit()
        self.id_ex = ID_EX_Register()
        self.ex_mem = EX_MEM_Register()

    def test_no_forwarding_when_invalid(self):
        fwd_a, fwd_b = self.fu.compute_signals(
            id_ex=self.id_ex,
            ex_mem=self.ex_mem,
            wb_reg_write=0,
            wb_write_reg=0,
        )
        self.assertEqual(fwd_a, ForwardingUnit.NO_FORWARD)
        self.assertEqual(fwd_b, ForwardingUnit.NO_FORWARD)

    def test_ex_hazard_forwarding_rs_and_rt(self):
        # Instruccion en EX lee rs=8 y rt=9
        self.id_ex.latch(
            valid=True,
            control={"RegWrite": 1, "ALUSrc": 0},
            data={"rs": 8, "rt": 9, "read_data_1": 10, "read_data_2": 20},
        )
        # Instruccion previa en EX/MEM escribe en el registro 8
        self.ex_mem.latch(
            valid=True,
            control={"RegWrite": 1},
            data={"write_reg": 8, "alu_result": 99},
        )

        fwd_a, fwd_b = self.fu.compute_signals(
            id_ex=self.id_ex,
            ex_mem=self.ex_mem,
            wb_reg_write=0,
            wb_write_reg=0,
        )
        self.assertEqual(fwd_a, ForwardingUnit.FROM_EX_MEM)
        self.assertEqual(fwd_b, ForwardingUnit.NO_FORWARD)

        # Ahora tambien escribe en el registro 9
        self.ex_mem.latch(
            valid=True,
            control={"RegWrite": 1},
            data={"write_reg": 9, "alu_result": 77},
        )
        fwd_a, fwd_b = self.fu.compute_signals(
            id_ex=self.id_ex,
            ex_mem=self.ex_mem,
            wb_reg_write=0,
            wb_write_reg=0,
        )
        self.assertEqual(fwd_a, ForwardingUnit.NO_FORWARD)
        self.assertEqual(fwd_b, ForwardingUnit.FROM_EX_MEM)

    def test_mem_hazard_forwarding(self):
        # Instruccion en EX lee rs=8
        self.id_ex.latch(
            valid=True,
            control={"RegWrite": 1, "ALUSrc": 0},
            data={"rs": 8, "rt": 9, "read_data_1": 10, "read_data_2": 20},
        )
        # EX/MEM no escribe en 8
        self.ex_mem.latch(
            valid=True,
            control={"RegWrite": 1},
            data={"write_reg": 15, "alu_result": 55},
        )

        # Pero WB escribe en 8
        fwd_a, fwd_b = self.fu.compute_signals(
            id_ex=self.id_ex,
            ex_mem=self.ex_mem,
            wb_reg_write=1,
            wb_write_reg=8,
        )
        self.assertEqual(fwd_a, ForwardingUnit.FROM_MEM_WB)
        self.assertEqual(fwd_b, ForwardingUnit.NO_FORWARD)

    def test_double_hazard_priority(self):
        # Si tanto EX/MEM como WB escriben en el mismo registro, EX/MEM tiene prioridad
        self.id_ex.latch(
            valid=True,
            control={"RegWrite": 1, "ALUSrc": 0},
            data={"rs": 8, "rt": 8, "read_data_1": 1, "read_data_2": 1},
        )
        self.ex_mem.latch(
            valid=True,
            control={"RegWrite": 1},
            data={"write_reg": 8, "alu_result": 200},
        )

        fwd_a, fwd_b = self.fu.compute_signals(
            id_ex=self.id_ex,
            ex_mem=self.ex_mem,
            wb_reg_write=1,
            wb_write_reg=8,
        )
        self.assertEqual(fwd_a, ForwardingUnit.FROM_EX_MEM)
        self.assertEqual(fwd_b, ForwardingUnit.FROM_EX_MEM)

    def test_never_forward_zero_register(self):
        # $zero ($0) nunca debe generar forwarding
        self.id_ex.latch(
            valid=True,
            control={"RegWrite": 1},
            data={"rs": 0, "rt": 0, "read_data_1": 0, "read_data_2": 0},
        )
        self.ex_mem.latch(
            valid=True,
            control={"RegWrite": 1},
            data={"write_reg": 0, "alu_result": 999},
        )

        fwd_a, fwd_b = self.fu.compute_signals(
            id_ex=self.id_ex,
            ex_mem=self.ex_mem,
            wb_reg_write=1,
            wb_write_reg=0,
        )
        self.assertEqual(fwd_a, ForwardingUnit.NO_FORWARD)
        self.assertEqual(fwd_b, ForwardingUnit.NO_FORWARD)

    def test_select_alu_operands(self):
        self.id_ex.latch(
            valid=True,
            control={"ALUSrc": 0},
            data={"read_data_1": 10, "read_data_2": 20, "imm_ext": 30, "rs": 8, "rt": 9},
        )
        self.ex_mem.latch(
            valid=True,
            control={"RegWrite": 1},
            data={"write_reg": 8, "alu_result": 100},
        )
        self.fu.forward_a = ForwardingUnit.FROM_EX_MEM
        self.fu.forward_b = ForwardingUnit.FROM_MEM_WB

        alu_a, alu_b, sw_val = self.fu.select_alu_operands(
            id_ex=self.id_ex,
            ex_mem=self.ex_mem,
            wb_write_data=200,
        )
        self.assertEqual(alu_a, 100)
        self.assertEqual(alu_b, 200)
        self.assertEqual(sw_val, 200)

        # Con ALUSrc=1 (Tipo-I), alu_in_b selecciona imm_ext, pero sw_val conserva el valor de rt
        self.id_ex.control["ALUSrc"] = 1
        alu_a, alu_b, sw_val = self.fu.select_alu_operands(
            id_ex=self.id_ex,
            ex_mem=self.ex_mem,
            wb_write_data=200,
        )
        self.assertEqual(alu_a, 100)
        self.assertEqual(alu_b, 30)
        self.assertEqual(sw_val, 200)


class TestHazardDetectionUnit(unittest.TestCase):

    def setUp(self):
        self.hdu = HazardDetectionUnit()
        self.if_id = IF_ID_Register()
        self.id_ex = ID_EX_Register()

    def test_detect_load_use_on_rs(self):
        # Instruccion en ID/EX es 'lw' (MemRead=1) hacia rt=8
        self.id_ex.latch(
            valid=True,
            control={"MemRead": 1},
            data={"rt": 8},
        )
        # Instruccion en IF/ID es 'add $t3, $t0, $t1' -> opcode 0, rs=8, rt=9
        # Formato Tipo-R: (rs=8 << 21) | (rt=9 << 16) | (rd=11 << 11) | funct 0x20
        instr = (0 << 26) | (8 << 21) | (9 << 16) | (11 << 11) | 0x20
        self.if_id.latch(
            valid=True,
            control=ControlUnit.make_bubble_signals(),
            data={"instr": instr},
        )

        has_hazard = self.hdu.detect_load_use(self.if_id, self.id_ex)
        self.assertTrue(has_hazard)

    def test_detect_load_use_on_rt(self):
        # 'lw' hacia rt=9
        self.id_ex.latch(
            valid=True,
            control={"MemRead": 1},
            data={"rt": 9},
        )
        # 'add $t3, $t0, $t1' -> rs=8, rt=9
        instr = (0 << 26) | (8 << 21) | (9 << 16) | (11 << 11) | 0x20
        self.if_id.latch(
            valid=True,
            control=ControlUnit.make_bubble_signals(),
            data={"instr": instr},
        )

        has_hazard = self.hdu.detect_load_use(self.if_id, self.id_ex)
        self.assertTrue(has_hazard)

    def test_no_load_use_for_non_lw(self):
        # Instruccion en ID/EX no es lw (MemRead=0)
        self.id_ex.latch(
            valid=True,
            control={"MemRead": 0},
            data={"rt": 8},
        )
        instr = (0 << 26) | (8 << 21) | (9 << 16) | (11 << 11) | 0x20
        self.if_id.latch(
            valid=True,
            control=ControlUnit.make_bubble_signals(),
            data={"instr": instr},
        )

        self.assertFalse(self.hdu.detect_load_use(self.if_id, self.id_ex))

    def test_no_load_use_on_addi_destination(self):
        # 'lw' hacia rt=8
        self.id_ex.latch(
            valid=True,
            control={"MemRead": 1},
            data={"rt": 8},
        )
        # 'addi $t0, $zero, 10' -> rs=0, rt=8 (addi solo lee rs, no rt!)
        instr = (ControlUnit.OP_ADDI << 26) | (0 << 21) | (8 << 16) | 10
        self.if_id.latch(
            valid=True,
            control=ControlUnit.make_bubble_signals(),
            data={"instr": instr},
        )

        # No hay riesgo Load-Use porque addi sobreescribe rt sin leerlo
        self.assertFalse(self.hdu.detect_load_use(self.if_id, self.id_ex))

    def test_evaluate_hazards_priority(self):
        # Prioridad 1: Branch taken en EX anula todo y vacia IF/ID y ID/EX
        self.hdu.evaluate_hazards_in_id(
            if_id=self.if_id,
            id_ex=self.id_ex,
            branch_taken_in_ex=True,
            jump_in_id=True,
        )
        self.assertTrue(self.hdu.if_id_flush)
        self.assertTrue(self.hdu.id_ex_flush)
        self.assertTrue(self.hdu.pc_write)

        # Prioridad 2: Load-Use stall congela PC e IF/ID, e inyecta burbuja en ID/EX
        self.id_ex.latch(valid=True, control={"MemRead": 1}, data={"rt": 8})
        instr = (0 << 26) | (8 << 21) | (0 << 16) | (1 << 11) | 0x20
        self.if_id.latch(valid=True, control={}, data={"instr": instr})

        self.hdu.evaluate_hazards_in_id(
            if_id=self.if_id,
            id_ex=self.id_ex,
            branch_taken_in_ex=False,
            jump_in_id=False,
        )
        self.assertFalse(self.hdu.pc_write)
        self.assertTrue(self.hdu.if_id_stall)
        self.assertTrue(self.hdu.id_ex_flush)
        self.assertTrue(self.hdu.load_use_stall)

        # Prioridad 3: Jump en ID vacia IF/ID
        self.hdu.evaluate_hazards_in_id(
            if_id=self.if_id,
            id_ex=ID_EX_Register(),  # sin load-use
            branch_taken_in_ex=False,
            jump_in_id=True,
        )
        self.assertTrue(self.hdu.if_id_flush)
        self.assertFalse(self.hdu.id_ex_flush)
        self.assertTrue(self.hdu.pc_write)

    def test_is_branch_taken_in_ex(self):
        # beq tomado cuando alu_zero=True
        self.id_ex.latch(valid=True, control={"Branch": 1, "BranchNe": 0}, data={})
        self.assertTrue(HazardDetectionUnit.is_branch_taken_in_ex(self.id_ex, alu_zero=True))
        self.assertFalse(HazardDetectionUnit.is_branch_taken_in_ex(self.id_ex, alu_zero=False))

        # bne tomado cuando alu_zero=False
        self.id_ex.latch(valid=True, control={"Branch": 0, "BranchNe": 1}, data={})
        self.assertTrue(HazardDetectionUnit.is_branch_taken_in_ex(self.id_ex, alu_zero=False))
        self.assertFalse(HazardDetectionUnit.is_branch_taken_in_ex(self.id_ex, alu_zero=True))


if __name__ == "__main__":
    unittest.main()
