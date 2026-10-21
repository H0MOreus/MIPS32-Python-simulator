"""
registers.py
Banco de 32 registros de proposito general sin punteros de pila/sistema preconfigurados,
y Contador de Programa (PC).
"""

from typing import Dict
from lib_bits import to_unsigned32


class RegisterFile:
    """
    Banco de 32 registros de 32 bits.
    Inicializados a 0, $zero no cambia
    """

    NAMES: Dict[str, int] = {
        "$zero": 0, "$0": 0,
        "$at": 1,   "$1": 1,
        "$v0": 2,   "$2": 2,  "$v1": 3,   "$3": 3,
        "$a0": 4,   "$4": 4,  "$a1": 5,   "$5": 5,  "$a2": 6,   "$6": 6,  "$a3": 7,   "$7": 7,
        "$t0": 8,   "$8": 8,  "$t1": 9,   "$9": 9,  "$t2": 10,  "$10": 10, "$t3": 11, "$11": 11,
        "$t4": 12,  "$12": 12, "$t5": 13, "$13": 13, "$t6": 14, "$14": 14, "$t7": 15, "$15": 15,
        "$s0": 16,  "$16": 16, "$s1": 17, "$17": 17, "$s2": 18, "$18": 18, "$s3": 19, "$19": 19,
        "$s4": 20,  "$20": 20, "$s5": 21, "$21": 21, "$s6": 22, "$22": 22, "$s7": 23, "$23": 23,
        "$t8": 24,  "$24": 24, "$t9": 25, "$25": 25,
        "$k0": 26,  "$26": 26, "$k1": 27, "$27": 27,
        "$gp": 28,  "$28": 28, "$sp": 29, "$29": 29, "$fp": 30, "$30": 30, "$ra": 31, "$31": 31,
    }

    INDEX_TO_NAMES: Dict[int, str] = {
        0: "$zero", 1: "$at", 2: "$v0", 3: "$v1",
        4: "$a0", 5: "$a1", 6: "$a2", 7: "$a3",
        8: "$t0", 9: "$t1", 10: "$t2", 11: "$t3",
        12: "$t4", 13: "$t5", 14: "$t6", 15: "$t7",
        16: "$s0", 17: "$s1", 18: "$s2", 19: "$s3",
        20: "$s4", 21: "$s5", 22: "$s6", 23: "$s7",
        24: "$t8", 25: "$t9", 26: "$k0", 27: "$k1",
        28: "$gp", 29: "$sp", 30: "$fp", 31: "$ra"
    }

    def __init__(self) -> None:
        self._regs: list[int] = [0] * 32

    def reset(self) -> None:
        self._regs = [0] * 32

    def _validate_reg(self, reg_num: int) -> None:
        if not (0 <= reg_num <= 31):
            raise ValueError(f"Index Out of Range [0..31]: {reg_num}")

    def read(self, reg_num: int) -> int:
        self._validate_reg(reg_num)
        return 0 if reg_num == 0 else self._regs[reg_num]

    def write(self, reg_num: int, x: int, reg_write: bool = True) -> None:
        if not reg_write:
            return
        self._validate_reg(reg_num)
        if reg_num != 0:
            self._regs[reg_num] = to_unsigned32(x)

    @classmethod #privado
    def resolve_name(cls, name: str) -> int:
        clean = name.strip().lower()
        if clean not in cls.NAMES:
            raise ValueError(f"register unknown: '{name}'")
        return cls.NAMES[clean]


    """
    Recorre los registros e imprime el contenido
    Si se usa 'cond'= false, se imprimen todos, sino solo los distintos de zero
    """
    def dump(self, cond: bool = True) -> Dict[str, str]:
        snapshot: Dict[str, str] = {}
        for idx in range(32):
            val = self._regs[idx]
            if not cond or val != 0 or idx == 0:
                snapshot[f"{self.INDEX_TO_NAMES[idx]} (${idx})"] = f"0x{val:08X}"
        return snapshot


class ProgramCounter:
    INITIAL_PC = 0x00400000

    def __init__(self) -> None:
        self._value: int = self.INITIAL_PC

    def reset(self) -> None:
        self._value = self.INITIAL_PC

    @property
    def value(self) -> int:
        return self._value

    def write(self, next_pc: int, pc_write: bool = True) -> None:
        if pc_write:
            self._value = to_unsigned32(next_pc)
