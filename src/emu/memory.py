from __future__ import annotations


class Memory:
    def __init__(self, size: int = 1024 * 1024) -> None:
        self.size = size
        self.data = bytearray(size)

    def _check(self, addr: int, length: int = 1) -> None:
        if addr < 0 or addr + length > self.size:
            raise IndexError(f"Acceso a memoria fuera de límites: {addr:#x}")

    def phys(self, segment: int, offset: int) -> int:
        return ((segment & 0xFFFF) << 4) + (offset & 0xFFFF)

    def read8(self, addr: int) -> int:
        self._check(addr, 1)
        return self.data[addr]

    def write8(self, addr: int, value: int) -> None:
        self._check(addr, 1)
        self.data[addr] = value & 0xFF

    def read16(self, addr: int) -> int:
        lo = self.read8(addr)
        hi = self.read8(addr + 1)
        return lo | (hi << 8)

    def write16(self, addr: int, value: int) -> None:
        self.write8(addr, value & 0xFF)
        self.write8(addr + 1, (value >> 8) & 0xFF)

    def read_block(self, addr: int, length: int) -> bytes:
        self._check(addr, length)
        return bytes(self.data[addr : addr + length])

    def write_block(self, addr: int, payload: bytes) -> None:
        self._check(addr, len(payload))
        self.data[addr : addr + len(payload)] = payload

    def read_c_string(self, addr: int, max_len: int = 65535) -> str:
        chars = []
        for i in range(max_len):
            b = self.read8(addr + i)
            if b == 0:
                break
            chars.append(b)
        return bytes(chars).decode("ascii", errors="replace")

    def read_dollar_string(self, addr: int, max_len: int = 65535) -> str:
        chars = []
        for i in range(max_len):
            b = self.read8(addr + i)
            if b == 0x24:
                break
            chars.append(b)
        return bytes(chars).decode("ascii", errors="replace")
