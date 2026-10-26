
import ast
import re
import struct
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
    R_TYPE_FUNCT: Dict[str, int] = {
        "add":  ALUControl.FUNCT_ADD,
        "addu": ALUControl.FUNCT_ADDU,
        "sub":  ALUControl.FUNCT_SUB,
        "subu": ALUControl.FUNCT_SUBU,
        "and":  ALUControl.FUNCT_AND,
        "or":   ALUControl.FUNCT_OR,
        "nor":  ALUControl.FUNCT_NOR,
        "slt":  ALUControl.FUNCT_SLT,
    }

    I_J_OPCODES: Dict[str, int] = {
        "addi":  ControlUnit.OP_ADDI,
        "addiu": ControlUnit.OP_ADDIU,
        "ori":   ControlUnit.OP_ORI,
        "lui":   ControlUnit.OP_LUI,
        "lw":    ControlUnit.OP_LW,
        "lbu":   ControlUnit.OP_LBU,
        "lb":    ControlUnit.OP_LB,
        "sw":    ControlUnit.OP_SW,
        "sb":    ControlUnit.OP_SB,
        "beq":   ControlUnit.OP_BEQ,
        "bne":   ControlUnit.OP_BNE,
        "j":     ControlUnit.OP_J,
    }

    MEM_OPERAND_REGEX = re.compile(
        r"^\s*([+-]?(?:0x[0-9a-fA-F]+|\d+))\s*\(\s*(\$[a-zA-Z0-9]+)\s*\)\s*$"
    )
    LABEL_NAME_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    def __init__(
        self,
        base_address: int = Memory.TEXT_BASE,
        data_base_address: int = Memory.DATA_BASE,
    ) -> None:
        self.base_address: int = to_unsigned32(base_address)
        self.data_base_address: int = to_unsigned32(data_base_address)
        self.symbol_table: Dict[str, int] = {}
        self.source_map: Dict[int, str] = {}
        self.data_image: bytearray = bytearray()


    def assemble(self, source_code: str) -> List[int]:
        machine_words, _, _ = self.assemble_with_listing(source_code)
        return machine_words


    def assemble_with_listing(
        self, source_code: str
    ) -> Tuple[List[int], Dict[str, int], List[Dict[str, str]]]:
        self.symbol_table.clear()
        self.source_map.clear()
        self.data_image.clear()

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

    # Primera pasada : secciones .data / .text, tags y casi nmemonicos

    def _first_pass(self, source_code: str) -> List[ParsedInstruction]:
        parsed_list: List[ParsedInstruction] = []
        current_text_addr = self.base_address
        in_data_section = False

        for idx, raw_line in enumerate(source_code.splitlines(), start=1):
            line_no_comments = self._strip_comments(raw_line).strip()
            if not line_no_comments:
                continue

            # Extraer etiquetas respetando comillas de cadenas (.asciiz "a:b")
            while ":" in line_no_comments:
                colon_pos = line_no_comments.find(":")
                quote_pos = line_no_comments.find('"')
                if quote_pos != -1 and quote_pos < colon_pos:
                    break

                label_name = line_no_comments[:colon_pos].strip()
                if not self.LABEL_NAME_REGEX.match(label_name):
                    raise AssemblerSyntaxError(
                        f" Identificador de etiqueta invalido: '{label_name}'", idx, raw_line
                    )
                if label_name in self.symbol_table:
                    raise AssemblerSyntaxError(
                        f" Etiqueta duplicada: '{label_name}'", idx, raw_line
                    )

                if in_data_section:
                    self.symbol_table[label_name] = to_unsigned32(
                        self.data_base_address + len(self.data_image)
                    )
                else:
                    self.symbol_table[label_name] = current_text_addr

                line_no_comments = line_no_comments[colon_pos + 1 :].strip()

            if not line_no_comments:
                continue

            # Manejo de directivas (.data, .text, .globl, .asciiz, .space, .word)
            if line_no_comments.startswith("."):
                parts = line_no_comments.split(None, 1)
                directive = parts[0].lower()
                dir_arg = parts[1].strip() if len(parts) > 1 else ""

                if directive == ".data":
                    in_data_section = True
                    continue
                if directive == ".text":
                    in_data_section = False
                    continue
                if directive in (".globl", ".global"):
                    continue

                if not in_data_section:
                    raise AssemblerSyntaxError(
                        f"Directiva '{directive}' fuera de la seccion .data", idx, raw_line
                    )

                self._process_data_directive(directive, dir_arg, idx, raw_line)
                continue

            if in_data_section:
                raise AssemblerSyntaxError(
                    "I nstruccion encontrada dentro de la seccion .data ", idx, raw_line
                )

            # Separar mnemonico y operandos respetando comas entre comillas (ej. ',')
            parts = line_no_comments.split(None, 1)
            mnemonic = parts[0].lower()
            operands_str = parts[1] if len(parts) == 2 else ""
            operands = self._split_operands(operands_str) if operands_str else []

            # Expandir pseudoinstrucciones a instrucciones nativas MIPS32
            expanded = self._expand_pseudoinstruction(mnemonic, operands, idx, raw_line)
            for exp_mnem, exp_ops in expanded:
                parsed_list.append(
                    ParsedInstruction(
                        address=current_text_addr,
                        line_num=idx,
                        raw_line=raw_line,
                        mnemonic=exp_mnem,
                        operands=exp_ops,
                    )
                )
                current_text_addr = to_unsigned32(current_text_addr + 4)

        return parsed_list

    def _process_data_directive(
        self, directive: str, arg: str, idx: int, raw_line: str
    ) -> None:
        if directive in (".asciiz", ".ascii"):
            if not (arg.startswith('"') and arg.endswith('"')):
                raise AssemblerSyntaxError(
                    f"{directive} requiere una cadena entre comillas dobles", idx, raw_line
                )
            try:
                decoded_str = ast.literal_eval(arg)
            except Exception as err:
                raise AssemblerSyntaxError(f"Cadena invalida en {directive}", idx, raw_line) from err

            self.data_image.extend(decoded_str.encode("utf-8"))
            if directive == ".asciiz":
                self.data_image.append(0)

        elif directive == ".space":
            size = self._parse_int_or_char(arg, idx, raw_line)
            if size < 0:
                raise AssemblerSyntaxError(".space no admite tamaños negativos", idx, raw_line)
            self.data_image.extend(b"\x00" * size)

        elif directive == ".word":
            # Alinear a 4 bytes antes de colocar palabras de 32 bits
            while (len(self.data_image) % 4) != 0:
                self.data_image.append(0)
            for tok in self._split_operands(arg):
                val = self._parse_int_or_char(tok, idx, raw_line)
                self.data_image.extend(struct.pack(">I", to_unsigned32(val)))

        elif directive == ".byte":
            for tok in self._split_operands(arg):
                val = self._parse_int_or_char(tok, idx, raw_line)
                self.data_image.append(val & 0xFF)
        else:
            raise AssemblerSyntaxError(
                f"Directiva de datos no soportada: '{directive}'", idx, raw_line
            )

    def _expand_pseudoinstruction(
        self, mnem: str, ops: List[str], idx: int, raw_line: str
    ) -> List[Tuple[str, List[str]]]:
        # Convierte pseudoinstrucciones
        if mnem == "la":
            if len(ops) != 2:
                raise AssemblerSyntaxError("'la' requiere 2 operandos: rd, etiqueta", idx, raw_line)
            # Se resuelve en Pasada 2 usando marcadores internos %hi(label) y %lo(label)
            # algo parecido hace MARS
            return [
                ("lui", ["$at", f"%hi({ops[1]})"]),
                ("ori", [ops[0], "$at", f"%lo({ops[1]})"]),
            ]

        if mnem == "li":
            if len(ops) != 2:
                raise AssemblerSyntaxError("'li' requiere 2 operandos: rd, valor", idx, raw_line)
            val = self._parse_int_or_char(ops[1], idx, raw_line)
            if -32768 <= val <= 32767:
                return [("addi", [ops[0], "$zero", str(val)])]
            if 0 <= val <= 0xFFFF:
                return [("ori", [ops[0], "$zero", str(val)])]
            upper = (val >> 16) & 0xFFFF
            lower = val & 0xFFFF
            return [
                ("lui", ["$at", str(upper)]),
                ("ori", [ops[0], "$at", str(lower)]),
            ]

        if mnem == "move":
            if len(ops) != 2:
                raise AssemblerSyntaxError("'move' requiere 2 operandos: rd, rs", idx, raw_line)
            return [("addu", [ops[0], ops[1], "$zero"])]

        if mnem == "beqz":
            if len(ops) != 2:
                raise AssemblerSyntaxError("'beqz' requiere 2 operandos: rs, etiqueta", idx, raw_line)
            return [("beq", [ops[0], "$zero", ops[1]])]

        if mnem == "bnez":
            if len(ops) != 2:
                raise AssemblerSyntaxError("'bnez' requiere 2 operandos: rs, etiqueta", idx, raw_line)
            return [("bne", [ops[0], "$zero", ops[1]])]

        if mnem == "blt":
            if len(ops) != 3:
                raise AssemblerSyntaxError("'blt' requiere 3 operandos: rs, rt, etiqueta", idx, raw_line)
            return [
                ("slt", ["$at", ops[0], ops[1]]),
                ("bne", ["$at", "$zero", ops[2]]),
            ]

        if mnem == "bgt":
            if len(ops) != 3:
                raise AssemblerSyntaxError("'bgt' requiere 3 operandos: rs, rt, etiqueta", idx, raw_line)
            return [
                ("slt", ["$at", ops[1], ops[0]]),
                ("bne", ["$at", "$zero", ops[2]]),
            ]

        if mnem == "ble":
            if len(ops) != 3:
                raise AssemblerSyntaxError("'ble' requiere 3 operandos: rs, rt, etiqueta", idx, raw_line)
            return [
                ("slt", ["$at", ops[1], ops[0]]),
                ("beq", ["$at", "$zero", ops[2]]),
            ]

        if mnem == "bge":
            if len(ops) != 3:
                raise AssemblerSyntaxError("'bge' requiere 3 operandos: rs, rt, etiqueta", idx, raw_line)
            return [
                ("slt", ["$at", ops[0], ops[1]]),
                ("beq", ["$at", "$zero", ops[2]]),
            ]

        return [(mnem, ops)]

    # segunda pasada 2: codificacion bianria
    

    def _encode_instruction(self, item: ParsedInstruction) -> int:
        mnem = item.mnemonic

        if mnem == "nop":
            if item.operands:
                raise AssemblerSyntaxError("'nop' no lleva operandos", item.line_num, item.raw_line)
            return 0x00000000

        if mnem == "syscall":
            if item.operands:
                raise AssemblerSyntaxError("'syscall' no lleva operandos", item.line_num, item.raw_line)
            return to_unsigned32((ControlUnit.OP_RTYPE << 26) | ALUControl.FUNCT_SYSCALL)


        if mnem in self.R_TYPE_FUNCT:
            return self._encode_r_type(item)


        if mnem in ("addi", "addiu"):
            return self._encode_imm_signed(item)


        if mnem == "ori":
            return self._encode_ori(item)


        if mnem == "lui":
            return self._encode_lui(item)


        if mnem in ("lw", "sw", "lbu", "lb", "sb"):
            return self._encode_memory_offset(item)


        if mnem in ("beq", "bne"):
            return self._encode_branch(item)


        if mnem == "j":
            return self._encode_jump(item)

        raise AssemblerSyntaxError(f"Instruccion desconocida: '{mnem}'", item.line_num, item.raw_line)

    def _encode_r_type(self, item: ParsedInstruction) -> int:
        if len(item.operands) != 3:
            raise AssemblerSyntaxError(
                f"'{item.mnemonic}' requiere 3 operandos: rd, rs, rt", item.line_num, item.raw_line
            )
        rd = self._parse_register(item.operands[0], item)
        rs = self._parse_register(item.operands[1], item)
        rt = self._parse_register(item.operands[2], item)
        funct = self.R_TYPE_FUNCT[item.mnemonic]
        word = (ControlUnit.OP_RTYPE << 26) | (rs << 21) | (rt << 16) | (rd << 11) | funct
        return to_unsigned32(word)

    def _encode_imm_signed(self, item: ParsedInstruction) -> int:
        if len(item.operands) != 3:
            raise AssemblerSyntaxError(
                f"'{item.mnemonic}' requiere 3 operandos: rt, rs, imm", item.line_num, item.raw_line
            )
        rt = self._parse_register(item.operands[0], item)
        rs = self._parse_register(item.operands[1], item)
        imm16 = self._parse_signed_16bit_immediate(item.operands[2], item)
        opcode = self.I_J_OPCODES[item.mnemonic]
        return to_unsigned32((opcode << 26) | (rs << 21) | (rt << 16) | (imm16 & 0xFFFF))

    def _encode_ori(self, item: ParsedInstruction) -> int:
        if len(item.operands) != 3:
            raise AssemblerSyntaxError("'ori' requiere 3 operandos: rt, rs, imm16", item.line_num, item.raw_line)
        rt = self._parse_register(item.operands[0], item)
        rs = self._parse_register(item.operands[1], item)
        imm16 = self._resolve_hi_lo_or_u16(item.operands[2], item)
        return to_unsigned32((ControlUnit.OP_ORI << 26) | (rs << 21) | (rt << 16) | (imm16 & 0xFFFF))

    def _encode_lui(self, item: ParsedInstruction) -> int:
        if len(item.operands) != 2:
            raise AssemblerSyntaxError("'lui' requiere 2 operandos: rt, imm16", item.line_num, item.raw_line)
        rt = self._parse_register(item.operands[0], item)
        imm16 = self._resolve_hi_lo_or_u16(item.operands[1], item)
        return to_unsigned32((ControlUnit.OP_LUI << 26) | (rt << 16) | (imm16 & 0xFFFF))

    def _encode_memory_offset(self, item: ParsedInstruction) -> int:
        if len(item.operands) != 2:
            raise AssemblerSyntaxError(
                f"'{item.mnemonic}' requiere 2 operandos: rt, offset(rs)", item.line_num, item.raw_line
            )
        rt = self._parse_register(item.operands[0], item)
        match = self.MEM_OPERAND_REGEX.match(item.operands[1])
        if not match:
            raise AssemblerSyntaxError(
                f"Formato de direccion invalido '{item.operands[1]}'", item.line_num, item.raw_line
            )
        imm16 = self._parse_signed_16bit_immediate(match.group(1), item)
        rs = self._parse_register(match.group(2), item)
        opcode = self.I_J_OPCODES[item.mnemonic]
        return to_unsigned32((opcode << 26) | (rs << 21) | (rt << 16) | (imm16 & 0xFFFF))

    def _encode_branch(self, item: ParsedInstruction) -> int:
        if len(item.operands) != 3:
            raise AssemblerSyntaxError(
                f"'{item.mnemonic}' requiere 3 operandos: rs, rt, etiqueta", item.line_num, item.raw_line
            )
        rs = self._parse_register(item.operands[0], item)
        rt = self._parse_register(item.operands[1], item)
        target_token = item.operands[2]

        if target_token in self.symbol_table:
            target_address = self.symbol_table[target_token]
            byte_diff = target_address - (item.address + 4)
            if (byte_diff % 4) != 0:
                raise AssemblerSyntaxError(
                    f"Destino desalineado hacia '{target_token}'", item.line_num, item.raw_line
                )
            offset_words = byte_diff // 4
            if not (-32768 <= offset_words <= 32767):
                raise AssemblerSyntaxError("Salto relativo fuera de rango", item.line_num, item.raw_line)
        else:
            try:
                offset_words = self._parse_signed_16bit_immediate(target_token, item)
            except AssemblerSyntaxError as err:
                raise AssemblerSyntaxError(
                    f"Etiqueta no definida: '{target_token}'", item.line_num, item.raw_line
                ) from err

        opcode = self.I_J_OPCODES[item.mnemonic]
        return to_unsigned32((opcode << 26) | (rs << 21) | (rt << 16) | (offset_words & 0xFFFF))

    def _encode_jump(self, item: ParsedInstruction) -> int:
        if len(item.operands) != 1:
            raise AssemblerSyntaxError("'j' requiere 1 operando", item.line_num, item.raw_line)
        target_token = item.operands[0]
        if target_token in self.symbol_table:
            target_address = self.symbol_table[target_token]
        else:
            try:
                target_address = int(target_token, 0)
            except ValueError as err:
                raise AssemblerSyntaxError(
                    f"Etiqueta de salto no definida: '{target_token}'", item.line_num, item.raw_line
                ) from err

        if (target_address & 0x3) != 0:
            raise AssemblerSyntaxError("Direccion de 'j' no alineada a 4 bytes", item.line_num, item.raw_line)
        if (target_address & 0xF0000000) != ((item.address + 4) & 0xF0000000):
            raise AssemblerSyntaxError("Destino de 'j' cruza frontera de 256 MB", item.line_num, item.raw_line)

        instr_index_26 = (target_address & 0x0FFFFFFF) >> 2
        return to_unsigned32((ControlUnit.OP_J << 26) | (instr_index_26 & 0x03FFFFFF))


    @staticmethod
    def _strip_comments(raw_line: str) -> str:
        # elimina comentarios, no elimina
        in_single = False
        in_double = False
        for i, ch in enumerate(raw_line):
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif ch == "#" and not in_single and not in_double:
                return raw_line[:i]
        return raw_line

    @staticmethod
    def _split_operands(ops_str: str) -> List[str]:
        tokens: List[str] = []
        current: List[str] = []
        in_quotes = False
        quote_char = ""
        for ch in ops_str:
            if ch in ("'", '"'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = ch
                elif quote_char == ch:
                    in_quotes = False
                current.append(ch)
            elif ch == "," and not in_quotes:
                tok = "".join(current).strip()
                if tok:
                    tokens.append(tok)
                current = []
            else:
                current.append(ch)
        last = "".join(current).strip()
        if last:
            tokens.append(last)
        return tokens

    @classmethod
    def _parse_int_or_char(cls, token: str, line_num: int, raw_line: str) -> int:
        t = token.strip()
        if len(t) >= 3 and t.startswith("'") and t.endswith("'"):
            try:
                ch = ast.literal_eval(t)
                if isinstance(ch, str) and len(ch) == 1:
                    return ord(ch)
            except Exception:
                pass
            raise AssemblerSyntaxError(f"Literal de caracter invalido: {t}", line_num, raw_line)
        try:
            return int(t, 0)
        except ValueError as err:
            raise AssemblerSyntaxError(f"Valor numerico invalido: '{t}'", line_num, raw_line) from err

    def _resolve_hi_lo_or_u16(self, token: str, item: ParsedInstruction) -> int:
        t = token.strip()
        if t.startswith("%hi(") and t.endswith(")"):
            label = t[4:-1].strip()
            if label not in self.symbol_table:
                raise AssemblerSyntaxError(f"Etiqueta no definida en 'la': '{label}'", item.line_num, item.raw_line)
            return (self.symbol_table[label] >> 16) & 0xFFFF

        if t.startswith("%lo(") and t.endswith(")"):
            label = t[4:-1].strip()
            if label not in self.symbol_table:
                raise AssemblerSyntaxError(f"Etiqueta no definida en 'la': '{label}'", item.line_num, item.raw_line)
            return self.symbol_table[label] & 0xFFFF

        val = self._parse_int_or_char(t, item.line_num, item.raw_line)
        if not (0 <= val <= 0xFFFF):
            raise AssemblerSyntaxError(f"Inmediato de 16 bits sin signo fuera de rango: {val}", item.line_num, item.raw_line)
        return val

    @staticmethod
    def _parse_register(reg_str: str, item: ParsedInstruction) -> int:
        try:
            return RegisterFile.resolve_name(reg_str)
        except ValueError as err:
            raise AssemblerSyntaxError(str(err), item.line_num, item.raw_line) from err

    @classmethod
    def _parse_signed_16bit_immediate(cls, imm_str: str, item: ParsedInstruction) -> int:
        val = cls._parse_int_or_char(imm_str, item.line_num, item.raw_line)
        if not (-32768 <= val <= 32767):
            raise AssemblerSyntaxError(
                f"El inmediato {val} excede el rango [-32768, 32767]", item.line_num, item.raw_line
            )
        return val
