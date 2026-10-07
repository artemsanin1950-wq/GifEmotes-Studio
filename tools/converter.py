"""
GifEmotes CLI Converter (Stay Gold Edition)
Headless utility to batch convert GIF/MP4/WebM files to Project Zomboid emotes.
"""

import os
import re
import shutil
from pathlib import Path
from PIL import Image, ImageSequence, ImageDraw
import cv2

USER_HOME = Path.home()
ZOMBOID_USER_DIR = USER_HOME / "Zomboid"
GIFS_DIR = ZOMBOID_USER_DIR / "gifs"

SCRIPT_DIR = Path(__file__).resolve().parent

def find_base_mod_dir() -> Path:
    for p in [SCRIPT_DIR, SCRIPT_DIR.parent, SCRIPT_DIR.parent.parent]:
        if (p / "media").exists():
            return p
    local_mod = ZOMBOID_USER_DIR / "mods" / "GifEmotes"
    if local_mod.exists():
        return local_mod
    return SCRIPT_DIR.parent

BASE_DIR = find_base_mod_dir()

def find_steam_mod_dir() -> Path:
    candidates = []
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

TEXTURES_DIR = BASE_DIR / "media" / "textures" / "gifs"
SUPPORTED_EXTS = {".gif", ".mp4", ".webm", ".avi", ".mov"}


def clean_id(filename: str) -> str:
    name = Path(filename).stem
    if "doc_" in name or "doc-" in name:
        return "miyabi_reaction"
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "custom_media"


def format_title(clean_name: str) -> str:
    if clean_name == "miyabi_reaction":
        return "Miyabi Reaction"
    words = clean_name.replace("_", " ").split()
    return " ".join(w.capitalize() for w in words)


def extract_frames(media_path: Path):
    ext = media_path.suffix.lower()
    frames = []
    fps = 25

    if ext == ".gif":
        im = Image.open(media_path)
        durs = []
        for fr in ImageSequence.Iterator(im):
            d = fr.info.get("duration", 40)
            if d <= 0: d = 40
            durs.append(d)
            frames.append(fr.convert("RGBA"))
        if durs:
            fps = max(5, min(30, round(1000.0 / (sum(durs) / len(durs)))))
    elif ext in {".mp4", ".webm", ".avi", ".mov"}:
        cap = cv2.VideoCapture(str(media_path))
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


def convert_file(path: Path) -> bool:
    if not path.exists() or path.suffix.lower() not in SUPPORTED_EXTS:
        return False

    media_id = clean_id(path.name)
    out_dir = TEXTURES_DIR / media_id
    out_dir.mkdir(parents=True, exist_ok=True)

    frames, fps = extract_frames(path)
    if not frames:
        return False

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
        canvas.save(out_dir / f"{idx}.png", format="PNG")

    print(f"[*] Processed {path.name} -> {media_id} ({len(frames)} frames @ {fps} fps)")
    return True


def sync_all():
    registered = []
    if TEXTURES_DIR.exists():
        for d in TEXTURES_DIR.iterdir():
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
        "-- Auto-generated by GifEmotes Converter",
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
    for target in TARGET_DIRS:
        target.mkdir(parents=True, exist_ok=True)
        for sub in ["42", "common"]:
            s_dir = target / sub
            s_dir.mkdir(parents=True, exist_ok=True)
            (s_dir / "mod.info").write_text(mod_info_content, encoding="utf-8")

        media_dirs = [
            target / "media",
            target / "42" / "media",
            target / "common" / "media"
        ]
        for target_media in media_dirs:
            target_media.mkdir(parents=True, exist_ok=True)
            (target_media / "AnimSets").mkdir(parents=True, exist_ok=True)
            (target_media / "actiongroups").mkdir(parents=True, exist_ok=True)

            # Sync textures
            dst_tex = target_media / "textures" / "gifs"
            if dst_tex != TEXTURES_DIR and TEXTURES_DIR.exists():
                shutil.copytree(TEXTURES_DIR, dst_tex, dirs_exist_ok=True)

            # Sync all Lua files
            src_lua = BASE_DIR / "media" / "lua"
            dst_lua = target_media / "lua"
            if dst_lua != src_lua and src_lua.exists():
                shutil.copytree(src_lua, dst_lua, dirs_exist_ok=True)

            # Write CustomRegistry
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

    print("[*] Synced all mod targets successfully.")


if __name__ == "__main__":
    raw_dir = GIFS_DIR / "gifs"
    for d in [raw_dir, GIFS_DIR]:
        if d.exists():
            for f in d.iterdir():
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS:
                    convert_file(f)
    sync_all()
