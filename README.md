# MIPS32 Python Simulator

Simulador completo de una arquitectura **MIPS32 segmentada de 5 etapas** (*pipelined CPU*) implementado en Python orientado a objetos.

El proyecto modela de forma precisa el camino de datos (*segmentacion*), registros de acoplamiento, unidad de control, banco de registros, jerarquía de memoria virtual (segmentos `.text` y `.data`), resolución de riesgos de datos (adelantamiento / *forwarding*), riesgos estructurales y de control (*stalls* y *flushes*), además de incluir un **ensamblador de dos pasadas**.

---

## 🏛️ Arquitectura del Cauce (5 Etapas)

La CPU sigue el modelo clásico RISC de segmentación:

1. **IF (Instruction Fetch):** Lectura de la instrucción de 32 bits desde el segmento `.text` de memoria según el `ProgramCounter` (PC) y cálculo de `PC + 4`.
2. **ID (Instruction Decode / Register Read):** Decodificación de los campos de la instrucción, lectura del banco de 32 registros y extensión de signo/cero de inmediatos.
3. **EX (Execute / Address Calculation):** Ejecución de la operación en la ALU de 32 bits, cálculo de la dirección efectiva de memoria o evaluación de salto.
4. **MEM (Memory Access):** Lectura o escritura en la memoria de datos (`.data`) para instrucciones de carga (`lw`) y almacenamiento (`sw`).
5. **WB (Write Back):** Escritura del resultado (procedente de la ALU o de la memoria) en el registro destino del banco de registros.

---

## ⚡ Manejo de Riesgos (Hazards)

### 1. Unidad de Adelantamiento (*Forwarding Unit*)

Evita paradas innecesarias por dependencias de datos RAW (*Read-After-Write*):

* **EX Hazard:** Adelanta datos calculados en la etapa `EX/MEM` directamente a las entradas de la ALU.
* **MEM Hazard:** Adelanta datos desde la etapa `MEM/WB` a las entradas de la ALU.
* **Store Forwarding:** Adelanta datos directamente hacia el operando a escribir de la instrucción `sw`.

### 2. Detección de Riesgos y Paradas (*Hazard Detection Unit*)

* **Riesgo Load-Use:** Si una instrucción depende inmediatamente del dato cargado por una instrucción `lw`, se introduce automáticamente una parada (*stall*) de 1 ciclo (bloqueando el PC y el registro `IF/ID`, e insertando una burbuja en `ID/EX`).

### 3. Riesgos de Control (*Branch & Jump Flush*)

* Al tomarse un salto condicional (`beq`, `bne`) o incondicional (`j`), las instrucciones que entraron especulativamente al cauce son purgadas (*flushed*) convirtiendo sus señales de control en operaciones nulas (NOP / burbuja).

---

## 📦 Repertorio de Instrucciones Soportado

| Tipo | Mnemónicos | Descripción |
| :--- | :--- | :--- |
| **Tipo-R** | `add`, `sub`, `and`, `or`, `nor`, `slt`, `nop` | Operaciones aritmético-lógicas entre registros y no-operación. |
| **Tipo-I** | `addi`, `lw`, `sw`, `beq`, `bne` | Inmediatos, acceso a memoria y saltos condicionales relativos. |
| **Tipo-J** | `j` | Salto incondicional a dirección absoluta. |

---

## 📂 Estructura del Proyecto

* **`segmentacion.py`**: Clase `MIPS32PipelineCPU`. Coordina el ciclo de reloj, las cinco etapas en orden inverso (`WB -> MEM -> EX -> ID -> IF`) para propagación limpia, telemetría y ejecución.
* **`pipeline_regs.py`**: Modelado de los cuatro registros inter-etapa (`IF/ID`, `ID/EX`, `EX/MEM`, `MEM/WB`), con control de retención (*stall*), purga (*flush*) y propagación de señales.
* **`forwarding.py`**: Implementación de la `ForwardingUnit` y la `HazardDetectionUnit`.
* **`control.py`**: Unidad de control principal (`ControlUnit`) que genera señales como `RegWrite`, `MemRead`, `MemWrite`, `Branch`, `ALUSrc`, `RegDst`, etc.
* **`alu.py`**: ALU de 32 bits y decodificador `ALUControl` según el campo `funct` u operación.
* **`registers.py`**: Banco de 32 registros de propósito general (`RegisterFile`) con invariante `$zero == 0` y contador de programa (`ProgramCounter`).
* **`memorias.py`**: Memoria virtual Harvard de 32 bits con secciones `.text` (`0x00400000`) y `.data` (`0x10000000`), control de alineamiento y excepciones de segmentación.
* **`ensamblador.py`**: Ensamblador MIPS32 de dos pasadas. Permite procesar código fuente con etiquetas (*labels*), comentarios y cálculo automático de saltos relativos.
* **`lib_bits.py`**: Primitivas a nivel de bit: extensiones de signo/cero, máscaras de 32/16 bits y extracción de campos de bits.
* **`main.py`**: Punto de entrada con demostración completa de ejecución ciclo a ciclo.

---

## 🚀 Puesta en Marcha

### Requisitos

* Python 3.10 o superior (no requiere librerías externas adicionales).

### Ejecución

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
    