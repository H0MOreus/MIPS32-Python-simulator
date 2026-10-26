from typing import Any, Dict, List, Optional
from lib_bits import get_bits, sign_extend_16_32, zero_extend_16_32, to_unsigned32
from memorias import Memory
from registers import RegisterFile, ProgramCounter
from alu import ALU, ALUControl
from control import ControlUnit
from pipeline_regs import (
    IF_ID_Register,
    ID_EX_Register,
    EX_MEM_Register,
    MEM_WB_Register,
)
from forwarding import ForwardingUnit, HazardDetectionUnit


class MIPS32PipelineCPU:
    """
    Procesador MIPS32 segmentado de 5 etapas.
    """

    def __init__(self) -> None:
        self.memory = Memory()
        self.regs = RegisterFile()
        self.pc = ProgramCounter()

        self.control_unit = ControlUnit()
        self.alu = ALU()
        self.alu_control = ALUControl()
        self.forwarding = ForwardingUnit()
        self.hazards = HazardDetectionUnit()

        self.if_id = IF_ID_Register()
        self.id_ex = ID_EX_Register()
        self.ex_mem = EX_MEM_Register()
        self.mem_wb = MEM_WB_Register()

        self.program_end: int = Memory.TEXT_BASE

        # Banderas de parada por syscall
        self._syscall_in_pipeline: bool = False
        self.halted_by_syscall: bool = False

        # Contadores de rendimiento
        self.cycle_count: int = 0
        self.instructions_retired: int = 0
        self.load_use_stalls: int = 0
        self.branch_flushes: int = 0
        self.jump_flushes: int = 0

        # Cables transitorios intraciclo
        self._wb_reg_write: int = 0
        self._wb_write_reg: int = 0
        self._wb_write_data: int = 0x00000000

        self._ex_branch_taken: bool = False
        self._ex_branch_target: int = 0x00000000

        self._id_jump_taken: bool = False
        self._id_jump_target: int = 0x00000000

    def reset(self) -> None:
        self.memory.reset()
        self.regs.reset()
        self.pc.reset()

        self.if_id.flush()
        self.id_ex.flush()
        self.ex_mem.flush()
        self.mem_wb.flush()

        self.program_end = Memory.TEXT_BASE
        self._syscall_in_pipeline = False
        self.halted_by_syscall = False

        self.cycle_count = 0
        self.instructions_retired = 0
        self.load_use_stalls = 0
        self.branch_flushes = 0
        self.jump_flushes = 0
        self._reset_transient_wires()

    def _reset_transient_wires(self) -> None:
        self._wb_reg_write = 0
        self._wb_write_reg = 0
        self._wb_write_data = 0x00000000

        self._ex_branch_taken = False
        self._ex_branch_target = 0x00000000

        self._id_jump_taken = False
        self._id_jump_target = 0x00000000

    def load_program(
        self,
        machine_words: List[int],
        base_address: int = Memory.TEXT_BASE,
        data_bytes: Optional[bytes | bytearray] = None,
    ) -> None:
        self.if_id.flush()
        self.id_ex.flush()
        self.ex_mem.flush()
        self.mem_wb.flush()
        self._syscall_in_pipeline = False
        self.halted_by_syscall = False
        self.cycle_count = 0
        self.instructions_retired = 0
        self.load_use_stalls = 0
        self.branch_flushes = 0
        self.jump_flushes = 0
        self._reset_transient_wires()

        if data_bytes:
            self.memory.load_data_bytes(data_bytes, base_address=Memory.DATA_BASE)
        self.memory.load_program(machine_words, base_address)
        self.pc.write(base_address, pc_write=True)
        self.program_end = to_unsigned32(base_address + (len(machine_words) * 4))

    #(WB -> MEM -> EX -> ID -> IF)    

    def _stage_wb(self) -> None:
        if not self.mem_wb.valid:
            self._wb_reg_write = 0
            self._wb_write_reg = 0
            self._wb_write_data = 0x00000000
            return

        self.instructions_retired += 1

        # Si la instruccion que llega a WB es syscall, no hace nada y detiene la CPU
        if self.mem_wb.control.get("Syscall", 0) == 1:
            self._wb_reg_write = 0
            self._wb_write_reg = 0
            self._wb_write_data = 0x00000000
            self.halted_by_syscall = True
            return

        mem_to_reg = self.mem_wb.control.get("MemtoReg", 0)
        reg_write = self.mem_wb.control.get("RegWrite", 0)
        write_reg = self.mem_wb.data["write_reg"]

        if mem_to_reg == 1:
            write_data = self.mem_wb.data["mem_read_data"]
        else:
            write_data = self.mem_wb.data["alu_result"]

        write_data = to_unsigned32(write_data)
        self.regs.write(write_reg, write_data, reg_write=(reg_write == 1))

        self._wb_reg_write = reg_write
        self._wb_write_reg = write_reg
        self._wb_write_data = write_data

    def _stage_mem(self) -> None:
        if not self.ex_mem.valid:
            self.mem_wb.flush()
            return

        mem_read = self.ex_mem.control.get("MemRead", 0)
        mem_write = self.ex_mem.control.get("MemWrite", 0)
        mem_byte = self.ex_mem.control.get("MemByte", 0)
        mem_signed = bool(self.ex_mem.control.get("MemSigned", 0))
        alu_result = self.ex_mem.data["alu_result"]
        write_data = self.ex_mem.data["write_data"]

        mem_read_data = 0x00000000

        if mem_read == 1:
            if mem_byte == 1:
                mem_read_data = self.memory.read_byte(alu_result, signed=mem_signed)
            else:
                mem_read_data = self.memory.read_word(alu_result)
        elif mem_write == 1:
            if mem_byte == 1:
                self.memory.write_byte(alu_result, write_data)
            else:
                self.memory.write_word(alu_result, write_data)

        self.mem_wb.latch(
            valid=True,
            control=self.ex_mem.control,
            data={
                "pc": self.ex_mem.data["pc"],
                "mem_read_data": to_unsigned32(mem_read_data),
                "alu_result": to_unsigned32(alu_result),
                "write_reg": self.ex_mem.data["write_reg"],
            },
        )

    def _stage_ex(self) -> None:
        if not self.id_ex.valid:
            self.forwarding.reset()
            self.ex_mem.flush()
            return

        # Si es syscall, pasa directo hacia MEM sin operar la ALU
        if self.id_ex.control.get("Syscall", 0) == 1:
            self.forwarding.reset()
            self.ex_mem.latch(
                valid=True,
                control=self.id_ex.control,
                data={
                    "pc": self.id_ex.data["pc"],
                    "branch_target": 0,
                    "alu_zero": 0,
                    "alu_result": 0,
                    "write_data": 0,
                    "write_reg": 0,
                },
            )
            return

        self.forwarding.compute_signals(
            id_ex=self.id_ex,
            ex_mem=self.ex_mem,
            wb_reg_write=self._wb_reg_write,
            wb_write_reg=self._wb_write_reg,
        )

        alu_in_a, alu_in_b, rt_value_for_sw = self.forwarding.select_alu_operands(
            id_ex=self.id_ex,
            ex_mem=self.ex_mem,
            wb_write_data=self._wb_write_data,
        )

        alu_op = self.id_ex.control.get("ALUOp", 0b00)
        funct = self.id_ex.data["funct"]
        alu_ctrl_code = self.alu_control.resolve(alu_op, funct)

        alu_result, alu_zero = self.alu.execute(alu_in_a, alu_in_b, alu_ctrl_code)

        if self.id_ex.control.get("RegDst", 0) == 1:
            write_reg = self.id_ex.data["rd"]
        else:
            write_reg = self.id_ex.data["rt"]

        imm_ext = self.id_ex.data["imm_ext"]
        pc_plus_4 = self.id_ex.data["pc_plus_4"]
        branch_target = to_unsigned32(pc_plus_4 + (imm_ext << 2))

        self._ex_branch_taken = self.hazards.is_branch_taken_in_ex(self.id_ex, alu_zero)
        self._ex_branch_target = branch_target

        self.ex_mem.latch(
            valid=True,
            control=self.id_ex.control,
            data={
                "pc": self.id_ex.data["pc"],
                "branch_target": branch_target,
                "alu_zero": 1 if alu_zero else 0,
                "alu_result": alu_result,
                "write_data": rt_value_for_sw,
                "write_reg": write_reg,
            },
        )

    def _stage_id(self) -> None:
        if not self.if_id.valid:
            self.hazards.evaluate_hazards_in_id(
                if_id=self.if_id,
                id_ex=self.id_ex,
                branch_taken_in_ex=self._ex_branch_taken,
                jump_in_id=False,
            )
            if self._ex_branch_taken:
                self.branch_flushes += 1
                self._syscall_in_pipeline = False  # Si un salto anulo una syscall especulativa
            self.id_ex.flush()
            return

        instr = self.if_id.data["instr"]
        pc = self.if_id.data["pc"]
        pc_plus_4 = self.if_id.data["pc_plus_4"]

        opcode = get_bits(instr, 31, 26)
        rs = get_bits(instr, 25, 21)
        rt = get_bits(instr, 20, 16)
        rd = get_bits(instr, 15, 11)
        imm16 = get_bits(instr, 15, 0)
        funct = get_bits(instr, 5, 0)
        jump_index_26 = get_bits(instr, 25, 0)

        control_signals = self.control_unit.decode(opcode, full_instruction=instr)

        if control_signals.get("Jump", 0) == 1:
            self._id_jump_taken = True
            self._id_jump_target = to_unsigned32((pc_plus_4 & 0xF0000000) | (jump_index_26 << 2))
        else:
            self._id_jump_taken = False
            self._id_jump_target = 0x00000000

        self.hazards.evaluate_hazards_in_id(
            if_id=self.if_id,
            id_ex=self.id_ex,
            branch_taken_in_ex=self._ex_branch_taken,
            jump_in_id=self._id_jump_taken,
        )

        if self._ex_branch_taken:
            self.branch_flushes += 1
            self._syscall_in_pipeline = False
        elif self.hazards.load_use_stall:
            self.load_use_stalls += 1
        elif self._id_jump_taken:
            self.jump_flushes += 1

        if self.hazards.id_ex_flush:
            self.id_ex.flush()
            return

        # Si entra una syscall valida en ID/EX, bloqueamos busquedas posteriores en IF
        if control_signals.get("Syscall", 0) == 1:
            self._syscall_in_pipeline = True

        read_data_1 = self.regs.read(rs)
        read_data_2 = self.regs.read(rt)

        if control_signals.get("ZeroExt", 0) == 1:
            imm_ext = zero_extend_16_32(imm16)
        else:
            imm_ext = sign_extend_16_32(imm16)

        self.id_ex.latch(
            valid=True,
            control=control_signals,
            data={
                "pc": pc,
                "pc_plus_4": pc_plus_4,
                "read_data_1": read_data_1,
                "read_data_2": read_data_2,
                "imm_ext": imm_ext,
                "rs": rs,
                "rt": rt,
                "rd": rd,
                "funct": funct,
            },
        )

    def _stage_if(self) -> None:
        if self.hazards.if_id_flush:
            self.if_id.flush()
            if self._ex_branch_taken:
                self.pc.write(self._ex_branch_target, pc_write=self.hazards.pc_write)
            elif self._id_jump_taken:
                self.pc.write(self._id_jump_target, pc_write=self.hazards.pc_write)
            return

        if self.hazards.if_id_stall:
            self.if_id.stall(True)
            self.pc.write(self.pc.value, pc_write=False)
            self.if_id.stall(False)
            return

        # Si ya se detecto syscall o se alcanzo el fin del programa, drenar con burbujas
        current_pc = self.pc.value
        if self._syscall_in_pipeline or self.halted_by_syscall or current_pc >= self.program_end:
            self.if_id.flush()
            return

        instr = self.memory.fetch_instruction(current_pc)
        pc_plus_4 = to_unsigned32(current_pc + 4)

        self.if_id.latch(
            valid=True,
            control=ControlUnit.make_bubble_signals(),
            data={
                "instr": instr,
                "pc_plus_4": pc_plus_4,
                "pc": current_pc,
            },
        )
        self.pc.write(pc_plus_4, pc_write=self.hazards.pc_write)

    # Interfaz

    def step_cycle(self) -> Dict[str, Any]:
        self._reset_transient_wires()
        self.cycle_count += 1

        self._stage_wb()
        if not self.halted_by_syscall:
            self._stage_mem()
            self._stage_ex()
            self._stage_id()
            self._stage_if()
        else:
            # Al terminar por syscall en WB, limpiamos el resto del cauce
            self.if_id.flush()
            self.id_ex.flush()
            self.ex_mem.flush()
            self.mem_wb.flush()

        return self.get_cycle_snapshot()

    def is_pipeline_empty(self) -> bool:
        return not (
            self.if_id.valid
            or self.id_ex.valid
            or self.ex_mem.valid
            or self.mem_wb.valid
        )

    def is_halted(self) -> bool:
        return self.halted_by_syscall or (
            (self.pc.value >= self.program_end) and self.is_pipeline_empty()
        )

    def run(self, max_cycles: int = 10000) -> List[Dict[str, Any]]:
        history: List[Dict[str, Any]] = []
        while not self.is_halted() and self.cycle_count < max_cycles:
            snapshot = self.step_cycle()
            history.append(snapshot)
        return history

    def get_cycle_snapshot(self) -> Dict[str, Any]:
        return {
            "cycle": self.cycle_count,
            "pc": f"0x{self.pc.value:08X}",
            "ForwardA": f"0b{self.forwarding.forward_a:02b}",
            "ForwardB": f"0b{self.forwarding.forward_b:02b}",
            "load_use_stall": self.hazards.load_use_stall,
            "branch_taken": self._ex_branch_taken,
            "jump_taken": self._id_jump_taken,
            "halted_by_syscall": self.halted_by_syscall,
            "stages": {
                "IF/ID": self.if_id.snapshot(),
                "ID/EX": self.id_ex.snapshot(),
                "EX/MEM": self.ex_mem.snapshot(),
                "MEM/WB": self.mem_wb.snapshot(),
            },
            "registers": self.regs.dump(cond=True),
        }
