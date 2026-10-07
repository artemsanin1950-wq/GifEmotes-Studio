"""
GifEmotes Studio
================
Open-source Desktop GUI Manager for Project Zomboid Build 42
Author: shadeisreal & shadeisnotreal (shadeisgold)

Native Windowed Python Application (.pyw) with icon & zero console popups.
Features:
- Native Windows Drag & Drop for .gif, .mp4, .webm
- File Browser picker
- Tenor URL direct stream downloader
- Interactive live circular emote preview with gold bezel ring
- Clickable installed emotes list with instant live preview
- Left-aligned delete button for long titles
- One-click build and automatic synchronization to Project Zomboid mod directories
"""

import os
import re
import sys
import shutil
import threading
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Enable Windows taskbar grouping and custom icon display
try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("shadeisgold.gifemotes.studio")
except Exception:
    pass

import customtkinter as ctk
import tkinter
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageSequence, ImageTk

try:
    import windnd
except ImportError:
    windnd = None

try:
    import cv2
except ImportError:
    cv2 = None

# Configure CustomTkinter Theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Dynamic Path Resolution (Portable across any Windows / Linux / Steam setup)
USER_HOME = Path.home()
ZOMBOID_USER_DIR = USER_HOME / "Zomboid"
GIFS_DIR = ZOMBOID_USER_DIR / "gifs"
RAW_GIFS_DIR = GIFS_DIR / "gifs"

SCRIPT_DIR = Path(__file__).resolve().parent

def find_base_mod_dir() -> Path:
    # 1. Search relative to script location
    for p in [SCRIPT_DIR, SCRIPT_DIR.parent, SCRIPT_DIR.parent.parent]:
        if (p / "media").exists():
            return p
    # 2. Check user's Zomboid/mods directory
    local_mod = ZOMBOID_USER_DIR / "mods" / "GifEmotes"
    if local_mod.exists():
        return local_mod
    # 3. Fallback
    return SCRIPT_DIR.parent if (SCRIPT_DIR.parent / "media").exists() else SCRIPT_DIR

BASE_DIR = find_base_mod_dir()

def find_steam_mod_dir() -> Optional[Path]:
    candidates = []
    # 1. Query Windows Registry for Steam installation path
    try:
        import winreg
        for subkey in [r"Software\Valve\Steam", r"Software\Wow6432Node\Valve\Steam"]:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey)
                steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
                winreg.CloseKey(key)
                if steam_path:
                    sp = Path(steam_path)
                    candidates.append(sp / "steamapps" / "common" / "ProjectZomboid" / "mods" / "GifEmotes")
                    vdf = sp / "steamapps" / "libraryfolders.vdf"
                    if vdf.exists():
                        for line in vdf.read_text(encoding="utf-8", errors="ignore").splitlines():
                            if '"path"' in line:
                                parts = line.split('"')
                                if len(parts) >= 4:
                                    lib = Path(parts[3].replace(r"\\", "\\"))
                                    candidates.append(lib / "steamapps" / "common" / "ProjectZomboid" / "mods" / "GifEmotes")
            except Exception:
                pass
    except Exception:
        pass

    # 2. Common drive letters fallback
    for drive in ["C", "D", "E", "F", "G", "H"]:
        candidates.extend([
            Path(f"{drive}:/SteamLibrary/steamapps/common/ProjectZomboid/mods/GifEmotes"),
            Path(f"{drive}:/Program Files (x86)/Steam/steamapps/common/ProjectZomboid/mods/GifEmotes"),
            Path(f"{drive}:/Steam/steamapps/common/ProjectZomboid/mods/GifEmotes"),
        ])

    for c in candidates:
        if c.exists() or (c.parent.exists() and c.parent.name == "mods"):
            return c
    return None

STEAM_DIR = find_steam_mod_dir()
TARGET_DIRS = [BASE_DIR]
if STEAM_DIR and STEAM_DIR.resolve() != BASE_DIR.resolve():
    TARGET_DIRS.append(STEAM_DIR)

WORKSHOP_MOD = ZOMBOID_USER_DIR / "Workshop" / "GifEmotes" / "Contents" / "mods" / "GifEmotes"
if WORKSHOP_MOD.exists() and WORKSHOP_MOD.resolve() not in [p.resolve() for p in TARGET_DIRS]:
    TARGET_DIRS.append(WORKSHOP_MOD)

SUPPORTED_EXTS = {".gif", ".mp4", ".webm", ".avi", ".mov"}


