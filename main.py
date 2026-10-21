"""
1) Se desea la creacion de una simulacion de segmentacion de instrucciones
mediante Python. Esta simulacion debe ser intuitiva y facil de seguir. No es
necesario que sea grafica y visual, puede ser por consola, pero debera ser lo
suficientemente explicativa: estado actual de los registros contador del
programa, registro de instruccion, informacion en registros, caminos utilizados
por cada instruccion en cada fase de la segmentacion, etc. Asi el programa debe
indicar en cada momento la etapa y lugares del camino de datos que realizan
cada tarea especifica para las instrucciones a procesar.

2) Se deben utilizar estructuras de datos adecuadas para el correcto
funcionamiento de la simulacion. Ademas, debera utilizarse programacion
orientada a objetos para proporcionar la adecuada abstraccion.

3) La inicializacion del sistema debe presentar la cadena de montaje de la
segmentacion vacia. Esta se ira llenando segun se procesen instrucciones.
"""

from lib_bits import sign_extend_16_32
from datapath import MIPS32PipelineCPU

if __name__ == "__main__":
    cpu = MIPS32PipelineCPU()

    # Base de .data = 0x10000000. Pre-cargamos $s0 ($16) con 0x10000000 para direccionar .data
    cpu.regs.write(16, 0x10000000, reg_write=True)

    # Programa en código máquina MIPS32:
    # 1. addi $t0, $zero, 25      -> 0x20080019 ($t0 = 25)
    # 2. addi $t1, $t0, 15        -> 0x2109000F ($t1 = $t0 + 15 = 40) [Riesgo EX/MEM en $t0]
    # 3. sw   $t1, 0($s0)         -> 0xAE090000 (MEM[0x10000000] = $t1 = 40) [ForwardB en sw]
    # 4. lw   $t2, 0($s0)         -> 0x8E0A0000 ($t2 = MEM[0x10000000] = 40)
    # 5. add  $t3, $t2, $t0       -> 0x01485820 ($t3 = $t2 + $t0 = 65) [Riesgo Load-Use en $t2!]
    # 6. beq  $t1, $t2, +1        -> 0x112A0001 (Como $t1 == $t2 == 40, salta 1 instr adelante)
    # 7. addi $t4, $zero, 999     -> 0x200C03E7 (Debe ser ANULADA por el flush del beq)
    # 8. addi $t5, $t3, 5         -> 0x216D0005 ($t5 = $t3 + 5 = 70) [Destino del salto beq]
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

    cpu.load_program(program)
    traces = cpu.run()

    print(f"Ciclos totales ejecutados : {cpu.cycle_count}")
    print(f"Instrucciones retiradas   : {cpu.instructions_retired}")
    print(f"Paradas Load-Use (stalls) : {cpu.load_use_stalls}")
    print(f"Vaciados por Branch       : {cpu.branch_flushes}")
    print("Estado final de registros :", cpu.regs.dump(cond=True))
    print(f"Valor en .data[0x10000000]: {cpu.memory.read_word(0x10000000)}")
