from __future__ import annotations

from pathlib import Path
import sys
import builtins
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from emu.emulator import Emulator, EmulatorConfig
from emu.cpu import FLAG_CF, FLAG_PF, FLAG_AF, FLAG_ZF, FLAG_SF, FLAG_OF, FLAG_IF, FLAG_DF


class TextWriter:
    def __init__(self, widget: tk.Text) -> None:
        self.widget = widget

    def write(self, text: str) -> None:
        self.widget.configure(state="normal")
        self.widget.insert("end", text)
        self.widget.see("end")
        self.widget.configure(state="disabled")

    def flush(self) -> None:
        return


class StdIORedirect:
    def __init__(self, output_widget: tk.Text, root: tk.Tk) -> None:
        self.output_widget = output_widget
        self.root = root
        self._old_stdout = None
        self._old_input = None

    def __enter__(self) -> None:
        self._old_stdout = sys.stdout
        self._old_input = builtins.input
        sys.stdout = TextWriter(self.output_widget)
        builtins.input = self._input_dialog

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._old_stdout is not None:
            sys.stdout = self._old_stdout
        if self._old_input is not None:
            builtins.input = self._old_input

    def _input_dialog(self, prompt: str | None = None) -> str:
        prompt_text = prompt or "Input"
        return simpledialog.askstring("Input", prompt_text, parent=self.root) or ""


class EmulatorUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("MASM 6.11 Emulator")

        self.emu: Emulator | None = None
        self.program = None
        self.breakpoints: set[int] = set()
        self.line_to_ip: dict[int, int] = {}
        self._last_code = ""
        self.mem_window: tk.Toplevel | None = None
        self.stack_window: tk.Toplevel | None = None
        self.mem_text: tk.Text | None = None
        self.stack_text: tk.Text | None = None
        self.reg_fields: dict[str, ttk.Entry] = {}
        self.reg_hl_fields: dict[str, tuple[ttk.Entry, ttk.Entry]] = {}
        self.flags_var = tk.StringVar(value="FLAGS=")
        self.current_var = tk.StringVar(value="")
        self.mem_off_var = tk.StringVar(value="0000")
        self.mem_len_var = tk.StringVar(value="256")
        self.mem_auto_var = tk.BooleanVar(value=True)
        self.stack_len_var = tk.StringVar(value="128")

        self._build_ui()
        self._load_example()
        self._schedule_auto_refresh()

    def _build_ui(self) -> None:
        self.root.geometry("1100x700")
        self.root.minsize(900, 600)

        main = ttk.Frame(self.root, padding=8)
        main.pack(fill="both", expand=True)

        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        code_frame = ttk.LabelFrame(main, text="Code")
        code_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        code_frame.rowconfigure(0, weight=1)
        code_frame.columnconfigure(1, weight=1)

        self.code_gutter = tk.Canvas(code_frame, width=28, highlightthickness=0, background="#1e1e1e")
        self.code_gutter.grid(row=0, column=0, sticky="ns")

        self.code_text = tk.Text(code_frame, font=("Consolas", 11), wrap="none")
        self.code_text.grid(row=0, column=1, sticky="nsew")

        code_scroll = ttk.Scrollbar(code_frame, orient="vertical", command=self._on_code_scrollbar)
        code_scroll.grid(row=0, column=2, sticky="ns")
        self.code_text.configure(yscrollcommand=lambda *args: self._on_code_scroll(args, code_scroll))

        self.code_text.bind("<KeyRelease>", lambda _event: self._refresh_gutter())
        self.code_text.bind("<MouseWheel>", lambda _event: self._refresh_gutter())
        self.code_gutter.bind("<Button-1>", self._toggle_breakpoint_gutter)

        output_frame = ttk.LabelFrame(main, text="Output")
        output_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)

        self.output_text = tk.Text(output_frame, font=("Consolas", 11), state="disabled")
        self.output_text.grid(row=0, column=0, sticky="nsew")

        side = ttk.Frame(main)
        side.grid(row=0, column=1, rowspan=2, sticky="nsew")
        side.rowconfigure(2, weight=1)

        controls = ttk.LabelFrame(side, text="Controls")
        controls.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        btn_frame = ttk.Frame(controls)
        btn_frame.pack(fill="x", padx=8, pady=8)

        ttk.Button(btn_frame, text="Load", command=self._load_program).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Run", command=self._run_program).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Step", command=self._step_program).pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Clear Output", command=self._clear_output).pack(fill="x", pady=2)

        bp_frame = ttk.LabelFrame(side, text="Breakpoints")
        bp_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 8))

        self.bp_entry = ttk.Entry(bp_frame)
        self.bp_entry.pack(fill="x", padx=8, pady=(8, 4))

        bp_btns = ttk.Frame(bp_frame)
        bp_btns.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(bp_btns, text="Add", command=self._add_breakpoint).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(bp_btns, text="Clear", command=self._clear_breakpoints).pack(side="left", expand=True, fill="x")

        self.bp_list = tk.Listbox(bp_frame, height=6)
        self.bp_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        regs_frame = ttk.LabelFrame(side, text="Registers")
        regs_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        regs_frame.columnconfigure(1, weight=1)
        regs_frame.columnconfigure(2, weight=1)

        ttk.Label(regs_frame, text="").grid(row=0, column=0, padx=(8, 2))
        ttk.Label(regs_frame, text="H").grid(row=0, column=1)
        ttk.Label(regs_frame, text="L").grid(row=0, column=2)

        self._add_reg_hl(regs_frame, "AX", 1)
        self._add_reg_hl(regs_frame, "BX", 2)
        self._add_reg_hl(regs_frame, "CX", 3)
        self._add_reg_hl(regs_frame, "DX", 4)

        self._add_reg16(regs_frame, "CS", 5)
        self._add_reg16(regs_frame, "IP", 6)
        self._add_reg16(regs_frame, "SS", 7)
        self._add_reg16(regs_frame, "SP", 8)
        self._add_reg16(regs_frame, "BP", 9)
        self._add_reg16(regs_frame, "SI", 10)
        self._add_reg16(regs_frame, "DI", 11)
        self._add_reg16(regs_frame, "DS", 12)
        self._add_reg16(regs_frame, "ES", 13)

        flags_label = ttk.Label(regs_frame, textvariable=self.flags_var, anchor="w")
        flags_label.grid(row=14, column=0, columnspan=3, sticky="w", padx=8, pady=(4, 0))

        current_label = ttk.Label(regs_frame, textvariable=self.current_var, anchor="w")
        current_label.grid(row=15, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 6))

        view_frame = ttk.LabelFrame(side, text="Viewers")
        view_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
        view_frame.columnconfigure(0, weight=1)
        ttk.Button(view_frame, text="Open Memory Viewer", command=self._open_memory_viewer).pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(view_frame, text="Open Stack Viewer", command=self._open_stack_viewer).pack(fill="x", padx=8, pady=(0, 8))

        self.status_var = tk.StringVar(value="Ready")
        status = ttk.Label(side, textvariable=self.status_var, anchor="w")
        status.grid(row=4, column=0, sticky="ew", pady=(8, 0))

    def _load_example(self) -> None:
        example = Path("examples/hello.asm")
        if example.exists():
            self.code_text.insert("1.0", example.read_text(encoding="utf-8"))

    def _add_reg_hl(self, parent: ttk.Frame, name: str, row: int) -> None:
        ttk.Label(parent, text=name).grid(row=row, column=0, sticky="w", padx=8, pady=2)
        h = ttk.Entry(parent, width=4, justify="center", state="readonly")
        l = ttk.Entry(parent, width=4, justify="center", state="readonly")
        h.grid(row=row, column=1, sticky="ew", padx=(0, 4), pady=2)
        l.grid(row=row, column=2, sticky="ew", padx=(0, 8), pady=2)
        self.reg_hl_fields[name] = (h, l)

    def _add_reg16(self, parent: ttk.Frame, name: str, row: int) -> None:
        ttk.Label(parent, text=name).grid(row=row, column=0, sticky="w", padx=8, pady=2)
        entry = ttk.Entry(parent, width=8, justify="center", state="readonly")
        entry.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(0, 8), pady=2)
        self.reg_fields[name] = entry

    def _open_memory_viewer(self) -> None:
        if self.mem_window is not None and self.mem_window.winfo_exists():
            self.mem_window.lift()
            return
        self.mem_window = tk.Toplevel(self.root)
        self.mem_window.title("Memory Viewer")
        self.mem_window.protocol("WM_DELETE_WINDOW", self._close_memory_viewer)

        mem_frame = ttk.Frame(self.mem_window, padding=8)
        mem_frame.pack(fill="both", expand=True)
        mem_frame.columnconfigure(1, weight=1)

        ttk.Label(mem_frame, text="Addr (DS):").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
        addr_frame = ttk.Frame(mem_frame)
        addr_frame.grid(row=0, column=1, sticky="w", pady=(0, 6))
        vcmd = (self.root.register(self._validate_hex_offset), "%P")
        mem_off_entry = ttk.Entry(addr_frame, textvariable=self.mem_off_var, width=6, validate="key", validatecommand=vcmd)
        mem_off_entry.pack(side="left")
        mem_off_entry.bind("<FocusOut>", lambda _event: self._normalize_offset())

        ttk.Label(mem_frame, text="Len").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
        ttk.Entry(mem_frame, textvariable=self.mem_len_var, width=8).grid(row=1, column=1, sticky="w", pady=(0, 6))

        ttk.Checkbutton(mem_frame, text="Auto refresh", variable=self.mem_auto_var, command=self._update_memory_view).grid(
            row=1, column=1, sticky="e", pady=(0, 6)
        )

        self.mem_text = tk.Text(mem_frame, font=("Consolas", 10), state="disabled", height=18)
        self.mem_text.grid(row=2, column=0, columnspan=2, sticky="nsew")
        mem_frame.rowconfigure(2, weight=1)
        self._update_memory_view()

    def _close_memory_viewer(self) -> None:
        if self.mem_window is not None:
            self.mem_window.destroy()
        self.mem_window = None
        self.mem_text = None

    def _open_stack_viewer(self) -> None:
        if self.stack_window is not None and self.stack_window.winfo_exists():
            self.stack_window.lift()
            return
        self.stack_window = tk.Toplevel(self.root)
        self.stack_window.title("Stack Viewer")
        self.stack_window.protocol("WM_DELETE_WINDOW", self._close_stack_viewer)

        stack_frame = ttk.Frame(self.stack_window, padding=8)
        stack_frame.pack(fill="both", expand=True)
        stack_frame.columnconfigure(1, weight=1)

        ttk.Label(stack_frame, text="Len").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
        ttk.Entry(stack_frame, textvariable=self.stack_len_var, width=8).grid(row=0, column=1, sticky="w", pady=(0, 6))

        self.stack_text = tk.Text(stack_frame, font=("Consolas", 10), state="disabled", height=14)
        self.stack_text.grid(row=1, column=0, columnspan=2, sticky="nsew")
        stack_frame.rowconfigure(1, weight=1)
        self._update_stack_view()

    def _close_stack_viewer(self) -> None:
        if self.stack_window is not None:
            self.stack_window.destroy()
        self.stack_window = None
        self.stack_text = None

    def _clear_output(self) -> None:
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.configure(state="disabled")

    def _load_program(self) -> None:
        code = self.code_text.get("1.0", "end-1c")
        self.emu = Emulator(EmulatorConfig())
        try:
            self.program = self.emu.load_asm(code)
        except Exception as exc:
            messagebox.showerror("Parse error", str(exc))
            self.program = None
            return
        self.breakpoints = {bp for bp in self.breakpoints if bp < len(self.program.instructions)}
        self.line_to_ip = {}
        for idx, instr in enumerate(self.program.instructions):
            self.line_to_ip.setdefault(instr.line, idx)
        self._last_code = code
        self._refresh_breakpoint_list()
        self._update_state()
        self._refresh_gutter()
        self._update_memory_view()
        self._update_stack_view()
        self.status_var.set("Program loaded")

    def _ensure_loaded(self) -> bool:
        code = self.code_text.get("1.0", "end-1c")
        if self.emu is None or self.program is None or code != self._last_code:
            self._load_program()
        return self.program is not None

    def _run_program(self) -> None:
        if not self._ensure_loaded():
            return
        if self.emu is None:
            return
        try:
            with StdIORedirect(self.output_text, self.root):
                self.emu.run_until_breakpoint(self.breakpoints)
        except Exception as exc:
            messagebox.showerror("Runtime error", str(exc))
        self._update_state()
        self._update_memory_view()
        self._update_stack_view()
        if self.emu and self.emu.cpu.halted:
            self.status_var.set("Program halted")
        elif self.emu and self.emu.cpu.ip in self.breakpoints:
            self.status_var.set(f"Breakpoint at IP {self.emu.cpu.ip}")

    def _step_program(self) -> None:
        if not self._ensure_loaded():
            return
        if self.emu is None:
            return
        try:
            with StdIORedirect(self.output_text, self.root):
                self.emu.step()
        except Exception as exc:
            messagebox.showerror("Runtime error", str(exc))
        self._update_state()
        self._update_memory_view()
        self._update_stack_view()

    def _add_breakpoint(self) -> None:
        if not self._ensure_loaded():
            return
        token = self.bp_entry.get().strip().lower()
        if not token:
            return
        index = None
        if self.program and token in self.program.labels:
            index = self.program.labels[token]
        elif token.startswith("line "):
            try:
                line_num = int(token.split(None, 1)[1])
            except ValueError:
                line_num = None
            if line_num is not None:
                index = self.line_to_ip.get(line_num)
        else:
            try:
                index = int(token)
            except ValueError:
                index = None
        if index is None or not self.program or index < 0 or index >= len(self.program.instructions):
            messagebox.showwarning("Breakpoint", "Invalid breakpoint (use label, IP index, or 'line N')")
            return
        self.breakpoints.add(index)
        self._refresh_breakpoint_list()
        self._refresh_gutter()

    def _clear_breakpoints(self) -> None:
        self.breakpoints.clear()
        self._refresh_breakpoint_list()
        self._refresh_gutter()

    def _refresh_breakpoint_list(self) -> None:
        self.bp_list.delete(0, "end")
        for bp in sorted(self.breakpoints):
            label = self._label_for_ip(bp)
            self.bp_list.insert("end", f"{bp} {label}")

    def _label_for_ip(self, ip: int) -> str:
        if not self.program:
            return ""
        for name, idx in self.program.labels.items():
            if idx == ip:
                return f"({name})"
        return ""

    def _update_state(self) -> None:
        if self.emu is None:
            return
        regs = self.emu.cpu.dump()
        flags = self.emu.cpu.flags
        flag_str = " ".join(
            [
                "CF" if flags & FLAG_CF else "cf",
                "PF" if flags & FLAG_PF else "pf",
                "AF" if flags & FLAG_AF else "af",
                "ZF" if flags & FLAG_ZF else "zf",
                "SF" if flags & FLAG_SF else "sf",
                "OF" if flags & FLAG_OF else "of",
                "IF" if flags & FLAG_IF else "if",
                "DF" if flags & FLAG_DF else "df",
            ]
        )
        current = ""
        if self.program and 0 <= self.emu.cpu.ip < len(self.program.instructions):
            instr = self.program.instructions[self.emu.cpu.ip]
            current = f"IP {self.emu.cpu.ip} | Line {instr.line}: {instr.raw.strip()}"
        self.flags_var.set(f"FLAGS={regs['FLAGS']:04X} [{flag_str}]")
        self.current_var.set(current)
        for name in ("AX", "BX", "CX", "DX"):
            h_entry, l_entry = self.reg_hl_fields.get(name, (None, None))
            if h_entry and l_entry:
                value = regs[name]
                self._set_entry(h_entry, f"{(value >> 8) & 0xFF:02X}")
                self._set_entry(l_entry, f"{value & 0xFF:02X}")
        for name in ("CS", "IP", "SS", "SP", "BP", "SI", "DI", "DS", "ES"):
            entry = self.reg_fields.get(name)
            if entry:
                self._set_entry(entry, f"{regs[name]:04X}")
        self._highlight_current_line()
        self._refresh_gutter()

    def _highlight_current_line(self) -> None:
        self.code_text.tag_remove("current_line", "1.0", "end")
        if self.program and self.emu and 0 <= self.emu.cpu.ip < len(self.program.instructions):
            line = self.program.instructions[self.emu.cpu.ip].line
            self.code_text.tag_add("current_line", f"{line}.0", f"{line}.0 lineend")
            self.code_text.tag_configure("current_line", background="#fff4b8")

    def _on_code_scroll(self, args, scrollbar: ttk.Scrollbar) -> None:
        scrollbar.set(*args)
        self._refresh_gutter()

    def _on_code_scrollbar(self, *args) -> None:
        self.code_text.yview(*args)
        self._refresh_gutter()

    def _toggle_breakpoint_gutter(self, event: tk.Event) -> None:
        if not self._ensure_loaded():
            return
        index = self.code_text.index(f"@0,{event.y}")
        line = int(index.split(".")[0])
        ip = self.line_to_ip.get(line)
        if ip is None:
            return
        if ip in self.breakpoints:
            self.breakpoints.remove(ip)
        else:
            self.breakpoints.add(ip)
        self._refresh_breakpoint_list()
        self._refresh_gutter()

    def _refresh_gutter(self) -> None:
        self.code_gutter.delete("all")
        line_index = self.code_text.index("@0,0")
        while True:
            info = self.code_text.dlineinfo(line_index)
            if info is None:
                break
            y = info[1]
            line = int(line_index.split(".")[0])
            ip = self.line_to_ip.get(line)
            if ip is not None and ip in self.breakpoints:
                self.code_gutter.create_oval(8, y + 4, 20, y + 16, fill="#ff4d4d", outline="")
            if self.emu and self.program and 0 <= self.emu.cpu.ip < len(self.program.instructions):
                if line == self.program.instructions[self.emu.cpu.ip].line:
                    self.code_gutter.create_polygon(2, y + 5, 2, y + 15, 10, y + 10, fill="#58a6ff", outline="")
            line_index = self.code_text.index(f"{line_index}+1line")

    def _update_memory_view(self) -> None:
        if self.emu is None or self.mem_text is None or self.mem_window is None:
            return
        try:
            length = int(self.mem_len_var.get().strip(), 10)
        except ValueError:
            length = 256
        if length <= 0:
            length = 256
        base_off = self._parse_hex_offset(self.mem_off_var.get())
        lines = self._format_memory_block(self.emu.cpu.ds, base_off, length)
        self.mem_text.configure(state="normal")
        self.mem_text.delete("1.0", "end")
        self.mem_text.insert("end", "\n".join(lines))
        self.mem_text.configure(state="disabled")

    def _update_stack_view(self) -> None:
        if self.emu is None or self.stack_text is None or self.stack_window is None:
            return
        try:
            length = int(self.stack_len_var.get().strip(), 10)
        except ValueError:
            length = 128
        if length <= 0:
            length = 128
        sp = self.emu.cpu.sp & 0xFFFF
        lines = [f"[SS:{self.emu.cpu.ss:04X}] SP={sp:04X}"]
        lines.extend(self._format_memory_block(self.emu.cpu.ss, sp, length))
        self.stack_text.configure(state="normal")
        self.stack_text.delete("1.0", "end")
        self.stack_text.insert("end", "\n".join(lines))
        self.stack_text.configure(state="disabled")

    def _format_memory_block(self, seg: int, off: int, length: int) -> list[str]:
        base = self.emu.memory.phys(seg, off)
        data = self.emu.memory.read_block(base, min(length, 4096))
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i : i + 16]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{(off + i) & 0xFFFF:04X}: {hex_part:<47} {ascii_part}")
        return lines

    def _parse_hex_offset(self, token: str) -> int:
        token = token.strip()
        if not token:
            return 0
        try:
            return int(token, 16) & 0xFFFF
        except ValueError:
            return 0

    def _validate_hex_offset(self, proposed: str) -> bool:
        if proposed == "":
            return True
        if len(proposed) > 4:
            return False
        return all(ch in "0123456789abcdefABCDEF" for ch in proposed)

    def _normalize_offset(self) -> None:
        value = self.mem_off_var.get().strip()
        if not value:
            self.mem_off_var.set("0000")
            return
        if not self._validate_hex_offset(value):
            self.mem_off_var.set("0000")
            return
        self.mem_off_var.set(value.upper().zfill(4))
        self._update_memory_view()

    def _schedule_auto_refresh(self) -> None:
        if self.mem_auto_var.get():
            self._update_memory_view()
            self._update_stack_view()
        self.root.after(250, self._schedule_auto_refresh)

    def _set_entry(self, entry: ttk.Entry, value: str) -> None:
        entry.configure(state="normal")
        entry.delete(0, "end")
        entry.insert(0, value)
        entry.configure(state="readonly")


def main() -> None:
    root = tk.Tk()
    EmulatorUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
