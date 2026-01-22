from __future__ import annotations

from pathlib import Path
import sys
import builtins
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from emu.emulator import Emulator, EmulatorConfig
from emu.cpu import FLAG_CF, FLAG_ZF, FLAG_SF, FLAG_OF, FLAG_IF, FLAG_DF


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

        state_frame = ttk.LabelFrame(side, text="State")
        state_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        state_frame.rowconfigure(0, weight=1)
        state_frame.columnconfigure(0, weight=1)

        self.state_text = tk.Text(state_frame, font=("Consolas", 10), state="disabled", height=10)
        self.state_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        mem_frame = ttk.LabelFrame(side, text="Memory Viewer")
        mem_frame.grid(row=3, column=0, sticky="nsew")
        mem_frame.columnconfigure(1, weight=1)

        ttk.Label(mem_frame, text="Addr").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        self.mem_addr_var = tk.StringVar(value="DS:0000")
        ttk.Entry(mem_frame, textvariable=self.mem_addr_var).grid(row=0, column=1, sticky="ew", padx=8, pady=(8, 2))

        ttk.Label(mem_frame, text="Len").grid(row=1, column=0, sticky="w", padx=8, pady=(0, 8))
        self.mem_len_var = tk.StringVar(value="256")
        ttk.Entry(mem_frame, textvariable=self.mem_len_var, width=8).grid(row=1, column=1, sticky="w", padx=8, pady=(0, 8))

        self.mem_auto_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(mem_frame, text="Auto refresh", variable=self.mem_auto_var, command=self._update_memory_view).grid(
            row=1, column=1, sticky="e", padx=8, pady=(0, 8)
        )

        self.mem_text = tk.Text(mem_frame, font=("Consolas", 10), state="disabled", height=10)
        self.mem_text.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=8, pady=(0, 8))
        mem_frame.rowconfigure(2, weight=1)

        self.status_var = tk.StringVar(value="Ready")
        status = ttk.Label(side, textvariable=self.status_var, anchor="w")
        status.grid(row=4, column=0, sticky="ew", pady=(8, 0))

    def _load_example(self) -> None:
        example = Path("examples/hello.asm")
        if example.exists():
            self.code_text.insert("1.0", example.read_text(encoding="utf-8"))

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
        lines = [
            f"AX={regs['AX']:04X}  BX={regs['BX']:04X}  CX={regs['CX']:04X}  DX={regs['DX']:04X}",
            f"SP={regs['SP']:04X}  BP={regs['BP']:04X}  SI={regs['SI']:04X}  DI={regs['DI']:04X}",
            f"CS={regs['CS']:04X}  DS={regs['DS']:04X}  ES={regs['ES']:04X}  SS={regs['SS']:04X}",
            f"FLAGS={regs['FLAGS']:04X} [{flag_str}]",
            current,
        ]
        self.state_text.configure(state="normal")
        self.state_text.delete("1.0", "end")
        self.state_text.insert("end", "\n".join(lines))
        self.state_text.configure(state="disabled")
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
        if self.emu is None or self.mem_text is None:
            return
        try:
            length = int(self.mem_len_var.get().strip(), 10)
        except ValueError:
            length = 256
        if length <= 0:
            length = 256
        seg, off = self._parse_address(self.mem_addr_var.get().strip())
        base = self.emu.memory.phys(seg, off)
        data = self.emu.memory.read_block(base, min(length, 4096))
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i : i + 16]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{(off + i) & 0xFFFF:04X}: {hex_part:<47} {ascii_part}")
        self.mem_text.configure(state="normal")
        self.mem_text.delete("1.0", "end")
        self.mem_text.insert("end", "\n".join(lines))
        self.mem_text.configure(state="disabled")

    def _parse_address(self, token: str) -> tuple[int, int]:
        if not token:
            return 0, 0
        token = token.lower()
        if ":" in token:
            seg_txt, off_txt = token.split(":", 1)
            if seg_txt in {"cs", "ds", "es", "ss"} and self.emu:
                seg = self.emu.cpu.get_reg16(seg_txt)
            else:
                seg = self._parse_number(seg_txt)
            off = self._parse_number(off_txt)
            return seg & 0xFFFF, off & 0xFFFF
        if token in {"cs", "ds", "es", "ss"} and self.emu:
            return self.emu.cpu.get_reg16(token), 0
        return self.emu.cpu.ds if self.emu else 0, self._parse_number(token)

    def _parse_number(self, token: str) -> int:
        token = token.strip().lower()
        if token.endswith("h"):
            return int(token[:-1], 16)
        if token.startswith("0x"):
            return int(token, 16)
        if token.endswith("b"):
            return int(token[:-1], 2)
        return int(token or "0", 10)

    def _schedule_auto_refresh(self) -> None:
        if self.mem_auto_var.get():
            self._update_memory_view()
        self.root.after(250, self._schedule_auto_refresh)


def main() -> None:
    root = tk.Tk()
    EmulatorUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
