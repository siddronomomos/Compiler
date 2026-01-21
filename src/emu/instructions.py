from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Instruction:
    op: str
    args: list[str]
    line: int
    raw: str
