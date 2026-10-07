# 🌟 GifEmotes (Stay Gold Edition)

[![Project Zomboid Build 42](https://img.shields.io/badge/Project%20Zomboid-Build%2042%20%26%2041-gold)](https://projectzomboid.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Author: shadeisgold](https://img.shields.io/badge/Production-shadeisreal%20%26%20shadeisnotreal-060608?colorA=060608&colorB=f59e0b)](https://t.me/shadeisreal)

An open-source, high-performance overhead animated GIF emote system for **Project Zomboid (Build 42 & Build 41)** with seamless multiplayer synchronization, customizable 5-slot radial menu, and Obsidian & Radiant Gold UI styling.

---

## ✨ Features

- **Overhead Circular Emote Bubbles:** Renders animated emotes comfortably over characters' heads with an obsidian glass backdrop, radiant gold outer bezel, and speech pointer.
- **Strict 5.5s Playback with Seamless Loop:** Any animation (whether 1.0s or 3.3s) loops seamlessly without hitching until the total 5.5s duration completes, concluding with a gentle fade-out and float-up effect.
- **5-Slot Radial Menu (Press `G`):**
  - **Slot 0:** `[⚙️] Меню GIF...` — Opens the full GUI manager.
  - **Slots 1–4:** Quick emotes triggerable via mouse click, gamepad stick, or pressing **keys 1, 2, 3, 4** on your keyboard.
  - Fully remappable keybind under the in-game **Options -> Mods** tab.
- **Multiplayer Synchronized:** Uses native client-to-server (`sendClientCommand`) and server-to-client (`sendServerCommand`) packets to synchronize overhead emotes across all players on dedicated servers.
- **Zero Input Interference:** Built-in pass-through overlay ensures loot crates, inventory scrolling, and containers remain 100% responsive.
- **Transparent Open-Source Asset Pipeline:** Includes `convert_gifs.py` for converting `.gif`, `.mp4`, `.webm` files and Tenor links into 4x supersampled anti-aliased sprite sequences.

---

## 🎮 How to Use in Game

1. Press **`G`** (default key) to open the 5-slot radial wheel.
2. Click any slot or press **`1`**, **`2`**, **`3`**, or **`4`** on your keyboard to trigger that emote.
3. To customize quick slots:
   - Click the gear icon (`[⚙️] Меню GIF...`).
   - Select any emote from the list.
   - Click **`[1] Слот 1`**, **`[2] Слот 2`**, **`[3] Слот 3`**, or **`[4] Слот 4`** to bind it.
   - Your bindings are automatically saved to `Zomboid/Lua/GifEmotes_Slots.ini` and persist across all servers and singleplayer saves.

---

## 🌐 Multiplayer Architecture

```
[Player A Client] 
   └── Presses "1" (Slot 1: "stay_gold_stay")
   └── sendClientCommand("GifEmotes", "playGif", { playerID = A, gifId = "stay_gold_stay" })
            │
            ▼
[Project Zomboid Server] (GifEmotes_NetServer.lua)
   └── Validates player and broadcast request
   └── sendServerCommand("GifEmotes", "playGif", { playerOnlineId = A, gifId = "stay_gold_stay" })
            │
            ├─────────────────────────────────────────┐
            ▼                                         ▼
   [Player B Client]                         [Player C Client]
   (GifEmotes_NetClient.lua)                 (GifEmotes_NetClient.lua)
   └── Renders emote over Player A's head    └── Renders emote over Player A's head
```

> **Note for Server Admins:** All players connected to a server will see emotes that are installed in the server's mod pack. If a player triggers an unknown emote ID, other clients safely fall back to a default animation without desync or Lua errors.

---

## 🛠️ Adding Custom GIFs & Videos (`GifEmotes_Studio.pyw`)

The repository includes a modern, native windowed desktop application (**`GifEmotes_Studio.pyw`**) with zero console windows:

### Features:
- **Native Drag & Drop:** Drop `.gif`, `.mp4`, `.webm` files directly into the window.
- **Tenor Downloader:** Paste any Tenor or video link to download and convert in 1 click.
- **Live Circular Preview:** Real-time animated 96x96 circular preview with golden bezel ring.
- **Auto-Sync:** Slices, antialiases, and deploys directly into all Project Zomboid mod directories (`common/`, `42/`, and root).

### Requirements
```bash
pip install customtkinter windnd Pillow opencv-python
```

---

## 📁 Repository Structure

```
GifEmotes/
├── mod.info                           # Root mod metadata (Build 41/42)
├── poster.png                         # Workshop preview poster
├── icon.png                           # Workshop icon
├── README.md                          # Documentation
├── GifEmotes_Studio.pyw               # Standalone desktop app (Windowed, zero cmd popups)
├── tools/                             # Tools & asset processing
│   ├── GifEmotes_Studio.pyw           # GUI manager with Drag & Drop & Tenor downloader
│   ├── converter.py                   # Headless CLI batch converter
│   └── assets/                        # Custom gold icon (.ico / .png)
├── media/
│   ├── lua/
│   │   ├── client/
│   │   │   ├── GifEmotes_Core.lua     # Overhead rendering engine (OnPostUIDraw)
│   │   │   ├── GifEmotes_RadialHook.lua # 5-slot radial wheel & ModOptions keybind
│   │   │   ├── GifEmotes_UI.lua       # SHADEISGOLD management window & slot binding
│   │   │   └── GifEmotes_NetClient.lua# Multiplayer packet receiver
│   │   ├── server/
│   │   │   └── GifEmotes_NetServer.lua# Dedicated server relay & broadcaster
│   │   └── shared/
│   │       ├── GifEmotes_Registry.lua # Built-in emote registry & persistence
│   │       ├── GifEmotes_CustomRegistry.lua # Auto-generated user registry
│   │       └── Translate/             # Localization files (RU / EN)
│   └── textures/
│       ├── ui/                        # Golden ring bezel, backdrop, pointer
│       └── gifs/                      # Pre-rendered 96x96 circular frame sequences
├── common/                            # Build 42 common mirror
└── 42/                                # Build 42 specific mirror
```

---

## 👤 Credits & Authors
- **shadeisreal (Artyom)** — Concept, creative vision, visual direction.
- **shadeisnotreal** — Digital execution, engine architecture & Lua implementation.
- Produced by **HS Production / SHADEISGOLD**.
