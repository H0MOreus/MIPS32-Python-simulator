import unittest
from ensamblador import MIPS32Assembler, AssemblerSyntaxError
from memorias import Memory


class TestAssembler(unittest.TestCase):

    def setUp(self):
        self.asm = MIPS32Assembler(base_address=Memory.TEXT_BASE)

    def test_assemble_nop(self):
        words = self.asm.assemble("nop")
        self.assertEqual(words, [0x00000000])

    def test_assemble_r_types(self):
        code = """
        add $t0, $t1, $t2
        sub $t3, $t4, $t5
        and $s0, $s1, $s2
        or  $s3, $s4, $s5
        nor $s6, $s7, $t8
        slt $t9, $a0, $a1
        """
        words = self.asm.assemble(code)
        self.assertEqual(len(words), 6)

        # add $t0, $t1, $t2 -> rd=8, rs=9, rt=10, funct=0x20
        # (0 << 26) | (9 << 21) | (10 << 16) | (8 << 11) | 0x20
        expected_add = (0 << 26) | (9 << 21) | (10 << 16) | (8 << 11) | 0x20
        self.assertEqual(words[0], expected_add)

    def test_assemble_addi(self):
        # addi $t0, $zero, 25 -> opcode=0x08, rs=0, rt=8, imm=25
        code = "addi $t0, $zero, 25"
        words = self.asm.assemble(code)
        self.assertEqual(words, [0x20080019])

        # addi con numero negativo: addi $t0, $t0, -5 -> imm=0xFFFB
        code_neg = "addi $t0, $t0, -5"
        words_neg = self.asm.assemble(code_neg)
        expected_neg = (0x08 << 26) | (8 << 21) | (8 << 16) | 0xFFFB
        self.assertEqual(words_neg, [expected_neg])

    def test_assemble_lw_sw(self):
        code = """
        sw $t1, 0($s0)
        lw $t2, 4($s0)
        """
        words = self.asm.assemble(code)
        # sw: opcode 0x2B (43), rs=16 ($s0), rt=9 ($t1), offset=0 -> 0xAE090000
        self.assertEqual(words[0], 0xAE090000)
        # lw: opcode 0x23 (35), rs=16 ($s0), rt=10 ($t2), offset=4 -> 0x8E0A0004
        self.assertEqual(words[1], 0x8E0A0004)

    def test_assemble_branch_forward_and_backward(self):
        code = """
        loop:
            addi $t0, $t0, 1
            beq  $t0, $t1, exit
            j    loop
        exit:
            addi $t2, $zero, 99
        """
        words = self.asm.assemble(code)
        # loop esta en 0x00400000 (addi)
        # beq esta en 0x00400004. pc_plus_4 = 0x00400008.
        # j esta en 0x00400008.
        # exit esta en 0x0040000C.
        # byte_diff para beq = 0x0040000C - 0x00400008 = +4 bytes = +1 palabra
        # beq $t0, $t1, exit: opcode 0x04, rs=8, rt=9, offset=1 -> (4<<26)|(8<<21)|(9<<16)|1
        expected_beq = (0x04 << 26) | (8 << 21) | (9 << 16) | 1
        self.assertEqual(words[1], expected_beq)

        # j loop: loop address = 0x00400000.
        # instr_index = (0x00400000 & 0x0FFFFFFF) >> 2 = 0x00100000
        expected_j = (0x02 << 26) | 0x00100000
        self.assertEqual(words[2], expected_j)

    def test_assemble_bne(self):
        code = """
        start:
            bne $t0, $t1, start
        """
        # pc = 0x00400000. pc_plus_4 = 0x00400004.
        # target = 0x00400000. byte_diff = -4 bytes = -1 palabra.
        # offset_words = -1 -> 0xFFFF
        words = self.asm.assemble(code)
        expected_bne = (0x05 << 26) | (8 << 21) | (9 << 16) | 0xFFFF
        self.assertEqual(words[0], expected_bne)

    def test_assemble_with_listing(self):
        code = "addi $t0, $zero, 10"
        words, syms, listing = self.asm.assemble_with_listing(code)
        self.assertEqual(words, [0x2008000A])
        self.assertEqual(listing[0]["hex"], "0x2008000A")
        self.assertEqual(listing[0]["address"], "0x00400000")

    def test_comments_and_empty_lines(self):
        code = """
        # Comentario inicial
        
        main: # Etiqueta con comentario
            nop # no operation
            
        """
        words = self.asm.assemble(code)
        self.assertEqual(words, [0x00000000])

    def test_duplicate_label_error(self):
        code = """
        loop:
            nop
        loop:
            nop
        """
        with self.assertRaises(AssemblerSyntaxError):
            self.asm.assemble(code)

    def test_invalid_label_name(self):
        code = "123badlabel: nop"
        with self.assertRaises(AssemblerSyntaxError):
            self.asm.assemble(code)

    def test_unknown_instruction(self):
        code = "xyz $t0, $t1, $t2"
        with self.assertRaises(AssemblerSyntaxError):
            self.asm.assemble(code)

    def test_operand_count_mismatch(self):
        code = "add $t0, $t1"
        with self.assertRaises(AssemblerSyntaxError):
            self.asm.assemble(code)

    def test_invalid_register_name(self):
        code = "add $t0, $t1, $foo"
        with self.assertRaises(AssemblerSyntaxError):
            self.asm.assemble(code)

    def test_immediate_out_of_range(self):
        code = "addi $t0, $zero, 70000"
        with self.assertRaises(AssemblerSyntaxError):
            self.asm.assemble(code)

    def test_unsupported_directive(self):
        code = ".desconocida"
        with self.assertRaises(AssemblerSyntaxError):
            self.asm.assemble(code)


if __name__ == "__main__":
    unittest.main()
