# MASM 6.11 Emulator (Python, subset)

This is a **software emulator** for a small MASM 6.11-compatible subset. It focuses on DOS interrupts for printing, file I/O, and text color. It does **not** assemble to machine code; it parses MASM-like syntax into an internal IR and interprets it.

## Current Features
- 16-bit CPU state (registers, flags)
- 1MB memory model
- `.data` and `.code` sections with labels
- `db` and `dw` data directives
- Instructions: `mov`, `lea`, `add`, `sub`, `cmp`, `inc`, `dec`, `jmp`, `je`/`jz`, `jne`/`jnz`, `call`, `ret`, `push`, `pop`, `int`, `nop`, `hlt`
- DOS `int 21h` services:
  - `AH=02h` display character (`DL`)
  - `AH=09h` display `$`-terminated string (`DS:DX`)
  - `AH=0Ah` buffered input (`DS:DX`)
  - `AH=3Ch` create file (DOS 8.3)
  - `AH=3Dh` open file (read/write/rdwr)
  - `AH=3Eh` close file
  - `AH=3Fh` read file
  - `AH=40h` write file (handle 1 = stdout)
  - `AH=41h` delete file
  - `AH=42h` seek
  - `AH=4Ch` exit
- BIOS `int 10h` services (text mode):
  - `AH=00h` set video mode
  - `AH=0Bh` set background/border
  - `AH=09h` write char+attribute

## DOS 8.3 Rules
- Filenames are validated strictly as 8.3 (per path segment).
- Invalid names set `CF=1` and `AX` to an error code.

## Running the Example
```
python src/main.py examples/hello.asm
```

## Project Layout
- src/emu: emulator core
- examples: sample programs
