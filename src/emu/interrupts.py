from __future__ import annotations

import os
import sys
import fnmatch
import time
from dataclasses import dataclass
from typing import BinaryIO

from .cpu import CPU, FLAG_CF, FLAG_ZF
from .memory import Memory

ERROR_FILE_NOT_FOUND = 0x02
ERROR_PATH_NOT_FOUND = 0x03
ERROR_ACCESS_DENIED = 0x05
ERROR_INVALID_HANDLE = 0x06
ERROR_INVALID_ACCESS = 0x0C
ERROR_INVALID_NAME = 0x03
ERROR_NO_MORE_FILES = 0x12


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
        self.cursor_row = 0
        self.cursor_col = 0
        self.dta_segment = cpu.ds
        self.dta_offset = 0x0080
        self._find_results: list[os.DirEntry] = []
        self._find_index = 0

    def int_21h(self) -> None:
        ah = self.cpu.get_reg8("ah")
        if ah == 0x02:
            self._int21_display_char()
        elif ah == 0x01:
            self._int21_read_char_echo()
        elif ah == 0x08:
            self._int21_read_char_no_echo()
        elif ah == 0x09:
            self._int21_display_string()
        elif ah == 0x0A:
            self._int21_buffered_input()
        elif ah == 0x0C:
            self._int21_clear_input()
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
        elif ah == 0x43:
            self._int21_file_attributes()
        elif ah == 0x47:
            self._int21_get_current_dir()
        elif ah == 0x19:
            self._int21_get_current_drive()
        elif ah == 0x4E:
            self._int21_find_first()
        elif ah == 0x4F:
            self._int21_find_next()
        elif ah == 0x57:
            self._int21_file_datetime()
        elif ah == 0x1A:
            self._int21_set_dta()
        elif ah == 0x4C:
            self._int21_exit()
        else:
            self._set_error(ERROR_INVALID_ACCESS)

    def int_10h(self) -> None:
        ah = self.cpu.get_reg8("ah")
        if ah == 0x00:
            self._int10_set_video_mode()
        elif ah == 0x0F:
            self._int10_get_video_mode()
        elif ah == 0x02:
            self._int10_set_cursor_pos()
        elif ah == 0x03:
            self._int10_get_cursor_pos()
        elif ah == 0x0B:
            self._int10_set_palette()
        elif ah == 0x09:
            self._int10_write_char_attr()
        elif ah == 0x0E:
            self._int10_teletype()
        else:
            self._set_error(ERROR_INVALID_ACCESS)

    def int_20h(self) -> None:
        self.cpu.exit_code = self.cpu.get_reg8("al")
        self.cpu.halted = True
        self._clear_error()

    def int_16h(self) -> None:
        ah = self.cpu.get_reg8("ah")
        if ah == 0x00:
            try:
                ch = sys.stdin.read(1)
            except Exception:
                ch = ""
            if not ch:
                ch = "\n"
            self.cpu.set_reg8("al", ord(ch[0]))
            self.cpu.set_reg8("ah", 0x00)
            self._clear_error()
            return
        if ah == 0x01:
            self.cpu.set_flag(FLAG_CF, False)
            self.cpu.set_flag(FLAG_ZF, True)
            return
        self._set_error(ERROR_INVALID_ACCESS)

    def int_1Ah(self) -> None:
        ah = self.cpu.get_reg8("ah")
        if ah == 0x00:
            now = time.localtime()
            seconds = now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec
            ticks = int(seconds * 18.2065)
            self.cpu.set_reg16("cx", (ticks >> 16) & 0xFFFF)
            self.cpu.set_reg16("dx", ticks & 0xFFFF)
            self.cpu.set_reg8("al", 0x00)
            self._clear_error()
            return
        if ah == 0x02:
            now = time.localtime()
            self.cpu.set_reg8("ch", self._to_bcd(now.tm_hour))
            self.cpu.set_reg8("cl", self._to_bcd(now.tm_min))
            self.cpu.set_reg8("dh", self._to_bcd(now.tm_sec))
            self._clear_error()
            return
        self._set_error(ERROR_INVALID_ACCESS)

    def _clear_error(self) -> None:
        self.cpu.set_flag(FLAG_CF, False)

    def _set_error(self, code: int) -> None:
        self.cpu.set_flag(FLAG_CF, True)
        self.cpu.set_reg16("ax", code)

    def _to_bcd(self, value: int) -> int:
        return ((value // 10) << 4) | (value % 10)

    def _int21_display_char(self) -> None:
        ch = self.cpu.get_reg8("dl")
        self._console_write(bytes([ch]))
        self._clear_error()

    def _int21_read_char_echo(self) -> None:
        try:
            ch = sys.stdin.read(1)
        except Exception:
            ch = ""
        if not ch:
            ch = "\n"
        self._console_write(ch.encode("ascii", errors="replace"))
        self.cpu.set_reg8("al", ord(ch[0]))
        self._clear_error()

    def _int21_read_char_no_echo(self) -> None:
        try:
            ch = sys.stdin.read(1)
        except Exception:
            ch = ""
        if not ch:
            ch = "\n"
        self.cpu.set_reg8("al", ord(ch[0]))
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

    def _int21_clear_input(self) -> None:
        func = self.cpu.get_reg8("al")
        if func == 0x01:
            self._int21_read_char_echo()
        elif func == 0x08:
            self._int21_read_char_no_echo()
        elif func == 0x0A:
            self._int21_buffered_input()
        else:
            self._int21_read_char_no_echo()

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

    def _int21_file_attributes(self) -> None:
        name = self._read_asciiz(self.cpu.ds, self.cpu.get_reg16("dx"))
        resolved = self._resolve_path(name)
        if resolved is None:
            self._set_error(ERROR_INVALID_NAME)
            return
        al = self.cpu.get_reg8("al")
        if al == 0x00:
            try:
                attr = 0x10 if os.path.isdir(resolved) else 0x20
            except OSError:
                self._set_error(ERROR_FILE_NOT_FOUND)
                return
            self.cpu.set_reg16("cx", attr)
            self._clear_error()
            return
        if al == 0x01:
            self._clear_error()
            return
        self._set_error(ERROR_INVALID_ACCESS)

    def _int21_file_datetime(self) -> None:
        handle = self.cpu.get_reg16("bx")
        entry = self._handles.get(handle)
        if entry is None:
            self._set_error(ERROR_INVALID_HANDLE)
            return
        try:
            stat = os.fstat(entry.file.fileno())
        except OSError:
            self._set_error(ERROR_ACCESS_DENIED)
            return
        mtime = int(stat.st_mtime)
        dos_date, dos_time = self._unix_to_dos_datetime(mtime)
        al = self.cpu.get_reg8("al")
        if al == 0x00:
            self.cpu.set_reg16("cx", dos_time)
            self.cpu.set_reg16("dx", dos_date)
            self._clear_error()
            return
        if al == 0x01:
            self._clear_error()
            return
        self._set_error(ERROR_INVALID_ACCESS)

    def _int21_get_current_dir(self) -> None:
        addr = self.memory.phys(self.cpu.ds, self.cpu.get_reg16("si"))
        path = "\\"
        self.memory.write_block(addr, path.encode("ascii"))
        self.memory.write8(addr + len(path), 0x00)
        self._clear_error()

    def _int21_get_current_drive(self) -> None:
        self.cpu.set_reg8("al", 2)
        self._clear_error()

    def _int21_set_dta(self) -> None:
        self.dta_segment = self.cpu.ds
        self.dta_offset = self.cpu.get_reg16("dx")
        self._clear_error()

    def _int21_find_first(self) -> None:
        pattern = self._read_asciiz(self.cpu.ds, self.cpu.get_reg16("dx"))
        resolved = self._resolve_path(pattern)
        if resolved is None:
            self._set_error(ERROR_INVALID_NAME)
            return
        base = os.path.dirname(resolved)
        mask = os.path.basename(resolved)
        try:
            entries = list(os.scandir(base))
        except FileNotFoundError:
            self._set_error(ERROR_PATH_NOT_FOUND)
            return
        self._find_results = [e for e in entries if fnmatch.fnmatch(e.name.upper(), mask.upper())]
        self._find_index = 0
        if not self._find_results:
            self._set_error(ERROR_NO_MORE_FILES)
            return
        self._write_dta(self._find_results[0])
        self._clear_error()

    def _int21_find_next(self) -> None:
        self._find_index += 1
        if self._find_index >= len(self._find_results):
            self._set_error(ERROR_NO_MORE_FILES)
            return
        self._write_dta(self._find_results[self._find_index])
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

    def _int10_get_video_mode(self) -> None:
        self.cpu.set_reg8("al", self.video_mode)
        self.cpu.set_reg8("ah", 80)
        self.cpu.set_reg8("bh", 0)
        self._clear_error()

    def _int10_set_cursor_pos(self) -> None:
        self.cursor_row = self.cpu.get_reg8("dh")
        self.cursor_col = self.cpu.get_reg8("dl")
        self._clear_error()

    def _int10_get_cursor_pos(self) -> None:
        self.cpu.set_reg8("dh", self.cursor_row)
        self.cpu.set_reg8("dl", self.cursor_col)
        self.cpu.set_reg8("bh", 0)
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

    def _int10_teletype(self) -> None:
        ch = self.cpu.get_reg8("al")
        self._console_write(bytes([ch]))
        if ch == 0x0A:
            self.cursor_row = (self.cursor_row + 1) % 25
            self.cursor_col = 0
        else:
            self.cursor_col = (self.cursor_col + 1) % 80
        self._clear_error()

    def _console_write(self, payload: bytes, attr_override: int | None = None) -> None:
        attr = self.text_attr if attr_override is None else attr_override
        use_ansi = False
        try:
            use_ansi = bool(getattr(sys.stdout, "isatty", lambda: False)())
        except Exception:
            use_ansi = False
        ansi = self._ansi_from_attr(attr) if use_ansi else ""
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

    def _unix_to_dos_datetime(self, timestamp: int) -> tuple[int, int]:
        from datetime import datetime

        dt = datetime.fromtimestamp(timestamp)
        date = ((dt.year - 1980) << 9) | (dt.month << 5) | dt.day
        time = (dt.hour << 11) | (dt.minute << 5) | (dt.second // 2)
        return date & 0xFFFF, time & 0xFFFF

    def _write_dta(self, entry: os.DirEntry) -> None:
        addr = self.memory.phys(self.dta_segment, self.dta_offset)
        try:
            stat = entry.stat()
        except OSError:
            stat = None
        attr = 0x10 if entry.is_dir() else 0x20
        size = stat.st_size if stat else 0
        mtime = int(stat.st_mtime) if stat else 0
        dos_date, dos_time = self._unix_to_dos_datetime(mtime)

        self.memory.write8(addr + 0x15, attr)
        self.memory.write16(addr + 0x16, dos_time)
        self.memory.write16(addr + 0x18, dos_date)
        self.memory.write16(addr + 0x1A, size & 0xFFFF)
        self.memory.write16(addr + 0x1C, (size >> 16) & 0xFFFF)

        name = entry.name.upper()
        name_bytes = name.encode("ascii", errors="replace")[:12]
        self.memory.write_block(addr + 0x1E, name_bytes)
        self.memory.write8(addr + 0x1E + len(name_bytes), 0x00)

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
