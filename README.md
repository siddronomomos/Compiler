# MASM 6.11 Emulator (Python, subset)

This is a **software emulator** for a small MASM 6.11-compatible subset. It focuses on DOS interrupts for printing, file I/O, and text color. It does **not** assemble to machine code; it parses MASM-like syntax into an internal IR and interprets it.

## Current Features
- 16-bit CPU state with flags (CF, PF, AF, ZF, SF, OF, IF, DF)
- 1MB memory model
- `.data`, `.code`, and `.stack` sections
- `db`/`dw` data directives, `dup`, `org` in `.data`, and `equ` constants (including `$` expressions like `$ - label`)
- MASM-style labels and `offset` support
- String instructions with REP/REPE/REPNE semantics for `cmps`/`scas`
- UI: code editor, breakpoints, register grid, and popup memory/stack viewers

## Instruction Reference
### Data movement
- `mov`: copy register/memory/immediate to register or memory
- `lea`: load effective address (label offset) into a 16-bit register
- `xchg`: exchange two registers or register with memory
- `push`/`pop`: push/pop 16-bit value
- `pushf`/`popf`: push/pop FLAGS
- `pusha`/`popa`: push/pop all general registers
- `enter`/`leave`: stack frame setup/teardown (`enter` supports nesting level 0 only)
- `cbw`: sign-extend AL into AX
- `cwd`: sign-extend AX into DX:AX
- `xlat`: table lookup: AL = DS:[BX + AL]

### Arithmetic
- `add`/`adc`: add (with carry)
- `sub`/`sbb`: subtract (with borrow)
- `cmp`: compare (subtract, set flags only)
- `inc`/`dec`: increment/decrement
- `neg`: two’s complement negate
- `daa`/`das`: decimal adjust after add/sub
- `aaa`/`aas`: ASCII adjust after add/sub
- `aam`/`aad`: ASCII adjust after multiply/divide (base optional)
- `mul`/`imul`: unsigned/signed multiply
- `div`/`idiv`: unsigned/signed divide

### Logic and bit operations
- `and`/`or`/`xor`: bitwise logic
- `test`: logical AND that only updates flags
- `not`: bitwise complement
- `shl`/`sal`: shift left
- `shr`: logical shift right
- `sar`: arithmetic shift right
- `rol`/`ror`: rotate left/right

### Control flow
- `jmp`: unconditional jump
- `je`/`jz`: jump if ZF=1
- `jne`/`jnz`: jump if ZF=0
- `jc`: jump if CF=1
- `jnc`/`jae`: jump if CF=0
- `jg`: jump if greater (ZF=0 and SF=OF)
- `jl`: jump if less (SF≠OF)
- `jge`: jump if greater or equal (SF=OF)
- `jle`: jump if less or equal (ZF=1 or SF≠OF)
- `loop`: decrement CX and jump if not zero
- `loope`: loop while CX!=0 and ZF=1
- `loopne`: loop while CX!=0 and ZF=0
- `call`: call procedure (push return address)
- `ret`: return; if no return address, emulator halts

### Flags
- `clc`/`stc`/`cmc`: clear/set/complement CF
- `cli`/`sti`: clear/set IF
- `lahf`: load SF,ZF,AF,PF,CF into AH
- `sahf`: store AH into SF,ZF,AF,PF,CF

### String instructions
- `movsb`/`movsw`: move byte/word from DS:SI to ES:DI
- `stosb`/`stosw`: store AL/AX to ES:DI
- `lodsb`/`lodsw`: load from DS:SI into AL/AX
- `cmpsb`/`cmpsw`: compare DS:SI with ES:DI
- `scasb`/`scasw`: compare AL/AX with ES:DI
- `rep`/`repe`/`repne`: repeat string instruction; `repe/repne` only affect `cmps`/`scas` termination

### System
- `int`: software interrupt
- `int3`: breakpoint interrupt (halts emulator)
- `iret`: return from interrupt (pop IP, CS, FLAGS)
- `nop`: no operation
- `hlt`: halt execution

## Interrupts and Services
### DOS INT 21h
- `AH=01h`: read char with echo
- `AH=08h`: read char without echo
- `AH=0Ch`: clear input + read
- `AH=02h`: display character (`DL`)
- `AH=09h`: display `$`-terminated string (`DS:DX`)
- `AH=0Ah`: buffered input (`DS:DX`)
- `AH=1Ah`: set DTA
- `AH=19h`: get current drive
- `AH=3Ch`: create file (DOS 8.3)
- `AH=3Dh`: open file (read/write/rdwr)
- `AH=3Eh`: close file
- `AH=3Fh`: read file
- `AH=40h`: write file (handle 1 = stdout)
- `AH=41h`: delete file
- `AH=42h`: seek
- `AH=43h`: get/set file attributes (get only)
- `AH=47h`: get current directory
- `AH=4Eh`: find first (DTA)
- `AH=4Fh`: find next (DTA)
- `AH=57h`: get/set file date/time (get only)
- `AH=4Ch`: exit

### BIOS INT 10h (text mode)
- `AH=00h`: set video mode
- `AH=0Fh`: get video mode
- `AH=02h`: set cursor position
- `AH=03h`: get cursor position
- `AH=0Bh`: set background/border
- `AH=09h`: write char+attribute
- `AH=0Eh`: teletype output

### BIOS INT 16h (keyboard)
- `AH=00h`: read key (returns AL)
- `AH=01h`: check key (sets ZF if none)

### BIOS INT 1Ah (time)
- `AH=00h`: ticks since midnight in CX:DX
- `AH=02h`: current time in BCD (CH=HH, CL=MM, DH=SS)

### DOS INT 20h
- Terminate program (uses AL as exit code)

## DOS 8.3 Rules
- Filenames are validated strictly as 8.3 (per path segment).
- Invalid names set `CF=1` and `AX` to an error code.

## Assembler Parsing Notes
- `equ` constants are supported.
- `org` is supported in `.data`.
- `dup` is supported in `db`/`dw` (e.g., `db 10 dup(0)`).
- Binary literals are supported (e.g., `1011b`).
- Escaped characters in strings are supported (e.g., `\n`, `\r`, `\t`).

## Running the Examples
- `python src/main.py examples/hello.asm`
- `python src/main.py examples/bubble_sort.asm`

## Project Layout
- src/emu: emulator core
- examples: sample programs
