from typing import Tuple
from lib_bits import to_unsigned32, to_signed32


class ALUControl:

    # Codigos de 4 bits para las operaciones internas de la ALU
    ALU_AND = 0b0000
    ALU_OR  = 0b0001
    ALU_ADD = 0b0010
    ALU_SUB = 0b0110
    ALU_SLT = 0b0111
    ALU_NOR = 0b1100
    ALU_LUI = 0b1101

    # Codigos de campo 'funct' (6 bits) en instrucciones Tipo-R (opcode = 0x00)
    FUNCT_ADD     = 0x20
    FUNCT_ADDU    = 0x21
    FUNCT_SUB     = 0x22
    FUNCT_SUBU    = 0x23
    FUNCT_AND     = 0x24
    FUNCT_OR      = 0x25
    FUNCT_NOR     = 0x27
    FUNCT_SLT     = 0x2A
    FUNCT_SYSCALL = 0x0C
    FUNCT_NOP     = 0x00  # sll $0, $0, 0 -> Manual de MIPS32 original (datazo)

    @classmethod
    def resolve(cls, alu_op: int, funct: int) -> int:
        """
          - ALUOp == 0b00  : Suma 
          - ALUOp == 0b01  : Resta
          - ALUOp == 0b11  : ORI (OR a nivel de bit)
          - ALUOp == 0b100 : LUI (Carga en parte alta)
          - ALUOp == 0b10  : campo 'funct' (Tipo-R)
        """
        if alu_op == 0b00:
            return cls.ALU_ADD
        if alu_op == 0b01:
            return cls.ALU_SUB
        if alu_op == 0b101:
            return cls.ALU_OR
        if alu_op == 0b100:
            return cls.ALU_LUI
        if alu_op == 0b10:
            map_alu_op = {
                cls.FUNCT_ADD:     cls.ALU_ADD,
                cls.FUNCT_ADDU:    cls.ALU_ADD,
                cls.FUNCT_SUB:     cls.ALU_SUB,
                cls.FUNCT_SUBU:    cls.ALU_SUB,
                cls.FUNCT_AND:     cls.ALU_AND,
                cls.FUNCT_OR:      cls.ALU_OR,
                cls.FUNCT_NOR:     cls.ALU_NOR,
                cls.FUNCT_SLT:     cls.ALU_SLT,
                cls.FUNCT_SYSCALL: cls.ALU_ADD,
                cls.FUNCT_NOP:     cls.ALU_ADD,
            }
            if funct not in map_alu_op:
                raise ValueError(f"Unsupported operation: 0x{funct:02X}")
            return map_alu_op[funct]

        raise ValueError(f"ALUOp Signal non valid: 0b{alu_op:02b}")


class ALU:

    @staticmethod
    def execute(op1: int, op2: int, alu_control: int) -> Tuple[int, bool]:
        
        a = to_unsigned32(op1)
        b = to_unsigned32(op2)

        if alu_control == ALUControl.ALU_AND:
            res = a & b
        elif alu_control == ALUControl.ALU_OR:
            res = a | b
        elif alu_control == ALUControl.ALU_NOR:
            res = ~(a | b)
        elif alu_control == ALUControl.ALU_ADD:
            res = a + b
        elif alu_control == ALUControl.ALU_SUB:
            res = a - b
        elif alu_control == ALUControl.ALU_SLT:
            # Comparacion estricta en complemento a dos (con signo)
            res = 1 if to_signed32(a) < to_signed32(b) else 0
        elif alu_control == ALUControl.ALU_LUI:
            res = (b & 0xFFFF) << 16
        else:
            raise ValueError(f"ALU Control code non valid: 0b{alu_control:04b}")

        result_32 = to_unsigned32(res)
        zero_flag = (result_32 == 0)
        return result_32, zero_flag
