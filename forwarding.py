from typing import Tuple
from lib_bits import get_bits, to_unsigned32
from control import ControlUnit
from pipeline_regs import IF_ID_Register, ID_EX_Register, EX_MEM_Register


class ForwardingUnit:
    """ 
      - id_ex          : Registro ID/EX; instruccion actual en EX (I3).
      - ex_mem         : Registro EX/MEM; instruccion anterior (I2).
      - wb_reg_write   : Signal RegWrite (0 o 1); retenida de WB en el Paso 1 (I1).
      - wb_write_reg   : Registro destino (0..31) retenido de WB en el Paso 1 (I1).
      - wb_write_data 
    """
    
    NO_FORWARD  = 0b00  
    FROM_MEM_WB = 0b01  
    FROM_EX_MEM = 0b10  

    def __init__(self) -> None:
        self.forward_a: int = self.NO_FORWARD
        self.forward_b: int = self.NO_FORWARD

    def reset(self) -> None:
        self.forward_a = self.NO_FORWARD
        self.forward_b = self.NO_FORWARD

    def compute_signals(
        self,
        id_ex: ID_EX_Register,
        ex_mem: EX_MEM_Register,
        wb_reg_write: int,
        wb_write_reg: int,
    ) -> Tuple[int, int]:

        self.reset()

        if not id_ex.valid:
            return self.forward_a, self.forward_b

        rs = id_ex.data["rs"]
        rt = id_ex.data["rt"]

        # Datos de EX/MEM
        ex_mem_writes = ex_mem.valid and (ex_mem.control.get("RegWrite", 0) == 1)
        ex_mem_rd = ex_mem.data.get("write_reg", 0)

        # Datos de WB
        wb_writes = (wb_reg_write == 1)
        wb_rd = wb_write_reg

        # ForwardA
        if ex_mem_writes and (ex_mem_rd != 0) and (ex_mem_rd == rs):
            self.forward_a = self.FROM_EX_MEM
        elif wb_writes and (wb_rd != 0) and (wb_rd == rs):
            self.forward_a = self.FROM_MEM_WB

        # ForwardB
        if ex_mem_writes and (ex_mem_rd != 0) and (ex_mem_rd == rt):
            self.forward_b = self.FROM_EX_MEM
        elif wb_writes and (wb_rd != 0) and (wb_rd == rt):
            self.forward_b = self.FROM_MEM_WB

        return self.forward_a, self.forward_b


    """        
        Returj: una tupla con 3 valores de 32 bits;
          1. alu_in_a         : Operando A entrante en ALU.
          2. alu_in_b         : Operando B entrante en ALU (mux ALUSrc).
          3. rt_value_for_sw  : Valor actualizado del registro rt (para guardar en memoria si es 'sw').
    """
    
    def select_alu_operands(
        self,
        id_ex: ID_EX_Register,
        ex_mem: EX_MEM_Register,
        wb_write_data: int,
    ) -> Tuple[int, int, int]:
        
        # Forward A
        if self.forward_a == self.FROM_EX_MEM:
            alu_in_a = ex_mem.data["alu_result"]
        elif self.forward_a == self.FROM_MEM_WB:
            alu_in_a = wb_write_data
        else:
            alu_in_a = id_ex.data["read_data_1"]

        # Forward B
        if self.forward_b == self.FROM_EX_MEM:
            rt_value_for_sw = ex_mem.data["alu_result"]
        elif self.forward_b == self.FROM_MEM_WB:
            rt_value_for_sw = wb_write_data
        else:
            rt_value_for_sw = id_ex.data["read_data_2"]

        # ALUSrc mux
        if id_ex.control.get("ALUSrc", 0) == 1:
            alu_in_b = id_ex.data["imm_ext"]
        else:
            alu_in_b = rt_value_for_sw

        return to_unsigned32(alu_in_a), to_unsigned32(alu_in_b), to_unsigned32(rt_value_for_sw)


class HazardDetectionUnit:
    
    def __init__(self) -> None:
        self.pc_write: bool = True
        self.if_id_stall: bool = False
        self.if_id_flush: bool = False
        self.id_ex_flush: bool = False
        self.load_use_stall: bool = False

    def reset_cycle_signals(self) -> None:
        self.pc_write = True
        self.if_id_stall = False
        self.if_id_flush = False
        self.id_ex_flush = False
        self.load_use_stall = False

    """
    Determina si la instruccion en EX es un 'beq' o 'bne'
    """
    @staticmethod
    def is_branch_taken_in_ex(id_ex: ID_EX_Register, alu_zero: bool) -> bool:
        
        if not id_ex.valid:
            return False
        take_beq = (id_ex.control.get("Branch", 0) == 1) and alu_zero
        take_bne = (id_ex.control.get("BranchNe", 0) == 1) and (not alu_zero)
        return take_beq or take_bne

    """
    Return: (lee_rs, lee_rt, num_rs, num_rt)
    """
    @staticmethod
    def _get_read_registers_in_id(instr: int) -> Tuple[bool, bool, int, int]:
        if instr == 0x00000000:
            return False, False, 0, 0

        opcode = get_bits(instr, 31, 26)
        rs = get_bits(instr, 25, 21)
        rt = get_bits(instr, 20, 16)
        funct = get_bits(instr, 5, 0)

        # 'syscall' no lee ningun registro: solo detiene la simulacion
        if opcode == ControlUnit.OP_RTYPE and funct == 0x0C:
            return False, False, 0, 0

        # 'j' y 'lui' no leen registros fuente
        if opcode in (ControlUnit.OP_J, ControlUnit.OP_LUI):
            return False, False, rs, rt

        # Instrucciones Tipo-I que solo leen 'rs' (escriben en 'rt')
        if opcode in (
            ControlUnit.OP_ADDI,
            ControlUnit.OP_ADDIU,
            ControlUnit.OP_ORI,
            ControlUnit.OP_LW,
            ControlUnit.OP_LBU,
            ControlUnit.OP_LB,
        ):
            return True, False, rs, rt

        # Tipo-R, 'sw', 'sb', 'beq' y 'bne' leen tanto 'rs' como 'rt'
        return True, True, rs, rt


    """
    Si la instruccion anterior es 'lw', se compara el rd de I-1 con el rs/rt de I
    """
    def detect_load_use(
        self,
        if_id: IF_ID_Register,
        id_ex: ID_EX_Register,
    ) -> bool:
        if not if_id.valid or not id_ex.valid:
            return False

        if id_ex.control.get("MemRead", 0) != 1:
            return False

        lw_dest_rt = id_ex.data["rt"]
        if lw_dest_rt == 0:
            return False

        reads_rs, reads_rt, id_rs, id_rt = self._get_read_registers_in_id(if_id.data["instr"])

        cond_rs = reads_rs and (lw_dest_rt == id_rs)
        cond_rt = reads_rt and (lw_dest_rt == id_rt)

        return cond_rs or cond_rt

    def evaluate_hazards_in_id(
        self,
        if_id: IF_ID_Register,
        id_ex: ID_EX_Register,
        branch_taken_in_ex: bool,
        jump_in_id: bool,
    ) -> None:

        self.reset_cycle_signals()

        if branch_taken_in_ex:
            self.pc_write = True
            self.if_id_flush = True
            self.id_ex_flush = True
            return

        if self.detect_load_use(if_id, id_ex):
            self.pc_write = False
            self.if_id_stall = True
            self.id_ex_flush = True
            self.load_use_stall = True
            return

        if jump_in_id:
            self.pc_write = True
            self.if_id_flush = True
            return
