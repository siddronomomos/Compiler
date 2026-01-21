from __future__ import annotations

import argparse
from pathlib import Path

from emu.emulator import Emulator, EmulatorConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="MASM 6.11 emulator (subset)")
    parser.add_argument("asm", type=Path, help="Path to .asm file")
    parser.add_argument("--dos-root", type=Path, default=Path("dos_root"), help="DOS root folder")
    args = parser.parse_args()

    asm_text = args.asm.read_text(encoding="utf-8")
    config = EmulatorConfig(dos_root=str(args.dos_root))
    emu = Emulator(config)
    emu.load_asm(asm_text)
    exit_code = emu.run()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
