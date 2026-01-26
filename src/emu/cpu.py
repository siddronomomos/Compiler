from __future__ import annotations

from dataclasses import dataclass, field


FLAG_CF = 0x0001
FLAG_PF = 0x0004
FLAG_AF = 0x0010
FLAG_ZF = 0x0040
FLAG_SF = 0x0080
FLAG_IF = 0x0200
FLAG_DF = 0x0400
FLAG_OF = 0x0800


@dataclass
class CPU:
    ax: int = 0
    bx: int = 0
    cx: int = 0
    dx: int = 0
    sp: int = 0
    bp: int = 0
    si: int = 0
    di: int = 0

    cs: int = 0
    ds: int = 0
    es: int = 0
    ss: int = 0

    ip: int = 0
    flags: int = 0

    halted: bool = False
    exit_code: int | None = None

    def _mask16(self, value: int) -> int:
        return value & 0xFFFF

    def _mask8(self, value: int) -> int:
        return value & 0xFF

    def get_reg16(self, name: str) -> int:
        return getattr(self, name.lower())

    def set_reg16(self, name: str, value: int) -> None:
        setattr(self, name.lower(), self._mask16(value))

    def get_reg8(self, name: str) -> int:
        name = name.lower()
        if name == "ah":
            return (self.ax >> 8) & 0xFF
        if name == "al":
            return self.ax & 0xFF
        if name == "bh":
            return (self.bx >> 8) & 0xFF
        if name == "bl":
            return self.bx & 0xFF
        if name == "ch":
            return (self.cx >> 8) & 0xFF
        if name == "cl":
            return self.cx & 0xFF
        if name == "dh":
            return (self.dx >> 8) & 0xFF
        if name == "dl":
            return self.dx & 0xFF
        raise KeyError(f"Unknown 8-bit register: {name}")

    def set_reg8(self, name: str, value: int) -> None:
        value = self._mask8(value)
        name = name.lower()
        if name == "ah":
            self.ax = self._mask16((self.ax & 0x00FF) | (value << 8))
            return
        if name == "al":
            self.ax = self._mask16((self.ax & 0xFF00) | value)
            return
        if name == "bh":
            self.bx = self._mask16((self.bx & 0x00FF) | (value << 8))
            return
        if name == "bl":
            self.bx = self._mask16((self.bx & 0xFF00) | value)
            return
        if name == "ch":
            self.cx = self._mask16((self.cx & 0x00FF) | (value << 8))
            return
        if name == "cl":
            self.cx = self._mask16((self.cx & 0xFF00) | value)
            return
        if name == "dh":
            self.dx = self._mask16((self.dx & 0x00FF) | (value << 8))
            return
        if name == "dl":
            self.dx = self._mask16((self.dx & 0xFF00) | value)
            return
        raise KeyError(f"Unknown 8-bit register: {name}")

    def set_flag(self, mask: int, value: bool) -> None:
        if value:
            self.flags |= mask
        else:
            self.flags &= ~mask

    def get_flag(self, mask: int) -> bool:
        return (self.flags & mask) != 0

    def dump(self) -> dict[str, int]:
        return {
            "AX": self.ax,
            "BX": self.bx,
            "CX": self.cx,
            "DX": self.dx,
            "SP": self.sp,
            "BP": self.bp,
            "SI": self.si,
            "DI": self.di,
            "CS": self.cs,
            "DS": self.ds,
            "ES": self.es,
            "SS": self.ss,
            "IP": self.ip,
            "FLAGS": self.flags,
        }
