import unittest
from segmentacion import MIPS32PipelineCPU
from ensamblador import MIPS32Assembler
from memorias import Memory


class TestPipelineCPU(unittest.TestCase):

    def setUp(self):
        self.cpu = MIPS32PipelineCPU()
        self.asm = MIPS32Assembler()

    def test_main_reference_program(self):
        """
        Verifica la ejecucion exacta del programa de prueba de main.py:
        1. addi $t0, $zero, 25      -> $t0 = 25
        2. addi $t1, $t0, 15        -> $t1 = 40 (Forwarding EX/MEM en $t0)
        3. sw   $t1, 0($s0)         -> MEM[0x10000000] = 40 (ForwardB en sw)
        4. lw   $t2, 0($s0)         -> $t2 = 40
        5. add  $t3, $t2, $t0       -> $t3 = 65 (Load-Use stall en $t2!)
        6. beq  $t1, $t2, +1        -> Salta sobre la siguiente instruccion
        7. addi $t4, $zero, 999     -> Anulada por el branch flush
        8. addi $t5, $t3, 5         -> $t5 = 70
        """
        self.cpu.regs.write(16, Memory.DATA_BASE, reg_write=True)

        program = [
            0x20080019,
            0x2109000F,
            0xAE090000,
            0x8E0A0000,
            0x01485820,
            0x112A0001,
            0x200C03E7,
            0x216D0005,
        ]

        self.cpu.load_program(program)
        traces = self.cpu.run()

        self.assertEqual(self.cpu.cycle_count, 14)
        self.assertEqual(self.cpu.instructions_retired, 7)
        self.assertEqual(self.cpu.load_use_stalls, 1)
        self.assertEqual(self.cpu.branch_flushes, 1)

        # Registros esperados
        self.assertEqual(self.cpu.regs.read(8), 25)    # $t0
        self.assertEqual(self.cpu.regs.read(9), 40)    # $t1
        self.assertEqual(self.cpu.regs.read(10), 40)   # $t2
        self.assertEqual(self.cpu.regs.read(11), 65)   # $t3
        self.assertEqual(self.cpu.regs.read(12), 0)    # $t4 (anulado por branch flush!)
        self.assertEqual(self.cpu.regs.read(13), 70)   # $t5
        self.assertEqual(self.cpu.regs.read(16), Memory.DATA_BASE)  # $s0

        # Memoria escrita
        self.assertEqual(self.cpu.memory.read_word(Memory.DATA_BASE), 40)
        self.assertTrue(self.cpu.is_pipeline_empty())
        self.assertTrue(self.cpu.is_halted())

    def test_pipeline_raw_hazard_forwarding(self):
        """
        Verifica los dos tipos de adelantamiento (EX/MEM y MEM/WB) para dependencias RAW.
        """
        code = """
        addi $t0, $zero, 10
        add  $t1, $t0, $zero   # EX hazard: $t0 adelantado desde EX/MEM
        add  $t2, $t0, $zero   # MEM hazard: $t0 adelantado desde MEM/WB
        """
        words = self.asm.assemble(code)
        self.cpu.load_program(words)
        self.cpu.run()

        self.assertEqual(self.cpu.regs.read(8), 10)
        self.assertEqual(self.cpu.regs.read(9), 10)
        self.assertEqual(self.cpu.regs.read(10), 10)
        self.assertEqual(self.cpu.load_use_stalls, 0)

    def test_pipeline_all_r_type_operations(self):
        """
        Verifica el flujo por el cauce de todas las operaciones Tipo-R.
        """
        code = """
        addi $t0, $zero, 20
        addi $t1, $zero, 4
        add  $s0, $t0, $t1     # 24
        sub  $s1, $t0, $t1     # 16
        and  $s2, $t0, $t1     # 20 & 4 = 4
        or   $s3, $t0, $t1     # 20 | 4 = 20
        nor  $s4, $t0, $t1     # ~(20)
        slt  $s5, $t1, $t0     # 4 < 20 -> 1
        slt  $s6, $t0, $t1     # 20 < 4 -> 0
        nop
        """
        words = self.asm.assemble(code)
        self.cpu.load_program(words)
        self.cpu.run()

        self.assertEqual(self.cpu.regs.read(16), 24)
        self.assertEqual(self.cpu.regs.read(17), 16)
        self.assertEqual(self.cpu.regs.read(18), 4)
        self.assertEqual(self.cpu.regs.read(19), 20)
        self.assertEqual(self.cpu.regs.read(20), (~20) & 0xFFFFFFFF)
        self.assertEqual(self.cpu.regs.read(21), 1)
        self.assertEqual(self.cpu.regs.read(22), 0)

    def test_pipeline_branch_not_taken(self):
        """
        Si un salto condicional (beq o bne) no se toma, no debe haber ningun flush.
        """
        code = """
        addi $t0, $zero, 1
        addi $t1, $zero, 2
        beq  $t0, $t1, target   # 1 == 2 es Falso
        addi $t2, $zero, 100    # Debe ejecutarse normalmente
        target:
        addi $t3, $zero, 200
        """
        words = self.asm.assemble(code)
        self.cpu.load_program(words)
        self.cpu.run()

        self.assertEqual(self.cpu.branch_flushes, 0)
        self.assertEqual(self.cpu.regs.read(10), 100)
        self.assertEqual(self.cpu.regs.read(11), 200)

    def test_pipeline_unconditional_jump(self):
        """
        El salto incondicional 'j' se resuelve en ID y vacia la instruccion en IF (1 flush).
        """
        code = """
        addi $t0, $zero, 1
        j    dest
        addi $t1, $zero, 999    # Debe ser purgada
        dest:
        addi $t2, $zero, 42
        """
        words = self.asm.assemble(code)
        self.cpu.load_program(words)
        self.cpu.run()

        self.assertEqual(self.cpu.jump_flushes, 1)
        self.assertEqual(self.cpu.regs.read(8), 1)
        self.assertEqual(self.cpu.regs.read(9), 0)   # Anulada
        self.assertEqual(self.cpu.regs.read(10), 42)

    def test_pipeline_loop_execution(self):
        """
        Bucle iterativo con salto hacia atras y condicion de parada:
        Calcula la suma de los primeros 5 enteros (0+1+2+3+4 = 10).
        """
        code = """
            addi $t0, $zero, 0
            addi $t1, $zero, 5
            addi $t2, $zero, 0
        loop:
            beq  $t0, $t1, end
            add  $t2, $t2, $t0
            addi $t0, $t0, 1
            j    loop
        end:
            addi $t3, $zero, 777
        """
        words = self.asm.assemble(code)
        self.cpu.load_program(words)
        self.cpu.run(max_cycles=200)

        self.assertEqual(self.cpu.regs.read(8), 5)    # i = 5
        self.assertEqual(self.cpu.regs.read(10), 10)  # sum = 10
        self.assertEqual(self.cpu.regs.read(11), 777) # fin alcanzado
        self.assertTrue(self.cpu.is_halted())

    def test_pipeline_store_load_hazards(self):
        """
        Verifica:
        - Store forwarding desde EX/MEM
        - Load-use stall cuando 'lw' va seguido de 'sw'
        - Load-use stall cuando 'lw' va seguido de otro 'lw' con base en el registro cargado
        """
        self.cpu.regs.write(16, Memory.DATA_BASE, reg_write=True)

        code = """
        addi $t0, $zero, 123
        sw   $t0, 0($s0)        # Store forwarding EX/MEM de $t0
        lw   $t1, 0($s0)        # $t1 = 123
        sw   $t1, 4($s0)        # Load-use stall en rt! luego store forwarding WB
        lw   $t2, 4($s0)        # $t2 = 123
        """
        words = self.asm.assemble(code)
        self.cpu.load_program(words)
        self.cpu.run()

        self.assertEqual(self.cpu.memory.read_word(Memory.DATA_BASE), 123)
        self.assertEqual(self.cpu.memory.read_word(Memory.DATA_BASE + 4), 123)
        self.assertEqual(self.cpu.regs.read(9), 123)
        self.assertEqual(self.cpu.regs.read(10), 123)
        self.assertGreaterEqual(self.cpu.load_use_stalls, 1)

    def test_reset(self):
        program = [0x20080019]
        self.cpu.load_program(program)
        self.cpu.step_cycle()
        self.cpu.reset()

        self.assertEqual(self.cpu.cycle_count, 0)
        self.assertEqual(self.cpu.instructions_retired, 0)
        self.assertEqual(self.cpu.pc.value, Memory.TEXT_BASE)
        self.assertTrue(self.cpu.is_pipeline_empty())


if __name__ == "__main__":
    unittest.main()
