from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .cpu import CPU, FLAG_CF, FLAG_PF, FLAG_AF, FLAG_ZF, FLAG_SF, FLAG_OF, FLAG_IF, FLAG_DF
from .memory import Memory
from .interrupts import DOSKernel


SUPPORTED_OPS: tuple[str, ...] = (
    "mov",
    "lea",
    "add",
    "adc",
    "sub",
    "sbb",
    "cmp",
    "inc",
    "dec",
    "and",
    "or",
    "xor",
    "not",
    "neg",
    "test",
    "shl",
    "sal",
    "shr",
    "sar",
    "rol",
    "ror",
    "mul",
    "imul",
    "div",
    "idiv",
    "jmp",
    "je",
    "jz",
    "jne",
    "jnz",
    "jc",
    "jnc",
    "jae",
    "jg",
    "jl",
    "jge",
    "jle",
    "loop",
    "loope",
    "loopne",
    "call",
    "ret",
    "push",
    "pop",
    "pushf",
    "popf",
    "clc",
    "stc",
    "cmc",
    "cli",
    "sti",
    "xchg",
    "movsb",
    "movsw",
    "stosb",
    "stosw",
    "lodsb",
    "lodsw",
    "cmpsb",
    "cmpsw",
    "scasb",
    "scasw",
    "rep",
    "repe",
    "repne",
    "int",
    "nop",
    "hlt",
    "daa",
    "das",
    "aaa",
    "aas",
    "aam",
    "aad",
    "lahf",
    "sahf",
    "cbw",
    "cwd",
    "xlat",
    "enter",
    "leave",
    "int3",
    "iret",
    "pusha",
    "popa",
)


def validate_opcode(op: str, line: int | None = None) -> None:
    if op not in SUPPORTED_OPS:
        detail = f" at line {line}" if line is not None else ""
        raise NotImplementedError(f"Unsupported op: {op}{detail}")


