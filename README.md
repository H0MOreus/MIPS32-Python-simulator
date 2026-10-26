# MIPS32 Python Simulator

Simulador completo de una arquitectura **MIPS32 segmentada de 5 etapas** (*pipelined CPU*) implementado en Python orientado a objetos.

El proyecto modela de forma precisa el camino de datos (*segmentacion*), registros de acoplamiento, unidad de control, banco de registros, jerarquia de memoria virtual (segmentos `.text` y `.data`), resolucion de riesgos de datos (adelantamiento / *forwarding*), riesgos estructurales y de control (*stalls* y *flushes*), ademas de incluir un **ensamblador de dos pasadas**.

---

## 🏛️ Arquitectura del Cauce (5 Etapas)

La CPU sigue el modelo clasico RISC de segmentacion:

1. **IF (Instruction Fetch):** Lectura de la instruccion de 32 bits desde el segmento `.text` de memoria segun el `ProgramCounter` (PC) y calculo de `PC + 4`.
2. **ID (Instruction Decode / Register Read):** Decodificacion de los campos de la instruccion, lectura del banco de 32 registros y extension de signo/cero de inmediatos.
3. **EX (Execute / Address Calculation):** Ejecucion de la operacion en la ALU de 32 bits, calculo de la direccion efectiva de memoria o evaluacion de salto.
4. **MEM (Memory Access):** Lectura o escritura en la memoria de datos (`.data`) para instrucciones de carga (`lw`) y almacenamiento (`sw`).
5. **WB (Write Back):** Escritura del resultado (procedente de la ALU o de la memoria) en el registro destino del banco de registros.

---

## ⚡ Manejo de Riesgos (Hazards)

### 1. Unidad de Adelantamiento (*Forwarding Unit*)

Evita paradas innecesarias por dependencias de datos RAW (*Read-After-Write*):

* **EX Hazard:** Adelanta datos calculados en la etapa `EX/MEM` directamente a las entradas de la ALU.
* **MEM Hazard:** Adelanta datos desde la etapa `MEM/WB` a las entradas de la ALU.
* **Store Forwarding:** Adelanta datos directamente hacia el operando a escribir de la instruccion `sw`.

### 2. Deteccion de Riesgos y Paradas (*Hazard Detection Unit*)

* **Riesgo Load-Use:** Si una instruccion depende inmediatamente del dato cargado por una instruccion `lw`, se introduce automaticamente una parada (*stall*) de 1 ciclo (bloqueando el PC y el registro `IF/ID`, e insertando una burbuja en `ID/EX`).

### 3. Riesgos de Control (*Branch & Jump Flush*)

* Al tomarse un salto condicional (`beq`, `bne`) o incondicional (`j`), las instrucciones que entraron especulativamente al cauce son purgadas (*flushed*) convirtiendo sus señales de control en operaciones nulas (NOP / burbuja).

---

## 📦 Repertorio de Instrucciones Soportado

| Tipo | Mnemonicos | Descripcion |
| :--- | :--- | :--- |
| **Tipo-R** | `add`, `sub`, `and`, `or`, `nor`, `slt`, `nop` | Operaciones aritmetico-logicas entre registros y no-operacion. |
| **Tipo-I** | `addi`, `lw`, `sw`, `beq`, `bne` | Inmediatos, acceso a memoria y saltos condicionales relativos. |
| **Tipo-J** | `j` | Salto incondicional a direccion absoluta. |

---

## 📂 Estructura del Proyecto

* **`segmentacion.py`**: Clase `MIPS32PipelineCPU`. Coordina el ciclo de reloj, las cinco etapas en orden inverso (`WB -> MEM -> EX -> ID -> IF`) para propagacion limpia, telemetria y ejecucion.
* **`pipeline_regs.py`**: Modelado de los cuatro registros inter-etapa (`IF/ID`, `ID/EX`, `EX/MEM`, `MEM/WB`), con control de retencion (*stall*), purga (*flush*) y propagacion de señales.
* **`forwarding.py`**: Implementacion de la `ForwardingUnit` y la `HazardDetectionUnit`.
* **`control.py`**: Unidad de control principal (`ControlUnit`) que genera señales como `RegWrite`, `MemRead`, `MemWrite`, `Branch`, `ALUSrc`, `RegDst`, etc.
* **`alu.py`**: ALU de 32 bits y decodificador `ALUControl` segun el campo `funct` u operacion.
* **`registers.py`**: Banco de 32 registros de proposito general (`RegisterFile`) con invariante `$zero == 0` y contador de programa (`ProgramCounter`).
* **`memorias.py`**: Memoria virtual Harvard de 32 bits con secciones `.text` (`0x00400000`) y `.data` (`0x10000000`), control de alineamiento y excepciones de segmentacion.
* **`ensamblador.py`**: Ensamblador MIPS32 de dos pasadas. Permite procesar codigo fuente con etiquetas (*labels*), comentarios y calculo automatico de saltos relativos.
* **`lib_bits.py`**: Primitivas a nivel de bit: extensiones de signo/cero, mascaras de 32/16 bits y extraccion de campos de bits.
* **`main.py`**: Punto de entrada con demostracion completa de ejecucion ciclo a ciclo.

---

## 🚀 Puesta en Marcha

### Requisitos

* Python 3.10 o superior (no requiere librerias externas adicionales).

### Ejecucion

Para ejecutar el programa de prueba integrado:

```bash
python3 main.py
```

### Salida esperada

El programa ejecuta un flujo de instrucciones de prueba que demuestra el funcionamiento coordinado de *forwarding*, *load-use stall*, *branch flush* y acceso a memoria:

```text
Ciclos totales ejecutados : 14
Instrucciones retiradas   : 7
Paradas Load-Use (stalls) : 1
Vaciados por Branch       : 1
Estado final de registros : {'$zero ($0)': '0x00000000', '$t0 ($8)': '0x00000019', '$t1 ($9)': '0x00000028', '$t2 ($10)': '0x00000028', '$t3 ($11)': '0x00000041', '$t5 ($13)': '0x00000046', '$s0 ($16)': '0x10000000'}
Valor en .data[0x10000000]: 40
```

## TODO

    - Implementar y testear usar un parametro de entrada del programa para cargar un programa mips32
    - Explicar y documentar el funcionamiento del simulador
    - Depurar y limpiar el codigo
    - Comentar linea de razonamiento y metodologia de trabajo
    