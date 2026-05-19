from __future__ import annotations

import argparse
import queue
import os
import sys
import threading
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
import tkinter as tk

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    for bundled_runtime in [
        Path(sys._MEIPASS) / "spectrum_runtime",
        Path(sys._MEIPASS) / "CLI Tool" / "vendor" / "spectrum_algo",
    ]:
        if (bundled_runtime / "dictionary.py").exists() and (bundled_runtime / "spec_format").exists():
            os.environ.setdefault("SPECTRUM_REPO_ROOT", str(bundled_runtime))
            break

from spectrum_core import append_to_pack, export_distributable, inspect_pack, is_encrypted_pack, is_generated_path, verify_pack
from spectrum_index import build_index
from spectrum_server.app import PackRegistry, SpectrumServer, create_handler

from spectrum_cli.main import _default_project_pack_path, command_project_init


HOST = "127.0.0.1"
DEFAULT_PORT = 7777
ASSET_DIR = Path("spectrum_cli") / "assets"


@dataclass(frozen=True)
class PackDetails:
    path: Path
    name: str
    size_bytes: int
    size_label: str
    entries: int
    source_root: str
    encrypted: bool
    locked: bool
    hint: str


def format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def load_pack_details(pack_path: str | Path, *, passphrase: str | None = None) -> PackDetails:
    path = Path(pack_path).expanduser().resolve()
    if path.suffix.lower() != ".specpack":
        raise ValueError("Select a .specpack file.")
    summary = inspect_pack(path, passphrase=passphrase)
    return PackDetails(
        path=path,
        name=path.stem,
        size_bytes=path.stat().st_size,
        size_label=format_bytes(path.stat().st_size),
        entries=int(summary.get("entries", 0)),
        source_root=str(summary.get("source_root") or ""),
        encrypted=bool(summary.get("encrypted", False)),
        locked=bool(summary.get("locked", False)),
        hint=str(summary.get("hint") or ""),
    )


def _create_root():
    try:
        from tkinterdnd2 import TkinterDnD  # type: ignore

        return TkinterDnD.Tk(), True
    except Exception:
        return tk.Tk(), False


