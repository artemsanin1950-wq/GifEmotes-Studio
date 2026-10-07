-- GifEmotes_Registry.lua
-- Registry of GIF emotes and 4 radial quick-slots for Project Zomboid (Stay Gold Edition)

GifEmotes = GifEmotes or {}
GifEmotes.Registry = GifEmotes.Registry or {}

-- ─── 1. Built-in Workshop Ready GIF Emotes ───────────────────────────
GifEmotes.Registry["remielle_dance"] = {
    id = "remielle_dance",
    name = "Remielle Dance",
    basePath = "media/textures/gifs/remielle_dance/",
    frameCount = 102,
    fps = 25,
    durationSec = 4.08,
    preview = "media/textures/gifs/remielle_dance/0.png"
}

GifEmotes.Registry["stay_gold_stay"] = {
    id = "stay_gold_stay",
    name = "Stay Gold Stay",
    basePath = "media/textures/gifs/stay_gold_stay/",
    frameCount = 30,
    fps = 30,
    durationSec = 1.0,
    preview = "media/textures/gifs/stay_gold_stay/0.png"
}

GifEmotes.Registry["stay_gold_stay_gold_running"] = {
    id = "stay_gold_stay_gold_running",
    name = "Stay Gold Running",
    basePath = "media/textures/gifs/stay_gold_stay_gold_running/",
    frameCount = 9,
    fps = 29,
    durationSec = 0.31,
    preview = "media/textures/gifs/stay_gold_stay_gold_running/0.png"
}

GifEmotes.Registry["uma_musume_oguri_cap"] = {
    id = "uma_musume_oguri_cap",
    name = "Oguri Cap",
    basePath = "media/textures/gifs/uma_musume_oguri_cap/",
    frameCount = 169,
    fps = 30,
    durationSec = 5.63,
    preview = "media/textures/gifs/uma_musume_oguri_cap/0.png"
}

-- ─── 2. Persistent 4-Slot Radial Menu Configuration ─────────────────
GifEmotes.Slots = {
    [1] = "remielle_dance",
    [2] = "stay_gold_stay",
    [3] = "stay_gold_stay_gold_running",
    [4] = "uma_musume_oguri_cap"
}

-- Active overhead emote bubbles table: key -> bubbleData
GifEmotes.ActiveBubbles = {}

-- Save slot assignments to local INI so they persist across servers & worlds
function GifEmotes.saveSlots()
    pcall(function()
        local fw = getFileWriter("GifEmotes_Slots.ini", true, false)
        if fw then
            for i = 1, 4 do
                fw:write(string.format("%d=%s\r\n", i, tostring(GifEmotes.Slots[i] or "")))
            end
            fw:close()
        end
    end)
end

-- Load slot assignments from local INI
function GifEmotes.loadSlots()
    pcall(function()
        local fr = getFileReader("GifEmotes_Slots.ini", false)
        if not fr then return end
        local count = 0
        while count < 50 do
            count = count + 1
            local line = fr:readLine()
            if not line then break end
            line = string.trim(line)
            if line ~= "" then
                local slotStr, idStr = line:match("^(%d)=([%w_]+)")
                if slotStr and idStr then
                    local s = tonumber(slotStr)
                    if s and s >= 1 and s <= 4 and GifEmotes.Registry[idStr] then
                        GifEmotes.Slots[s] = idStr
                    end
                end
            end
        end
        fr:close()
    end)
end

-- Helper to register or update a custom GIF
function GifEmotes.registerGif(id, name, basePath, frameCount, fps, durationSec)
    GifEmotes.Registry[id] = {
        id = id,
        name = name,
        basePath = basePath,
        frameCount = frameCount or 30,
        fps = fps or 20,
        durationSec = durationSec or 5.5,
        preview = basePath .. "0.png"
    }
end

-- Safely load custom GIFs if present
pcall(function()
    require "GifEmotes_CustomRegistry"
end)

-- Load immediately on script load
GifEmotes.loadSlots()

Events.OnGameStart.Add(function()
    pcall(GifEmotes.loadSlots)
end)
