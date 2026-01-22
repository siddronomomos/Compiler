# MASM 6.11 Emulator (Python, subset)

This is a **software emulator** for a small MASM 6.11-compatible subset. It focuses on DOS interrupts for printing, file I/O, and text color. It does **not** assemble to machine code; it parses MASM-like syntax into an internal IR and interprets it.

## Current Features
- 16-bit CPU state (registers, flags)
- 1MB memory model
- `.data` and `.code` sections with labels
- `db` and `dw` data directives
- Instructions: `mov`, `lea`, `add`, `sub`, `cmp`, `inc`, `dec`, `and`, `or`, `xor`, `not`, `neg`, `test`, `shl`/`sal`, `shr`, `sar`, `rol`, `ror`, `mul`, `imul`, `div`, `idiv`, `jmp`, `je`/`jz`, `jne`/`jnz`, `jc`, `jnc`, `jg`, `jl`, `jge`, `jle`, `loop`, `loope`, `loopne`, `call`, `ret`, `push`, `pop`, `pushf`, `popf`, `clc`, `stc`, `cmc`, `cli`, `sti`, `xchg`, `movsb`, `movsw`, `stosb`, `stosw`, `lodsb`, `lodsw`, `rep`, `repe`, `repne`, `int`, `nop`, `hlt`
- DOS `int 21h` services:
  - `AH=01h` read char with echo
  - `AH=08h` read char without echo
  - `AH=0Ch` clear input + read
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
  - `AH=43h` get/set file attributes (get only)
  - `AH=47h` get current directory
  - `AH=19h` get current drive
  - `AH=4Eh` find first (DTA)
  - `AH=4Fh` find next (DTA)
  - `AH=57h` get/set file date/time (get only)
  - `AH=1Ah` set DTA
  - `AH=4Ch` exit
- BIOS `int 10h` services (text mode):
  - `AH=00h` set video mode
  - `AH=0Fh` get video mode
  - `AH=02h` set cursor position
  - `AH=03h` get cursor position
  - `AH=0Bh` set background/border
  - `AH=09h` write char+attribute
  - `AH=0Eh` teletype output

## DOS 8.3 Rules
- Filenames are validated strictly as 8.3 (per path segment).
- Invalid names set `CF=1` and `AX` to an error code.

## Assembler Parsing Notes
- `equ` constants are supported.
- `org` is supported in `.data`.
- `dup` is supported in `db`/`dw` (e.g., `db 10 dup(0)`).
- Binary literals are supported (e.g., `1011b`).
- Escaped characters in strings are supported (e.g., `\n`, `\r`, `\t`).

## Running the Example
```
python src/main.py examples/hello.asm
```

## Project Layout
- src/emu: emulator core
- examples: sample programs
