from typing import Dict


class ControlUnit:

    OP_RTYPE = 0x00
    OP_J     = 0x02
    OP_BEQ   = 0x04
    OP_BNE   = 0x05
    OP_ADDI  = 0x08
    OP_LW    = 0x23
    OP_SW    = 0x2B

    @staticmethod
    def make_bubble_signals() -> Dict[str, int]:
        # NOP
        return {
            "RegDst": 0,
            "ALUSrc": 0,
            "MemtoReg": 0,
            "RegWrite": 0,
            "MemRead": 0,
            "MemWrite": 0,
            "Branch": 0,
            "BranchNe": 0,
            "Jump": 0,
            "ALUOp": 0b00,
        }

    @classmethod
    def decode(cls, opcode: int, inst: int = 0) -> Dict[str, int]:
        
        if inst == 0x00000000:
            return cls.make_bubble_signals()

        # critico que no haya errores despues de esto
        # por simplicidad de codigo 'limpiamos' las señales
        # en la vida real se hubieran consumido
        # sobra decir que si algo falla despues de la linea signals
        # perdemos un ciclo con una signal NOP falsa
        # es mas facil que hacer una llamada de limpieza en cada ciclo
        signals = cls.make_bubble_signals()

        if opcode == cls.OP_RTYPE:
            signals.update({
                "RegDst": 1,
                "ALUSrc": 0,
                "MemtoReg": 0,
                "RegWrite": 1,
                "ALUOp": 0b10,
            })

        elif opcode == cls.OP_ADDI:
            signals.update({
                "RegDst": 0,
                "ALUSrc": 1,
                "MemtoReg": 0,
                "RegWrite": 1,
                "ALUOp": 0b00,
            })

        elif opcode == cls.OP_LW:
            signals.update({
                "RegDst": 0,
                "ALUSrc": 1,
                "MemtoReg": 1,
                "RegWrite": 1,
                "MemRead": 1,
                "ALUOp": 0b00,
            })

        elif opcode == cls.OP_SW:
            signals.update({
                "ALUSrc": 1,
                "MemWrite": 1,
                "ALUOp": 0b00,
            })

        elif opcode == cls.OP_BEQ:
            signals.update({
                "ALUSrc": 0,
                "Branch": 1,
                "ALUOp": 0b01,
            })

        elif opcode == cls.OP_BNE:
            signals.update({
                "ALUSrc": 0,
                "BranchNe": 1,
                "ALUOp": 0b01,
            })

        elif opcode == cls.OP_J:
            signals.update({
                "Jump": 1,
            })
            
        else:
            raise ValueError(f"Unsuppoted operation: 0x{opcode:02X}")

        return signals