def find_icon_path() -> Optional[Path]:
    candidates = [
        SCRIPT_DIR / "assets" / "studio_icon.ico",
        SCRIPT_DIR / "studio_icon.ico",
        SCRIPT_DIR / "tools" / "assets" / "studio_icon.ico",
        SCRIPT_DIR.parent / "assets" / "studio_icon.ico",
        BASE_DIR / "tools" / "assets" / "studio_icon.ico",
        BASE_DIR / "assets" / "studio_icon.ico",
        GIFS_DIR / "assets" / "studio_icon.ico",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def clean_id(filename: str) -> str:
    stem = Path(filename).stem
    if "doc_" in stem or "doc-" in stem:
        return "miyabi_reaction"
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", stem).lower()
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "custom_media"


def format_title(clean_name: str) -> str:
    if clean_name == "miyabi_reaction":
        return "Miyabi Reaction"
    words = clean_name.replace("_", " ").split()
    return " ".join(w.capitalize() for w in words)


class GifEmotesStudio(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("GifEmotes Studio")
        self.geometry("920x680")
        self.minsize(880, 640)
        self.configure(fg_color="#0b0c10")

        # Set window and taskbar icon
        self._tk_icon = None
        icon_path = find_icon_path()
        if icon_path and icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass
            try:
                ico_img = Image.open(icon_path)
                self._tk_icon = ImageTk.PhotoImage(ico_img)
                self.iconphoto(True, self._tk_icon)
            except Exception:
                pass

        # Active media state
        self.current_media_path: Optional[Path] = None
        self.preview_frames: List[Image.Image] = []
        self.preview_tk_frames: List[ImageTk.PhotoImage] = []
        self.preview_fps: int = 25
        self.anim_thread_running: bool = False
        self.anim_idx: int = 0
        self.is_processing: bool = False
        self.selected_installed_id: Optional[str] = None

        self.setup_ui()
        self.load_installed_emotes()

        # Hook Windows Drag & Drop
        if windnd:
            try:
                windnd.hook_dropfiles(self, func=self.on_drop_files)
            except Exception as e:
                print(f"[!] Drag & drop note: {e}")

    def setup_ui(self):
        # Top Header Bar
        self.header_frame = ctk.CTkFrame(self, fg_color="#12131a", corner_radius=0, height=54)
        self.header_frame.pack(fill="x", side="top")

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="✨ GIFEMOTES STUDIO",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color="#f59e0b"
        )
        self.title_label.pack(side="left", padx=20, pady=12)

        self.sub_label = ctk.CTkLabel(
            self.header_frame,
            text="Project Zomboid Build 42 Emote Studio",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#9ca3af"
        )
        self.sub_label.pack(side="left", padx=5, pady=14)

        self.open_mod_btn = ctk.CTkButton(
            self.header_frame,
            text="📁 Папка мода",
            width=110,
            height=28,
            fg_color="#1f212d",
            hover_color="#2b2d3d",
            border_width=1,
            border_color="#f59e0b",
            font=ctk.CTkFont(size=12),
            command=self.open_mod_folder
        )
        self.open_mod_btn.pack(side="right", padx=16, pady=12)

        # Main Layout: 2 Columns
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=16, pady=16)

        # ─── LEFT COLUMN: Ingestion Controls ─────────────────────────
        self.left_col = ctk.CTkFrame(self.main_container, fg_color="#14151f", corner_radius=12, border_width=1, border_color="#262837")
        self.left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # 1. Drag & Drop Zone
        self.drop_zone = ctk.CTkFrame(
            self.left_col,
            fg_color="#191b28",
            corner_radius=10,
            border_width=2,
            border_color="#f59e0b"
        )
        self.drop_zone.pack(fill="x", padx=16, pady=(16, 12))

        self.drop_icon = ctk.CTkLabel(
            self.drop_zone,
            text="📥",
            font=ctk.CTkFont(size=32)
        )
        self.drop_icon.pack(pady=(16, 4))

        self.drop_title = ctk.CTkLabel(
            self.drop_zone,
            text="Перетащите сюда .GIF, .MP4 или .WEBM",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#f3f4f6"
        )
        self.drop_title.pack(pady=2)

        self.drop_sub = ctk.CTkLabel(
            self.drop_zone,
            text="или нажмите кнопку ниже для выбора файла в Проводнике",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#9ca3af"
        )
        self.drop_sub.pack(pady=(0, 8))

        self.browse_btn = ctk.CTkButton(
            self.drop_zone,
            text="Выбрать файл в Проводнике...",
            fg_color="#2a2d3e",
            hover_color="#373b52",
            border_width=1,
            border_color="#d97706",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=32,
            command=self.browse_file
        )
        self.browse_btn.pack(pady=(0, 14))

        # 2. Tenor / Web URL Downloader
        self.url_frame = ctk.CTkFrame(self.left_col, fg_color="#191b28", corner_radius=10)
        self.url_frame.pack(fill="x", padx=16, pady=6)

        self.url_label = ctk.CTkLabel(
            self.url_frame,
            text="🌐 Загрузка по ссылке из Tenor / Интернета:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#fbbf24"
        )
        self.url_label.pack(anchor="w", padx=12, pady=(10, 4))

        self.url_input_row = ctk.CTkFrame(self.url_frame, fg_color="transparent")
        self.url_input_row.pack(fill="x", padx=12, pady=(0, 10))

        self.url_entry = ctk.CTkEntry(
            self.url_input_row,
            placeholder_text="Вставьте ссылку Tenor или прямой URL на .gif / .mp4...",
            height=34,
            fg_color="#0e1017",
            border_color="#373b52"
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.url_paste_btn = ctk.CTkButton(
            self.url_input_row,
            text="📋 Вставить",
            width=85,
            height=34,
            fg_color="#2b2d42",
            hover_color="#3f4263",
            text_color="#f8fafc",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.paste_to_url_entry
        )
        self.url_paste_btn.pack(side="left", padx=(0, 6))

        self.url_dl_btn = ctk.CTkButton(
            self.url_input_row,
            text="Скачать",
            width=80,
            height=34,
            fg_color="#f59e0b",
            hover_color="#d97706",
            text_color="#000000",
            font=ctk.CTkFont(weight="bold"),
            command=self.download_url_action
        )
        self.url_dl_btn.pack(side="right")

        # 3. Emote Details & Parameters
        self.details_frame = ctk.CTkFrame(self.left_col, fg_color="#191b28", corner_radius=10)
        self.details_frame.pack(fill="x", padx=16, pady=8)

        self.name_label = ctk.CTkLabel(
            self.details_frame,
            text="Название эмоции в игре:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#e5e7eb"
        )
        self.name_label.pack(anchor="w", padx=12, pady=(10, 2))

        self.name_entry = ctk.CTkEntry(
            self.details_frame,
            placeholder_text="Например: Stay Gold Running",
            height=32,
            fg_color="#0e1017",
            border_color="#373b52"
        )
        self.name_entry.pack(fill="x", padx=12, pady=(0, 8))

        # Universal shortcuts (Ctrl+V in EN and RU layouts, Shift+Insert, right-click context menu)
        self._setup_entry_shortcuts(self.url_entry)
        self._setup_entry_shortcuts(self.name_entry)

        self.info_text = ctk.CTkLabel(
            self.details_frame,
            text="Файл не выбран. Перетащите файл или выберите эмоцию из списка.",
            font=ctk.CTkFont(size=12),
            text_color="#9ca3af",
            justify="left"
        )
        self.info_text.pack(anchor="w", padx=12, pady=(0, 10))

        # 4. Action Button & Progress
        self.progress_bar = ctk.CTkProgressBar(self.left_col, height=8, fg_color="#1f212d", progress_color="#f59e0b")
        self.progress_bar.pack(fill="x", padx=16, pady=(12, 4))
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(
            self.left_col,
            text="Готов к работе",
            font=ctk.CTkFont(size=12),
            text_color="#9ca3af"
        )
        self.status_label.pack(padx=16, pady=2)

        self.add_btn = ctk.CTkButton(
            self.left_col,
            text="✨ ДОБАВИТЬ ЭМОЦИЮ В ИГРУ (PROJECT ZOMBOID)",
            height=42,
            fg_color="#f59e0b",
            hover_color="#fbbf24",
            text_color="#0b0c10",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.build_and_add_emote
        )
        self.add_btn.pack(fill="x", padx=16, pady=(4, 16))

        # ─── RIGHT COLUMN: Live Preview & Installed Emotes ───────────
        self.right_col = ctk.CTkFrame(self.main_container, fg_color="#14151f", corner_radius=12, border_width=1, border_color="#262837", width=380)
        self.right_col.pack(side="right", fill="both", padx=(10, 0))
        self.right_col.pack_propagate(False)

        # Live Circular Preview Box
        self.preview_header = ctk.CTkLabel(
            self.right_col,
            text="Интерактивный предпросмотр (96x96)",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#f59e0b"
        )
        self.preview_header.pack(pady=(16, 6))

        self.preview_canvas = ctk.CTkLabel(self.right_col, text="", width=128, height=128)
        self.preview_canvas.pack(pady=4)

        # Installed Emotes Header & List
        self.installed_header_row = ctk.CTkFrame(self.right_col, fg_color="transparent")
        self.installed_header_row.pack(fill="x", padx=14, pady=(12, 4))

        self.inst_title = ctk.CTkLabel(
            self.installed_header_row,
            text="Установленные эмоции в моде:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#e5e7eb"
        )
        self.inst_title.pack(side="left")

        self.refresh_inst_btn = ctk.CTkButton(
            self.installed_header_row,
            text="🔄",
            width=28,
            height=24,
            fg_color="#20222f",
            hover_color="#2d3042",
            command=self.load_installed_emotes
        )
        self.refresh_inst_btn.pack(side="right")

        self.installed_scroll = ctk.CTkScrollableFrame(
            self.right_col,
            fg_color="#0e1017",
            corner_radius=8,
            border_width=1,
            border_color="#1f212d"
        )
        self.installed_scroll.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    # ─── File Ingestion Logic ────────────────────────────────────────

    def on_drop_files(self, files):
        if not files:
            return
        first = files[0]
        if isinstance(first, bytes):
            first = os.fsdecode(first)
        path = Path(first)
        self.load_file_into_pipeline(path)

    def browse_file(self):
        f = filedialog.askopenfilename(
            title="Выберите GIF или видео",
            filetypes=[
                ("Все поддерживаемые форматы", "*.gif *.mp4 *.webm *.avi *.mov"),
                ("GIF анимации", "*.gif"),
                ("MP4 / WebM видео", "*.mp4 *.webm"),
                ("Все файлы", "*.*")
            ]
        )
        if f:
            self.load_file_into_pipeline(Path(f))

    def load_file_into_pipeline(self, path: Path):
        if not path.exists():
            return
        if path.suffix.lower() not in SUPPORTED_EXTS:
            messagebox.showwarning("Формат не поддерживается", f"Файл {path.name} не является .gif, .mp4 или .webm.")
            return

        self.current_media_path = path
        self.selected_installed_id = None
        self._highlight_installed_row(None)

        clean_name = clean_id(path.name)
        title = format_title(clean_name)
        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, title)

        self.status_label.configure(text=f"Загрузка кадров: {path.name}...", text_color="#fbbf24")
        self.update_idletasks()

        threading.Thread(target=self._process_preview_async, args=(path,), daemon=True).start()

    def _process_preview_async(self, path: Path):
        frames, fps = self._extract_raw_frames(path)
        if not frames:
            self.after(0, lambda: self.status_label.configure(text="Не удалось извлечь кадры из файла", text_color="#ef4444"))
            return

        dur_sec = min(6.0, round(len(frames) / fps, 2))
        info_str = f"Кадров: {len(frames)} | FPS: {fps} | Длительность: {dur_sec} сек\n(Будет плавно повторяться до 5.5 сек над головой)"
        title = format_title(clean_id(path.name))

        self.after(0, lambda: self._apply_circular_preview(frames, fps, title, info_str))

    def _apply_circular_preview(self, frames: List[Image.Image], fps: int, title: str, info_str: str):
        self.preview_frames = frames
        self.preview_fps = fps

        masked_tk = []
        ss = 4
        c_size = 128
        diam = 116
        rad = diam / 2
        cen = c_size / 2

        mask = Image.new("L", (c_size * ss, c_size * ss), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse([(cen - rad) * ss, (cen - rad) * ss, (cen + rad) * ss, (cen + rad) * ss], fill=255)
        circle_mask = mask.resize((c_size, c_size), Image.Resampling.LANCZOS)

        for f in frames[:60]:
            fw, fh = f.size
            scale = min(diam / fw, diam / fh)
            nw, nh = max(1, int(fw * scale)), max(1, int(fh * scale))
            res = f.resize((nw, nh), Image.Resampling.BILINEAR)

            canvas = Image.new("RGBA", (c_size, c_size), (11, 12, 16, 255))
            canvas.paste(res, ((c_size - nw) // 2, (c_size - nh) // 2), res)

            r, g, b, a = canvas.split()
            combined_alpha = Image.composite(a, Image.new("L", (c_size, c_size), 0), circle_mask)
            canvas.putalpha(combined_alpha)

            ring_draw = ImageDraw.Draw(canvas)
            ring_draw.ellipse([cen - rad, cen - rad, cen + rad, cen + rad], outline=(245, 158, 11, 230), width=4)

            masked_tk.append(ctk.CTkImage(light_image=canvas, dark_image=canvas, size=(c_size, c_size)))

        self.preview_tk_frames = masked_tk
        self.info_text.configure(text=info_str)
        self.status_label.configure(text=f"Готов: {title}", text_color="#10b981")

        self.start_preview_animation()

    def _extract_raw_frames(self, path: Path) -> Tuple[List[Image.Image], int]:
        ext = path.suffix.lower()
        frames = []
        fps = 25

        if ext == ".gif":
            im = Image.open(path)
            durs = []
            for fr in ImageSequence.Iterator(im):
                d = fr.info.get("duration", 40)
                if d <= 0: d = 40
                durs.append(d)
                frames.append(fr.convert("RGBA"))
            if durs:
                fps = max(5, min(30, round(1000.0 / (sum(durs) / len(durs)))))
        elif ext in {".mp4", ".webm", ".avi", ".mov"} and cv2:
            cap = cv2.VideoCapture(str(path))
            v_fps = cap.get(cv2.CAP_PROP_FPS)
            fps = round(v_fps) if v_fps and 5 < v_fps <= 60 else 30
            while True:
                ret, frame = cap.read()
                if not ret: break
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(Image.fromarray(rgb).convert("RGBA"))
            cap.release()

        if len(frames) > 180:
            step = len(frames) / 180
            frames = [frames[int(i * step)] for i in range(180)]

        return frames, fps

    def start_preview_animation(self):
        self.anim_thread_running = True
        self.anim_idx = 0
        self._next_preview_frame()

    def _next_preview_frame(self):
        if not self.preview_tk_frames or not self.anim_thread_running:
            return
        frame = self.preview_tk_frames[self.anim_idx % len(self.preview_tk_frames)]
        self.preview_canvas.configure(image=frame)
        self.anim_idx += 1
        delay_ms = max(20, int(1000 / max(10, self.preview_fps)))
        self.after(delay_ms, self._next_preview_frame)

    # ─── Clipboard & Universal Entry Shortcuts ───────────────────────

    def paste_to_url_entry(self):
        try:
            text = self.clipboard_get()
            if text:
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, text.strip())
                self.status_label.configure(text="Ссылка вставлена из буфера", text_color="#10b981")
        except Exception:
            messagebox.showinfo("Буфер обмена", "Буфер обмена пуст или текст недоступен.")

    def _setup_entry_shortcuts(self, entry_widget):
        inner = getattr(entry_widget, "_entry", entry_widget)

        def do_paste(event=None):
            try:
                text = self.clipboard_get()
                if text:
                    try:
                        inner.delete("sel.first", "sel.last")
                    except Exception:
                        pass
                    inner.insert("insert", text.strip())
                return "break"
            except Exception:
                pass

        def do_copy(event=None):
            try:
                selected = inner.selection_get()
                self.clipboard_clear()
                self.clipboard_append(selected)
                return "break"
            except Exception:
                pass

        def do_cut(event=None):
            try:
                selected = inner.selection_get()
                self.clipboard_clear()
                self.clipboard_append(selected)
                inner.delete("sel.first", "sel.last")
                return "break"
            except Exception:
                pass

        def do_select_all(event=None):
            inner.select_range(0, "end")
            inner.icursor("end")
            return "break"

        def do_clear(event=None):
            inner.delete(0, "end")

        def on_key_press(event):
            ctrl_pressed = (event.state & 4) != 0
            if not ctrl_pressed:
                if event.keysym == "Insert" and (event.state & 1) != 0: # Shift+Insert
                    return do_paste(event)
                return None

            # Win32 Virtual Key Codes: V=86, C=67, X=88, A=65 (identical across EN/RU/all layouts)
            if event.keycode == 86 or getattr(event, "char", "") in ("\x16", "v", "V", "м", "М"):
                return do_paste(event)
            elif event.keycode == 67 or getattr(event, "char", "") in ("\x03", "c", "C", "с", "С"):
                return do_copy(event)
            elif event.keycode == 88 or getattr(event, "char", "") in ("\x18", "x", "X", "ч", "Ч"):
                return do_cut(event)
            elif event.keycode == 65 or getattr(event, "char", "") in ("\x01", "a", "A", "ф", "Ф"):
                return do_select_all(event)
            return None

        inner.bind("<KeyPress>", on_key_press)
        entry_widget.bind("<KeyPress>", on_key_press)

        # Standard virtual events
        try:
            inner.bind("<<Paste>>", do_paste)
            entry_widget.bind("<<Paste>>", do_paste)
        except Exception:
            pass

        # Right-Click Context Menu
        menu = tkinter.Menu(inner, tearoff=0, bg="#1e2233", fg="#e2e8f0", activebackground="#f59e0b", activeforeground="#000000", borderwidth=1)
        menu.add_command(label="Вставить", command=do_paste)
        menu.add_command(label="Копировать", command=do_copy)
        menu.add_command(label="Вырезать", command=do_cut)
        menu.add_separator()
        menu.add_command(label="Выделить всё", command=do_select_all)
        menu.add_command(label="Очистить", command=do_clear)

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        inner.bind("<Button-3>", show_menu)
        entry_widget.bind("<Button-3>", show_menu)

    # ─── Tenor / URL Downloader ──────────────────────────────────────

    def download_url_action(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showinfo("Введите ссылку", "Пожалуйста, вставьте ссылку на Tenor или прямой URL на .gif")
            return

        self.status_label.configure(text="Скачивание из сети...", text_color="#fbbf24")
        self.progress_bar.set(0.3)

        threading.Thread(target=self._download_url_worker, args=(url,), daemon=True).start()

    def _download_url_worker(self, url: str):
        RAW_GIFS_DIR.mkdir(parents=True, exist_ok=True)
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        direct_url = url
        hint = "tenor_download"

        if "tenor.com" in url:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=12) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                    m = re.search(r'https://media[0-9]?\.tenor\.com/[^"\'<>\s]+?\.(?:gif|mp4)', html)
                    if not m:
                        m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
                    if m:
                        direct_url = m.group(1) if m.lastindex else m.group(0)
                    slug = url.rstrip("/").split("/")[-1]
                    slug = re.sub(r'-gif-[0-9]+$', '', slug)
                    if slug: hint = slug
            except Exception as e:
                print(f"[!] Error resolving Tenor: {e}")

        try:
            req = urllib.request.Request(direct_url, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = resp.read()
                ext = ".mp4" if direct_url.endswith(".mp4") else ".gif"
                out_path = RAW_GIFS_DIR / f"{clean_id(hint)}{ext}"
                out_path.write_bytes(data)
                self.progress_bar.set(0.7)
                self.after(0, lambda: self.load_file_into_pipeline(out_path))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Ошибка загрузки", f"Не удалось скачать: {e}"))
            self.after(0, lambda: self.status_label.configure(text="Ошибка загрузки", text_color="#ef4444"))

    # ─── Build & Sync Pipeline ───────────────────────────────────────

    def build_and_add_emote(self):
        if not self.current_media_path or not self.current_media_path.exists():
            messagebox.showwarning("Нет файла", "Сначала выберите или перетащите файл анимации.")
            return

        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Введите имя", "Укажите название эмоции.")
            return

        if self.is_processing:
            return
        self.is_processing = True
        self.add_btn.configure(state="disabled")
        self.status_label.configure(text="Обработка и нарезка кадров...", text_color="#f59e0b")
        self.progress_bar.set(0.2)

        threading.Thread(target=self._build_worker, args=(self.current_media_path, name), daemon=True).start()

    def _build_worker(self, path: Path, title: str):
        try:
            media_id = clean_id(path.name)
            out_textures = BASE_DIR / "media" / "textures" / "gifs" / media_id
            out_textures.mkdir(parents=True, exist_ok=True)

            frames, fps = self._extract_raw_frames(path)
            total_frames = len(frames)
            duration_sec = min(6.0, round(total_frames / fps, 2))

            canvas_size = 96
            circle_diameter = 86
            radius = circle_diameter / 2
            center = canvas_size / 2

            ss = 4
            mask_high = Image.new("L", (canvas_size * ss, canvas_size * ss), 0)
            draw_high = ImageDraw.Draw(mask_high)
            draw_high.ellipse([(center - radius) * ss, (center - radius) * ss, (center + radius) * ss, (center + radius) * ss], fill=255)
            circle_mask = mask_high.resize((canvas_size, canvas_size), Image.Resampling.LANCZOS)

            for idx, frame in enumerate(frames):
                fw, fh = frame.size
                scale = min(circle_diameter / fw, circle_diameter / fh)
                nw, nh = max(1, int(fw * scale)), max(1, int(fh * scale))
                resized = frame.resize((nw, nh), Image.Resampling.BILINEAR)

                canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
                canvas.paste(resized, ((canvas_size - nw) // 2, (canvas_size - nh) // 2), resized)

                r, g, b, a = canvas.split()
                combined_alpha = Image.composite(a, Image.new("L", (canvas_size, canvas_size), 0), circle_mask)
                canvas.putalpha(combined_alpha)

                canvas.save(out_textures / f"{idx}.png", format="PNG")
                if idx % 10 == 0:
                    self.progress_bar.set(0.2 + 0.6 * (idx / total_frames))

            self.progress_bar.set(0.85)

            self._sync_all_mods()

            self.progress_bar.set(1.0)
            self.after(0, lambda: self.status_label.configure(text=f"✓ Эмоция '{title}' успешно добавлена в игру!", text_color="#10b981"))
            self.after(0, lambda: messagebox.showinfo("Успех!", f"Эмоция '{title}' добавлена в Project Zomboid!\nТеперь она доступна в радиальном меню (клавиша G)."))
            self.after(0, self.load_installed_emotes)

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка обработки: {e}"))
            self.after(0, lambda: self.status_label.configure(text="Ошибка обработки", text_color="#ef4444"))
        finally:
            self.is_processing = False
            self.after(0, lambda: self.add_btn.configure(state="normal"))

    def _sync_all_mods(self):
        gifs_root = BASE_DIR / "media" / "textures" / "gifs"
        registered = []

        if gifs_root.exists():
            for d in gifs_root.iterdir():
                if d.is_dir() and (d / "0.png").exists():
                    f_count = len([f for f in d.iterdir() if f.name.endswith(".png")])
                    fps = 30
                    dur = min(6.0, round(f_count / fps, 2))
                    registered.append({
                        "id": d.name,
                        "name": format_title(d.name),
                        "basePath": f"media/textures/gifs/{d.name}/",
                        "frameCount": f_count,
                        "fps": fps,
                        "durationSec": dur,
                        "preview": f"media/textures/gifs/{d.name}/0.png"
                    })

        lua_lines = [
            "-- GifEmotes_CustomRegistry.lua",
            "-- Auto-generated by GifEmotes Studio",
            "",
            "GifEmotes = GifEmotes or {}",
            "GifEmotes.Registry = GifEmotes.Registry or {}",
            ""
        ]

        for item in registered:
            lua_lines.extend([
                f'GifEmotes.Registry["{item["id"]}"] = {{',
                f'    id = "{item["id"]}",',
                f'    name = "{item["name"]}",',
                f'    basePath = "{item["basePath"]}",',
                f'    frameCount = {item["frameCount"]},',
                f'    fps = {item["fps"]},',
                f'    durationSec = {item["durationSec"]},',
                f'    preview = "{item["preview"]}"',
                '}',
                ''
            ])

        # Auto-register all frames into ZomboidFileSystem activeFileMap so new textures load instantly (Client-only)
        lua_lines.extend([
            "-- Dynamically register texture frames in ZomboidFileSystem (Client-only)",
            "local function registerCustomTextures()",
            "    if isServer and isServer() then return end",
            "    local fs = getZomboidFileSystem and getZomboidFileSystem()",
            "    if not (fs and fs.activeFileMap) then return end",
            "",
            '    local docFolder = (getMyDocumentFolder and getMyDocumentFolder()) or (fs.getCacheDir and fs:getCacheDir()) or "Zomboid"',
            '    docFolder = docFolder:gsub("\\\\", "/")',
            "",
            "    local modDir = nil",
            '    if fs.getModDir then',
            '        local ok, val = pcall(function() return fs:getModDir("GifEmotes") end)',
            '        if ok and val then modDir = val end',
            '    end',
            '    if not modDir and getModDirectory then',
            '        local ok, val = pcall(function() return getModDirectory("GifEmotes") end)',
            '        if ok and val then modDir = val end',
            '    end',
            '    if modDir then',
            '        modDir = modDir:gsub("\\\\", "/")',
            '    end',
            "",
            "    if not GifEmotes or not GifEmotes.Registry then return end",
            "    for _, g in pairs(GifEmotes.Registry) do",
            "        if g.basePath and g.frameCount then",
            "            for i = 0, (g.frameCount - 1) do",
            '                local rel = g.basePath .. tostring(i) .. ".png"',
            '                local key = rel:lower():gsub("\\\\", "/")',
            "                if fs.relativeMap then",
            "                    fs.relativeMap:put(key, key)",
            "                end",
            "                if modDir then",
            '                    fs.activeFileMap:put(key, modDir .. "/" .. rel)',
            '                    fs.activeFileMap:put(rel, modDir .. "/" .. rel)',
            '                    fs.activeFileMap:put(key, modDir .. "/42/" .. rel)',
            '                    fs.activeFileMap:put(rel, modDir .. "/42/" .. rel)',
            "                end",
            '                fs.activeFileMap:put(key, docFolder .. "/mods/GifEmotes/" .. rel)',
            '                fs.activeFileMap:put(rel, docFolder .. "/mods/GifEmotes/" .. rel)',
            '                fs.activeFileMap:put(key, docFolder .. "/mods/GifEmotes/42/" .. rel)',
            '                fs.activeFileMap:put(rel, docFolder .. "/mods/GifEmotes/42/" .. rel)',
            "            end",
            "        end",
            "    end",
            "end",
            "pcall(registerCustomTextures)",
            ""
        ])

        lua_content = "\n".join(lua_lines)
        mod_info_content = (
            "name=GIF Emotes (Over Head)\n"
            "id=GifEmotes\n"
            "description=Play animated GIF emote bubbles over your head from a dedicated radial menu (G key)! Supports multiplayer and custom GIFs.\n"
            "poster=poster.png\n"
            "icon=icon.png\n"
            "versionMin=42.0.0\n"
            "modversion=1.0.0\n"
            "author=shadeisnotreal & shadeisreal\n"
        )

        for target_base in TARGET_DIRS:
            target_base.mkdir(parents=True, exist_ok=True)
            for sub in ["42", "common"]:
                s_dir = target_base / sub
                s_dir.mkdir(parents=True, exist_ok=True)
                (s_dir / "mod.info").write_text(mod_info_content, encoding="utf-8")

            media_dirs = [
                target_base / "media",
                target_base / "42" / "media",
                target_base / "common" / "media"
            ]
            for target_media in media_dirs:
                target_media.mkdir(parents=True, exist_ok=True)
                (target_media / "AnimSets").mkdir(parents=True, exist_ok=True)
                (target_media / "actiongroups").mkdir(parents=True, exist_ok=True)

                # Sync textures
                dst_textures = target_media / "textures" / "gifs"
                if dst_textures != gifs_root and gifs_root.exists():
                    shutil.copytree(gifs_root, dst_textures, dirs_exist_ok=True)

                # Sync all Lua scripts (Core, UI, RadialHook, NetClient, Registry)
                src_lua = BASE_DIR / "media" / "lua"
                dst_lua = target_media / "lua"
                if dst_lua != src_lua and src_lua.exists():
                    shutil.copytree(src_lua, dst_lua, dirs_exist_ok=True)

                reg_dir = target_media / "lua" / "shared"
                reg_dir.mkdir(parents=True, exist_ok=True)
                final_reg = reg_dir / "GifEmotes_CustomRegistry.lua"
                tmp_reg = reg_dir / "GifEmotes_CustomRegistry.lua.tmp"
                tmp_reg.write_text(lua_content, encoding="utf-8")
                try:
                    import os
                    os.replace(tmp_reg, final_reg)
                except Exception:
                    final_reg.write_text(lua_content, encoding="utf-8")

        # Write live sync token for running game instances (instant hot-reload without restart)
        import time
        sync_token = str(int(time.time() * 1000))
        sync_targets = [
            ZOMBOID_USER_DIR / "Lua" / "gifs_sync.ini",
            ZOMBOID_USER_DIR / "gifs_sync.ini",
            BASE_DIR / "gifs_sync.ini",
        ]
        if STEAM_DIR:
            sync_targets.append(STEAM_DIR / "gifs_sync.ini")
        for st in sync_targets:
            try:
                st.parent.mkdir(parents=True, exist_ok=True)
                st.write_text(sync_token, encoding="utf-8")
            except Exception:
                pass

    # ─── Installed Emotes Management ─────────────────────────────────

    def load_installed_emotes(self):
        for widget in self.installed_scroll.winfo_children():
            widget.destroy()

        gifs_root = BASE_DIR / "media" / "textures" / "gifs"
        if not gifs_root.exists():
            return

        folders = [d for d in gifs_root.iterdir() if d.is_dir() and (d / "0.png").exists()]
        folders.sort(key=lambda d: d.name.lower())

        for d in folders:
            f_count = len([f for f in d.iterdir() if f.name.endswith(".png")])
            title = format_title(d.name)

            row = ctk.CTkFrame(self.installed_scroll, fg_color="#181a24", corner_radius=6)
            row.pack(fill="x", padx=4, pady=3)
            row._emote_id = d.name

            # LEFT: Delete / Trash Button (always visible regardless of title length)
            del_btn = ctk.CTkButton(
                row,
                text="🗑️",
                width=28,
                height=24,
                fg_color="#2b1416",
                hover_color="#ef4444",
                font=ctk.CTkFont(size=12),
                command=lambda p=d: self.delete_installed_emote(p)
            )
            del_btn.pack(side="left", padx=(6, 8), pady=4)

            # RIGHT: Emote Title Label (clickable for live preview)
            lbl = ctk.CTkLabel(
                row,
                text=f"{title} ({f_count} кадр.)",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#f3f4f6",
                anchor="w",
                cursor="hand2"
            )
            lbl.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=6)

            # Interactive Click to Preview
            row.configure(cursor="hand2")
            row.bind("<Button-1>", lambda e, p=d: self.preview_installed_emote(p))
            lbl.bind("<Button-1>", lambda e, p=d: self.preview_installed_emote(p))

            def on_enter(e, r=row, p=d):
                if self.selected_installed_id != p.name:
                    r.configure(fg_color="#212433")

            def on_leave(e, r=row, p=d):
                if self.selected_installed_id != p.name:
                    r.configure(fg_color="#181a24")

            row.bind("<Enter>", on_enter)
            row.bind("<Leave>", on_leave)
            lbl.bind("<Enter>", on_enter)
            lbl.bind("<Leave>", on_leave)

        if self.selected_installed_id:
            self._highlight_installed_row(self.selected_installed_id)

    def _highlight_installed_row(self, emote_id: Optional[str]):
        for child in self.installed_scroll.winfo_children():
            child_id = getattr(child, "_emote_id", None)
            if child_id and emote_id and child_id == emote_id:
                child.configure(fg_color="#24283b", border_width=1, border_color="#f59e0b")
            elif hasattr(child, "_emote_id"):
                child.configure(fg_color="#181a24", border_width=0)

    def preview_installed_emote(self, folder: Path):
        title = format_title(folder.name)
        self.selected_installed_id = folder.name
        self._highlight_installed_row(folder.name)

        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, title)

        # Check if matching source video/gif exists in RAW_GIFS_DIR or GIFS_DIR
        source_found = None
        for cand_dir in [RAW_GIFS_DIR, GIFS_DIR]:
            if cand_dir.exists():
                for f in cand_dir.iterdir():
                    if f.is_file() and clean_id(f.name) == folder.name:
                        source_found = f
                        break
            if source_found:
                break
        self.current_media_path = source_found

        self.status_label.configure(text=f"Загрузка предпросмотра: {title}...", text_color="#fbbf24")
        self.update_idletasks()

        threading.Thread(target=self._preview_installed_async, args=(folder,), daemon=True).start()

    def _preview_installed_async(self, folder: Path):
        try:
            png_files = [f for f in folder.iterdir() if f.name.endswith(".png")]
            if not png_files:
                self.after(0, lambda: self.status_label.configure(text="Кадры не найдены в папке", text_color="#ef4444"))
                return

            def sort_key(p: Path):
                return int(p.stem) if p.stem.isdigit() else 999999

            png_files.sort(key=sort_key)

            frames = []
            for pf in png_files[:60]:
                try:
                    with Image.open(pf) as img:
                        frames.append(img.convert("RGBA"))
                except Exception:
                    pass

            if not frames:
                return

            fps = 30
            dur_sec = min(6.0, round(len(png_files) / fps, 2))
            info_str = f"Установлена в игре (активна)\nКадров: {len(png_files)} | FPS: {fps} | Длительность: {dur_sec} сек"
            title = format_title(folder.name)

            self.after(0, lambda: self._apply_circular_preview(frames, fps, title, info_str))
        except Exception as e:
            self.after(0, lambda: self.status_label.configure(text=f"Ошибка предпросмотра: {e}", text_color="#ef4444"))

    def delete_installed_emote(self, folder: Path):
        title = format_title(folder.name)
        if messagebox.askyesno("Удалить эмоцию", f"Удалить '{title}' из мода?"):
            try:
                shutil.rmtree(folder)
                self._sync_all_mods()
                if self.selected_installed_id == folder.name:
                    self.selected_installed_id = None
                    self.anim_thread_running = False
                    self.preview_canvas.configure(image="")
                    self.info_text.configure(text="Эмоция удалена.")
                self.load_installed_emotes()
                messagebox.showinfo("Удалено", f"Эмоция '{title}' удалена.")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить: {e}")

    def open_mod_folder(self):
        if BASE_DIR.exists():
            os.startfile(str(BASE_DIR))


def main():
    app = GifEmotesStudio()
    app.mainloop()


if __name__ == "__main__":
    main()