class InstructionExecutor:
    def __init__(self, cpu: CPU, memory: Memory, kernel: DOSKernel) -> None:
        self.cpu = cpu
        self.memory = memory
        self.kernel = kernel
        self.program: Any | None = None
        self._dispatch = self._build_dispatch()

    def set_program(self, program: Any | None) -> None:
        self.program = program

    def execute(self, instr: Instruction) -> None:
        op = instr.op
        args = instr.args
        validate_opcode(op, instr.line)
        self._validate_operands(op, args, instr)
        handler = self._dispatch.get(op)
        if handler is None:
            raise NotImplementedError(f"Unsupported op: {op} at line {instr.line}")
        handler(op, args, instr)
        self.cpu.ip += 1

    def _validate_operands(self, op: str, args: list[str], instr: Instruction) -> None:
        zero_ops = {
            "ret",
            "pushf",
            "popf",
            "clc",
            "stc",
            "cmc",
            "cli",
            "sti",
            "nop",
            "hlt",
            "movsb",
            "movsw",
            "stosb",
            "stosw",
            "lodsb",
            "lodsw",
            "cmpsb",
            "cmpsw",
            "scasb",
            "scasw",
            "daa",
            "das",
            "aaa",
            "aas",
            "lahf",
            "sahf",
            "cbw",
            "cwd",
            "xlat",
            "leave",
            "int3",
            "iret",
            "pusha",
            "popa",
        }
        one_ops = {
            "inc",
            "dec",
            "jmp",
            "je",
            "jz",
            "jne",
            "jnz",
            "jc",
            "jnc",
            "jae",
            "jg",
            "jl",
            "jge",
            "jle",
            "loop",
            "loope",
            "loopne",
            "call",
            "push",
            "pop",
            "int",
            "mul",
            "imul",
            "div",
            "idiv",
            "not",
            "neg",
            "rep",
            "repe",
            "repne",
        }
        two_ops = {
            "mov",
            "lea",
            "add",
            "adc",
            "sub",
            "sbb",
            "cmp",
            "and",
            "or",
            "xor",
            "test",
            "shl",
            "sal",
            "shr",
            "sar",
            "rol",
            "ror",
            "xchg",
        }
        if op in zero_ops and args:
            raise ValueError(f"{op} expects no operands at line {instr.line}")
        if op in one_ops and len(args) != 1:
            raise ValueError(f"{op} expects 1 operand at line {instr.line}")
        if op in two_ops and len(args) != 2:
            raise ValueError(f"{op} expects 2 operands at line {instr.line}")
        if op in {"aam", "aad"} and len(args) > 1:
            raise ValueError(f"{op} expects 0 or 1 operand at line {instr.line}")
        if op in {"aam", "aad"} and len(args) == 1:
            try:
                value = self._parse_number(args[0], label_ok=True)
            except Exception as exc:
                raise ValueError(f"{op} expects an immediate byte at line {instr.line}") from exc
            if value & 0xFF != value:
                raise ValueError(f"{op} expects an immediate byte at line {instr.line}")
        if op == "enter":
            if len(args) not in {1, 2}:
                raise ValueError(f"enter expects 1 or 2 operands at line {instr.line}")
            size = self._parse_number(args[0], label_ok=True)
            if size & 0xFFFF != size:
                raise ValueError(f"enter expects a 16-bit size at line {instr.line}")
            if len(args) == 2:
                level = self._parse_number(args[1], label_ok=True)
                if level & 0xFF != level:
                    raise ValueError(f"enter expects an 8-bit nesting level at line {instr.line}")
        if op in {"rep", "repe", "repne"}:
            target = args[0].lower()
            valid_targets = {"movsb", "movsw", "stosb", "stosw", "lodsb", "lodsw", "cmpsb", "cmpsw", "scasb", "scasw"}
            if target not in valid_targets:
                raise ValueError(f"{op} expects a string instruction at line {instr.line}")

    def _build_dispatch(self) -> dict[str, Callable[[str, list[str], Instruction], None]]:
        return {
            "mov": lambda _op, args, instr: self._exec_mov(args, instr),
            "lea": lambda _op, args, instr: self._exec_lea(args, instr),
            "add": lambda _op, args, instr: self._exec_add(args, instr),
            "adc": lambda _op, args, instr: self._exec_adc(args, instr),
            "sub": lambda _op, args, instr: self._exec_sub(args, instr),
            "sbb": lambda _op, args, instr: self._exec_sbb(args, instr),
            "cmp": lambda _op, args, instr: self._exec_cmp(args, instr),
            "and": lambda _op, args, instr: self._exec_and(args, instr),
            "or": lambda _op, args, instr: self._exec_or(args, instr),
            "xor": lambda _op, args, instr: self._exec_xor(args, instr),
            "not": lambda _op, args, instr: self._exec_not(args, instr),
            "neg": lambda _op, args, instr: self._exec_neg(args, instr),
            "test": lambda _op, args, instr: self._exec_test(args, instr),
            "shl": lambda _op, args, instr: self._exec_shift(args, instr, kind="shl"),
            "sal": lambda _op, args, instr: self._exec_shift(args, instr, kind="shl"),
            "shr": lambda _op, args, instr: self._exec_shift(args, instr, kind="shr"),
            "sar": lambda _op, args, instr: self._exec_shift(args, instr, kind="sar"),
            "rol": lambda _op, args, instr: self._exec_rotate(args, instr, kind="rol"),
            "ror": lambda _op, args, instr: self._exec_rotate(args, instr, kind="ror"),
            "mul": lambda _op, args, instr: self._exec_mul(args, instr, signed=False),
            "imul": lambda _op, args, instr: self._exec_mul(args, instr, signed=True),
            "div": lambda _op, args, instr: self._exec_div(args, instr, signed=False),
            "idiv": lambda _op, args, instr: self._exec_div(args, instr, signed=True),
            "inc": lambda _op, args, instr: self._exec_inc(args, instr),
            "dec": lambda _op, args, instr: self._exec_dec(args, instr),
            "jmp": lambda _op, args, instr: self._exec_jmp(args, instr),
            "je": lambda _op, args, instr: self._exec_je(args, instr),
            "jz": lambda _op, args, instr: self._exec_je(args, instr),
            "jne": lambda _op, args, instr: self._exec_jne(args, instr),
            "jnz": lambda _op, args, instr: self._exec_jne(args, instr),
            "jc": lambda _op, args, instr: self._exec_jc(args, instr),
            "jnc": lambda _op, args, instr: self._exec_jnc(args, instr),
            "jae": lambda _op, args, instr: self._exec_jnc(args, instr),
            "jg": lambda _op, args, instr: self._exec_jg(args, instr),
            "jl": lambda _op, args, instr: self._exec_jl(args, instr),
            "jge": lambda _op, args, instr: self._exec_jge(args, instr),
            "jle": lambda _op, args, instr: self._exec_jle(args, instr),
            "loop": lambda _op, args, instr: self._exec_loop(args, instr, kind="loop"),
            "loope": lambda _op, args, instr: self._exec_loop(args, instr, kind="loope"),
            "loopne": lambda _op, args, instr: self._exec_loop(args, instr, kind="loopne"),
            "call": lambda _op, args, instr: self._exec_call(args, instr),
            "ret": lambda _op, args, instr: self._exec_ret(args, instr),
            "push": lambda _op, args, instr: self._exec_push(args, instr),
            "pop": lambda _op, args, instr: self._exec_pop(args, instr),
            "pushf": lambda _op, args, instr: self._exec_pushf(args, instr),
            "popf": lambda _op, args, instr: self._exec_popf(args, instr),
            "clc": lambda _op, _args, _instr: self.cpu.set_flag(FLAG_CF, False),
            "stc": lambda _op, _args, _instr: self.cpu.set_flag(FLAG_CF, True),
            "cmc": lambda _op, _args, _instr: self.cpu.set_flag(FLAG_CF, not self.cpu.get_flag(FLAG_CF)),
            "cli": lambda _op, _args, _instr: self.cpu.set_flag(FLAG_IF, False),
            "sti": lambda _op, _args, _instr: self.cpu.set_flag(FLAG_IF, True),
            "xchg": lambda _op, args, instr: self._exec_xchg(args, instr),
            "movsb": lambda _op, _args, _instr: self._exec_movs(size=8),
            "movsw": lambda _op, _args, _instr: self._exec_movs(size=16),
            "stosb": lambda _op, _args, _instr: self._exec_stos(size=8),
            "stosw": lambda _op, _args, _instr: self._exec_stos(size=16),
            "lodsb": lambda _op, _args, _instr: self._exec_lods(size=8),
            "lodsw": lambda _op, _args, _instr: self._exec_lods(size=16),
            "cmpsb": lambda _op, _args, _instr: self._exec_cmps(size=8),
            "cmpsw": lambda _op, _args, _instr: self._exec_cmps(size=16),
            "scasb": lambda _op, _args, _instr: self._exec_scas(size=8),
            "scasw": lambda _op, _args, _instr: self._exec_scas(size=16),
            "rep": lambda op, args, instr: self._exec_rep(op, args, instr),
            "repe": lambda op, args, instr: self._exec_rep(op, args, instr),
            "repne": lambda op, args, instr: self._exec_rep(op, args, instr),
            "int": lambda _op, args, instr: self._exec_int(args, instr),
            "nop": lambda _op, _args, _instr: None,
            "hlt": lambda _op, _args, _instr: setattr(self.cpu, "halted", True),
            "daa": lambda _op, _args, instr: self._exec_daa(instr),
            "das": lambda _op, _args, instr: self._exec_das(instr),
            "aaa": lambda _op, _args, instr: self._exec_aaa(instr),
            "aas": lambda _op, _args, instr: self._exec_aas(instr),
            "aam": lambda _op, args, instr: self._exec_aam(args, instr),
            "aad": lambda _op, args, instr: self._exec_aad(args, instr),
            "lahf": lambda _op, _args, instr: self._exec_lahf(instr),
            "sahf": lambda _op, _args, instr: self._exec_sahf(instr),
            "cbw": lambda _op, _args, instr: self._exec_cbw(instr),
            "cwd": lambda _op, _args, instr: self._exec_cwd(instr),
            "xlat": lambda _op, _args, instr: self._exec_xlat(instr),
            "enter": lambda _op, args, instr: self._exec_enter(args, instr),
            "leave": lambda _op, _args, instr: self._exec_leave(instr),
            "int3": lambda _op, _args, instr: self._exec_int3(instr),
            "iret": lambda _op, _args, instr: self._exec_iret(instr),
            "pusha": lambda _op, _args, instr: self._exec_pusha(instr),
            "popa": lambda _op, _args, instr: self._exec_popa(instr),
        }

    def _exec_mov(self, args, instr) -> None:
        if len(args) != 2:
            raise ValueError(f"mov expects 2 operands at line {instr.line}")
        dest = args[0].lower()
        src = args[1].lower()

        if dest in self._reg8_names():
            value = self._resolve_operand(src, size=8)
            self.cpu.set_reg8(dest, value)
            return
        if dest in self._reg16_names():
            value = self._resolve_operand(src, size=16)
            self.cpu.set_reg16(dest, value)
            return
        if self._is_memory(dest):
            size = self._resolve_mem_size(dest) or self._resolve_size_hint(src)
            if size is None:
                raise NotImplementedError(f"mov to memory requires size at line {instr.line}")
            value = self._resolve_operand(src, size=size)
            self._write_memory(dest, size, value)
            return
        raise NotImplementedError(f"Unsupported mov dest: {dest} at line {instr.line}")

    def _exec_lea(self, args, instr) -> None:
        if len(args) != 2:
            raise ValueError(f"lea expects 2 operands at line {instr.line}")
        dest = args[0].lower()
        label = args[1].lower()
        if dest not in self._reg16_names():
            raise NotImplementedError(f"lea dest must be 16-bit register at line {instr.line}")
        offset = self._resolve_label(label)
        self.cpu.set_reg16(dest, offset)

    def _exec_add(self, args, instr) -> None:
        if len(args) != 2:
            raise ValueError(f"add expects 2 operands at line {instr.line}")
        dest = args[0].lower()
        src = args[1].lower()
        if dest in self._reg8_names():
            self._arith_reg(dest, src, 8, op="add")
            return
        if dest in self._reg16_names():
            self._arith_reg(dest, src, 16, op="add")
            return
        if self._is_memory(dest):
            self._arith_mem(dest, src, op="add")
            return
        raise NotImplementedError(f"Unsupported add dest: {dest} at line {instr.line}")

    def _exec_adc(self, args, instr) -> None:
        if len(args) != 2:
            raise ValueError(f"adc expects 2 operands at line {instr.line}")
        dest = args[0].lower()
        src = args[1].lower()
        carry = 1 if self.cpu.get_flag(FLAG_CF) else 0
        if dest in self._reg8_names():
            left = self.cpu.get_reg8(dest)
            right = self._resolve_operand(src, size=8)
            right_carry = (right + carry) & 0xFF
            result = left + right_carry
            self._update_add_flags(left, right_carry, result, 8)
            self._update_zf(result, 8)
            self._update_sf(result, 8)
            self.cpu.set_reg8(dest, result & 0xFF)
            return
        if dest in self._reg16_names():
            left = self.cpu.get_reg16(dest)
            right = self._resolve_operand(src, size=16)
            right_carry = (right + carry) & 0xFFFF
            result = left + right_carry
            self._update_add_flags(left, right_carry, result, 16)
            self._update_zf(result, 16)
            self._update_sf(result, 16)
            self.cpu.set_reg16(dest, result & 0xFFFF)
            return
        if self._is_memory(dest):
            size = self._resolve_mem_size(dest) or self._resolve_size_hint(src)
            if size is None:
                raise NotImplementedError("memory adc requires size")
            left = self._read_memory(dest, size)
            right = self._resolve_operand(src, size=size)
            right_carry = (right + carry) & self._mask(size)
            result = left + right_carry
            self._update_add_flags(left, right_carry, result, size)
            self._update_zf(result, size)
            self._update_sf(result, size)
            self._write_memory(dest, size, result)
            return
        raise NotImplementedError(f"Unsupported adc dest: {dest} at line {instr.line}")

    def _exec_sub(self, args, instr) -> None:
        if len(args) != 2:
            raise ValueError(f"sub expects 2 operands at line {instr.line}")
        dest = args[0].lower()
        src = args[1].lower()
        if dest in self._reg8_names():
            self._arith_reg(dest, src, 8, op="sub")
            return
        if dest in self._reg16_names():
            self._arith_reg(dest, src, 16, op="sub")
            return
        if self._is_memory(dest):
            self._arith_mem(dest, src, op="sub")
            return
        raise NotImplementedError(f"Unsupported sub dest: {dest} at line {instr.line}")

    def _exec_sbb(self, args, instr) -> None:
        if len(args) != 2:
            raise ValueError(f"sbb expects 2 operands at line {instr.line}")
        dest = args[0].lower()
        src = args[1].lower()
        borrow = 1 if self.cpu.get_flag(FLAG_CF) else 0
        if dest in self._reg8_names():
            left = self.cpu.get_reg8(dest)
            right = self._resolve_operand(src, size=8)
            right_borrow = (right + borrow) & 0xFF
            result = left - right_borrow
            self._update_sub_flags(left, right_borrow, result, 8)
            self._update_zf(result, 8)
            self._update_sf(result, 8)
            self.cpu.set_reg8(dest, result & 0xFF)
            return
        if dest in self._reg16_names():
            left = self.cpu.get_reg16(dest)
            right = self._resolve_operand(src, size=16)
            right_borrow = (right + borrow) & 0xFFFF
            result = left - right_borrow
            self._update_sub_flags(left, right_borrow, result, 16)
            self._update_zf(result, 16)
            self._update_sf(result, 16)
            self.cpu.set_reg16(dest, result & 0xFFFF)
            return
        if self._is_memory(dest):
            size = self._resolve_mem_size(dest) or self._resolve_size_hint(src)
            if size is None:
                raise NotImplementedError("memory sbb requires size")
            left = self._read_memory(dest, size)
            right = self._resolve_operand(src, size=size)
            right_borrow = (right + borrow) & self._mask(size)
            result = left - right_borrow
            self._update_sub_flags(left, right_borrow, result, size)
            self._update_zf(result, size)
            self._update_sf(result, size)
            self._write_memory(dest, size, result)
            return
        raise NotImplementedError(f"Unsupported sbb dest: {dest} at line {instr.line}")

    def _exec_cmp(self, args, instr) -> None:
        if len(args) != 2:
            raise ValueError(f"cmp expects 2 operands at line {instr.line}")
        dest = args[0].lower()
        src = args[1].lower()
        if dest in self._reg8_names():
            self._cmp_reg(dest, src, 8)
            return
        if dest in self._reg16_names():
            self._cmp_reg(dest, src, 16)
            return
        if self._is_memory(dest):
            self._cmp_mem(dest, src)
            return
        raise NotImplementedError(f"Unsupported cmp dest: {dest} at line {instr.line}")

    def _exec_inc(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"inc expects 1 operand at line {instr.line}")
        dest = args[0].lower()
        if dest in self._reg8_names():
            self._inc_reg(dest, 8)
            return
        if dest in self._reg16_names():
            self._inc_reg(dest, 16)
            return
        if self._is_memory(dest):
            self._inc_mem(dest)
            return
        raise NotImplementedError(f"Unsupported inc dest: {dest} at line {instr.line}")

    def _exec_dec(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"dec expects 1 operand at line {instr.line}")
        dest = args[0].lower()
        if dest in self._reg8_names():
            self._dec_reg(dest, 8)
            return
        if dest in self._reg16_names():
            self._dec_reg(dest, 16)
            return
        if self._is_memory(dest):
            self._dec_mem(dest)
            return
        raise NotImplementedError(f"Unsupported dec dest: {dest} at line {instr.line}")

    def _exec_jmp(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"jmp expects 1 operand at line {instr.line}")
        target = self._resolve_jump_target(args[0])
        self._jump_to(target)

    def _exec_je(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"je expects 1 operand at line {instr.line}")
        if self.cpu.get_flag(FLAG_ZF):
            target = self._resolve_jump_target(args[0])
            self._jump_to(target)

    def _exec_jne(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"jne expects 1 operand at line {instr.line}")
        if not self.cpu.get_flag(FLAG_ZF):
            target = self._resolve_jump_target(args[0])
            self._jump_to(target)

    def _exec_call(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"call expects 1 operand at line {instr.line}")
        target = self._resolve_jump_target(args[0])
        self._push16(self.cpu.ip + 1)
        self._jump_to(target)

    def _exec_ret(self, args, instr) -> None:
        if args:
            raise ValueError(f"ret expects no operands at line {instr.line}")
        if self.cpu.sp == 0xFFFE:
            self.cpu.halted = True
            return
        addr = self._pop16()
        self._jump_to(addr)

    def _exec_push(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"push expects 1 operand at line {instr.line}")
        value = self._resolve_operand(args[0].lower(), size=16)
        self._push16(value)

    def _exec_pop(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"pop expects 1 operand at line {instr.line}")
        dest = args[0].lower()
        value = self._pop16()
        if dest in self._reg16_names():
            self.cpu.set_reg16(dest, value)
            return
        if self._is_memory(dest):
            self._write_memory(dest, 16, value)
            return
        raise NotImplementedError(f"Unsupported pop dest: {dest} at line {instr.line}")

    def _exec_int(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"int expects 1 operand at line {instr.line}")
        vector = self._parse_number(args[0])
        self._handle_interrupt(vector, instr)

    def _handle_interrupt(self, vector: int, instr) -> None:
        if vector == 0x21:
            self.kernel.int_21h()
            return
        if vector == 0x10:
            self.kernel.int_10h()
            return
        if vector == 0x20:
            self.kernel.int_20h()
            return
        if vector == 0x16:
            self.kernel.int_16h()
            return
        if vector == 0x1A:
            self.kernel.int_1Ah()
            return
        if vector == 0x03:
            self.cpu.halted = True
            return
        raise NotImplementedError(f"Unsupported interrupt: {vector:#x} at line {instr.line}")

    def _resolve_operand(self, token: str, size: int) -> int:
        token = token.strip().lower()
        if token in self._reg8_names():
            return self.cpu.get_reg8(token)
        if token in self._reg16_names():
            return self.cpu.get_reg16(token)
        if token.startswith("offset "):
            label = token.split(None, 1)[1]
            return self._resolve_label(label)
        if self._is_memory(token):
            return self._read_memory(token, size)
        return self._parse_number(token, label_ok=True)

    def _resolve_label(self, label: str) -> int:
        if self.program is None:
            raise RuntimeError("No program loaded")
        label = label.lower()
        if label in self.program.data_labels:
            return self.program.data_labels[label]
        if label in self.program.labels:
            return self.program.labels[label]
        raise KeyError(f"Unknown label: {label}")

    def _parse_number(self, token: str, label_ok: bool = False) -> int:
        token = token.strip().lower()
        if label_ok and self.program is not None and token in self.program.data_labels:
            return self.program.data_labels[token]
        if label_ok and self.program is not None and token in self.program.constants:
            return self.program.constants[token]
        if token.endswith("b") and len(token) > 1:
            return int(token[:-1], 2)
        if token.endswith("h"):
            return int(token[:-1], 16)
        if token.startswith("0x"):
            return int(token, 16)
        if token.startswith("'") and token.endswith("'") and len(token) == 3:
            return self._decode_char_literal(token)
        return int(token, 10)

    def _reg8_names(self) -> set[str]:
        return {"ah", "al", "bh", "bl", "ch", "cl", "dh", "dl"}

    def _reg16_names(self) -> set[str]:
        return {"ax", "bx", "cx", "dx", "sp", "bp", "si", "di", "cs", "ds", "es", "ss"}

    def _arith_reg(self, dest: str, src: str, size: int, op: str) -> None:
        if size == 8:
            left = self.cpu.get_reg8(dest)
        else:
            left = self.cpu.get_reg16(dest)
        right = self._resolve_operand(src, size=size)
        if op == "add":
            result = left + right
            self._update_add_flags(left, right, result, size)
        else:
            result = left - right
            self._update_sub_flags(left, right, result, size)
        self._update_zf(result, size)
        self._update_sf(result, size)
        value = result & self._mask(size)
        if size == 8:
            self.cpu.set_reg8(dest, value)
        else:
            self.cpu.set_reg16(dest, value)

    def _arith_mem(self, dest: str, src: str, op: str) -> None:
        size = self._resolve_mem_size(dest) or self._resolve_size_hint(src)
        if size is None:
            raise NotImplementedError("memory arithmetic requires size")
        left = self._read_memory(dest, size)
        right = self._resolve_operand(src, size=size)
        if op == "add":
            result = left + right
            self._update_add_flags(left, right, result, size)
        else:
            result = left - right
            self._update_sub_flags(left, right, result, size)
        self._update_zf(result, size)
        self._update_sf(result, size)
        self._write_memory(dest, size, result)

    def _cmp_reg(self, dest: str, src: str, size: int) -> None:
        if size == 8:
            left = self.cpu.get_reg8(dest)
        else:
            left = self.cpu.get_reg16(dest)
        right = self._resolve_operand(src, size=size)
        result = left - right
        self._update_sub_flags(left, right, result, size)
        self._update_zf(result, size)
        self._update_sf(result, size)

    def _cmp_mem(self, dest: str, src: str) -> None:
        size = self._resolve_mem_size(dest) or self._resolve_size_hint(src)
        if size is None:
            raise NotImplementedError("memory cmp requires size")
        left = self._read_memory(dest, size)
        right = self._resolve_operand(src, size=size)
        result = left - right
        self._update_sub_flags(left, right, result, size)
        self._update_zf(result, size)
        self._update_sf(result, size)

    def _inc_reg(self, dest: str, size: int) -> None:
        if size == 8:
            old = self.cpu.get_reg8(dest)
            value = (old + 1) & 0xFF
            self.cpu.set_reg8(dest, value)
        else:
            old = self.cpu.get_reg16(dest)
            value = (old + 1) & 0xFFFF
            self.cpu.set_reg16(dest, value)
        self.cpu.set_flag(FLAG_AF, ((old & 0x0F) + 1) > 0x0F)
        self._update_zf(value, size)
        self._update_sf(value, size)
        self._update_pf(value)

    def _dec_reg(self, dest: str, size: int) -> None:
        if size == 8:
            old = self.cpu.get_reg8(dest)
            value = (old - 1) & 0xFF
            self.cpu.set_reg8(dest, value)
        else:
            old = self.cpu.get_reg16(dest)
            value = (old - 1) & 0xFFFF
            self.cpu.set_reg16(dest, value)
        self.cpu.set_flag(FLAG_AF, (old & 0x0F) == 0x00)
        self._update_zf(value, size)
        self._update_sf(value, size)
        self._update_pf(value)

    def _inc_mem(self, dest: str) -> None:
        size = self._resolve_mem_size(dest)
        if size is None:
            raise NotImplementedError("memory inc requires size")
        old = self._read_memory(dest, size)
        value = (old + 1) & self._mask(size)
        self._write_memory(dest, size, value)
        self.cpu.set_flag(FLAG_AF, ((old & 0x0F) + 1) > 0x0F)
        self._update_zf(value, size)
        self._update_sf(value, size)
        self._update_pf(value)

    def _dec_mem(self, dest: str) -> None:
        size = self._resolve_mem_size(dest)
        if size is None:
            raise NotImplementedError("memory dec requires size")
        old = self._read_memory(dest, size)
        value = (old - 1) & self._mask(size)
        self._write_memory(dest, size, value)
        self.cpu.set_flag(FLAG_AF, (old & 0x0F) == 0x00)
        self._update_zf(value, size)
        self._update_sf(value, size)
        self._update_pf(value)

    def _push16(self, value: int) -> None:
        self.cpu.sp = (self.cpu.sp - 2) & 0xFFFF
        addr = self.memory.phys(self.cpu.ss, self.cpu.sp)
        self.memory.write16(addr, value & 0xFFFF)

    def _pop16(self) -> int:
        addr = self.memory.phys(self.cpu.ss, self.cpu.sp)
        value = self.memory.read16(addr)
        self.cpu.sp = (self.cpu.sp + 2) & 0xFFFF
        return value

    def _resolve_jump_target(self, token: str) -> int:
        token = token.strip().lower()
        if self.program is not None and token in self.program.labels:
            return self.program.labels[token]
        return self._parse_number(token, label_ok=True)

    def _jump_to(self, index: int) -> None:
        self.cpu.ip = index - 1

    def _mask(self, size: int) -> int:
        return 0xFF if size == 8 else 0xFFFF

    def _update_zf(self, result: int, size: int) -> None:
        self.cpu.set_flag(FLAG_ZF, (result & self._mask(size)) == 0)

    def _update_sf(self, result: int, size: int) -> None:
        mask = 0x80 if size == 8 else 0x8000
        self.cpu.set_flag(FLAG_SF, (result & mask) != 0)

    def _update_pf(self, result: int) -> None:
        low = result & 0xFF
        self.cpu.set_flag(FLAG_PF, (low.bit_count() % 2) == 0)

    def _update_add_flags(self, left: int, right: int, result: int, size: int) -> None:
        mask = self._mask(size)
        self.cpu.set_flag(FLAG_CF, result > mask)
        sign_bit = 0x80 if size == 8 else 0x8000
        self.cpu.set_flag(FLAG_AF, ((left ^ right ^ result) & 0x10) != 0)
        self.cpu.set_flag(
            FLAG_OF,
            (~(left ^ right) & (left ^ result) & sign_bit) != 0,
        )
        self._update_pf(result)

    def _update_sub_flags(self, left: int, right: int, result: int, size: int) -> None:
        self.cpu.set_flag(FLAG_CF, left < right)
        sign_bit = 0x80 if size == 8 else 0x8000
        self.cpu.set_flag(FLAG_AF, ((left ^ right ^ result) & 0x10) != 0)
        self.cpu.set_flag(
            FLAG_OF,
            ((left ^ right) & (left ^ result) & sign_bit) != 0,
        )
        self._update_pf(result)

    def _resolve_size_hint(self, token: str) -> int | None:
        token = token.strip().lower()
        if token in self._reg8_names():
            return 8
        if token in self._reg16_names():
            return 16
        if token.startswith("byte "):
            return 8
        if token.startswith("word "):
            return 16
        return None

    def _is_memory(self, token: str) -> bool:
        return "[" in token and "]" in token

    def _resolve_mem_size(self, token: str) -> int | None:
        token = token.strip().lower()
        if token.startswith("byte ptr ") or token.startswith("byte "):
            return 8
        if token.startswith("word ptr ") or token.startswith("word "):
            return 16
        return None

    def _strip_size_prefix(self, token: str) -> str:
        token = token.strip().lower()
        for prefix in ("byte ptr ", "word ptr ", "byte ", "word "):
            if token.startswith(prefix):
                return token[len(prefix) :].strip()
        return token

    def _read_memory(self, token: str, size: int) -> int:
        seg, offset = self._resolve_memory_address(token)
        addr = self.memory.phys(seg, offset)
        return self.memory.read8(addr) if size == 8 else self.memory.read16(addr)

    def _write_memory(self, token: str, size: int, value: int) -> None:
        seg, offset = self._resolve_memory_address(token)
        addr = self.memory.phys(seg, offset)
        if size == 8:
            self.memory.write8(addr, value)
        else:
            self.memory.write16(addr, value)

    def _resolve_memory_address(self, token: str) -> tuple[int, int]:
        token = self._strip_size_prefix(token)
        seg_override = None
        if ":" in token:
            prefix, rest = token.split(":", 1)
            prefix = prefix.strip().lower()
            if prefix in {"cs", "ds", "es", "ss"}:
                seg_override = prefix
                token = rest.strip()
        start = token.find("[")
        end = token.rfind("]")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"Invalid memory operand: {token}")
        expr = token[start + 1 : end].strip().lower()
        if not expr:
            raise ValueError(f"Empty memory operand: {token}")
        use_ss = False
        offset = 0
        expr = expr.replace("-", "+-")
        for term in expr.split("+"):
            term = term.strip()
            if not term:
                continue
            sign = 1
            if term.startswith("-"):
                sign = -1
                term = term[1:].strip()
            if term in self._reg16_names():
                if term == "bp":
                    use_ss = True
                value = self.cpu.get_reg16(term)
            elif term in self._reg8_names():
                value = self.cpu.get_reg8(term)
            elif self.program is not None and term in self.program.data_labels:
                value = self.program.data_labels[term]
            elif self.program is not None and term in self.program.constants:
                value = self.program.constants[term]
            else:
                value = self._parse_number(term, label_ok=True)
            offset = (offset + sign * value) & 0xFFFF
        if seg_override is not None:
            segment = self.cpu.get_reg16(seg_override)
        else:
            segment = self.cpu.ss if use_ss else self.cpu.ds
        return segment, offset

    def _decode_char_literal(self, token: str) -> int:
        if len(token) < 3:
            raise ValueError(f"Invalid char literal: {token}")
        inner = token[1:-1]
        if inner.startswith("\\") and len(inner) >= 2:
            mapping = {
                "n": "\n",
                "r": "\r",
                "t": "\t",
                "0": "\0",
                "'": "'",
                "\\": "\\",
            }
            return ord(mapping.get(inner[1], inner[1]))
        return ord(inner[0])

    def _exec_rep(self, op: str, args, instr) -> None:
        if not args:
            raise ValueError(f"{op} expects an instruction at line {instr.line}")
        target = args[0].lower()
        mode = "rep" if op == "rep" else op
        if target == "movsb":
            self._exec_movs(size=8, rep=True)
            return
        if target == "movsw":
            self._exec_movs(size=16, rep=True)
            return
        if target == "stosb":
            self._exec_stos(size=8, rep=True)
            return
        if target == "stosw":
            self._exec_stos(size=16, rep=True)
            return
        if target == "lodsb":
            self._exec_lods(size=8, rep=True)
            return
        if target == "lodsw":
            self._exec_lods(size=16, rep=True)
            return
        if target == "cmpsb":
            self._exec_rep_cmps(size=8, mode=mode)
            return
        if target == "cmpsw":
            self._exec_rep_cmps(size=16, mode=mode)
            return
        if target == "scasb":
            self._exec_rep_scas(size=8, mode=mode)
            return
        if target == "scasw":
            self._exec_rep_scas(size=16, mode=mode)
            return
        raise NotImplementedError(f"Unsupported rep target: {target} at line {instr.line}")

    def _exec_and(self, args, instr) -> None:
        self._exec_logic(args, instr, op="and")

    def _exec_or(self, args, instr) -> None:
        self._exec_logic(args, instr, op="or")

    def _exec_xor(self, args, instr) -> None:
        self._exec_logic(args, instr, op="xor")

    def _exec_logic(self, args, instr, op: str) -> None:
        if len(args) != 2:
            raise ValueError(f"{op} expects 2 operands at line {instr.line}")
        dest = args[0].lower()
        src = args[1].lower()
        if dest in self._reg8_names():
            result = self._logic_compute(self.cpu.get_reg8(dest), self._resolve_operand(src, 8), op, 8)
            self.cpu.set_reg8(dest, result)
            return
        if dest in self._reg16_names():
            result = self._logic_compute(self.cpu.get_reg16(dest), self._resolve_operand(src, 16), op, 16)
            self.cpu.set_reg16(dest, result)
            return
        if self._is_memory(dest):
            size = self._resolve_mem_size(dest) or self._resolve_size_hint(src)
            if size is None:
                raise NotImplementedError("memory logic requires size")
            left = self._read_memory(dest, size)
            result = self._logic_compute(left, self._resolve_operand(src, size), op, size)
            self._write_memory(dest, size, result)
            return
        raise NotImplementedError(f"Unsupported {op} dest: {dest} at line {instr.line}")

    def _logic_compute(self, left: int, right: int, op: str, size: int) -> int:
        if op == "and":
            result = left & right
        elif op == "or":
            result = left | right
        else:
            result = left ^ right
        self.cpu.set_flag(FLAG_CF, False)
        self.cpu.set_flag(FLAG_AF, False)
        self.cpu.set_flag(FLAG_OF, False)
        self._update_zf(result, size)
        self._update_sf(result, size)
        self._update_pf(result)
        return result & self._mask(size)

    def _exec_not(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"not expects 1 operand at line {instr.line}")
        dest = args[0].lower()
        if dest in self._reg8_names():
            self.cpu.set_reg8(dest, (~self.cpu.get_reg8(dest)) & 0xFF)
            return
        if dest in self._reg16_names():
            self.cpu.set_reg16(dest, (~self.cpu.get_reg16(dest)) & 0xFFFF)
            return
        if self._is_memory(dest):
            size = self._resolve_mem_size(dest)
            if size is None:
                raise NotImplementedError("memory not requires size")
            value = self._read_memory(dest, size)
            self._write_memory(dest, size, (~value) & self._mask(size))
            return
        raise NotImplementedError(f"Unsupported not dest: {dest} at line {instr.line}")

    def _exec_neg(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"neg expects 1 operand at line {instr.line}")
        dest = args[0].lower()
        if dest in self._reg8_names():
            value = self.cpu.get_reg8(dest)
            result = (-value) & 0xFF
            self.cpu.set_reg8(dest, result)
            self.cpu.set_flag(FLAG_CF, value != 0)
            self.cpu.set_flag(FLAG_AF, (value & 0x0F) != 0)
            self.cpu.set_flag(FLAG_OF, value == 0x80)
            self._update_zf(result, 8)
            self._update_sf(result, 8)
            self._update_pf(result)
            return
        if dest in self._reg16_names():
            value = self.cpu.get_reg16(dest)
            result = (-value) & 0xFFFF
            self.cpu.set_reg16(dest, result)
            self.cpu.set_flag(FLAG_CF, value != 0)
            self.cpu.set_flag(FLAG_AF, (value & 0x0F) != 0)
            self.cpu.set_flag(FLAG_OF, value == 0x8000)
            self._update_zf(result, 16)
            self._update_sf(result, 16)
            self._update_pf(result)
            return
        if self._is_memory(dest):
            size = self._resolve_mem_size(dest)
            if size is None:
                raise NotImplementedError("memory neg requires size")
            value = self._read_memory(dest, size)
            result = (-value) & self._mask(size)
            self._write_memory(dest, size, result)
            self.cpu.set_flag(FLAG_CF, value != 0)
            self.cpu.set_flag(FLAG_AF, (value & 0x0F) != 0)
            self.cpu.set_flag(FLAG_OF, value == (0x80 if size == 8 else 0x8000))
            self._update_zf(result, size)
            self._update_sf(result, size)
            self._update_pf(result)
            return
        raise NotImplementedError(f"Unsupported neg dest: {dest} at line {instr.line}")

    def _exec_test(self, args, instr) -> None:
        if len(args) != 2:
            raise ValueError(f"test expects 2 operands at line {instr.line}")
        dest = args[0].lower()
        src = args[1].lower()
        if dest in self._reg8_names():
            result = self.cpu.get_reg8(dest) & self._resolve_operand(src, 8)
            self.cpu.set_flag(FLAG_CF, False)
            self.cpu.set_flag(FLAG_AF, False)
            self.cpu.set_flag(FLAG_OF, False)
            self._update_zf(result, 8)
            self._update_sf(result, 8)
            self._update_pf(result)
            return
        if dest in self._reg16_names():
            result = self.cpu.get_reg16(dest) & self._resolve_operand(src, 16)
            self.cpu.set_flag(FLAG_CF, False)
            self.cpu.set_flag(FLAG_AF, False)
            self.cpu.set_flag(FLAG_OF, False)
            self._update_zf(result, 16)
            self._update_sf(result, 16)
            self._update_pf(result)
            return
        if self._is_memory(dest):
            size = self._resolve_mem_size(dest) or self._resolve_size_hint(src)
            if size is None:
                raise NotImplementedError("memory test requires size")
            result = self._read_memory(dest, size) & self._resolve_operand(src, size)
            self.cpu.set_flag(FLAG_CF, False)
            self.cpu.set_flag(FLAG_AF, False)
            self.cpu.set_flag(FLAG_OF, False)
            self._update_zf(result, size)
            self._update_sf(result, size)
            self._update_pf(result)
            return
        raise NotImplementedError(f"Unsupported test dest: {dest} at line {instr.line}")

    def _exec_shift(self, args, instr, kind: str) -> None:
        if len(args) != 2:
            raise ValueError(f"{kind} expects 2 operands at line {instr.line}")
        dest = args[0].lower()
        count = self._resolve_shift_count(args[1].lower())
        if count == 0:
            return
        if dest in self._reg8_names():
            value = self.cpu.get_reg8(dest)
            result = self._shift_value(value, count, 8, kind)
            self.cpu.set_reg8(dest, result)
            return
        if dest in self._reg16_names():
            value = self.cpu.get_reg16(dest)
            result = self._shift_value(value, count, 16, kind)
            self.cpu.set_reg16(dest, result)
            return
        if self._is_memory(dest):
            size = self._resolve_mem_size(dest)
            if size is None:
                raise NotImplementedError("memory shift requires size")
            value = self._read_memory(dest, size)
            result = self._shift_value(value, count, size, kind)
            self._write_memory(dest, size, result)
            return
        raise NotImplementedError(f"Unsupported {kind} dest: {dest} at line {instr.line}")

    def _shift_value(self, value: int, count: int, size: int, kind: str) -> int:
        mask = self._mask(size)
        count = count & 0x1F
        if count == 0:
            return value & mask
        if kind in {"shl"}:
            shifted = value << count
            self.cpu.set_flag(FLAG_CF, (shifted >> size) & 1 == 1)
            result = shifted & mask
        elif kind == "shr":
            self.cpu.set_flag(FLAG_CF, (value >> (count - 1)) & 1 == 1)
            result = (value >> count) & mask
        else:
            self.cpu.set_flag(FLAG_CF, (value >> (count - 1)) & 1 == 1)
            sign = value & (0x80 if size == 8 else 0x8000)
            result = value >> count
            if sign:
                fill = ((1 << count) - 1) << (size - count)
                result |= fill
            result &= mask
        self.cpu.set_flag(FLAG_AF, False)
        self.cpu.set_flag(FLAG_OF, False)
        self._update_zf(result, size)
        self._update_sf(result, size)
        self._update_pf(result)
        return result

    def _exec_rotate(self, args, instr, kind: str) -> None:
        if len(args) != 2:
            raise ValueError(f"{kind} expects 2 operands at line {instr.line}")
        dest = args[0].lower()
        count = self._resolve_shift_count(args[1].lower())
        if count == 0:
            return
        if dest in self._reg8_names():
            value = self.cpu.get_reg8(dest)
            result = self._rotate_value(value, count, 8, kind)
            self.cpu.set_reg8(dest, result)
            return
        if dest in self._reg16_names():
            value = self.cpu.get_reg16(dest)
            result = self._rotate_value(value, count, 16, kind)
            self.cpu.set_reg16(dest, result)
            return
        if self._is_memory(dest):
            size = self._resolve_mem_size(dest)
            if size is None:
                raise NotImplementedError("memory rotate requires size")
            value = self._read_memory(dest, size)
            result = self._rotate_value(value, count, size, kind)
            self._write_memory(dest, size, result)
            return
        raise NotImplementedError(f"Unsupported {kind} dest: {dest} at line {instr.line}")

    def _rotate_value(self, value: int, count: int, size: int, kind: str) -> int:
        mask = self._mask(size)
        count = count % size
        if count == 0:
            return value & mask
        if kind == "rol":
            result = ((value << count) | (value >> (size - count))) & mask
            self.cpu.set_flag(FLAG_CF, (result & 0x01) != 0)
        else:
            result = ((value >> count) | (value << (size - count))) & mask
            self.cpu.set_flag(FLAG_CF, (result & (0x80 if size == 8 else 0x8000)) != 0)
        return result

    def _resolve_shift_count(self, token: str) -> int:
        if token == "cl":
            return self.cpu.get_reg8("cl") & 0x1F
        return self._parse_number(token, label_ok=True) & 0x1F

    def _exec_mul(self, args, instr, signed: bool) -> None:
        if len(args) != 1:
            raise ValueError(f"mul expects 1 operand at line {instr.line}")
        op = args[0].lower()
        size = self._resolve_size_hint(op) or self._resolve_mem_size(op)
        if op in self._reg8_names():
            size = 8
        elif op in self._reg16_names():
            size = 16
        if size is None:
            raise NotImplementedError("mul requires operand size")
        if size == 8:
            left = self.cpu.get_reg8("al")
            right = self._resolve_operand(op, 8)
            if signed:
                result = (self._sign8(left) * self._sign8(right)) & 0xFFFF
            else:
                result = (left * right) & 0xFFFF
            self.cpu.set_reg16("ax", result)
            high = (result >> 8) & 0xFF
            if signed:
                self.cpu.set_flag(FLAG_CF, high not in {0x00, 0xFF})
                self.cpu.set_flag(FLAG_OF, high not in {0x00, 0xFF})
            else:
                self.cpu.set_flag(FLAG_CF, high != 0)
                self.cpu.set_flag(FLAG_OF, high != 0)
        else:
            left = self.cpu.get_reg16("ax")
            right = self._resolve_operand(op, 16)
            if signed:
                result = (self._sign16(left) * self._sign16(right)) & 0xFFFFFFFF
            else:
                result = (left * right) & 0xFFFFFFFF
            self.cpu.set_reg16("ax", result & 0xFFFF)
            self.cpu.set_reg16("dx", (result >> 16) & 0xFFFF)
            high = (result >> 16) & 0xFFFF
            if signed:
                self.cpu.set_flag(FLAG_CF, high not in {0x0000, 0xFFFF})
                self.cpu.set_flag(FLAG_OF, high not in {0x0000, 0xFFFF})
            else:
                self.cpu.set_flag(FLAG_CF, high != 0)
                self.cpu.set_flag(FLAG_OF, high != 0)

    def _exec_div(self, args, instr, signed: bool) -> None:
        if len(args) != 1:
            raise ValueError(f"div expects 1 operand at line {instr.line}")
        op = args[0].lower()
        size = self._resolve_size_hint(op) or self._resolve_mem_size(op)
        if op in self._reg8_names():
            size = 8
        elif op in self._reg16_names():
            size = 16
        if size is None:
            raise NotImplementedError("div requires operand size")
        if size == 8:
            divisor = self._resolve_operand(op, 8)
            if divisor == 0:
                raise ZeroDivisionError("Division by zero")
            dividend = self.cpu.get_reg16("ax")
            if signed:
                quotient = int(self._sign16(dividend) / self._sign8(divisor))
                remainder = int(self._sign16(dividend) % self._sign8(divisor))
            else:
                quotient = dividend // divisor
                remainder = dividend % divisor
            if quotient < -128 or quotient > 255:
                raise OverflowError("Division overflow")
            self.cpu.set_reg8("al", quotient & 0xFF)
            self.cpu.set_reg8("ah", remainder & 0xFF)
        else:
            divisor = self._resolve_operand(op, 16)
            if divisor == 0:
                raise ZeroDivisionError("Division by zero")
            dividend = (self.cpu.get_reg16("dx") << 16) | self.cpu.get_reg16("ax")
            if signed:
                quotient = int(self._sign32(dividend) / self._sign16(divisor))
                remainder = int(self._sign32(dividend) % self._sign16(divisor))
            else:
                quotient = dividend // divisor
                remainder = dividend % divisor
            if quotient < -32768 or quotient > 0xFFFF:
                raise OverflowError("Division overflow")
            self.cpu.set_reg16("ax", quotient & 0xFFFF)
            self.cpu.set_reg16("dx", remainder & 0xFFFF)

    def _exec_jc(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"jc expects 1 operand at line {instr.line}")
        if self.cpu.get_flag(FLAG_CF):
            self._jump_to(self._resolve_jump_target(args[0]))

    def _exec_jnc(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"jnc expects 1 operand at line {instr.line}")
        if not self.cpu.get_flag(FLAG_CF):
            self._jump_to(self._resolve_jump_target(args[0]))

    def _exec_jg(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"jg expects 1 operand at line {instr.line}")
        if not self.cpu.get_flag(FLAG_ZF) and (self.cpu.get_flag(FLAG_SF) == self.cpu.get_flag(FLAG_OF)):
            self._jump_to(self._resolve_jump_target(args[0]))

    def _exec_jl(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"jl expects 1 operand at line {instr.line}")
        if self.cpu.get_flag(FLAG_SF) != self.cpu.get_flag(FLAG_OF):
            self._jump_to(self._resolve_jump_target(args[0]))

    def _exec_jge(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"jge expects 1 operand at line {instr.line}")
        if self.cpu.get_flag(FLAG_SF) == self.cpu.get_flag(FLAG_OF):
            self._jump_to(self._resolve_jump_target(args[0]))

    def _exec_jle(self, args, instr) -> None:
        if len(args) != 1:
            raise ValueError(f"jle expects 1 operand at line {instr.line}")
        if self.cpu.get_flag(FLAG_ZF) or (self.cpu.get_flag(FLAG_SF) != self.cpu.get_flag(FLAG_OF)):
            self._jump_to(self._resolve_jump_target(args[0]))

    def _exec_loop(self, args, instr, kind: str) -> None:
        if len(args) != 1:
            raise ValueError(f"{kind} expects 1 operand at line {instr.line}")
        cx = (self.cpu.get_reg16("cx") - 1) & 0xFFFF
        self.cpu.set_reg16("cx", cx)
        should_jump = cx != 0
        if kind == "loope":
            should_jump = should_jump and self.cpu.get_flag(FLAG_ZF)
        elif kind == "loopne":
            should_jump = should_jump and not self.cpu.get_flag(FLAG_ZF)
        if should_jump:
            self._jump_to(self._resolve_jump_target(args[0]))

    def _exec_pushf(self, args, instr) -> None:
        if args:
            raise ValueError(f"pushf expects no operands at line {instr.line}")
        self._push16(self.cpu.flags)

    def _exec_popf(self, args, instr) -> None:
        if args:
            raise ValueError(f"popf expects no operands at line {instr.line}")
        self.cpu.flags = self._pop16()

    def _exec_xchg(self, args, instr) -> None:
        if len(args) != 2:
            raise ValueError(f"xchg expects 2 operands at line {instr.line}")
        left = args[0].lower()
        right = args[1].lower()
        if left in self._reg8_names() and right in self._reg8_names():
            a = self.cpu.get_reg8(left)
            b = self.cpu.get_reg8(right)
            self.cpu.set_reg8(left, b)
            self.cpu.set_reg8(right, a)
            return
        if left in self._reg16_names() and right in self._reg16_names():
            a = self.cpu.get_reg16(left)
            b = self.cpu.get_reg16(right)
            self.cpu.set_reg16(left, b)
            self.cpu.set_reg16(right, a)
            return
        if left in self._reg8_names() and self._is_memory(right):
            size = 8
            mem = self._read_memory(right, size)
            reg = self.cpu.get_reg8(left)
            self.cpu.set_reg8(left, mem)
            self._write_memory(right, size, reg)
            return
        if left in self._reg16_names() and self._is_memory(right):
            size = 16
            mem = self._read_memory(right, size)
            reg = self.cpu.get_reg16(left)
            self.cpu.set_reg16(left, mem)
            self._write_memory(right, size, reg)
            return
        if right in self._reg8_names() and self._is_memory(left):
            size = 8
            mem = self._read_memory(left, size)
            reg = self.cpu.get_reg8(right)
            self.cpu.set_reg8(right, mem)
            self._write_memory(left, size, reg)
            return
        if right in self._reg16_names() and self._is_memory(left):
            size = 16
            mem = self._read_memory(left, size)
            reg = self.cpu.get_reg16(right)
            self.cpu.set_reg16(right, mem)
            self._write_memory(left, size, reg)
            return
        raise NotImplementedError(f"Unsupported xchg operands at line {instr.line}")

    def _exec_movs(self, size: int, rep: bool = False) -> None:
        count = self.cpu.get_reg16("cx") if rep else 1
        step = -1 if self.cpu.get_flag(FLAG_DF) else 1
        for _ in range(count):
            src_addr = self.memory.phys(self.cpu.ds, self.cpu.get_reg16("si"))
            dst_addr = self.memory.phys(self.cpu.es, self.cpu.get_reg16("di"))
            if size == 8:
                value = self.memory.read8(src_addr)
                self.memory.write8(dst_addr, value)
                delta = step
            else:
                value = self.memory.read16(src_addr)
                self.memory.write16(dst_addr, value)
                delta = 2 * step
            self.cpu.si = (self.cpu.si + delta) & 0xFFFF
            self.cpu.di = (self.cpu.di + delta) & 0xFFFF
            if rep:
                self.cpu.cx = (self.cpu.cx - 1) & 0xFFFF

    def _exec_stos(self, size: int, rep: bool = False) -> None:
        count = self.cpu.get_reg16("cx") if rep else 1
        step = -1 if self.cpu.get_flag(FLAG_DF) else 1
        for _ in range(count):
            dst_addr = self.memory.phys(self.cpu.es, self.cpu.get_reg16("di"))
            if size == 8:
                self.memory.write8(dst_addr, self.cpu.get_reg8("al"))
                delta = step
            else:
                self.memory.write16(dst_addr, self.cpu.get_reg16("ax"))
                delta = 2 * step
            self.cpu.di = (self.cpu.di + delta) & 0xFFFF
            if rep:
                self.cpu.cx = (self.cpu.cx - 1) & 0xFFFF

    def _exec_lods(self, size: int, rep: bool = False) -> None:
        count = self.cpu.get_reg16("cx") if rep else 1
        step = -1 if self.cpu.get_flag(FLAG_DF) else 1
        for _ in range(count):
            src_addr = self.memory.phys(self.cpu.ds, self.cpu.get_reg16("si"))
            if size == 8:
                self.cpu.set_reg8("al", self.memory.read8(src_addr))
                delta = step
            else:
                self.cpu.set_reg16("ax", self.memory.read16(src_addr))
                delta = 2 * step
            self.cpu.si = (self.cpu.si + delta) & 0xFFFF
            if rep:
                self.cpu.cx = (self.cpu.cx - 1) & 0xFFFF

    def _exec_daa(self, instr) -> None:
        al = self.cpu.get_reg8("al")
        adjust = 0
        cf = self.cpu.get_flag(FLAG_CF)
        af = self.cpu.get_flag(FLAG_AF)
        if (al & 0x0F) > 9 or af:
            adjust |= 0x06
        if al > 0x99 or cf:
            adjust |= 0x60
        result = (al + adjust) & 0xFF
        self.cpu.set_reg8("al", result)
        self.cpu.set_flag(FLAG_AF, (adjust & 0x06) != 0)
        self.cpu.set_flag(FLAG_CF, (adjust & 0x60) != 0)
        self._update_zf(result, 8)
        self._update_sf(result, 8)
        self._update_pf(result)

    def _exec_das(self, instr) -> None:
        al = self.cpu.get_reg8("al")
        adjust = 0
        cf = self.cpu.get_flag(FLAG_CF)
        af = self.cpu.get_flag(FLAG_AF)
        if (al & 0x0F) > 9 or af:
            adjust |= 0x06
        if al > 0x99 or cf:
            adjust |= 0x60
        result = (al - adjust) & 0xFF
        self.cpu.set_reg8("al", result)
        self.cpu.set_flag(FLAG_AF, (adjust & 0x06) != 0)
        self.cpu.set_flag(FLAG_CF, (adjust & 0x60) != 0)
        self._update_zf(result, 8)
        self._update_sf(result, 8)
        self._update_pf(result)

    def _exec_aaa(self, instr) -> None:
        al = self.cpu.get_reg8("al")
        ah = self.cpu.get_reg8("ah")
        if (al & 0x0F) > 9 or self.cpu.get_flag(FLAG_AF):
            al = (al + 6) & 0xFF
            ah = (ah + 1) & 0xFF
            self.cpu.set_flag(FLAG_AF, True)
            self.cpu.set_flag(FLAG_CF, True)
        else:
            self.cpu.set_flag(FLAG_AF, False)
            self.cpu.set_flag(FLAG_CF, False)
        al &= 0x0F
        self.cpu.set_reg8("al", al)
        self.cpu.set_reg8("ah", ah)

    def _exec_aas(self, instr) -> None:
        al = self.cpu.get_reg8("al")
        ah = self.cpu.get_reg8("ah")
        if (al & 0x0F) > 9 or self.cpu.get_flag(FLAG_AF):
            al = (al - 6) & 0xFF
            ah = (ah - 1) & 0xFF
            self.cpu.set_flag(FLAG_AF, True)
            self.cpu.set_flag(FLAG_CF, True)
        else:
            self.cpu.set_flag(FLAG_AF, False)
            self.cpu.set_flag(FLAG_CF, False)
        al &= 0x0F
        self.cpu.set_reg8("al", al)
        self.cpu.set_reg8("ah", ah)

    def _exec_aam(self, args, instr) -> None:
        base = 10
        if args:
            base = self._parse_number(args[0], label_ok=True) & 0xFF
        if base == 0:
            raise ZeroDivisionError("AAM base cannot be zero")
        al = self.cpu.get_reg8("al")
        ah = (al // base) & 0xFF
        al = (al % base) & 0xFF
        self.cpu.set_reg8("ah", ah)
        self.cpu.set_reg8("al", al)
        self._update_zf(al, 8)
        self._update_sf(al, 8)
        self._update_pf(al)

    def _exec_aad(self, args, instr) -> None:
        base = 10
        if args:
            base = self._parse_number(args[0], label_ok=True) & 0xFF
        al = self.cpu.get_reg8("al")
        ah = self.cpu.get_reg8("ah")
        result = (ah * base + al) & 0xFF
        self.cpu.set_reg8("al", result)
        self.cpu.set_reg8("ah", 0)
        self._update_zf(result, 8)
        self._update_sf(result, 8)
        self._update_pf(result)

    def _exec_lahf(self, instr) -> None:
        flags = self.cpu.flags
        ah = 0
        if flags & FLAG_SF:
            ah |= 0x80
        if flags & FLAG_ZF:
            ah |= 0x40
        if flags & FLAG_AF:
            ah |= 0x10
        if flags & FLAG_PF:
            ah |= 0x04
        ah |= 0x02
        if flags & FLAG_CF:
            ah |= 0x01
        self.cpu.set_reg8("ah", ah)

    def _exec_sahf(self, instr) -> None:
        ah = self.cpu.get_reg8("ah")
        self.cpu.set_flag(FLAG_SF, (ah & 0x80) != 0)
        self.cpu.set_flag(FLAG_ZF, (ah & 0x40) != 0)
        self.cpu.set_flag(FLAG_AF, (ah & 0x10) != 0)
        self.cpu.set_flag(FLAG_PF, (ah & 0x04) != 0)
        self.cpu.set_flag(FLAG_CF, (ah & 0x01) != 0)

    def _exec_cbw(self, instr) -> None:
        al = self.cpu.get_reg8("al")
        self.cpu.set_reg16("ax", 0xFF00 | al if al & 0x80 else al)

    def _exec_cwd(self, instr) -> None:
        ax = self.cpu.get_reg16("ax")
        self.cpu.set_reg16("dx", 0xFFFF if ax & 0x8000 else 0x0000)

    def _exec_xlat(self, instr) -> None:
        addr = self.memory.phys(self.cpu.ds, (self.cpu.get_reg16("bx") + self.cpu.get_reg8("al")) & 0xFFFF)
        self.cpu.set_reg8("al", self.memory.read8(addr))

    def _exec_enter(self, args, instr) -> None:
        size = self._parse_number(args[0], label_ok=True) & 0xFFFF
        level = 0
        if len(args) == 2:
            level = self._parse_number(args[1], label_ok=True) & 0xFF
        if level != 0:
            raise NotImplementedError("enter with nesting level is not supported")
        self._push16(self.cpu.get_reg16("bp"))
        self.cpu.set_reg16("bp", self.cpu.get_reg16("sp"))
        self.cpu.sp = (self.cpu.sp - size) & 0xFFFF

    def _exec_leave(self, instr) -> None:
        self.cpu.set_reg16("sp", self.cpu.get_reg16("bp"))
        self.cpu.set_reg16("bp", self._pop16())

    def _exec_int3(self, instr) -> None:
        self._handle_interrupt(0x03, instr)

    def _exec_iret(self, instr) -> None:
        ip = self._pop16()
        cs = self._pop16()
        flags = self._pop16()
        self.cpu.set_reg16("cs", cs)
        self.cpu.flags = flags
        self._jump_to(ip)

    def _exec_pusha(self, instr) -> None:
        sp = self.cpu.get_reg16("sp")
        self._push16(self.cpu.get_reg16("ax"))
        self._push16(self.cpu.get_reg16("cx"))
        self._push16(self.cpu.get_reg16("dx"))
        self._push16(self.cpu.get_reg16("bx"))
        self._push16(sp)
        self._push16(self.cpu.get_reg16("bp"))
        self._push16(self.cpu.get_reg16("si"))
        self._push16(self.cpu.get_reg16("di"))

    def _exec_popa(self, instr) -> None:
        self.cpu.set_reg16("di", self._pop16())
        self.cpu.set_reg16("si", self._pop16())
        self.cpu.set_reg16("bp", self._pop16())
        _discard = self._pop16()
        self.cpu.set_reg16("bx", self._pop16())
        self.cpu.set_reg16("dx", self._pop16())
        self.cpu.set_reg16("cx", self._pop16())
        self.cpu.set_reg16("ax", self._pop16())

    def _exec_cmps(self, size: int) -> None:
        step = -1 if self.cpu.get_flag(FLAG_DF) else 1
        left_addr = self.memory.phys(self.cpu.ds, self.cpu.get_reg16("si"))
        right_addr = self.memory.phys(self.cpu.es, self.cpu.get_reg16("di"))
        if size == 8:
            left = self.memory.read8(left_addr)
            right = self.memory.read8(right_addr)
            delta = step
        else:
            left = self.memory.read16(left_addr)
            right = self.memory.read16(right_addr)
            delta = 2 * step
        result = left - right
        self._update_sub_flags(left, right, result, size)
        self._update_zf(result, size)
        self._update_sf(result, size)
        self.cpu.si = (self.cpu.si + delta) & 0xFFFF
        self.cpu.di = (self.cpu.di + delta) & 0xFFFF

    def _exec_scas(self, size: int) -> None:
        step = -1 if self.cpu.get_flag(FLAG_DF) else 1
        addr = self.memory.phys(self.cpu.es, self.cpu.get_reg16("di"))
        if size == 8:
            left = self.cpu.get_reg8("al")
            right = self.memory.read8(addr)
            delta = step
        else:
            left = self.cpu.get_reg16("ax")
            right = self.memory.read16(addr)
            delta = 2 * step
        result = left - right
        self._update_sub_flags(left, right, result, size)
        self._update_zf(result, size)
        self._update_sf(result, size)
        self.cpu.di = (self.cpu.di + delta) & 0xFFFF

    def _exec_rep_cmps(self, size: int, mode: str) -> None:
        while self.cpu.get_reg16("cx") != 0:
            self._exec_cmps(size)
            self.cpu.cx = (self.cpu.cx - 1) & 0xFFFF
            if mode == "repe" and not self.cpu.get_flag(FLAG_ZF):
                break
            if mode == "repne" and self.cpu.get_flag(FLAG_ZF):
                break

    def _exec_rep_scas(self, size: int, mode: str) -> None:
        while self.cpu.get_reg16("cx") != 0:
            self._exec_scas(size)
            self.cpu.cx = (self.cpu.cx - 1) & 0xFFFF
            if mode == "repe" and not self.cpu.get_flag(FLAG_ZF):
                break
            if mode == "repne" and self.cpu.get_flag(FLAG_ZF):
                break

    def _sign8(self, value: int) -> int:
        return value - 0x100 if value & 0x80 else value

    def _sign16(self, value: int) -> int:
        return value - 0x10000 if value & 0x8000 else value

    def _sign32(self, value: int) -> int:
        return value - 0x100000000 if value & 0x80000000 else value


@dataclass
class Instruction:
    op: str
    args: list[str]
    line: int
    raw: str
