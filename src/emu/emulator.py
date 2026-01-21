from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .cpu import CPU, FLAG_CF, FLAG_ZF
from .memory import Memory
from .interrupts import DOSKernel
from .parser import AsmParser, ProgramImage


@dataclass
class EmulatorConfig:
    memory_size: int = 1024 * 1024
    data_segment: int = 0x1000
    code_segment: int = 0x2000
    dos_root: str = "dos_root"


class Emulator:
    def __init__(self, config: EmulatorConfig | None = None) -> None:
        self.config = config or EmulatorConfig()
        self.cpu = CPU()
        self.memory = Memory(self.config.memory_size)
        self.kernel = DOSKernel(self.cpu, self.memory, self.config.dos_root)
        self.program: ProgramImage | None = None

        self.cpu.ds = self.config.data_segment
        self.cpu.cs = self.config.code_segment
        self.cpu.ss = 0x3000
        self.cpu.sp = 0xFFFE

    def load_asm(self, asm_text: str) -> ProgramImage:
        parser = AsmParser(self.memory, self.config.data_segment)
        program = parser.parse(asm_text.splitlines())
        self.program = program
        self.cpu.ip = 0
        return program

    def run(self, max_steps: int = 100000) -> int:
        if self.program is None:
            raise RuntimeError("No program loaded")
        steps = 0
        while not self.cpu.halted and steps < max_steps:
            if self.cpu.ip < 0 or self.cpu.ip >= len(self.program.instructions):
                break
            instr = self.program.instructions[self.cpu.ip]
            self._execute(instr)
            steps += 1
        if steps >= max_steps:
            raise RuntimeError("Execution limit reached")
        return self.cpu.exit_code or 0

    def _execute(self, instr) -> None:
        op = instr.op
        args = instr.args
        if op == "mov":
            self._exec_mov(args, instr)
        elif op == "lea":
            self._exec_lea(args, instr)
        elif op == "add":
            self._exec_add(args, instr)
        elif op == "sub":
            self._exec_sub(args, instr)
        elif op == "cmp":
            self._exec_cmp(args, instr)
        elif op == "inc":
            self._exec_inc(args, instr)
        elif op == "dec":
            self._exec_dec(args, instr)
        elif op == "jmp":
            self._exec_jmp(args, instr)
        elif op in {"je", "jz"}:
            self._exec_je(args, instr)
        elif op in {"jne", "jnz"}:
            self._exec_jne(args, instr)
        elif op == "call":
            self._exec_call(args, instr)
        elif op == "ret":
            self._exec_ret(args, instr)
        elif op == "push":
            self._exec_push(args, instr)
        elif op == "pop":
            self._exec_pop(args, instr)
        elif op == "int":
            self._exec_int(args, instr)
        elif op == "nop":
            pass
        elif op == "hlt":
            self.cpu.halted = True
        else:
            raise NotImplementedError(f"Unsupported op: {op} at line {instr.line}")
        self.cpu.ip += 1

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
        if vector == 0x21:
            self.kernel.int_21h()
        elif vector == 0x10:
            self.kernel.int_10h()
        else:
            raise NotImplementedError(f"Unsupported interrupt: {vector:#x}")

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
        if token.endswith("h"):
            return int(token[:-1], 16)
        if token.startswith("0x"):
            return int(token, 16)
        if token.startswith("'") and token.endswith("'") and len(token) == 3:
            return ord(token[1])
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
            self.cpu.set_flag(FLAG_CF, result > self._mask(size))
        else:
            result = (left - right) & 0x1FFFF
            self.cpu.set_flag(FLAG_CF, left < right)
        self._update_zf(result, size)
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
            self.cpu.set_flag(FLAG_CF, result > self._mask(size))
        else:
            result = (left - right) & 0x1FFFF
            self.cpu.set_flag(FLAG_CF, left < right)
        self._update_zf(result, size)
        self._write_memory(dest, size, result)

    def _cmp_reg(self, dest: str, src: str, size: int) -> None:
        if size == 8:
            left = self.cpu.get_reg8(dest)
        else:
            left = self.cpu.get_reg16(dest)
        right = self._resolve_operand(src, size=size)
        result = (left - right) & self._mask(size)
        self.cpu.set_flag(FLAG_CF, left < right)
        self._update_zf(result, size)

    def _cmp_mem(self, dest: str, src: str) -> None:
        size = self._resolve_mem_size(dest) or self._resolve_size_hint(src)
        if size is None:
            raise NotImplementedError("memory cmp requires size")
        left = self._read_memory(dest, size)
        right = self._resolve_operand(src, size=size)
        result = (left - right) & self._mask(size)
        self.cpu.set_flag(FLAG_CF, left < right)
        self._update_zf(result, size)

    def _inc_reg(self, dest: str, size: int) -> None:
        if size == 8:
            value = (self.cpu.get_reg8(dest) + 1) & 0xFF
            self.cpu.set_reg8(dest, value)
        else:
            value = (self.cpu.get_reg16(dest) + 1) & 0xFFFF
            self.cpu.set_reg16(dest, value)
        self._update_zf(value, size)

    def _dec_reg(self, dest: str, size: int) -> None:
        if size == 8:
            value = (self.cpu.get_reg8(dest) - 1) & 0xFF
            self.cpu.set_reg8(dest, value)
        else:
            value = (self.cpu.get_reg16(dest) - 1) & 0xFFFF
            self.cpu.set_reg16(dest, value)
        self._update_zf(value, size)

    def _inc_mem(self, dest: str) -> None:
        size = self._resolve_mem_size(dest)
        if size is None:
            raise NotImplementedError("memory inc requires size")
        value = (self._read_memory(dest, size) + 1) & self._mask(size)
        self._write_memory(dest, size, value)
        self._update_zf(value, size)

    def _dec_mem(self, dest: str) -> None:
        size = self._resolve_mem_size(dest)
        if size is None:
            raise NotImplementedError("memory dec requires size")
        value = (self._read_memory(dest, size) - 1) & self._mask(size)
        self._write_memory(dest, size, value)
        self._update_zf(value, size)

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
            else:
                value = self._parse_number(term, label_ok=True)
            offset = (offset + sign * value) & 0xFFFF
        segment = self.cpu.ss if use_ss else self.cpu.ds
        return segment, offset
