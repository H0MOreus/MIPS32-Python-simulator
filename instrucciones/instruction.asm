    .data
input:	.asciiz "Hola Mundo 123"
output: .space 32			# Reserva 32 bytes

	.text
	.globl main
main:
	# Carga de direcciones base en registros $s
	la $s0, input			# $s0 = puntero input
	la $s1, output			# $s1 = puntero output
	
	li $s2, 0			# $s2 = iterador (i)
	
	# constantes
	li $s4, 'a'			# 97
	li $s5, 'z'			# 122
	li $s6, 'A'			# 65
	li $s7, 'Z'			# 90

bucle:
	addu $t0, $s0, $s2		# $t0 = &input[i]
        # RAW modifico y leo $t0
	lbu  $s3, 0($t0)		# $s3 = input[i]
	
	beqz $s3, fin_cadena    # RAW escribo en $s3 desde memoria y luego leo $s3 para hacer una comparacion
	
	blt  $s3, $s4, check_upper	# Menor que 'a' -> check_upper
	bgt  $s3, $s5, store_char	# Mayor que 'z' -> no es letra

toUpper:
	# Es minuscula
	addi $s3, $s3, -32
	j    store_char

check_upper:
	blt  $s3, $s6, store_char	# Menor que 'A' -> no es letra
	bgt  $s3, $s7, store_char	# Mayor que 'Z' -> no es letra
    j toLower                   # no hace falta
toLower:
	addi $s3, $s3, 32

store_char:
	addu $t1, $s1, $s2		# $t1 = &output[i]
	sb   $s3, 0($t1)		# output[i] = $s3
                            # RAW: modifico $t1 y luego leo $t1
	
	addi $s2, $s2, 1		# i++
	j    bucle

fin_cadena:
	addu $t1, $s1, $s2
	sb   $zero, 0($t1)

end_main:
# no usaremos subrutas, solo simulare terminacion de programa.
	li   $v0, 10			# Salida del programa
	syscall