
from typing import Any, Dict, List
from lib_bits import get_bits, sign_extend_16_32, to_unsigned32
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
    Integra el bus de memoria (.text y .data), banco de 32 registros, ALU de 32 bits,
    Unidad de Control, registros de acoplamiento y unidades de Forwarding y Riesgos.
    """

    def __init__(self) -> None:
        # Subsistemas de almacenamiento y estado arquitectónico
        self.memory = Memory()
        self.regs = RegisterFile()
        self.pc = ProgramCounter()

        # Unidades combinacionales
        self.control_unit = ControlUnit()
        self.alu = ALU()
        self.alu_control = ALUControl()
        self.forwarding = ForwardingUnit()
        self.hazards = HazardDetectionUnit()

        # Registros de acoplamiento entre etapas
        self.if_id = IF_ID_Register()
        self.id_ex = ID_EX_Register()
        self.ex_mem = EX_MEM_Register()
        self.mem_wb = MEM_WB_Register()

        # Límite superior de instrucciones cargadas en .text
        self.program_end: int = Memory.TEXT_BASE

        # Contadores de rendimiento y telemetría de hardware
        self.cycle_count: int = 0
        self.instructions_retired: int = 0
        self.load_use_stalls: int = 0
        self.branch_flushes: int = 0
        self.jump_flushes: int = 0

        # Cables transitorios intraciclo (se reinician en cada flanco de reloj)
        self._wb_reg_write: int = 0
        self._wb_write_reg: int = 0
        self._wb_write_data: int = 0x00000000

        self._ex_branch_taken: bool = False
        self._ex_branch_target: int = 0x00000000

        self._id_jump_taken: bool = False
        self._id_jump_target: int = 0x00000000

    def reset(self) -> None:
        """Reinicia el procesador completo a su estado eléctrico inicial."""
        self.memory.reset()
        self.regs.reset()
        self.pc.reset()

        self.if_id.flush()
        self.id_ex.flush()
        self.ex_mem.flush()
        self.mem_wb.flush()

        self.program_end = Memory.TEXT_BASE
        self.cycle_count = 0
        self.instructions_retired = 0
        self.load_use_stalls = 0
        self.branch_flushes = 0
        self.jump_flushes = 0
        self._reset_transient_wires()

    def _reset_transient_wires(self) -> None:
        """Limpia los cables combinacionales al inicio de cada ciclo."""
        self._wb_reg_write = 0
        self._wb_write_reg = 0
        self._wb_write_data = 0x00000000

        self._ex_branch_taken = False
        self._ex_branch_target = 0x00000000

        self._id_jump_taken = False
        self._id_jump_target = 0x00000000

    def load_program(self, machine_words: List[int], base_address: int = Memory.TEXT_BASE) -> None:
        """
        Carga una lista de palabras máquina de 32 bits en el segmento .text
        y posiciona el PC en la dirección base.
        """
        self.memory.load_program(machine_words, base_address)
        self.pc.write(base_address, pc_write=True)
        self.program_end = to_unsigned32(base_address + (len(machine_words) * 4))

    # =========================================================================
    # EJECUCIÓN INVERSA DE LAS 5 ETAPAS DEL CAUCE (WB -> MEM -> EX -> ID -> IF)
    # =========================================================================

    def _stage_wb(self) -> None:
        """
        PASO 1: Etapa Write-Back (WB).
        Consume MEM/WB, escribe en el banco de registros y retiene sus 3 líneas
        de salida en cables transitorios para que EX pueda hacer Forwarding en el Paso 3.
        """
        if not self.mem_wb.valid:
            self._wb_reg_write = 0
            self._wb_write_reg = 0
            self._wb_write_data = 0x00000000
            return

        self.instructions_retired += 1

        mem_to_reg = self.mem_wb.control.get("MemtoReg", 0)
        reg_write = self.mem_wb.control.get("RegWrite", 0)
        write_reg = self.mem_wb.data["write_reg"]

        # Multiplexor MemtoReg: 1 selecciona el dato de memoria (lw), 0 el resultado de la ALU
        if mem_to_reg == 1:
            write_data = self.mem_wb.data["mem_read_data"]
        else:
            write_data = self.mem_wb.data["alu_result"]

        write_data = to_unsigned32(write_data)

        # Escritura en el Banco de Registros (ocurre en la primera mitad del ciclo, antes de ID)
        self.regs.write(write_reg, write_data, reg_write=(reg_write == 1))

        # Retener las señales de WB para la ForwardingUnit en el Paso 3 (EX)
        self._wb_reg_write = reg_write
        self._wb_write_reg = write_reg
        self._wb_write_data = write_data

    def _stage_mem(self) -> None:
        """
        PASO 2: Etapa Memory Access (MEM).
        Consume EX/MEM, realiza lecturas (lw) o escrituras (sw) en el segmento .data
        y actualiza el registro MEM/WB.
        """
        if not self.ex_mem.valid:
            self.mem_wb.flush()
            return

        mem_read = self.ex_mem.control.get("MemRead", 0)
        mem_write = self.ex_mem.control.get("MemWrite", 0)
        alu_result = self.ex_mem.data["alu_result"]
        write_data = self.ex_mem.data["write_data"]

        mem_read_data = 0x00000000

        # Acceso físico al segmento .data
        if mem_read == 1:
            mem_read_data = self.memory.read_word(alu_result)
        elif mem_write == 1:
            self.memory.write_word(alu_result, write_data)

        # Volcar resultados en MEM/WB (EX/MEM sigue intacto hasta que termine el Paso 3)
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
        """
        PASO 3: Etapa Execute / Address Calculation (EX).
        Consume ID/EX, resuelve adelantamientos (Forwarding) desde EX/MEM y los cables
        retenidos de WB, opera la ALU, evalúa saltos condicionales (beq/bne) y actualiza EX/MEM.
        """
        if not self.id_ex.valid:
            self.forwarding.reset()
            self.ex_mem.flush()
            return

        # 1. Calcular selectores de la ForwardingUnit (ForwardA y ForwardB)
        self.forwarding.compute_signals(
            id_ex=self.id_ex,
            ex_mem=self.ex_mem,
            wb_reg_write=self._wb_reg_write,
            wb_write_reg=self._wb_write_reg,
        )

        # 2. Aplicar multiplexores ForwardA, ForwardB y ALUSrc
        alu_in_a, alu_in_b, rt_value_for_sw = self.forwarding.select_alu_operands(
            id_ex=self.id_ex,
            ex_mem=self.ex_mem,
            wb_write_data=self._wb_write_data,
        )

        # 3. Decodificar la operación exacta de la ALU mediante ALUControl
        alu_op = self.id_ex.control.get("ALUOp", 0b00)
        funct = self.id_ex.data["funct"]
        alu_ctrl_code = self.alu_control.resolve(alu_op, funct)

        # 4. Ejecutar cálculo en la ALU de 32 bits
        alu_result, alu_zero = self.alu.execute(alu_in_a, alu_in_b, alu_ctrl_code)

        # 5. Multiplexor RegDst: 0 selecciona rt (Tipo-I), 1 selecciona rd (Tipo-R)
        if self.id_ex.control.get("RegDst", 0) == 1:
            write_reg = self.id_ex.data["rd"]
        else:
            write_reg = self.id_ex.data["rt"]

        # 6. Calcular dirección efectiva de ramificación: (PC + 4) + (imm_ext << 2)
        imm_ext = self.id_ex.data["imm_ext"]
        pc_plus_4 = self.id_ex.data["pc_plus_4"]
        branch_target = to_unsigned32(pc_plus_4 + (imm_ext << 2))

        # 7. Evaluar si el salto condicional (beq o bne) es efectivamente tomado
        self._ex_branch_taken = self.hazards.is_branch_taken_in_ex(self.id_ex, alu_zero)
        self._ex_branch_target = branch_target

        # 8. Actualizar EX/MEM (Nota: ID/EX sigue intacto para que el Paso 4 compruebe Load-Use)
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
        """
        PASO 4: Etapa Instruction Decode & Register Read (ID).
        Decodifica IF/ID, consulta la HazardDetectionUnit comparando IF/ID contra ID/EX
        (que aún conserva la instrucción que acaba de pasar por EX), e inyecta burbuja
        o actualiza ID/EX según corresponda.
        """
        # Si IF/ID contiene una burbuja, igual debemos evaluar si EX tomó un branch en este ciclo
        if not self.if_id.valid:
            self.hazards.evaluate_hazards_in_id(
                if_id=self.if_id,
                id_ex=self.id_ex,
                branch_taken_in_ex=self._ex_branch_taken,
                jump_in_id=False,
            )
            if self._ex_branch_taken:
                self.branch_flushes += 1
            self.id_ex.flush()
            return

        instr = self.if_id.data["instr"]
        pc = self.if_id.data["pc"]
        pc_plus_4 = self.if_id.data["pc_plus_4"]

        # 1. Extracción física de los campos de la instrucción MIPS32
        opcode = get_bits(instr, 31, 26)
        rs = get_bits(instr, 25, 21)
        rt = get_bits(instr, 20, 16)
        rd = get_bits(instr, 15, 11)
        imm16 = get_bits(instr, 15, 0)
        funct = get_bits(instr, 5, 0)
        jump_index_26 = get_bits(instr, 25, 0)

        # 2. Decodificación de señales en la Unidad de Control Principal
        control_signals = self.control_unit.decode(opcode, inst=instr)

        # 3. Comprobar si es un salto incondicional 'j' y calcular su dirección pseudodirecta
        if control_signals.get("Jump", 0) == 1:
            self._id_jump_taken = True
            self._id_jump_target = to_unsigned32((pc_plus_4 & 0xF0000000) | (jump_index_26 << 2))
        else:
            self._id_jump_taken = False
            self._id_jump_target = 0x00000000

        # 4. Evaluar riesgos (Branch en EX tiene prioridad sobre Load-Use y sobre Jump en ID)
        self.hazards.evaluate_hazards_in_id(
            if_id=self.if_id,
            id_ex=self.id_ex,
            branch_taken_in_ex=self._ex_branch_taken,
            jump_in_id=self._id_jump_taken,
        )

        # Contabilizar eventos de riesgo para telemetría
        if self._ex_branch_taken:
            self.branch_flushes += 1
        elif self.hazards.load_use_stall:
            self.load_use_stalls += 1
        elif self._id_jump_taken:
            self.jump_flushes += 1

        # 5. Si la unidad de riesgos ordena vaciar ID/EX (por Branch tomado o por parada Load-Use)
        if self.hazards.id_ex_flush:
            self.id_ex.flush()
            return

        # 6. Lectura del Banco de Registros y extensión de signo del inmediato
        read_data_1 = self.regs.read(rs)
        read_data_2 = self.regs.read(rt)
        imm_ext = sign_extend_16_32(imm16)

        # 7. Actualizar el registro ID/EX con la instrucción decodificada
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
        """
        PASO 5: Etapa Instruction Fetch (IF).
        Aplica las señales de congelación (stall) o vaciado (flush) emitidas en ID,
        busca la siguiente instrucción en .text si procede y actualiza IF/ID y el PC.
        """
        # Caso 1: Salto tomado (Branch en EX o Jump en ID) -> Vaciar IF/ID y redirigir el PC
        if self.hazards.if_id_flush:
            self.if_id.flush()
            if self._ex_branch_taken:
                self.pc.write(self._ex_branch_target, pc_write=self.hazards.pc_write)
            elif self._id_jump_taken:
                self.pc.write(self._id_jump_target, pc_write=self.hazards.pc_write)
            return

        # Caso 2: Parada por riesgo Load-Use -> Congelar IF/ID y mantener el PC sin cambios
        if self.hazards.if_id_stall:
            self.if_id.stall(True)
            self.pc.write(self.pc.value, pc_write=False)
            self.if_id.stall(False)
            return

        # Caso 3: El PC ha alcanzado el final del código cargado -> Drenar el cauce con burbujas
        current_pc = self.pc.value
        if current_pc >= self.program_end:
            self.if_id.flush()
            return

        # Caso 4: Búsqueda normal de instrucción en el segmento .text
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

    # =========================================================================
    # INTERFAZ DE CONTROL DE SIMULACIÓN Y TELEMETRÍA
    # =========================================================================

    def step_cycle(self) -> Dict[str, Any]:
        """
        Ejecuta exactamente 1 ciclo de reloj completo en orden inverso:
        WB -> MEM -> EX -> ID -> IF, devolviendo una instantánea detallada del estado.
        """
        self._reset_transient_wires()
        self.cycle_count += 1

        # Ejecución estricta de derecha a izquierda
        self._stage_wb()
        self._stage_mem()
        self._stage_ex()
        self._stage_id()
        self._stage_if()

        return self.get_cycle_snapshot()

    def is_pipeline_empty(self) -> bool:
        """Indica si los cuatro registros de acoplamiento contienen burbujas."""
        return not (
            self.if_id.valid
            or self.id_ex.valid
            or self.ex_mem.valid
            or self.mem_wb.valid
        )

    def is_halted(self) -> bool:
        """
        El procesador ha finalizado cuando el PC está en o tras el final del programa
        y todas las instrucciones en vuelo han terminado de drenarse por la etapa WB.
        """
        return (self.pc.value >= self.program_end) and self.is_pipeline_empty()

    def run(self, max_cycles: int = 10000) -> List[Dict[str, Any]]:
        """
        Ejecuta el programa ciclo a ciclo hasta que el cauce se drene por completo
        o se alcance el límite de seguridad 'max_cycles'.
        """
        history: List[Dict[str, Any]] = []
        while not self.is_halted() and self.cycle_count < max_cycles:
            snapshot = self.step_cycle()
            history.append(snapshot)
        return history

    def get_cycle_snapshot(self) -> Dict[str, Any]:
        """Genera un diccionario con el estado completo del procesador al final del ciclo."""
        return {
            "cycle": self.cycle_count,
            "pc": f"0x{self.pc.value:08X}",
            "ForwardA": f"0b{self.forwarding.forward_a:02b}",
            "ForwardB": f"0b{self.forwarding.forward_b:02b}",
            "load_use_stall": self.hazards.load_use_stall,
            "branch_taken": self._ex_branch_taken,
            "jump_taken": self._id_jump_taken,
            "stages": {
                "IF/ID": self.if_id.snapshot(),
                "ID/EX": self.id_ex.snapshot(),
                "EX/MEM": self.ex_mem.snapshot(),
                "MEM/WB": self.mem_wb.snapshot(),
            },
            "registers": self.regs.dump(cond=True),
        }
