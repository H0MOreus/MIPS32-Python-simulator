import re
from typing import Dict, List, Tuple
from lib_bits import to_unsigned32
from memorias import Memory
from registers import RegisterFile
from control import ControlUnit
from alu import ALUControl


class AssemblerSyntaxError(Exception):

    def __init__(self, message: str, line_num: int = 0, source_line: str = "") -> None:
        prefix = f"[Linea {line_num}] " if line_num > 0 else ""
        context = f" -> '{source_line.strip()}'" if source_line.strip() else ""
        super().__init__(f"{prefix}{message}{context}")

"""
Primera ola:
    Construimos la tabla de simbolos (tags)
    Contamos dir memoria de 4 en 4

Segunda ola:
    convertimos las instrucciones en palabras de 32 bits
"""
class ParsedInstruction:

    def __init__(
        self,
        address: int,
        line_num: int,
        raw_line: str,
        mnemonic: str,
        operands: List[str],
    ) -> None:
        self.address: int = address
        self.line_num: int = line_num
        self.raw_line: str = raw_line
        self.mnemonic: str = mnemonic
        self.operands: List[str] = operands


class MIPS32Assembler:
    """
    Ensamblador MIPS32 de dos pasadas para el repertorio basico de enteros:
      - Tipo-R : add, sub, and, or, nor, slt, nop
      - Tipo-I : addi, lw, sw, beq, bne
      - Tipo-J : j
    
    Es mas facil de implementar que uno de una unica pasada con BackPatching
    No rompemos las dependenciar y no tenemos que preocuparnos de resolver las referencias pendientes

    """

    # Mapa de instrucciones Tipo-R -> codigo 'funct' (6 bits)
    R_TYPE_FUNCT: Dict[str, int] = {
        "add": ALUControl.FUNCT_ADD,
        "sub": ALUControl.FUNCT_SUB,
        "and": ALUControl.FUNCT_AND,
        "or":  ALUControl.FUNCT_OR,
        "nor": ALUControl.FUNCT_NOR,
        "slt": ALUControl.FUNCT_SLT,
    }

    # Mapa de instrucciones Tipo-I e Tipo-J -> codigo 'opcode' (6 bits)
    I_J_OPCODES: Dict[str, int] = {
        "addi": ControlUnit.OP_ADDI,
        "lw":   ControlUnit.OP_LW,
        "sw":   ControlUnit.OP_SW,
        "beq":  ControlUnit.OP_BEQ,
        "bne":  ControlUnit.OP_BNE,
        "j":    ControlUnit.OP_J,
    }

    # Expresion regular para parsear el modo de direccionamiento 'offset($base)' en lw/sw
    """
    lee la linea hasta encontrar un caracter, puede o no haber un signo (+-)
    ignora el 0x de haberlo, deja lo demas hasta encontrar un '(', un '$',
    luego una letra o numero. Espera un cierre de parentesis.
    """
    MEM_OPERAND_REGEX = re.compile(r"^\s*([+-]?(?:0x[0-9a-fA-F]+|\d+))\s*\(\s*(\$[a-zA-Z0-9]+)\s*\)\s*$")
    LABEL_NAME_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    def __init__(self, base_address: int = Memory.TEXT_BASE) -> None:
        self.base_address: int = to_unsigned32(base_address)
        self.symbol_table: Dict[str, int] = {}
        self.source_map: Dict[int, str] = {}

    # INTERFAZ DE ENSAMBLADO

    def assemble(self, source_code: str) -> List[int]:
        """
        Ejecuta las dos pasadas de ensamblado sobre el texto fuente 'source_code'
        y devuelve la lista de palabras binarias de 32 bits.
        """
        self.symbol_table.clear()
        self.source_map.clear()

        # Pasada 1: Construir tabla de simbolos (tags) y lista de instrucciones
        parsed_instructions = self._first_pass(source_code)

        # Pasada 2: Codificar cada instruccion en una palabra de 32 bits
        machine_words: List[int] = []
        for item in parsed_instructions:
            word = self._encode_instruction(item)
            machine_words.append(word)
            self.source_map[item.address] = f"{item.mnemonic} {', '.join(item.operands)}".strip()

        return machine_words

    def assemble_with_listing(self, source_code: str) -> Tuple[List[int], Dict[str, int], List[Dict[str, str]]]:
    
        parsed_instructions = self._first_pass(source_code)
        machine_words: List[int] = []
        listing: List[Dict[str, str]] = []

        for item in parsed_instructions:
            word = self._encode_instruction(item)
            machine_words.append(word)
            clean_src = f"{item.mnemonic} {', '.join(item.operands)}".strip()
            self.source_map[item.address] = clean_src
            listing.append({
                "address": f"0x{item.address:08X}",
                "hex": f"0x{word:08X}",
                "binary": f"{word:032b}",
                "source": clean_src,
            })

        return machine_words, dict(self.symbol_table), listing

    # PASADA 1: ANALISIS LEXICO Y RESOLUCION DE ETIQUETAS
    

    def _first_pass(self, source_code: str) -> List[ParsedInstruction]:
        """
        Recorre el codigo fuente linea a linea, elimina comentarios, registra todas las
        etiquetas en 'self.symbol_table' con su direccion PC correspondiente y extrae
        los mnemonicos y operandos.
        """
        parsed_list: List[ParsedInstruction] = []
        current_address = self.base_address

        lines = source_code.splitlines()
        for idx, raw_line in enumerate(lines, start=1):
            # Eliminar comentarios (# ...) y espacios extremos
            line_no_comments = raw_line.split("#", 1)[0].strip()
            if not line_no_comments:
                continue

            # Extraer etiquetas al inicio de la linea (ej. "loop: inicio: add ...")
            while ":" in line_no_comments:
                label_part, rest = line_no_comments.split(":", 1)
                label_name = label_part.strip()

                if not self.LABEL_NAME_REGEX.match(label_name):
                    raise AssemblerSyntaxError(
                        f"Identificador de etiqueta invalido: '{label_name}'", idx, raw_line)
                if label_name in self.symbol_table:
                    raise AssemblerSyntaxError(
                        f"Etiqueta duplicada: '{label_name}' ya fue definida en 0x{self.symbol_table[label_name]:08X}", idx, raw_line)

                self.symbol_table[label_name] = current_address
                line_no_comments = rest.strip()

            # Si solo  etiqueta ("main:"), continue
            if not line_no_comments:
                continue

            # Ignorar la directiva de seccion '.text'
            if line_no_comments.lower() == ".text":
                continue
            if line_no_comments.startswith("."):
                raise AssemblerSyntaxError(
                    f"Directiva de ensamblador no soportada en el modelo basico: '{line_no_comments}'", idx, raw_line)

            # Separar el mnemonico de la cadena de operandos
            parts = line_no_comments.split(None, 1)
            mnemonic = parts[0].lower()
            operands_str = parts[1] if len(parts) == 2 else ""

            if operands_str:
                operands = [op.strip() for op in operands_str.split(",") if op.strip()]
            else:
                operands = []

            parsed_list.append(
                ParsedInstruction(
                    address=current_address,
                    line_num=idx,
                    raw_line=raw_line,
                    mnemonic=mnemonic,
                    operands=operands,
                )
            )
            current_address = to_unsigned32(current_address + 4)

        return parsed_list

    # PASADA 2: SINTESIS Y CODIFICACION DE PALABRAS DE 32 BITS    

    def _encode_instruction(self, item: ParsedInstruction) -> int:
        """Dirige la instruccion hacia su codificador especifico (NOP, R, I o J)."""
        mnem = item.mnemonic

        if mnem == "nop":
            if len(item.operands) != 0:
                raise AssemblerSyntaxError(
                    "'nop' can't have operands", item.line_num, item.raw_line
                )
            return 0x00000000

        if mnem in self.R_TYPE_FUNCT:
            return self._encode_r_type(item)

        if mnem == "addi":
            return self._encode_addi(item)

        if mnem in ("lw", "sw"):
            return self._encode_memory_offset(item)

        if mnem in ("beq", "bne"):
            return self._encode_branch(item)

        if mnem == "j":
            return self._encode_jump(item)

        raise AssemblerSyntaxError(
            f"Unknown instruction: '{mnem}'",
            item.line_num,
            item.raw_line,
        )

    def _encode_r_type(self, item: ParsedInstruction) -> int:
        """
        Codifica instrucciones Tipo-R: add, sub, and, or, nor, slt.
        Sintaxis: mnem rd, rs, rt
        Formato binario: opcode(0) [31:26] | rs [25:21] | rt [20:16] | rd [15:11] | shamt(0) [10:6] | funct [5:0]
        """
        if len(item.operands) != 3:
            raise AssemblerSyntaxError(
                f"'{item.mnemonic}' requires 3 operands: rd, rs, rt",
                item.line_num,
                item.raw_line,
            )

        rd = self._parse_register(item.operands[0], item)
        rs = self._parse_register(item.operands[1], item)
        rt = self._parse_register(item.operands[2], item)
        funct = self.R_TYPE_FUNCT[item.mnemonic]

        # el OR los une por nosotros
        word = (
            (ControlUnit.OP_RTYPE << 26)
            | (rs << 21)
            | (rt << 16)
            | (rd << 11)
            | (0 << 6)
            | funct
        )
        return to_unsigned32(word)

    def _encode_addi(self, item: ParsedInstruction) -> int:
        """
        Codifica 'addi'.
        Sintaxis: addi rt, rs, imm16
        Formato binario: opcode [31:26] | rs [25:21] | rt [20:16] | imm16 [15:0]
        """
        if len(item.operands) != 3:
            raise AssemblerSyntaxError(
                "'addi' requiere exactamente 3 operandos: rt, rs, imm",
                item.line_num,
                item.raw_line,
            )

        rt = self._parse_register(item.operands[0], item)
        rs = self._parse_register(item.operands[1], item)
        imm16 = self._parse_signed_16bit_immediate(item.operands[2], item)

        word = (
            (ControlUnit.OP_ADDI << 26)
            | (rs << 21)
            | (rt << 16)
            | (imm16 & 0xFFFF)
        )
        return to_unsigned32(word)

    def _encode_memory_offset(self, item: ParsedInstruction) -> int:
        """
        Codifica 'lw' y 'sw'.
        Sintaxis: lw/sw rt, offset(rs)
        Formato binario: opcode [31:26] | rs [25:21] | rt [20:16] | offset16 [15:0]
        """
        if len(item.operands) != 2:
            raise AssemblerSyntaxError(
                f"'{item.mnemonic}' requiere 2 operandos con formato: rt, offset(rs)",
                item.line_num,
                item.raw_line,
            )

        rt = self._parse_register(item.operands[0], item)

        match = self.MEM_OPERAND_REGEX.match(item.operands[1])
        if not match:
            raise AssemblerSyntaxError(
                f"Formato de direccion invalido '{item.operands[1]}'. Use 'offset($rs)', ej: 4($s0)",
                item.line_num,
                item.raw_line,
            )

        offset_str, rs_str = match.group(1), match.group(2)
        imm16 = self._parse_signed_16bit_immediate(offset_str, item)
        rs = self._parse_register(rs_str, item)
        opcode = self.I_J_OPCODES[item.mnemonic]

        word = (opcode << 26) | (rs << 21) | (rt << 16) | (imm16 & 0xFFFF)
        return to_unsigned32(word)

    def _encode_branch(self, item: ParsedInstruction) -> int:
        """
        Codifica 'beq' y 'bne'.
        Sintaxis: beq/bne rs, rt, etiqueta_o_offset
        Formato binario: opcode [31:26] | rs [25:21] | rt [20:16] | offset16 [15:0]
        """
        if len(item.operands) != 3:
            raise AssemblerSyntaxError(
                f"'{item.mnemonic}' requiere 3 operandos: rs, rt, etiqueta",
                item.line_num,
                item.raw_line,
            )

        rs = self._parse_register(item.operands[0], item)
        rt = self._parse_register(item.operands[1], item)
        target_token = item.operands[2]

        # Soportar tanto nombres de etiquetas como offsets numéricos directos
        if target_token in self.symbol_table:
            target_address = self.symbol_table[target_token]
            pc_plus_4 = item.address + 4
            byte_diff = target_address - pc_plus_4
            if (byte_diff % 4) != 0:
                raise AssemblerSyntaxError(
                    f"Destino de salto desalineado hacia '{target_token}'",
                    item.line_num,
                    item.raw_line,
                )
            offset_words = byte_diff // 4
            if not (-32768 <= offset_words <= 32767):
                raise AssemblerSyntaxError(
                    f"Salto relativo fuera del rango de 16 bits ({offset_words} palabras)",
                    item.line_num,
                    item.raw_line,
                )
        else:
            # Si no esta en la tabla de simbolos, verificar si es un literal numérico
            try:
                offset_words = self._parse_signed_16bit_immediate(target_token, item)
            except AssemblerSyntaxError:
                raise AssemblerSyntaxError(
                    f"Etiqueta no definida: '{target_token}'",
                    item.line_num,
                    item.raw_line,
                )

        opcode = self.I_J_OPCODES[item.mnemonic]
        word = (opcode << 26) | (rs << 21) | (rt << 16) | (offset_words & 0xFFFF)
        return to_unsigned32(word)

    def _encode_jump(self, item: ParsedInstruction) -> int:
        """
        Codifica el salto incondicional 'j'.
        Sintaxis: j etiqueta
        Formato binario: opcode [31:26] | instr_index [25:0]
        """
        if len(item.operands) != 1:
            raise AssemblerSyntaxError(
                "'j' requiere exactamente 1 operando: etiqueta o direccion",
                item.line_num,
                item.raw_line,
            )

        target_token = item.operands[0]
        if target_token in self.symbol_table:
            target_address = self.symbol_table[target_token]
        else:
            # Permitir direccion numérica explicita si es múltiplo de 4
            try:
                target_address = int(target_token, 0)
            except ValueError:
                raise AssemblerSyntaxError(
                    f"Etiqueta de salto no definida: '{target_token}'",
                    item.line_num,
                    item.raw_line,
                )

        if (target_address & 0x3) != 0:
            raise AssemblerSyntaxError(
                f"La direccion de salto 0x{target_address:08X} no es múltiplo de 4",
                item.line_num,
                item.raw_line,
            )

        pc_plus_4_upper = (item.address + 4) & 0xF0000000
        if (target_address & 0xF0000000) != pc_plus_4_upper:
            raise AssemblerSyntaxError(
                f"El destino 0x{target_address:08X} cruza la frontera de region de 256 MB de PC+4",
                item.line_num,
                item.raw_line,
            )

        instr_index_26 = (target_address & 0x0FFFFFFF) >> 2
        word = (ControlUnit.OP_J << 26) | (instr_index_26 & 0x03FFFFFF)
        return to_unsigned32(word)

    # =========================================================================
    # UTILIDADES DE VALIDACION DE REGISTROS E INMEDIATOS
    # =========================================================================

    @staticmethod
    def _parse_register(reg_str: str, item: ParsedInstruction) -> int:
        try:
            return RegisterFile.resolve_name(reg_str)
        except ValueError as err:
            raise AssemblerSyntaxError(str(err), item.line_num, item.raw_line) from err

    @staticmethod
    def _parse_signed_16bit_immediate(imm_str: str, item: ParsedInstruction) -> int:
        try:
            val = int(imm_str.strip(), 0)
        except ValueError as err:
            raise AssemblerSyntaxError(
                f"Valor inmediato invalido: '{imm_str}'", item.line_num, item.raw_line
            ) from err

        if not (-32768 <= val <= 32767):
            raise AssemblerSyntaxError(
                f"El inmediato {val} excede el rango con signo de 16 bits [-32768, 32767]",
                item.line_num,
                item.raw_line,
            )
        return val
