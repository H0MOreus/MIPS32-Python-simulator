import argparse
import sys
from pathlib import Path
from typing import Optional

from ensamblador import MIPS32Assembler, AssemblerSyntaxError
from segmentacion import Segmentacion
from memorias import Memory, HarwareMemException, AlignmentError, SegmentationFault

DEFAULT_CANDIDATE_PATHS = [
    Path("./instrucciones/instruction.txt"),
    Path("./instrucciones/instruction.asm"),
]


def resolve_instruction_file(custom_path: Optional[str] = None) -> Path:
    if custom_path:
        target = Path(custom_path)
        if not target.is_file():
            raise FileNotFoundError(f"No se encontro el archivo indicado: '{target}'")
        return target

    script_dir = Path(__file__).resolve().parent
    for rel_path in DEFAULT_CANDIDATE_PATHS:
        if rel_path.is_file():
            return rel_path
        alt_path = script_dir / rel_path
        if alt_path.is_file():
            return alt_path

    raise FileNotFoundError("No se encontro ningun archivo en ./instrucciones/")


def format_stage(stage_snap: dict, source_map: dict[int, str]) -> str:
    if not stage_snap["valid"]:
        return "[BURBUJA / NOP]"
    pc_int = int(stage_snap["data"]["pc"], 16)
    asm = source_map.get(pc_int, stage_snap["data"]["pc"])
    stall_tag = " (STALL)" if stage_snap["stalled"] else ""
    return f"0x{pc_int:08X}: {asm}{stall_tag}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulador MIPS32 segmentado de 5 etapas.")
    parser.add_argument("program", nargs="?", default=None, help="Ruta al archivo .txt o .asm")
    parser.add_argument("--max-cycles", type=int, default=5000, help="Limite de ciclos")
    parser.add_argument("--quiet", action="store_true", help="Oculta la traza ciclo a ciclo")
    args = parser.parse_args()

    try:
        source_path = resolve_instruction_file(args.program)
        source_code = source_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as err:
        print(f"[ERROR DE ARCHIVO] {err}", file=sys.stderr)
        return 1

    print(f"Archivo fuente cargado: {source_path}")

    assembler = MIPS32Assembler(base_address=Memory.TEXT_BASE)
    try:
        machine_words, symbols, listing = assembler.assemble_with_listing(source_code)
    except AssemblerSyntaxError as err:
        print(f"[ERROR DE ENSAMBLADO] {err}", file=sys.stderr)
        return 1

    cpu = Segmentacion()
    cpu.load_program(
        machine_words=machine_words,
        base_address=Memory.TEXT_BASE,
        data_bytes=assembler.data_image,
    )

    try:
        while not cpu.is_halted() and cpu.cycle_count < args.max_cycles:
            snap = cpu.step_cycle()
            if not args.quiet:
                print(
                    f"[Ciclo {snap['cycle']:03d}] PC={snap['pc']} | "
                    f"FwdA={snap['ForwardA']} FwdB={snap['ForwardB']} | "
                    f"Stall={snap['load_use_stall']} Branch={snap['branch_taken']} "
                    f"SyscallHalt={snap['halted_by_syscall']}"
                )
                for st_name in ("MEM/WB", "EX/MEM", "ID/EX", "IF/ID"):
                    print(f"  {st_name:<6}: {format_stage(snap['stages'][st_name], assembler.source_map)}")
    except (HarwareMemException, AlignmentError, SegmentationFault) as err:
        print(f"\n[EXCEPCION DE MEMORIA en ciclo {cpu.cycle_count}] {err}", file=sys.stderr)
        return 1

    print("\n" + "=" * 70)
    print(f"Ciclos totales ejecutados : {cpu.cycle_count}")
    print(f"Instrucciones retiradas   : {cpu.instructions_retired}")
    print(f"Paradas Load-Use (stalls) : {cpu.load_use_stalls}")
    print(f"Vaciados por Branch       : {cpu.branch_flushes}")
    print(f"Vaciados por Jump         : {cpu.jump_flushes}")
    print(f"Detenido por Syscall      : {cpu.halted_by_syscall}")
    print(f"Estado final de registros : {cpu.regs.dump(cond=True)}")

    if "input" in symbols and "output" in symbols:
        print(f"Cadena input  (.data)     : \"{cpu.memory.read_asciiz(symbols['input'])}\"")
        print(f"Cadena output (.data)     : \"{cpu.memory.read_asciiz(symbols['output'])}\"")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
