from __future__ import annotations

import argparse
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from mpinyin_dat import FormatError
from .dat_service import default_export_name, export_dat, import_dat
from .session import Session, generate_codes, parse_paste
from .workspace_store import save_workspace, workspace_path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACES = ROOT / "workspaces"
OUTPUT = ROOT / "output"

MODE_LABELS = {"self_study": "自学习词库", "user_phrase": "自定义短语"}
CODE_STYLE_LABELS = {"full": "全拼", "initials": "首字母"}
CODE_STYLE_VALUES = {label: value for value, label in CODE_STYLE_LABELS.items()}

USAGE_TEXT = """使用说明

1. 先在左侧选择“自学习词库”或“自定义短语”。
2. 点击“新建词库”从空白词库开始，或点击“导入词库”读取已有 DAT 文件。
3. 可新增、双击编辑、粘贴导入、一键编码和去重；编辑结果会自动保存为本地缓存。
4. 点击“导出词库”生成新的 DAT 文件。程序不会覆盖导入的原 DAT，也不会自动写入 Windows 输入法目录。
5. 导入前请先在微软拼音设置中备份原有词库，并在导入导出文件后自行确认结果。

提示：本工具支持的两类 DAT 文件用途不同，请勿混用。"""


def show_usage(parent: tk.Misc) -> None:
    """Display the safety-focused quick-start instructions."""
    messagebox.showinfo("使用说明", USAGE_TEXT, parent=parent)


