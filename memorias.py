import struct
from typing import Tuple
from lib_bits import to_unsigned32

# ExcepcionMemHardware
class HarwareMemException(Exception):
    pass

# Error de Alineamiento
class AlignmentError(Exception):
    pass

# Fallo de Segmentacion
class SegmentationFault(Exception):
    pass

class Memory:

    TEXT_BASE = 0x00400000
    TEXT_SIZE = 1 * 1024*1024       # hasta 0x004F FFFF
    
    DATA_BASE = 0x10000000
    DATA_SIZE = 2 * 1024*1024       # hasta 0x011F FFFF

    def __init__(self, strict_text_protection: bool = True) -> None:
        self._text = bytearray(self.TEXT_SIZE)
        self._data = bytearray(self.DATA_SIZE)
        self.strict_text_protection: bool = strict_text_protection

    #   Borrado a cero
    def reset(self)->None:
        self._text[:] = b"\x00" * self.TEXT_SIZE
        self._data[:] = b"\x00" * self.DATA_SIZE

    """
    Traducir la direccion
    Comprueba el alineamiento, permiso de escritura, comprueba que no sea fase Fetch (tratamiento especial, zona de memoria reservada)
    Devuelve la seccion de memoria (text, data) y un 'puntero' (es un entero al inicio del dato)
    """

    def _tAddr(self, addr:int, size:int, w:bool=False, isIF:bool=False)-> Tuple[bytearray, int]:
        addr = to_unsigned32(addr)

        # alineamiento palabra, y HF
        if size == 4 and (addr & 0x3) != 0:
            raise AlignmentError(f"Alignment Exception W in Dir 0x{addr:08x}")
        
        if size == 2 and (addr & 0x1) != 0:
            raise AlignmentError(f"Alignment Exception HW in Dir 0x{addr:08x}") # no uso halfs pero si bytes
        
        # pertenece a la seccion de texto
        if self.TEXT_BASE <= addr and (addr+size) <= (self.TEXT_BASE + self.TEXT_SIZE):
            if w and self.strict_text_protection:
                raise SegmentationFault(f"Segmentation Fault in 0x{addr:08x}, permision denied")
            return self._text, addr-self.TEXT_BASE
        
        if isIF:
            raise SegmentationFault(f"PC out of range: Dir 0x{addr:08x}")
        # pertenece a la seccion de data

        if self.DATA_BASE <= addr and (addr+size) <= (self.DATA_SIZE + self.DATA_BASE):
            return self._data, addr-self.DATA_BASE
        
        # no pertenece a nada
        raise SegmentationFault(
            f"Segmentation Fault: Dir 0x{addr:08X} (size {size}B)"
            f"Out of Range"
        )

    def fetch_instruction(self, pc: int)->int:
        buff, offset = self._tAddr(pc, size=4, w=False, isIF=True)
        (inst,) = struct.unpack_from(">I", buff, offset)
        # Solo contiene bytes, como guardo bytes,  uso > para Big Endian, I para enteros U.
        # deberia de haber un explicacion detallada... somewhere
        return inst

    def read_word(self, dir:int)->int:
        buff, offset = self._tAddr(dir, size=4, w=False, isIF=False)
        (word, ) = struct.unpack_from(">I", buff, offset)
        return word

    def write_word(self, dir: int, x: int) -> None:
        buff, offset = self._tAddr(dir, size=4, w=True)
        struct.pack_into(">I", buff, offset, to_unsigned32(x))

    # el codigo queda preparado, no testeado, no ncesario
    # def read_half(self, dir: int, signed: bool = True) -> int:
    #     buff, offset = self._tAddr(dir, size=2, w=False)
    #     formatt: str = ">h" if signed else ">H"
    #     (val, _) = struct.unpack_from(formatt, buff, offset)
    #     return to_unsigned32(val)

    # def write_half(self, dir: int, x: int) -> None:
    #     buff, offset = self._tAddr(dir, size=2, w=True)
    #     struct.pack_into(">H", buff, offset, x & 0xFFFF)

    def read_byte(self, dir: int, signed: bool = True) -> int:
        buff, offset = self._tAddr(dir, size=1, w=False)
        formatt: str = ">b" if signed else ">B"
        (val, ) = struct.unpack_from(formatt, buff, offset)
        return to_unsigned32(val)

    def write_byte(self, dir: int, x: int) -> None:
        buff, offset = self._tAddr(dir, size=1, w=True)
        struct.pack_into(">B", buff, offset, x & 0xFF)

    def load_program(self, machine_words: list[int], base_address: int = TEXT_BASE) -> None:
        addr = to_unsigned32(base_address)
        for word in machine_words:
            if not (self.TEXT_BASE <= addr and (addr + 4) <= (self.TEXT_BASE + self.TEXT_SIZE)):
                raise SegmentationFault(f"Load Overthrow in Dir: 0x{addr:08X}.")
            if (addr & 0x3) != 0:
                raise AlignmentError(f"Dir not Aligned: 0x{addr:08X}.")
            offset = addr - self.TEXT_BASE
            struct.pack_into(">I", self._text, offset, to_unsigned32(word))
            addr += 4  
        
    def load_data_bytes(self, raw_bytes: bytes | bytearray, base_address: int = DATA_BASE) -> None:
        # 
        addr = to_unsigned32(base_address)
        end = addr + len(raw_bytes)
        if not (self.DATA_BASE <= addr and end <= (self.DATA_BASE + self.DATA_SIZE)):
            raise SegmentationFault("Overflow while trying to read from  .data.")
        offset = addr - self.DATA_BASE
        self._data[offset : offset + len(raw_bytes)] = raw_bytes

    def read_asciiz(self, address: int, max_len: int = 256) -> str:
        # decidi usar la directiva .ASCIIZ........
        chars: list[int] = []
        for i in range(max_len):
            b = self.read_byte(address + i, signed=False)
            if b == 0:
                break
            chars.append(b)
        return bytes(chars).decode("utf-8", errors="replace")