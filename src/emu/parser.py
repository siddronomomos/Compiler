from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .instructions import Instruction
from .memory import Memory


@dataclass
class ProgramImage:
    instructions: list[Instruction]
    labels: dict[str, int]
    data_labels: dict[str, int]


class AsmParser:
    def __init__(self, memory: Memory, data_segment: int) -> None:
        self.memory = memory
        self.data_segment = data_segment

    def parse(self, lines: Iterable[str]) -> ProgramImage:
        section = None
        instructions: list[Instruction] = []
        labels: dict[str, int] = {}
        data_labels: dict[str, int] = {}
        data_offset = 0

        for line_no, raw in enumerate(lines, start=1):
            line = raw.split(";", 1)[0].strip()
            if not line:
                continue
            lower = line.lower()
            if lower == ".data":
                section = "data"
                continue
            if lower == ".code":
                section = "code"
                continue

            if section == "data":
                label, rest = self._split_label(line)
                if label:
                    data_labels[label.lower()] = data_offset
                    if not rest:
                        continue
                    line = rest
                self._parse_data(line, data_offset)
                data_offset += self._data_size(line)
            elif section == "code":
                label, rest = self._split_label(line)
                if label:
                    labels[label.lower()] = len(instructions)
                    if not rest:
                        continue
                    line = rest
                op, args = self._parse_instruction(line)
                instructions.append(Instruction(op=op, args=args, line=line_no, raw=raw.rstrip("\n")))
            else:
                continue

        return ProgramImage(instructions=instructions, labels=labels, data_labels=data_labels)

    def _split_label(self, line: str) -> tuple[str | None, str | None]:
        if ":" in line:
            name, rest = line.split(":", 1)
            name = name.strip()
            return name, rest.strip() if rest.strip() else None
        tokens = line.split(None, 1)
        if len(tokens) >= 2 and tokens[1].lower().startswith("db "):
            return tokens[0], tokens[1]
        if len(tokens) >= 2 and tokens[1].lower().startswith("dw "):
            return tokens[0], tokens[1]
        return None, line

    def _parse_instruction(self, line: str) -> tuple[str, list[str]]:
        tokens = line.split(None, 1)
        op = tokens[0].lower()
        args = []
        if len(tokens) > 1:
            args = [arg.strip() for arg in tokens[1].split(",")]
        return op, args

    def _parse_data(self, line: str, offset: int) -> None:
        tokens = line.split(None, 1)
        if len(tokens) < 2:
            return
        directive = tokens[0].lower()
        values = tokens[1]
        addr = self.memory.phys(self.data_segment, offset)

        if directive == "db":
            payload = self._parse_db(values)
            self.memory.write_block(addr, payload)
        elif directive == "dw":
            words = self._parse_dw(values)
            for i, word in enumerate(words):
                self.memory.write16(addr + (i * 2), word)

    def _parse_db(self, values: str) -> bytes:
        parts = [p.strip() for p in values.split(",")]
        payload = bytearray()
        for part in parts:
            if not part:
                continue
            if part.startswith("'") and part.endswith("'"):
                payload.extend(part[1:-1].encode("ascii", errors="replace"))
            else:
                payload.append(self._parse_number(part) & 0xFF)
        return bytes(payload)

    def _parse_dw(self, values: str) -> list[int]:
        parts = [p.strip() for p in values.split(",")]
        words = []
        for part in parts:
            if not part:
                continue
            words.append(self._parse_number(part) & 0xFFFF)
        return words

    def _data_size(self, line: str) -> int:
        tokens = line.split(None, 1)
        if len(tokens) < 2:
            return 0
        directive = tokens[0].lower()
        values = tokens[1]
        if directive == "db":
            return len(self._parse_db(values))
        if directive == "dw":
            return 2 * len(self._parse_dw(values))
        return 0

    def _parse_number(self, token: str) -> int:
        token = token.strip().lower()
        if token.endswith("h"):
            return int(token[:-1], 16)
        if token.startswith("0x"):
            return int(token, 16)
        if token.startswith("'") and token.endswith("'") and len(token) == 3:
            return ord(token[1])
        return int(token, 10)
