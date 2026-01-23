from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .cpu import CPU
from .memory import Memory
from .interrupts import DOSKernel
from .parser import AsmParser, ProgramImage
from .instructions import Instruction, InstructionExecutor


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
        self.executor = InstructionExecutor(self.cpu, self.memory, self.kernel)
        self.program: ProgramImage | None = None
        self._rep_prefix: str | None = None

        self.cpu.ds = self.config.data_segment
        self.cpu.cs = self.config.code_segment
        self.cpu.ss = 0x3000
        self.cpu.sp = 0xFFFE

    def load_asm(self, asm_text: str) -> ProgramImage:
        self.cpu = CPU()
        self.memory = Memory(self.config.memory_size)
        self.kernel = DOSKernel(self.cpu, self.memory, self.config.dos_root)
        self.executor = InstructionExecutor(self.cpu, self.memory, self.kernel)
        self.cpu.ds = self.config.data_segment
        self.cpu.cs = self.config.code_segment
        self.cpu.ss = 0x3000
        self.cpu.sp = 0xFFFE
        parser = AsmParser(self.memory, self.config.data_segment)
        program = parser.parse(asm_text.splitlines())
        self.program = program
        self.executor.set_program(program)
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

    def step(self) -> Instruction | None:
        if self.program is None:
            raise RuntimeError("No program loaded")
        if self.cpu.halted:
            return None
        if self.cpu.ip < 0 or self.cpu.ip >= len(self.program.instructions):
            self.cpu.halted = True
            return None
        instr = self.program.instructions[self.cpu.ip]
        self._execute(instr)
        return instr

    def run_until_breakpoint(self, breakpoints: set[int] | None = None, max_steps: int = 100000) -> int:
        if self.program is None:
            raise RuntimeError("No program loaded")
        steps = 0
        while not self.cpu.halted and steps < max_steps:
            if breakpoints and self.cpu.ip in breakpoints:
                break
            if self.step() is None:
                break
            steps += 1
        if steps >= max_steps:
            raise RuntimeError("Execution limit reached")
        return self.cpu.exit_code or 0

    def _execute(self, instr: Instruction) -> None:
        self.executor.execute(instr)
