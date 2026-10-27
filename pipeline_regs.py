from typing import Any, Dict
from control import ControlUnit


class PipelineRegister:
    """
    Valid es una signal que simplifica el manejo de las burbujas, en vez de mirar que las signal de control
    sean todas 0, miramos una sola.

    stalled restringe o permite escribir (y propagar) las signals de los registros de acoplamiento
    
    Las signals de control se propagan como un diccionario

    el metodo make_bubble_signals inicializa a 0 las señales de control, (tambien sirve para introducir bubbles)
    """
    def __init__(self, name: str) -> None:
        self.name: str = name
        self.valid: bool = False
        self.stalled: bool = False
        self.control: Dict[str, int] = ControlUnit.make_bubble_signals()
        self.data: Dict[str, int] = {}
        self.flush()

    def _default_data(self) -> Dict[str, int]:
        """ Cada registro de acoplamiento tendra su especificacion propia"""
        return {}

    def flush(self) -> None:

        self.valid = False
        self.stalled = False
        self.control = ControlUnit.make_bubble_signals()
        self.data = self._default_data()

    def stall(self, enable: bool = True) -> None:
        self.stalled = enable


    """
    Controla la propagacion de signals y datos.
    O la recepcion dependiendo de como se mire.
    """
    def latch(self, valid: bool, control: Dict[str, int], data: Dict[str, int]) -> None:
        
        if self.stalled:
            return
        if not valid:
            self.flush()
            return

        self.valid = True

        # copia de las signals que recive, para no modificar las signals de la etapa anterior
        self.control = dict(control)
        # especificacion del formato
        merged_data = self._default_data()
        # actualizacion del dict vacio
        merged_data.update(data)
        # nuevo puntero a data
        self.data = merged_data

    """
    Imprimir el estado del registro
    """
    def snapshot(self) -> Dict[str, Any]:
    
        return {
            "name": self.name,
            "valid": self.valid,
            "stalled": self.stalled,
            "control": dict(self.control),
            "data": {k: f"0x{v:08X}" for k, v in self.data.items()},
        }


class IF_ID_Register(PipelineRegister):

    def __init__(self) -> None:
        super().__init__("IF/ID")

    def _default_data(self) -> Dict[str, int]:
        return {
            "instr": 0x00000000,   # Palabra de instruccion de 32 bits
            "pc_plus_4": 0x00000000,
            "pc": 0x00000000,      # PC original de la instruccion
        }


class ID_EX_Register(PipelineRegister):

    def __init__(self) -> None:
        super().__init__("ID/EX")

    def _default_data(self) -> Dict[str, int]:
        return {
            "pc": 0x00000000,
            "pc_plus_4": 0x00000000,
            "read_data_1": 0x00000000,  # rs
            "read_data_2": 0x00000000,  # rt
            "imm_ext": 0x00000000,      # Inmediato de 16 bits con extension de signo a 32 bits
            "rs": 0,                    # Indice del registro fuente 1 (bits 25:21)
            "rt": 0,                    # Indice del registro fuente 2 / destino I (bits 20:16)
            "rd": 0,                    # Indice del registro destino r (bits 15:11)
            "funct": 0,                 # Campo funct (bits 5:0) para ALUControl
        }


class EX_MEM_Register(PipelineRegister):

    def __init__(self) -> None:
        super().__init__("EX/MEM")

    def _default_data(self) -> Dict[str, int]:
        return {
            "pc": 0x00000000,
            "branch_target": 0x00000000,  # Direccion efectiva de salto condicional
            "alu_zero": 0,                # Bandera Zero de la ALU (saltos)
            "alu_result": 0x00000000,     # Salida de la ALU
            "write_data": 0x00000000,     # Valor de rt (con forwarding aplicado) para 'sw'
            "write_reg": 0,
        }


class MEM_WB_Register(PipelineRegister):

    def __init__(self) -> None:
        super().__init__("MEM/WB")

    def _default_data(self) -> Dict[str, int]:
        return {
            "pc": 0x00000000,
            "read_data": 0x00000000,
            "mem_read_data": 0x00000000,        # Palabra de .data en 'lw'
            "alu_result": 0x00000000,       # Resultado de la ALU adelantado hacia WB
            "write_reg": 0,                        # registro destino
        }
