from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import BinaryIO

from .cpu import CPU, FLAG_CF
from .memory import Memory

ERROR_FILE_NOT_FOUND = 0x02
ERROR_PATH_NOT_FOUND = 0x03
ERROR_ACCESS_DENIED = 0x05
ERROR_INVALID_HANDLE = 0x06
ERROR_INVALID_ACCESS = 0x0C
ERROR_INVALID_NAME = 0x03


@dataclass
class HandleEntry:
    handle: int
    file: BinaryIO
    mode: str


class DOSKernel:
    def __init__(self, cpu: CPU, memory: Memory, root_dir: str) -> None:
        self.cpu = cpu
        self.memory = memory
        self.root_dir = root_dir
        self._handles: dict[int, HandleEntry] = {}
        self._next_handle = 5

        os.makedirs(self.root_dir, exist_ok=True)

        self.video_mode = 0x03
        self.text_attr = 0x07
        self.background_attr = 0x00
        self.border_attr = 0x00

    def int_21h(self) -> None:
        ah = self.cpu.get_reg8("ah")
        if ah == 0x02:
            self._int21_display_char()
        elif ah == 0x09:
            self._int21_display_string()
        elif ah == 0x0A:
            self._int21_buffered_input()
        elif ah == 0x3C:
            self._int21_create_file()
        elif ah == 0x3D:
            self._int21_open_file()
        elif ah == 0x3E:
            self._int21_close_file()
        elif ah == 0x3F:
            self._int21_read_file()
        elif ah == 0x40:
            self._int21_write_file()
        elif ah == 0x41:
            self._int21_delete_file()
        elif ah == 0x42:
            self._int21_seek_file()
        elif ah == 0x4C:
            self._int21_exit()
        else:
            self._set_error(ERROR_INVALID_ACCESS)

    def int_10h(self) -> None:
        ah = self.cpu.get_reg8("ah")
        if ah == 0x00:
            self._int10_set_video_mode()
        elif ah == 0x0B:
            self._int10_set_palette()
        elif ah == 0x09:
            self._int10_write_char_attr()
        else:
            self._set_error(ERROR_INVALID_ACCESS)

    def _clear_error(self) -> None:
        self.cpu.set_flag(FLAG_CF, False)

    def _set_error(self, code: int) -> None:
        self.cpu.set_flag(FLAG_CF, True)
        self.cpu.set_reg16("ax", code)

    def _int21_display_char(self) -> None:
        ch = self.cpu.get_reg8("dl")
        self._console_write(bytes([ch]))
        self._clear_error()

    def _int21_display_string(self) -> None:
        addr = self.memory.phys(self.cpu.ds, self.cpu.get_reg16("dx"))
        text = self.memory.read_dollar_string(addr)
        self._console_write(text.encode("ascii", errors="replace"))
        self._clear_error()

    def _int21_buffered_input(self) -> None:
        addr = self.memory.phys(self.cpu.ds, self.cpu.get_reg16("dx"))
        max_len = self.memory.read8(addr)
        try:
            line = input()
        except EOFError:
            line = ""
        line = line[:max_len]
        count = len(line)
        self.memory.write8(addr + 1, count)
        self.memory.write_block(addr + 2, line.encode("ascii", errors="replace"))
        if count < max_len:
            self.memory.write8(addr + 2 + count, 0x0D)
        self._clear_error()

    def _int21_create_file(self) -> None:
        name = self._read_asciiz(self.cpu.ds, self.cpu.get_reg16("dx"))
        resolved = self._resolve_path(name)
        if resolved is None:
            self._set_error(ERROR_INVALID_NAME)
            return
        try:
            f = open(resolved, "wb")
        except OSError:
            self._set_error(ERROR_ACCESS_DENIED)
            return
        handle = self._allocate_handle(f, "wb")
        self.cpu.set_reg16("ax", handle)
        self._clear_error()

    def _int21_open_file(self) -> None:
        name = self._read_asciiz(self.cpu.ds, self.cpu.get_reg16("dx"))
        resolved = self._resolve_path(name)
        if resolved is None:
            self._set_error(ERROR_INVALID_NAME)
            return
        mode = self.cpu.get_reg8("al")
        py_mode = "rb" if mode == 0x00 else "wb" if mode == 0x01 else "r+b"
        try:
            f = open(resolved, py_mode)
        except FileNotFoundError:
            self._set_error(ERROR_FILE_NOT_FOUND)
            return
        except OSError:
            self._set_error(ERROR_ACCESS_DENIED)
            return
        handle = self._allocate_handle(f, py_mode)
        self.cpu.set_reg16("ax", handle)
        self._clear_error()

    def _int21_close_file(self) -> None:
        handle = self.cpu.get_reg16("bx")
        entry = self._handles.pop(handle, None)
        if entry is None:
            self._set_error(ERROR_INVALID_HANDLE)
            return
        entry.file.close()
        self._clear_error()

    def _int21_read_file(self) -> None:
        handle = self.cpu.get_reg16("bx")
        count = self.cpu.get_reg16("cx")
        addr = self.memory.phys(self.cpu.ds, self.cpu.get_reg16("dx"))
        entry = self._handles.get(handle)
        if entry is None:
            self._set_error(ERROR_INVALID_HANDLE)
            return
        try:
            data = entry.file.read(count)
        except OSError:
            self._set_error(ERROR_ACCESS_DENIED)
            return
        self.memory.write_block(addr, data)
        self.cpu.set_reg16("ax", len(data))
        self._clear_error()

    def _int21_write_file(self) -> None:
        handle = self.cpu.get_reg16("bx")
        count = self.cpu.get_reg16("cx")
        addr = self.memory.phys(self.cpu.ds, self.cpu.get_reg16("dx"))
        payload = self.memory.read_block(addr, count)

        if handle == 1:
            self._console_write(payload)
            self.cpu.set_reg16("ax", count)
            self._clear_error()
            return

        entry = self._handles.get(handle)
        if entry is None:
            self._set_error(ERROR_INVALID_HANDLE)
            return
        try:
            written = entry.file.write(payload)
            entry.file.flush()
        except OSError:
            self._set_error(ERROR_ACCESS_DENIED)
            return
        self.cpu.set_reg16("ax", written)
        self._clear_error()

    def _int21_delete_file(self) -> None:
        name = self._read_asciiz(self.cpu.ds, self.cpu.get_reg16("dx"))
        resolved = self._resolve_path(name)
        if resolved is None:
            self._set_error(ERROR_INVALID_NAME)
            return
        try:
            os.remove(resolved)
        except FileNotFoundError:
            self._set_error(ERROR_FILE_NOT_FOUND)
            return
        except OSError:
            self._set_error(ERROR_ACCESS_DENIED)
            return
        self._clear_error()

    def _int21_seek_file(self) -> None:
        handle = self.cpu.get_reg16("bx")
        origin = self.cpu.get_reg8("al")
        offset = (self.cpu.get_reg16("cx") << 16) | self.cpu.get_reg16("dx")
        if offset & 0x80000000:
            offset = offset - 0x100000000
        entry = self._handles.get(handle)
        if entry is None:
            self._set_error(ERROR_INVALID_HANDLE)
            return
        if origin == 0:
            whence = os.SEEK_SET
        elif origin == 1:
            whence = os.SEEK_CUR
        elif origin == 2:
            whence = os.SEEK_END
        else:
            self._set_error(ERROR_INVALID_ACCESS)
            return
        try:
            pos = entry.file.seek(offset, whence)
        except OSError:
            self._set_error(ERROR_ACCESS_DENIED)
            return
        self.cpu.set_reg16("ax", pos & 0xFFFF)
        self.cpu.set_reg16("dx", (pos >> 16) & 0xFFFF)
        self._clear_error()

    def _int21_exit(self) -> None:
        code = self.cpu.get_reg8("al")
        self.cpu.exit_code = code
        self.cpu.halted = True
        self._clear_error()

    def _int10_set_video_mode(self) -> None:
        mode = self.cpu.get_reg8("al")
        self.video_mode = mode
        self.text_attr = 0x07
        self._clear_error()

    def _int10_set_palette(self) -> None:
        bh = self.cpu.get_reg8("bh")
        bl = self.cpu.get_reg8("bl")
        if bh == 0x00:
            self.background_attr = bl & 0x0F
        elif bh == 0x01:
            self.border_attr = bl & 0x0F
        self._clear_error()

    def _int10_write_char_attr(self) -> None:
        ch = self.cpu.get_reg8("al")
        attr = self.cpu.get_reg8("bl")
        count = self.cpu.get_reg16("cx")
        self.text_attr = attr
        payload = bytes([ch]) * count
        self._console_write(payload, attr_override=attr)
        self._clear_error()

    def _console_write(self, payload: bytes, attr_override: int | None = None) -> None:
        attr = self.text_attr if attr_override is None else attr_override
        ansi = self._ansi_from_attr(attr)
        text = payload.decode("ascii", errors="replace")
        if ansi:
            sys.stdout.write(ansi)
        sys.stdout.write(text)
        if ansi:
            sys.stdout.write("\x1b[0m")
        sys.stdout.flush()

    def _ansi_from_attr(self, attr: int) -> str:
        fg = attr & 0x0F
        bg = (attr >> 4) & 0x07
        fg_code = 30 + (fg & 0x07)
        bg_code = 40 + (bg & 0x07)
        bright = "1" if fg & 0x08 else "0"
        return f"\x1b[{bright};{fg_code};{bg_code}m"

    def _read_asciiz(self, segment: int, offset: int) -> str:
        addr = self.memory.phys(segment, offset)
        return self.memory.read_c_string(addr)

    def _allocate_handle(self, f: BinaryIO, mode: str) -> int:
        handle = self._next_handle
        self._next_handle += 1
        self._handles[handle] = HandleEntry(handle=handle, file=f, mode=mode)
        return handle

    def _resolve_path(self, name: str) -> str | None:
        name = name.strip().upper()
        if not name:
            return None
        parts = name.replace("/", "\\").split("\\")
        for part in parts:
            if not self._is_8_3(part):
                return None
        return os.path.join(self.root_dir, *parts)

    def _is_8_3(self, name: str) -> bool:
        if name in {".", ".."}:
            return False
        if "." in name:
            base, ext = name.split(".", 1)
        else:
            base, ext = name, ""
        if not (1 <= len(base) <= 8):
            return False
        if len(ext) > 3:
            return False
        allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789$%'-_@~`!(){}^#&"
        for ch in base:
            if ch not in allowed:
                return False
        for ch in ext:
            if ch not in allowed:
                return False
        return True