class DictionaryApp(ttk.Frame):
    """Two independent workspaces: one tab per Microsoft Pinyin DAT type."""

    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=10)
        self.master = master
        self.sessions: dict[str, Session | None] = {"self_study": None, "user_phrase": None}
        self.metadata: dict[str, dict[str, str]] = {"self_study": {}, "user_phrase": {}}
        self.workspaces: dict[str, Path | None] = {"self_study": None, "user_phrase": None}
        self.queries: dict[str, tk.StringVar] = {kind: tk.StringVar() for kind in self.sessions}
        self.code_styles: dict[str, tk.StringVar] = {kind: tk.StringVar(value=CODE_STYLE_LABELS["full"]) for kind in self.sessions}
        self.status = tk.StringVar(value="请选择工作模式后新建词库、导入词库或载入缓存")
        self.current_kind = "self_study"
        self.pages: dict[str, ttk.Frame] = {}
        self.sidebars: dict[str, ttk.Frame] = {}
        self._build()
        self.pack(fill="both", expand=True)

    @property
    def session(self) -> Session | None:
        return self.sessions[self.current_kind]

    @property
    def selected_code_style(self) -> str:
        return CODE_STYLE_VALUES[self.code_styles[self.current_kind].get()]

    def _build(self) -> None:
        self.master.title("微软拼音词库管理器")
        # Keep the initial window compact; minimum height is calculated after every sidebar exists.
        self.master.geometry("720x678")
        self.master.minsize(700, 678)

        # Do not use PanedWindow here: its sash can leave a stray separator line at the top-right.
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        # ttk.Notebook cannot place its native tabs vertically.  Build a dedicated tab strip
        # instead: the labels look and behave as tabs, while the pages remain independent.
        tab_strip = tk.Frame(body, width=160, bg="#f0f0f0", highlightthickness=0)
        tab_strip.pack(side="left", fill="y")
        content = ttk.Frame(body)
        content.pack(side="left", fill="both", expand=True)
        tk.Label(tab_strip, text="工作模式", anchor="w", bg="#f0f0f0", padx=10, pady=8).pack(fill="x")
        self.mode_tabs: dict[str, tk.Label] = {}
        for kind, title in MODE_LABELS.items():
            tab = tk.Label(tab_strip, text=title, anchor="w", padx=14, pady=10, cursor="hand2", relief="flat", bd=1)
            tab.pack(fill="x", pady=(0, 2))
            tab.bind("<Button-1>", lambda _event, k=kind: self.show_page(k))
            tab.bind("<Return>", lambda _event, k=kind: self.show_page(k))
            tab.bind("<space>", lambda _event, k=kind: self.show_page(k))
            tab.configure(takefocus=True)
            self.mode_tabs[kind] = tab
        for kind in MODE_LABELS:
            page = ttk.Frame(content, padding=8)
            self.pages[kind] = page
            self._build_page(kind, page)
        footer = ttk.Frame(self)
        # Keep the footer close to the workspace; the status text is shown in a
        # flat, read-only entry rather than a recessed status-bar groove.
        footer.pack(fill="x", pady=(2, 0))
        ttk.Button(footer, text="使用说明", command=lambda: show_usage(self.master)).pack(side="right")
        status_box = tk.Entry(
            footer,
            textvariable=self.status,
            state="readonly",
            relief="solid",
            bd=1,
            highlightthickness=0,
            readonlybackground="white",
            fg="#404040",
        )
        status_box.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._set_window_minimums()
        self.show_page(self.current_kind)

    def _set_window_minimums(self) -> None:
        self.update_idletasks()
        sidebar_height = max(sidebar.winfo_reqheight() for sidebar in self.sidebars.values())
        status_height = self.winfo_reqheight() - max(page.winfo_reqheight() for page in self.pages.values())
        self.master.minsize(700, max(678, sidebar_height + status_height + 16))

    def _build_page(self, kind: str, page: ttk.Frame) -> None:
        body = ttk.Frame(page)
        body.pack(fill="both", expand=True)
        # The operation area is fixed at 150px; a normal frame avoids a PanedWindow sash line.
        sidebar = ttk.Frame(body, padding=(0, 0, 10, 0), width=160)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self.sidebars[kind] = sidebar
        main = ttk.LabelFrame(body, text="编码区", padding=8)
        main.pack(side="left", fill="both", expand=True)

        file_group = ttk.LabelFrame(sidebar, text="文件", padding=6, width=150)
        file_group.pack(fill="x", pady=(0, 8))
        for text, command in [
            ("新建词库", lambda k=kind: self.new_dictionary(k)),
            ("导入词库", lambda k=kind: self.open_dat(k)),
            ("载入缓存", lambda k=kind: self.open_workspace(k)),
            ("导出词库", lambda k=kind: self.export(k)),
        ]:
            ttk.Button(file_group, text=text, command=command).pack(fill="x", pady=2)

        edit_group = ttk.LabelFrame(sidebar, text="编辑", padding=6, width=150)
        edit_group.pack(fill="x", pady=(0, 8))
        for text, command in [
            ("新增", lambda k=kind: self.quick_add(k)),
            ("删除", lambda k=kind: self.delete_selected(k)),
            ("清空", lambda k=kind: self.clear_all(k)),
            ("粘贴导入", lambda k=kind: self.paste_import(k)),
            ("一键编码", lambda k=kind: self.fill_codes(k)),
            ("一键去重", lambda k=kind: self.deduplicate(k)),
        ]:
            ttk.Button(edit_group, text=text, command=command).pack(fill="x", pady=2)

        if kind == "user_phrase":
            code_group = ttk.LabelFrame(sidebar, text="自动编码", padding=6, width=150)
            code_group.pack(fill="x", pady=(0, 8))
            ttk.Combobox(code_group, textvariable=self.code_styles[kind], values=list(CODE_STYLE_VALUES), state="readonly", width=12).pack(fill="x")
        else:
            code_group = ttk.LabelFrame(sidebar, text="自动编码", padding=6, width=150)
            code_group.pack(fill="x", pady=(0, 8))
            ttk.Label(code_group, text="固定使用全拼").pack(anchor="w")

        history_group = ttk.LabelFrame(sidebar, text="历史", padding=6, width=150)
        history_group.pack(fill="x", pady=(0, 8))
        for text, command in [("撤销", lambda k=kind: self.undo(k)), ("重做", lambda k=kind: self.redo(k))]:
            ttk.Button(history_group, text=text, command=command).pack(fill="x", pady=2)

        search_group = ttk.LabelFrame(sidebar, text="搜索", padding=6, width=150)
        search_group.pack(fill="x")
        ttk.Entry(search_group, textvariable=self.queries[kind]).pack(fill="x")
        self.queries[kind].trace_add("write", lambda *_args, k=kind: self.refresh(k))

        table_frame = ttk.Frame(main)
        table_frame.pack(fill="both", expand=True)
        columns = ("word", "pinyin", "rank")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        tree.heading("word", text="词条")
        tree.heading("pinyin", text="编码")
        tree.heading("rank", text="排序")
        tree.column("word", width=220, minwidth=100)
        tree.column("pinyin", width=275, minwidth=125)
        tree.column("rank", width=110, minwidth=55, anchor="center")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        tree.bind("<Double-1>", lambda event, k=kind: self.begin_edit(k, event))
        table_frame.bind("<Configure>", lambda event, k=kind: self.resize_columns(k, event))
        setattr(self, f"tree_{kind}", tree)

        self.master.bind("<Control-z>", lambda *_: self.undo(self.current_kind))
        self.master.bind("<Control-y>", lambda *_: self.redo(self.current_kind))

    def tree_for(self, kind: str) -> ttk.Treeview:
        return getattr(self, f"tree_{kind}")

    def show_page(self, kind: str) -> None:
        if kind == self.current_kind and self.pages[kind].winfo_manager():
            return
        for page in self.pages.values():
            page.pack_forget()
        self.pages[kind].pack(fill="both", expand=True)
        self.current_kind = kind
        for mode, tab in self.mode_tabs.items():
            selected = mode == kind
            tab.configure(
                bg="white" if selected else "#f0f0f0",
                fg="#1f1f1f" if selected else "#505050",
                relief="solid" if selected else "flat",
                highlightthickness=0,
            )
        self.refresh(kind)

    def resize_columns(self, kind: str, event: tk.Event) -> None:
        usable = max(event.width - 18, 330)
        unit = usable / 5.5
        tree = self.tree_for(kind)
        tree.column("word", width=round(unit * 2))
        tree.column("pinyin", width=round(unit * 2.5))
        tree.column("rank", width=round(unit))

    def require_session(self, kind: str) -> Session | None:
        session = self.sessions[kind]
        if not session:
            messagebox.showwarning("提示", f"请先在“{MODE_LABELS[kind]}”选项卡新建词库、导入词库或载入缓存")
        return session

    def auto_save(self, kind: str) -> None:
        session, workspace = self.sessions[kind], self.workspaces[kind]
        if session and workspace:
            save_workspace(workspace, session, **self.metadata[kind])
            self.status.set(f"{MODE_LABELS[kind]}已自动保存：{workspace}")

    def attach_session(self, kind: str, session: Session, metadata: dict[str, str], workspace: Path) -> None:
        if session.kind != kind:
            raise ValueError(f"该文件实际是“{MODE_LABELS[session.kind]}”，请切换到对应选项卡载入")
        self.sessions[kind], self.metadata[kind], self.workspaces[kind] = session, metadata, workspace
        session.on_change = lambda k=kind: self.auto_save(k)
        self.auto_save(kind)
        self.refresh(kind)

    def new_dictionary(self, kind: str) -> None:
        existing = self.sessions[kind]
        if existing and not messagebox.askyesno("新建词库", f"“{MODE_LABELS[kind]}”当前内容已自动保存。确定新建空词库？"):
            return
        workspace = workspace_path(WORKSPACES, kind)
        self.attach_session(kind, Session([], kind=kind), {"source_path": "", "source_sha256": ""}, workspace)
        self.status.set(f"已新建空白{MODE_LABELS[kind]}：{workspace}")

    def open_dat(self, kind: str) -> None:
        path = filedialog.askopenfilename(title=f"导入{MODE_LABELS[kind]}", filetypes=[("DAT 文件", "*.dat")])
        if not path:
            return
        try:
            session, metadata = import_dat(path, expected_kind=kind)
            workspace = workspace_path(WORKSPACES, kind)
            self.attach_session(kind, session, metadata, workspace)
            self.status.set(f"已导入{MODE_LABELS[kind]} {Path(path).name}，共 {len(session.entries)} 条；原文件未修改")
        except Exception as exc:
            messagebox.showerror("导入失败", str(exc))

    def open_workspace(self, kind: str) -> None:
        from .workspace_store import load_workspace
        path = filedialog.askopenfilename(title=f"载入{MODE_LABELS[kind]}缓存", initialdir=WORKSPACES, filetypes=[("JSON 缓存数据", "*.json")])
        if not path:
            return
        try:
            session, metadata = load_workspace(path)
            self.attach_session(kind, session, metadata, Path(path))
            self.status.set(f"已载入{MODE_LABELS[kind]}缓存，共 {len(session.entries)} 条")
        except Exception as exc:
            messagebox.showerror("载入失败", str(exc))

    def refresh(self, kind: str) -> None:
        tree = self.tree_for(kind)
        tree.delete(*tree.get_children())
        session = self.sessions[kind]
        if not session:
            return
        query = self.queries[kind].get().strip().lower()
        for index, item in enumerate(session.entries):
            code_text = " ".join(item.codes)
            if query and query not in item.word.lower() and query not in code_text.lower():
                continue
            tree.insert("", "end", iid=str(index), values=(item.word, code_text, "" if session.is_self_study else str(item.rank)))
        if kind == self.current_kind:
            self.status.set(f"{MODE_LABELS[kind]}：显示 {len(tree.get_children())} / 共 {len(session.entries)} 条；自动保存已开启")

    def quick_add(self, kind: str) -> None:
        session = self.require_session(kind)
        if not session:
            return
        word = simpledialog.askstring("新增", "词条：", parent=self.master)
        if not word:
            return
        style = "full" if session.is_self_study else CODE_STYLE_VALUES[self.code_styles[kind].get()]
        code = simpledialog.askstring("新增", "编码（已自动生成，可修改）：", initialvalue=" ".join(generate_codes(word, style=style)), parent=self.master)
        if not code:
            return
        rank = 0
        if not session.is_self_study:
            rank = simpledialog.askinteger("新增", "排序值（0-255）：", initialvalue=0, minvalue=0, maxvalue=255, parent=self.master)
            if rank is None:
                return
        result = parse_paste(f"{word}\t{code}\t{rank}", is_self_study=session.is_self_study, code_style=style)
        if result.errors:
            messagebox.showerror("格式错误", "\n".join(result.errors))
            return
        skipped = session.add(list(result.valid))
        if skipped:
            messagebox.showwarning("未新增", f"重复词条：{', '.join(skipped)}")
        self.refresh(kind)

    def paste_import(self, kind: str) -> None:
        session = self.require_session(kind)
        if not session:
            return
        style = "full" if session.is_self_study else CODE_STYLE_VALUES[self.code_styles[kind].get()]
        dialog = tk.Toplevel(self.master)
        dialog.title("粘贴批量导入")
        text = tk.Text(dialog, width=68, height=16)
        text.pack(padx=12, pady=12)
        ttk.Label(dialog, text="每行可只填词条，或填：词条<TAB>编码[<TAB>排序值]").pack(padx=12, anchor="w")
        def apply() -> None:
            result = parse_paste(text.get("1.0", "end"), is_self_study=session.is_self_study, code_style=style)
            existing = {entry.word for entry in session.entries}
            additions = [entry for entry in result.valid if entry.word not in existing]
            message = f"有效新增：{len(additions)}\n重复：{len(result.duplicates) + len(result.valid) - len(additions)}\n错误：{len(result.errors)}"
            if result.errors:
                message += "\n\n" + "\n".join(result.errors[:5])
            if additions and messagebox.askyesno("导入预检", message + "\n\n确认导入有效词条？", parent=dialog):
                session.add(additions)
                dialog.destroy()
                self.refresh(kind)
        ttk.Button(dialog, text="预检并导入", command=apply).pack(pady=12)

    def delete_selected(self, kind: str) -> None:
        session = self.require_session(kind)
        if not session:
            return
        selected = [int(item) for item in self.tree_for(kind).selection()]
        if selected and messagebox.askyesno("确认删除", f"确定删除选中的 {len(selected)} 条词条？"):
            session.delete_indices(selected)
            self.refresh(kind)

    def clear_all(self, kind: str) -> None:
        session = self.require_session(kind)
        if not session:
            return
        if not session.entries:
            return
        if messagebox.askyesno("确认清空", f"确定清空“{MODE_LABELS[kind]}”全部 {len(session.entries)} 条词条？\n\n可使用撤销恢复。"):
            session.replace_entries([])
            self.refresh(kind)

    def fill_codes(self, kind: str) -> None:
        session = self.require_session(kind)
        if not session:
            return
        style = "full" if session.is_self_study else CODE_STYLE_VALUES[self.code_styles[kind].get()]
        regenerated = [type(entry)(entry.word, generate_codes(entry.word, style=style), entry.rank) for entry in session.entries]
        changed = sum(old.codes != new.codes for old, new in zip(session.entries, regenerated))
        if not changed:
            messagebox.showinfo("一键编码", "所有词条编码已符合当前自动编码规则")
            return
        style_label = "全拼" if style == "full" else "首字母"
        if messagebox.askyesno("一键编码", f"将按“{style_label}”重填全部 {len(session.entries)} 条词条编码，其中 {changed} 条会变化。\n\n确定继续？"):
            session.replace_entries(regenerated)
            self.refresh(kind)

    def deduplicate(self, kind: str) -> None:
        session = self.require_session(kind)
        if not session:
            return
        removed = session.deduplicate()
        if removed:
            self.refresh(kind)
        else:
            messagebox.showinfo("一键去重", "未发现重复词条")

    def undo(self, kind: str) -> None:
        if self.sessions[kind] and self.sessions[kind].undo():
            self.refresh(kind)

    def redo(self, kind: str) -> None:
        if self.sessions[kind] and self.sessions[kind].redo():
            self.refresh(kind)

    def begin_edit(self, kind: str, event: tk.Event) -> None:
        session = self.require_session(kind)
        if not session:
            return
        tree = self.tree_for(kind)
        item, column = tree.identify_row(event.y), tree.identify_column(event.x)
        if not item or column not in ("#1", "#2", "#3") or (column == "#3" and session.is_self_study):
            return
        bbox = tree.bbox(item, column)
        if not bbox:
            return
        editor = ttk.Entry(tree)
        editor.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])
        editor.insert(0, tree.set(item, column))
        editor.focus_set()
        def commit(_: object = None) -> None:
            if not editor.winfo_exists():
                return
            values = list(tree.item(item, "values"))
            values[int(column[1:]) - 1] = editor.get().strip()
            try:
                rank = int(values[2]) if values[2] else 0
                parsed = parse_paste(f"{values[0]}\t{values[1]}\t{rank}", is_self_study=session.is_self_study)
                if parsed.errors:
                    raise FormatError(parsed.errors[0])
                session.update(int(item), parsed.valid[0])
                editor.destroy()
                self.refresh(kind)
            except Exception as exc:
                messagebox.showerror("修改失败", str(exc))
                editor.focus_set()
        editor.bind("<Return>", commit)
        editor.bind("<Escape>", lambda _: editor.destroy())
        editor.bind("<FocusOut>", commit)

    def export(self, kind: str) -> None:
        session = self.require_session(kind)
        if not session:
            return
        path = filedialog.asksaveasfilename(title=f"导出{MODE_LABELS[kind]} DAT", initialdir=OUTPUT, initialfile=default_export_name(kind), defaultextension=".dat", filetypes=[("DAT 文件", "*.dat")])
        if not path:
            return
        source = Path(self.metadata[kind].get("source_path", ""))
        if source and Path(path).resolve() == source.resolve():
            messagebox.showerror("导出已拒绝", "不能覆盖导入的原 DAT 文件")
            return
        try:
            target = export_dat(session, path)
            self.status.set(f"已导出：{target}")
            messagebox.showinfo("导出完成", f"已导出新 DAT：\n{target}")
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))


def run_smoke_test() -> int:
    root = tk.Tk(); root.withdraw()
    app = DictionaryApp(root)
    root.update_idletasks()
    app.destroy(); root.destroy()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--smoke-test", action="store_true")
    if parser.parse_args().smoke_test:
        return run_smoke_test()
    root = tk.Tk()
    DictionaryApp(root)
    root.after_idle(lambda: show_usage(root))
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
