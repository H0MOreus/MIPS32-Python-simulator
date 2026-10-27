from typing import Dict
from alu import ALUControl


"""
RegDst: register destination; Indica el registro en donde se escribira desde memoria (5 bits viajan hasta Mem)
MemtoReg: Flag que decide cual es el valor que retorna en la fase WB (si ALU o Memoria)
ALUSrc: 2 multiplexor de la entrada del ALU, decide si envia los valores de los registros o del inmediato
RegWrite: Habilita la escritura en el banco de registrs
MemRead: Habilita la lectura en memoria
MemWrite: Habilita la escritura en memoria
Branch: signal de salto condicional
BranchNe: signal de salto condicional negada (optimizacion)
Jump: signal de salto incondicional
ALUOp: 2 bits que indican la operacion que debe realizar la ALU
"""

class ControlUnit:
    OP_RTYPE = 0x00
    OP_J     = 0x02
    OP_BEQ   = 0x04
    OP_BNE   = 0x05
    OP_ADDI  = 0x08
    OP_ADDIU = 0x09
    OP_ORI   = 0x0D
    OP_LUI   = 0x0F
    OP_LB    = 0x20
    OP_LW    = 0x23
    OP_LBU   = 0x24
    OP_SB    = 0x28
    OP_SW    = 0x2B

    @staticmethod
    def make_bubble_signals() -> Dict[str, int]:
        return {
            "RegDst": 0,
            "ALUSrc": 0,
            "MemtoReg": 0,
            "RegWrite": 0,
            "MemRead": 0,
            "MemWrite": 0,
            "MemByte": 0,      
            "MemSigned": 0,    
            "ZeroExt": 0,      
            "Branch": 0,
            "BranchNe": 0,
            "Jump": 0,
            "Syscall": 0,
            "ALUOp": 0b00,
        }

    @classmethod
    def decode(cls, opcode: int, full_instruction: int = 0, inst: int = 0) -> Dict[str, int]:
        instr_val = full_instruction if full_instruction != 0 else inst
        if instr_val == 0x00000000 and opcode == cls.OP_RTYPE:
            return cls.make_bubble_signals()

        signals = cls.make_bubble_signals()
        funct = instr_val & 0x3F

        if opcode == cls.OP_RTYPE:
            if funct == ALUControl.FUNCT_SYSCALL:
                signals["Syscall"] = 1
            else:
                signals.update({
                    "RegDst": 1,
                    "ALUSrc": 0,
                    "MemtoReg": 0,
                    "RegWrite": 1,
                    "ALUOp": 0b10,
                })                                      
        elif opcode in (cls.OP_ADDI, cls.OP_ADDIU):
            signals.update({"RegDst": 0, "ALUSrc": 1, "RegWrite": 1, "ALUOp": 0b00})
        
        
        elif opcode == cls.OP_ORI:
            signals.update({"RegDst": 0, "ALUSrc": 1, "RegWrite": 1, "ZeroExt": 1, "ALUOp": 0b101})
        

        elif opcode == cls.OP_LUI:
            signals.update({"RegDst": 0, "ALUSrc": 1, "RegWrite": 1, "ZeroExt": 1, "ALUOp": 0b100})
        
        
        elif opcode == cls.OP_LW:
            signals.update({"RegDst": 0, "ALUSrc": 1, "MemtoReg": 1, "RegWrite": 1, "MemRead": 1, "ALUOp": 0b00})
       
        
        elif opcode == cls.OP_LBU:
            signals.update({"RegDst": 0, "ALUSrc": 1, "MemtoReg": 1, "RegWrite": 1, "MemRead": 1, "MemByte": 1, "MemSigned": 0, "ALUOp": 0b00})
        
        
        elif opcode == cls.OP_LB:
            signals.update({"RegDst": 0, "ALUSrc": 1, "MemtoReg": 1, "RegWrite": 1, "MemRead": 1, "MemByte": 1, "MemSigned": 1, "ALUOp": 0b00})
       
        
        elif opcode == cls.OP_SW:
            signals.update({"ALUSrc": 1, "MemWrite": 1, "ALUOp": 0b00})
        
        
        elif opcode == cls.OP_SB:
            signals.update({"ALUSrc": 1, "MemWrite": 1, "MemByte": 1, "ALUOp": 0b00})
        
        
        elif opcode == cls.OP_BEQ:
            signals.update({"ALUSrc": 0, "Branch": 1, "ALUOp": 0b01})
        
        
        elif opcode == cls.OP_BNE:
            signals.update({"ALUSrc": 0, "BranchNe": 1, "ALUOp": 0b01})
        
        
        elif opcode == cls.OP_J:
            signals.update({"Jump": 1})
        
        
        else:
            raise ValueError(f"Opcode no soportado: 0x{opcode:02X}")

        return signals
