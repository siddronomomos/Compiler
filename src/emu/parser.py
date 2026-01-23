from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .instructions import Instruction, validate_opcode
from .memory import Memory


@dataclass
class ProgramImage:
    instructions: list[Instruction]
    labels: dict[str, int]
    data_labels: dict[str, int]
    constants: dict[str, int]


class AsmParser:
    def __init__(self, memory: Memory, data_segment: int) -> None:
        self.memory = memory
        self.data_segment = data_segment

    def parse(self, lines: Iterable[str]) -> ProgramImage:
        section = None
        instructions: list[Instruction] = []
        labels: dict[str, int] = {}
        data_labels: dict[str, int] = {}
        constants: dict[str, int] = {}
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

            if self._is_equ(line):
                name, value = self._parse_equ(line)
                constants[name.lower()] = value
                continue

            if section == "data":
                if line.lower().startswith("org "):
                    data_offset = self._parse_number(line.split(None, 1)[1])
                    continue
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
                op, args = self._parse_instruction(line, line_no)
                instructions.append(Instruction(op=op, args=args, line=line_no, raw=raw.rstrip("\n")))
            else:
                continue

        return ProgramImage(instructions=instructions, labels=labels, data_labels=data_labels, constants=constants)

    def _split_label(self, line: str) -> tuple[str | None, str | None]:
        colon_index = self._find_colon_outside_quotes(line)
        if colon_index is not None:
            name = line[:colon_index].strip()
            rest = line[colon_index + 1 :].strip()
            return name, rest if rest else None
        tokens = line.split(None, 1)
        if len(tokens) >= 2 and tokens[1].lower().startswith("db "):
            return tokens[0], tokens[1]
        if len(tokens) >= 2 and tokens[1].lower().startswith("dw "):
            return tokens[0], tokens[1]
        return None, line

    def _find_colon_outside_quotes(self, line: str) -> int | None:
        in_quote = False
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "'":
                in_quote = not in_quote
            elif ch == ":" and not in_quote:
                return i
            # Skip escaped characters inside quotes to avoid toggling on escaped quotes
            if ch == "\\" and in_quote and i + 1 < len(line):
                i += 2
                continue
            i += 1
        return None

    def _parse_instruction(self, line: str, line_no: int) -> tuple[str, list[str]]:
        tokens = line.split(None, 1)
        op = tokens[0].lower()
        validate_opcode(op, line_no)
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
        payload = bytearray()
        for part in self._split_values(values):
            if not part:
                continue
            dup = self._parse_dup(part)
            if dup is not None:
                count, inner = dup
                inner_bytes = self._parse_db(inner)
                payload.extend(inner_bytes * count)
                continue
            if part.startswith("'") and part.endswith("'"):
                payload.extend(self._decode_string_literal(part))
            else:
                payload.append(self._parse_number(part) & 0xFF)
        return bytes(payload)

    def _parse_dw(self, values: str) -> list[int]:
        words: list[int] = []
        for part in self._split_values(values):
            if not part:
                continue
            dup = self._parse_dup(part)
            if dup is not None:
                count, inner = dup
                inner_words = self._parse_dw(inner)
                words.extend(inner_words * count)
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
        if token.endswith("b") and len(token) > 1:
            return int(token[:-1], 2)
        if token.endswith("h"):
            return int(token[:-1], 16)
        if token.startswith("0x"):
            return int(token, 16)
        if token.startswith("'") and token.endswith("'") and len(token) == 3:
            return self._decode_char_literal(token)
        return int(token, 10)

    def _is_equ(self, line: str) -> bool:
        parts = line.split()
        return len(parts) >= 3 and parts[1].lower() == "equ"

    def _parse_equ(self, line: str) -> tuple[str, int]:
        parts = line.split(None, 2)
        name = parts[0]
        value = self._parse_number(parts[2])
        return name, value

    def _split_values(self, values: str) -> list[str]:
        items: list[str] = []
        buf = []
        depth = 0
        in_quote = False
        for ch in values:
            if ch == "'":
                in_quote = not in_quote
            if ch == "(" and not in_quote:
                depth += 1
            elif ch == ")" and not in_quote and depth > 0:
                depth -= 1
            if ch == "," and depth == 0 and not in_quote:
                items.append("".join(buf).strip())
                buf = []
                continue
            buf.append(ch)
        if buf:
            items.append("".join(buf).strip())
        return items

    def _parse_dup(self, part: str) -> tuple[int, str] | None:
        match = re.match(r"^(\d+)\s+dup\((.*)\)$", part.strip(), re.IGNORECASE)
        if not match:
            return None
        count = int(match.group(1))
        inner = match.group(2).strip()
        return count, inner

    def _decode_char_literal(self, token: str) -> int:
        return self._decode_string_literal(token)[0]

    def _decode_string_literal(self, token: str) -> bytes:
        inner = token[1:-1]
        out = bytearray()
        i = 0
        while i < len(inner):
            ch = inner[i]
            if ch == "\\" and i + 1 < len(inner):
                nxt = inner[i + 1]
                mapping = {"n": "\n", "r": "\r", "t": "\t", "0": "\0", "'": "'", "\\": "\\"}
                out.extend(mapping.get(nxt, nxt).encode("ascii", errors="replace"))
                i += 2
                continue
            out.extend(ch.encode("ascii", errors="replace"))
            i += 1
        return bytes(out)
