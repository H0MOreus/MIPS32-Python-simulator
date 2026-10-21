# La simulacion debe cubrir al menos ocho instrucciones tipo aritmeticologicas
# cuatro instrucciones de almacenamiento y lectura de memoria
# tres saltos (al menos uno condicional y otro incondicional
# y uno hacia adelante y otro hacia atras obligatoriamente
# 


#int main (void) {
#    i = 0;
#     while ( (caracter = string[i]) != '\0' ) {
#         if ( (caracter >= 'a') and (caracter <= 'z') )
#             string[i] = caracter -'a' + 'A'; i++;
#     }
#     return 0;}

	.data
input:	.space 32
	.text
main:
	li $t0, 0
	la $s1, input 
	li $t6, 'a'	# menor que -> se suman 32
	li $t7, 'z'	# mayor que -> ya es mayuscula o es caracter especial.
while:
	addu $t2, $s1, $t0	#	t2 es el puntero; string[i]; 
	lbu   $t1, 0($t2)	# 	caracter =  string[i]
	
	beqz $t1, end_main
	bgt  $t1, $t7, itNext 		# si es mayuscula o caracter especial
	blt  $t1, $t6, itNext		# si no es un caracter
					# logica negativa
toUpper:
	addi $t1, $t1, -32
	sb   $t1, 0($t2)
toLower:

itNext:
	addi $t0, $t0, 1
	j while
	 	
end_main:
# no ponemos nada termina solo.
#    li $v0, 17
#    li $a0, 0
#    syscall



#	Caracter	Decimal		Hexadecimal		Binario (8 bits)
#		A			65			0x41		0100 0001
#		Z			90			0x5A		0101 1010
#		a			97			0x61		0110 0001
#		z			122			0x7A		0111 1010