def asset_path(name: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / ASSET_DIR / name
    return Path(__file__).resolve().parent / "assets" / name


class SpectrumHubGui:
    def __init__(self, root: tk.Tk, *, drag_drop_available: bool) -> None:
        self.root = root
        self.drag_drop_available = drag_drop_available
        self.pack_path: Path | None = None
        self.pending_paths: list[Path] = []
        self.pack_passphrases: dict[Path, str] = {}
        self.server: SpectrumServer | None = None
        self.server_thread: threading.Thread | None = None
        self.status_queue: queue.Queue[tuple] = queue.Queue()
        self.icon_image: tk.PhotoImage | None = None

        self.pack_name_var = tk.StringVar(value="No specpack loaded")
        self.pack_detail_var = tk.StringVar(value="Select or create a specpack to begin.")
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.backend_proxy_var = tk.StringVar(value="")
        self.server_var = tk.StringVar(value="Server stopped")
        self.replace_var = tk.BooleanVar(value=False)
        self.include_generated_var = tk.BooleanVar(value=False)
        self.rebuild_index_var = tk.BooleanVar(value=True)
        self.encrypt_var = tk.BooleanVar(value=False)
        self.append_status_var = tk.StringVar(value="Drop documents here, then confirm append.")
        self.append_progress_var = tk.DoubleVar(value=0)

        self._build()
        self._poll_status_queue()

    def _build(self) -> None:
        self.root.title("Spectrum Hub")
        self.root.geometry("860x560")
        self.root.minsize(760, 500)
        self._apply_icon()

        style = ttk.Style()
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Status.TLabel", foreground="#4b5563")

        main = ttk.Frame(self.root, padding=18)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)

        header = ttk.Frame(main)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(1, weight=1)
        if self.icon_image is not None:
            ttk.Label(header, image=self.icon_image).grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 12))
        ttk.Label(header, textvariable=self.pack_name_var, style="Title.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(header, textvariable=self.pack_detail_var, style="Status.TLabel").grid(row=1, column=1, sticky="w")

        pack_actions = ttk.Frame(main)
        pack_actions.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        pack_actions.columnconfigure(7, weight=1)
        ttk.Button(pack_actions, text="Open Specpack", command=self.open_specpack).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(pack_actions, text="Create Specpack", command=self.create_specpack).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(pack_actions, text="Files", command=self.open_files_view).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(pack_actions, text="Export", command=self.export_distributable).grid(row=0, column=3, padx=(0, 8))
        ttk.Checkbutton(pack_actions, text="Encrypt new pack", variable=self.encrypt_var).grid(row=0, column=4, padx=(8, 8))
        ttk.Label(pack_actions, text="Port").grid(row=0, column=5, padx=(8, 6))
        ttk.Entry(pack_actions, textvariable=self.port_var, width=8).grid(row=0, column=6, padx=(0, 8))

        server_actions = ttk.Frame(main)
        server_actions.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        server_actions.columnconfigure(7, weight=1)
        ttk.Button(server_actions, text="Start Server", command=self.start_server).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(server_actions, text="Stop Server", command=self.stop_server).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(server_actions, text="Open Dashboard", command=self.open_dashboard).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(server_actions, text="Open App", command=self.open_app).grid(row=0, column=3, padx=(0, 8))
        ttk.Label(server_actions, text="Backend").grid(row=0, column=4, padx=(8, 6))
        ttk.Entry(server_actions, textvariable=self.backend_proxy_var, width=28).grid(row=0, column=5, padx=(0, 8))
        ttk.Label(server_actions, textvariable=self.server_var, style="Status.TLabel").grid(row=0, column=6, sticky="w")

        append = ttk.LabelFrame(main, text="Append Documents", padding=12)
        append.grid(row=3, column=0, sticky="nsew")
        append.columnconfigure(0, weight=1)
        append.rowconfigure(1, weight=1)

        top = ttk.Frame(append)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(6, weight=1)
        ttk.Button(top, text="Add Files", command=self.add_files).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(top, text="Add Folder", command=self.add_folder).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(top, text="Clear", command=self.clear_pending).grid(row=0, column=2, padx=(0, 8))
        ttk.Checkbutton(top, text="Replace existing paths", variable=self.replace_var).grid(row=0, column=3, padx=(0, 8))
        ttk.Checkbutton(top, text="Include generated/build folders", variable=self.include_generated_var).grid(row=0, column=4, padx=(0, 8))
        ttk.Checkbutton(top, text="Rebuild index after append", variable=self.rebuild_index_var).grid(row=0, column=5, padx=(0, 8))

        self.pending_list = tk.Listbox(append, activestyle="none", selectmode=tk.EXTENDED)
        self.pending_list.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(append, orient="vertical", command=self.pending_list.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.pending_list.configure(yscrollcommand=scrollbar.set)

        self.drop_label = ttk.Label(append, textvariable=self.append_status_var, style="Status.TLabel")
        self.drop_label.grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.append_progress = ttk.Progressbar(append, variable=self.append_progress_var, maximum=100, mode="determinate")
        self.append_progress.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        bottom = ttk.Frame(main)
        bottom.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, textvariable=self.append_status_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="Rebuild Index", command=self.rebuild_index).grid(row=0, column=1, sticky="e", padx=(0, 8))
        ttk.Button(bottom, text="Confirm Append", command=self.confirm_append).grid(row=0, column=2, sticky="e")

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._enable_drag_drop()

    def _apply_icon(self) -> None:
        icon_png = asset_path("spec-icon.png")
        icon_ico = asset_path("spec-icon.ico")
        try:
            if icon_ico.exists():
                self.root.iconbitmap(default=str(icon_ico))
            if icon_png.exists():
                self.icon_image = tk.PhotoImage(file=str(icon_png))
                self.root.iconphoto(True, self.icon_image)
        except tk.TclError:
            self.icon_image = None

    def _enable_drag_drop(self) -> None:
        if not self.drag_drop_available:
            self.append_status_var.set(
                "Drag/drop needs tkinterdnd2 in this Python. Use Add Files or package with the optional drag-drop dependency."
            )
            return
        try:
            from tkinterdnd2 import DND_FILES  # type: ignore

            self.pending_list.drop_target_register(DND_FILES)
            self.pending_list.dnd_bind("<<Drop>>", self._on_drop)
            self.append_status_var.set("Drop documents here, then confirm append.")
        except Exception as exc:
            self.append_status_var.set(f"Drag/drop unavailable: {exc}. Use Add Files instead.")

    def _on_drop(self, event) -> None:
        values = [Path(item) for item in self.root.tk.splitlist(event.data)]
        self.stage_paths(values)

    def _poll_status_queue(self) -> None:
        try:
            while True:
                item = self.status_queue.get_nowait()
                kind = item[0]
                message = item[1] if len(item) > 1 else ""
                if kind == "server":
                    self.server_var.set(message)
                elif kind == "progress":
                    self.append_progress.stop()
                    self.append_progress.configure(mode="determinate", maximum=100)
                    self.append_progress_var.set(float(item[1]))
                elif kind == "busy":
                    self.append_progress.configure(mode="indeterminate")
                    self.append_progress.start(12)
                else:
                    self.append_progress.stop()
                    self.append_status_var.set(message)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_status_queue)

    def _require_pack(self) -> Path | None:
        if self.pack_path is None:
            messagebox.showinfo("Spectrum Hub", "Open or create a .specpack first.")
            return None
        return self.pack_path

    def _port(self) -> int | None:
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Spectrum Hub", "Port must be a number.")
            return None
        if not 0 < port < 65536:
            messagebox.showerror("Spectrum Hub", "Port must be between 1 and 65535.")
            return None
        return port

    def _passphrase_for_pack(self, pack: Path, *, prompt: bool = True) -> str | None:
        resolved = pack.expanduser().resolve()
        if not is_encrypted_pack(resolved):
            return None
        cached = self.pack_passphrases.get(resolved)
        if cached is not None:
            return cached
        if not prompt:
            return None
        hint = ""
        try:
            hint = str(inspect_pack(resolved).get("hint") or "")
        except Exception:
            pass
        message = "Unlock passphrase"
        if hint:
            message = f"Unlock passphrase\nHint: {hint}"
        value = simpledialog.askstring("Unlock encrypted specpack", message, show="*")
        if not value:
            return None
        try:
            inspect_pack(resolved, passphrase=value)
        except Exception as exc:
            messagebox.showerror("Spectrum Hub", f"Could not unlock specpack: {exc}")
            return None
        self.pack_passphrases[resolved] = value
        return value

    def _new_pack_encryption(self) -> tuple[bool, str | None, str | None] | None:
        if not self.encrypt_var.get():
            return False, None, None
        messagebox.showinfo(
            "Encrypt specpack",
            "Use a long memorable passphrase. Spectrum cannot recover it if it is forgotten.",
        )
        passphrase = simpledialog.askstring("Encrypt specpack", "Create passphrase", show="*")
        if not passphrase:
            return None
        confirm = simpledialog.askstring("Encrypt specpack", "Confirm passphrase", show="*")
        if passphrase != confirm:
            messagebox.showerror("Spectrum Hub", "Passphrases do not match.")
            return None
        hint = simpledialog.askstring("Passphrase hint", "Optional non-secret hint", initialvalue="") or None
        return True, passphrase, hint

    def open_specpack(self) -> None:
        filename = filedialog.askopenfilename(
            title="Open Spectrum specpack",
            filetypes=[("Spectrum specpack", "*.specpack"), ("All files", "*.*")],
        )
        if filename:
            self.set_pack(filename)

    def create_specpack(self) -> None:
        source = filedialog.askdirectory(title="Select project folder to pack")
        if not source:
            return
        source_path = Path(source)
        default_output = _default_project_pack_path(source_path)
        output = filedialog.asksaveasfilename(
            title="Save Spectrum specpack",
            initialdir=str(default_output.parent),
            initialfile=default_output.name,
            defaultextension=".specpack",
            filetypes=[("Spectrum specpack", "*.specpack")],
        )
        if not output:
            return
        name = simpledialog.askstring("Project name", "Specpack/project name", initialvalue=source_path.name)
        if not name:
            return
        port = self._port()
        if port is None:
            return
        encryption = self._new_pack_encryption()
        if encryption is None:
            return
        encrypt, passphrase, hint = encryption

        self.append_status_var.set("Creating specpack...")
        self.root.update_idletasks()
        try:
            code = command_project_init(
                argparse.Namespace(
                    source=str(source_path),
                    output=output,
                    name=name,
                    replace_template=False,
                    no_index=False,
                    port=port,
                    all=True,
                    language=None,
                    rle="off",
                    zlib_level=9,
                    verbose=False,
                    json=True,
                    encrypt=encrypt,
                    passphrase=passphrase,
                    kdf_profile="interactive",
                    hint=hint,
                )
            )
            if code:
                raise RuntimeError("Specpack creation failed.")
            if encrypt and passphrase:
                self.pack_passphrases[Path(output).expanduser().resolve()] = passphrase
            self.set_pack(output)
            self.append_status_var.set("Specpack created.")
        except Exception as exc:
            messagebox.showerror("Spectrum Hub", str(exc))
            self.append_status_var.set("Specpack creation failed.")

    def export_distributable(self) -> None:
        pack = self._require_pack()
        if pack is None:
            return
        passphrase = self._passphrase_for_pack(pack)
        if is_encrypted_pack(pack) and passphrase is None:
            return
        parent = filedialog.askdirectory(title="Choose where to create the decoded project folder")
        if not parent:
            return
        self.append_status_var.set("Exporting specpack...")
        threading.Thread(target=self._export_worker, args=(pack, Path(parent), passphrase), daemon=True).start()

    def _export_worker(self, pack: Path, parent: Path, passphrase: str | None) -> None:
        try:
            summary = export_distributable(pack, parent, passphrase=passphrase)
            self.root.after(0, self._after_export_success, summary)
        except Exception as exc:
            self.status_queue.put(("append", f"Export failed: {exc}"))
            self.root.after(0, messagebox.showerror, "Spectrum Hub", str(exc))

    def _after_export_success(self, summary: dict) -> None:
        output_dir = str(summary.get("output_dir") or "")
        restored = int(summary.get("restored_files") or 0)
        encoded = int(summary.get("restored_encoded_entries") or 0)
        external = int(summary.get("external_entries") or 0)
        self.append_status_var.set(
            f"Exported {restored} file{'s' if restored != 1 else ''} "
            f"({encoded} encoded, {external} external) to {output_dir}."
        )
        messagebox.showinfo("Spectrum Hub", f"Export complete:\n{output_dir}")

    def open_files_view(self) -> None:
        pack = self._require_pack()
        if pack is None:
            return
        passphrase = self._passphrase_for_pack(pack)
        if is_encrypted_pack(pack) and passphrase is None:
            return
        self.append_status_var.set("Preparing files view...")
        threading.Thread(target=self._files_view_worker, args=(pack, passphrase), daemon=True).start()

    def _files_view_worker(self, pack: Path, passphrase: str | None) -> None:
        try:
            summary = inspect_pack(pack, passphrase=passphrase)
            root_name = str(summary.get("source_root") or pack.stem)
            parent = pack.with_suffix(".files")
            target = parent / root_name
            if not target.exists():
                parent.mkdir(parents=True, exist_ok=True)
                exported = export_distributable(pack, parent, folder_name=root_name, passphrase=passphrase)
                target = Path(str(exported["output_dir"]))
            self.root.after(0, self._after_files_view_ready, target)
        except Exception as exc:
            self.status_queue.put(("append", f"Files view failed: {exc}"))
            self.root.after(0, messagebox.showerror, "Spectrum Hub", str(exc))

    def _after_files_view_ready(self, folder: Path) -> None:
        self.append_status_var.set(f"Files view ready: {folder}")
        try:
            os.startfile(str(folder))  # type: ignore[attr-defined]
        except AttributeError:
            webbrowser.open(folder.as_uri())
        except Exception as exc:
            messagebox.showerror("Spectrum Hub", f"Could not open files folder: {exc}")

    def set_pack(self, pack_path: str | Path) -> None:
        try:
            path = Path(pack_path).expanduser().resolve()
            details = load_pack_details(path, passphrase=self.pack_passphrases.get(path))
        except Exception as exc:
            messagebox.showerror("Spectrum Hub", str(exc))
            return
        self.pack_path = details.path
        self.pack_name_var.set(details.name)
        root = f" | source root: {details.source_root}" if details.source_root else ""
        lock = " | encrypted unlocked" if details.encrypted and not details.locked else " | encrypted locked" if details.encrypted else ""
        docs = f"{details.entries} documents" if not details.locked else "locked"
        self.pack_detail_var.set(f"{details.path} | {details.size_label} | {docs}{root}{lock}")

    def add_files(self) -> None:
        filenames = filedialog.askopenfilenames(title="Select documents to append")
        self.stage_paths(Path(filename) for filename in filenames)

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select folder to append")
        if folder:
            self.stage_paths([Path(folder)])

    def stage_paths(self, paths) -> None:
        added = 0
        existing = {path.resolve() for path in self.pending_paths if path.exists()}
        for path in paths:
            candidate = Path(path).expanduser()
            if not candidate.exists():
                continue
            resolved = candidate.resolve()
            if resolved in existing:
                continue
            self.pending_paths.append(resolved)
            existing.add(resolved)
            self.pending_list.insert(tk.END, str(resolved))
            added += 1
        total = len(self.pending_paths)
        self.append_status_var.set(f"Staged {total} item{'s' if total != 1 else ''}." if added else "No new files were staged.")

    def clear_pending(self) -> None:
        self.pending_paths.clear()
        self.pending_list.delete(0, tk.END)
        self.append_status_var.set("Staged list cleared.")
        self.append_progress_var.set(0)

    def confirm_append(self) -> None:
        pack = self._require_pack()
        if pack is None:
            return
        if not self.pending_paths:
            messagebox.showinfo("Spectrum Hub", "Add or drop documents before confirming.")
            return
        count = len(self.pending_paths)
        if not messagebox.askyesno("Confirm append", f"Append {count} item{'s' if count != 1 else ''} to {pack.name}?"):
            return
        paths = list(self.pending_paths)
        replace = self.replace_var.get()
        include_generated = self.include_generated_var.get()
        rebuild_index = self.rebuild_index_var.get()
        estimate = self._estimate_append(paths, include_generated=include_generated)
        large_append = estimate["files"] > 1000 or estimate["bytes"] > 250 * 1024 * 1024
        if large_append and rebuild_index:
            rebuild_index = False
            self.append_status_var.set(
                f"Large append detected ({estimate['files']} files, {format_bytes(estimate['bytes'])}); index rebuild deferred."
            )
        passphrase = self._passphrase_for_pack(pack)
        if is_encrypted_pack(pack) and passphrase is None:
            return
        threading.Thread(
            target=self._append_worker,
            args=(pack, paths, replace, passphrase, include_generated, rebuild_index),
            daemon=True,
        ).start()

    def _estimate_append(self, paths: list[Path], *, include_generated: bool) -> dict[str, int]:
        files = 0
        total_bytes = 0
        for path in paths:
            if path.is_file():
                files += 1
                try:
                    total_bytes += path.stat().st_size
                except OSError:
                    pass
                continue
            for root, dirnames, filenames in os.walk(path):
                root_path = Path(root)
                if not include_generated:
                    dirnames[:] = [
                        dirname
                        for dirname in dirnames
                        if not is_generated_path((root_path / dirname).relative_to(path))
                    ]
                for filename in filenames:
                    candidate = root_path / filename
                    if candidate.suffix.lower() in {".spec", ".specpack"}:
                        continue
                    files += 1
                    try:
                        total_bytes += candidate.stat().st_size
                    except OSError:
                        pass
        return {"files": files, "bytes": total_bytes}

    def _append_worker(
        self,
        pack: Path,
        paths: list[Path],
        replace: bool,
        passphrase: str | None,
        include_generated: bool,
        rebuild_index: bool,
    ) -> None:
        try:
            self.status_queue.put(("append", "Scanning and appending documents..."))
            appended = 0
            replaced = 0
            total = max(len(paths), 1)
            for index, path in enumerate(paths, start=1):
                self.status_queue.put(("append", f"Packing {path} ({index}/{total})..."))
                summary = append_to_pack(
                    pack,
                    path,
                    include_all=True,
                    include_generated=include_generated,
                    replace=replace,
                    passphrase=passphrase,
                )
                appended += int(summary.get("appended_entries", 0))
                replaced += int(summary.get("replaced_entries", 0))
                self.status_queue.put(("progress", 60 * index / total))
            self.status_queue.put(("append", "Verifying appended pack..."))
            self.status_queue.put(("busy", "verify"))
            verify = verify_pack(pack, passphrase=passphrase).to_dict()
            if not verify.get("valid"):
                failures = verify.get("failures") or []
                if failures:
                    preview = ", ".join(str(item) for item in failures[:8])
                    suffix = f" and {len(failures) - 8} more" if len(failures) > 8 else ""
                    raise RuntimeError(f"Pack append completed, but verification failed: {preview}{suffix}")
                raise RuntimeError("Pack append completed, but verification failed.")
            indexed_docs = None
            if rebuild_index:
                self.status_queue.put(("append", "Rebuilding embedded search index..."))
                self.status_queue.put(("busy", "index"))
                index = build_index(pack, embed=True, passphrase=passphrase)
                indexed_docs = int(index.get("documents", 0))
            self.status_queue.put(("progress", 100))
            self.root.after(0, self._after_append_success, appended, replaced, indexed_docs)
        except Exception as exc:
            self.status_queue.put(("append", f"Append failed: {exc}"))
            self.root.after(0, messagebox.showerror, "Spectrum Hub", str(exc))

    def _after_append_success(self, appended: int, replaced: int, indexed_docs: int | None) -> None:
        self.clear_pending()
        self.append_progress_var.set(100)
        if self.pack_path is not None:
            self.set_pack(self.pack_path)
        index_text = f"indexed {indexed_docs}" if indexed_docs is not None else "index rebuild deferred"
        self.append_status_var.set(
            f"Appended {appended} document{'s' if appended != 1 else ''}; "
            f"replaced {replaced}; {index_text}."
        )

    def rebuild_index(self) -> None:
        pack = self._require_pack()
        if pack is None:
            return
        passphrase = self._passphrase_for_pack(pack)
        if is_encrypted_pack(pack) and passphrase is None:
            return
        threading.Thread(target=self._rebuild_index_worker, args=(pack, passphrase), daemon=True).start()

    def _rebuild_index_worker(self, pack: Path, passphrase: str | None) -> None:
        try:
            self.status_queue.put(("append", "Rebuilding embedded search index..."))
            self.status_queue.put(("busy", "index"))
            index = build_index(pack, embed=True, passphrase=passphrase)
            self.status_queue.put(("progress", 100))
            self.status_queue.put(("append", f"Search index rebuilt for {int(index.get('documents', 0))} documents."))
        except Exception as exc:
            self.status_queue.put(("append", f"Index rebuild failed: {exc}"))
            self.root.after(0, messagebox.showerror, "Spectrum Hub", str(exc))

    def start_server(self) -> None:
        pack = self._require_pack()
        if pack is None:
            return
        port = self._port()
        if port is None:
            return
        if self.server is not None:
            self.server_var.set(f"Server already running at http://{HOST}:{port}/project")
            return
        try:
            passphrase = self._passphrase_for_pack(pack)
            if is_encrypted_pack(pack) and passphrase is None:
                return
            registry = PackRegistry()
            registry.add("repo", pack, passphrase=passphrase)
            backend_proxy = self.backend_proxy_var.get().strip()
            if backend_proxy:
                registry.set_app_proxy("repo", backend_proxy, routes=["/api/*"])
            server = SpectrumServer((HOST, port), create_handler(registry), quiet=True)
        except Exception as exc:
            messagebox.showerror("Spectrum Hub", str(exc))
            self.server_var.set("Server failed to start")
            return

        self.server = server
        self.server_thread = threading.Thread(target=self._serve_forever, daemon=True)
        self.server_thread.start()
        self.server_var.set(f"Server running at http://{HOST}:{port}/project")

    def _serve_forever(self) -> None:
        assert self.server is not None
        try:
            self.server.serve_forever()
        except Exception as exc:
            self.status_queue.put(("server", f"Server stopped: {exc}"))

    def stop_server(self) -> None:
        if self.server is None:
            self.server_var.set("Server stopped")
            return
        server = self.server
        self.server = None
        server.shutdown()
        server.server_close()
        self.server_var.set("Server stopped")

    def open_dashboard(self) -> None:
        port = self._port()
        if port is not None:
            webbrowser.open(f"http://{HOST}:{port}/project")

    def open_app(self) -> None:
        port = self._port()
        if port is not None:
            webbrowser.open(f"http://{HOST}:{port}/apps/repo/")

    def close(self) -> None:
        self.stop_server()
        self.root.destroy()


def main() -> int:
    root, drag_drop_available = _create_root()
    app = SpectrumHubGui(root, drag_drop_available=drag_drop_available)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
