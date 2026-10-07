-- GifEmotes_Core.lua
-- Core rendering engine for overhead GIF emote bubbles in Project Zomboid (Stay Gold Edition)
-- Architecture:
-- Uses Events.OnPostUIDraw for pure visual rendering.
-- NEVER adds a fullscreen element to UIManager.UI, ensuring crates, loot containers,
-- inventory panels, and mouse wheel scrolling remain 100% responsive and untouched.

require "ISUI/ISUIElement"
require "GifEmotes_Registry"

GifEmotes = GifEmotes or {}

-- Textures (lazy loaded on demand)
GifEmotes.backTex = nil
GifEmotes.ringTex = nil
GifEmotes.pointerTex = nil

local function ensureUiTextures()
    if not GifEmotes.backTex then
        GifEmotes.backTex = getTexture("media/textures/ui/bubble_back.png")
    end
    if not GifEmotes.ringTex then
        GifEmotes.ringTex = getTexture("media/textures/ui/bubble_ring.png")
    end
    if not GifEmotes.pointerTex then
        GifEmotes.pointerTex = getTexture("media/textures/ui/bubble_pointer.png")
    end
end

-- Uniform standing head height offset in screen pixels (raised comfortably above player)
local function getCharacterHeadHeightPx(char, zoom)
    local z = math.max(0.5, zoom or 1.0)
    return math.floor(118 / z)
end

-- Dynamic Hot-Reload and Live Sync Engine
GifEmotes.lastSyncToken = nil

-- Initialize token once on game start so world loading is instantaneous and never re-syncs
pcall(function()
    local reader = getFileReader("gifs_sync.ini", false)
    if reader then
        GifEmotes.lastSyncToken = reader:readLine()
        reader:close()
    end
end)

function GifEmotes.hotReload(force)
    -- 1. Clear module cache & re-execute updated registry Lua file
    pcall(function()
        if type(package) == "table" and type(package.loaded) == "table" then
            package.loaded["GifEmotes_CustomRegistry"] = nil
            package.loaded["media/lua/shared/GifEmotes_CustomRegistry.lua"] = nil
        end
    end)

    pcall(function()
        if reloadLuaFile then
            reloadLuaFile("media/lua/shared/GifEmotes_CustomRegistry.lua")
        else
            require "GifEmotes_CustomRegistry"
        end
    end)

    -- 2. Invalidate cached frames and purge nullTextures cache
    pcall(function()
        if GifEmotes.Registry then
            for id, gif in pairs(GifEmotes.Registry) do
                gif.frames = {}
                if Texture and Texture.nullTextures then
                    for i = 0, (gif.frameCount - 1) do
                        local rel = gif.basePath .. tostring(i) .. ".png"
                        Texture.nullTextures:remove(rel)
                        Texture.nullTextures:remove(rel:lower())
                    end
                end
            end
        end
    end)

    -- 3. Invalidate UI list if open and fully initialized
    pcall(function()
        local ui = GifEmotes_UI and (GifEmotes_UI.instance or GifEmotes.instance)
        if ui and ui.listBox and ui.populateGifList then
            ui:populateGifList()
        end
    end)

    -- 4. In multiplayer, notify other players if forced
    if force and isClient() then
        pcall(function()
            sendClientCommand("GifEmotes", "syncGifs", {})
        end)
    end
end

function GifEmotes.checkSync(force)
    local token = nil
    pcall(function()
        local reader = getFileReader("gifs_sync.ini", false)
        if reader then
            token = reader:readLine()
            reader:close()
        end
    end)

    if force or (token and token ~= GifEmotes.lastSyncToken) then
        GifEmotes.lastSyncToken = token
        GifEmotes.hotReload(force)
        return true
    end
    return false
end

-- Triggers an overhead GIF emote for a character (strictly 5.5s duration with seamless looping)
function GifEmotes.triggerEmote(character, gifId)
    if not character or character:isDead() then return end

    local gif = GifEmotes.Registry and GifEmotes.Registry[gifId]
    if not gif then
        GifEmotes.checkSync(true)
        gif = GifEmotes.Registry and GifEmotes.Registry[gifId]
    end
    gif = gif or (GifEmotes.Registry and GifEmotes.Registry["remielle_dance"])
    if not gif then return end

    local durSec = 5.5
    local charKey = character:isLocalPlayer() and ("local_" .. tostring(character:getPlayerNum())) or ("remote_" .. tostring(character:getOnlineID()))

    GifEmotes.ActiveBubbles[charKey] = {
        character = character,
        gif = gif,
        startTime = getTimestampMs(),
        durationMs = math.floor(durSec * 1000)
    }

    -- In multiplayer, sync with server
    if isClient() and character:isLocalPlayer() then
        sendClientCommand("GifEmotes", "playGif", {
            playerID = character:getOnlineID(),
            gifId = gif.id,
            duration = durSec
        })
    end
end

-- Triggers emote on a remote player (received from server)
function GifEmotes.triggerEmoteRemote(character, gifId, durOverride)
    if not character or character:isDead() then return end

    local gif = GifEmotes.Registry and GifEmotes.Registry[gifId]
    if not gif then
        GifEmotes.checkSync(true)
        gif = GifEmotes.Registry and GifEmotes.Registry[gifId]
    end
    gif = gif or (GifEmotes.Registry and GifEmotes.Registry["remielle_dance"])
    if not gif then return end

    local durSec = tonumber(durOverride) or 5.5
    local charKey = "remote_" .. tostring(character:getOnlineID())

    GifEmotes.ActiveBubbles[charKey] = {
        character = character,
        gif = gif,
        startTime = getTimestampMs(),
        durationMs = math.floor(durSec * 1000)
    }
end

-- Dedicated lightweight drawer (instantiated solely for OpenGL draw calls, NEVER added to UIManager.UI)
local function getDrawer()
    if not GifEmotes.drawer or not GifEmotes.drawer.javaObject then
        GifEmotes.drawer = ISUIElement:new(0, 0, 0, 0)
        GifEmotes.drawer.wantMouseEvents = false
        GifEmotes.drawer.wantKeyEvents = false
        GifEmotes.drawer.wantExtraMouseEvents = false
        GifEmotes.drawer.isPointOver = function() return false end
        GifEmotes.drawer.onMouseWheel = function() return false end
        GifEmotes.drawer.onMouseDown = function() return false end
        GifEmotes.drawer.onMouseUp = function() return false end
        GifEmotes.drawer:instantiate()
    end
    return GifEmotes.drawer
end

local function hasActiveBubbles()
    if not GifEmotes.ActiveBubbles then return false end
    for _ in pairs(GifEmotes.ActiveBubbles) do
        return true
    end
    return false
end

-- Dynamic texture resolver that registers unindexed textures into ZomboidFileSystem and clears nullTextures
function GifEmotes.getOrLoadTexture(relPath)
    if not relPath then return nil end
    local tex = getTexture(relPath)
    if tex then return tex end

    pcall(function()
        -- 1. Remove from Texture.nullTextures if present so engine doesn't reject it
        if Texture and Texture.forgetTexture then
            Texture.forgetTexture(relPath)
            Texture.forgetTexture(relPath:lower())
        end
        if Texture and Texture.nullTextures then
            Texture.nullTextures:remove(relPath)
            Texture.nullTextures:remove(relPath:lower())
        end

        -- 2. Inject into ZomboidFileSystem maps
        local fs = getZomboidFileSystem and getZomboidFileSystem()
        if fs and fs.activeFileMap then
            local docFolder = (getMyDocumentFolder and getMyDocumentFolder()) or (fs.getCacheDir and fs:getCacheDir()) or "Zomboid"
            docFolder = docFolder:gsub("\\", "/")

            local modDir = nil
            if fs.getModDir then
                pcall(function() modDir = fs:getModDir("GifEmotes") end)
            end
            if not modDir and getModDirectory then
                pcall(function() modDir = getModDirectory("GifEmotes") end)
            end
            if modDir then
                modDir = modDir:gsub("\\", "/")
            end

            local key = relPath:lower():gsub("\\", "/")

            -- relativeMap must map key -> key so getString queries activeFileMap with key
            if fs.relativeMap then
                fs.relativeMap:put(key, key)
            end

            -- Build candidate paths dynamically without hardcoded users or drives
            local candidates = {}
            if modDir then
                table.insert(candidates, modDir .. "/" .. relPath)
            end
            table.insert(candidates, docFolder .. "/mods/GifEmotes/" .. relPath)

            for i = 1, #candidates do
                local p = candidates[i]
                fs.activeFileMap:put(key, p)
                fs.activeFileMap:put(relPath, p)
                tex = getTexture(relPath)
                if tex then break end
            end
        end
    end)

    if not tex then
        tex = getTexture(relPath)
    end
    return tex
end

-- ─── Pure Render Callback (Events.OnPostUIDraw) ───────────────────────
function GifEmotes.renderBubbles()
    pcall(function()
        if not hasActiveBubbles() then
            return
        end

        local drawer = getDrawer()
        if not drawer or not drawer.javaObject then return end

        local now = getTimestampMs()
        local toRemove = {}

        local currentZoom = 1.0
        if getCore() and getCore().getZoom then
            currentZoom = getCore():getZoom(0) or 1.0
        end

        for key, bubble in pairs(GifEmotes.ActiveBubbles) do
            local elapsed = now - bubble.startTime
            if elapsed >= bubble.durationMs or not bubble.character or bubble.character:isDead() then
                table.insert(toRemove, key)
            else
                local char = bubble.character
                local cx = char:getX()
                local cy = char:getY()
                local cz = char:getZ()

                -- Project ground tile to 2D screen coordinates
                local footX = isoToScreenX(0, cx, cy, cz)
                local footY = isoToScreenY(0, cx, cy, cz)

                -- Compute head position on screen (uniform standing height)
                local headOffset = getCharacterHeadHeightPx(char, currentZoom)
                local headX = footX
                local headY = footY - headOffset

                -- Pop-in & fade-out scaling
                local scale = 1.0
                local alpha = 1.0
                local floatOffset = 0

                if elapsed < 250 then
                    -- 0.0 -> 0.25s pop-in
                    local progress = elapsed / 250
                    scale = 0.5 + 0.5 * progress
                    alpha = progress
                elseif (bubble.durationMs - elapsed) < 500 then
                    -- Last 0.5s fade-out & float up
                    local remaining = bubble.durationMs - elapsed
                    local outProgress = remaining / 500
                    scale = 0.85 + 0.15 * outProgress
                    alpha = math.max(0.0, outProgress)
                    floatOffset = (1.0 - outProgress) * 16
                end

                -- Seamless loop modulo: any animation loops seamlessly until 5.5s
                local currentSec = elapsed / 1000
                local frameIdx = math.floor(currentSec * bubble.gif.fps) % bubble.gif.frameCount

                if not bubble.gif.frames then bubble.gif.frames = {} end
                local frameTex = bubble.gif.frames[frameIdx]
                if not frameTex then
                    frameTex = GifEmotes.getOrLoadTexture(bubble.gif.basePath .. tostring(frameIdx) .. ".png")
                    bubble.gif.frames[frameIdx] = frameTex
                end

                local baseSize = math.floor(math.max(64, math.min(100, 84 / math.max(0.65, currentZoom))))
                local size = baseSize * scale

                local tailW = math.floor(18 * scale)
                local tailH = math.floor(12 * scale)
                local gap = math.floor(3 * scale)

                local drawX = headX - size / 2
                local drawY = (headY - gap - tailH + 2) - size - floatOffset
                local tailX = headX - tailW / 2
                local tailY = drawY + size - 2

                ensureUiTextures()

                -- 1. Speech bubble pointer pointing towards head
                if GifEmotes.pointerTex then
                    drawer:drawTextureScaled(GifEmotes.pointerTex, tailX, tailY, tailW, tailH, alpha, 1, 1, 1)
                end

                -- 2. Dark circular obsidian glass backdrop
                if GifEmotes.backTex then
                    drawer:drawTextureScaled(GifEmotes.backTex, drawX, drawY, size, size, alpha * 0.95, 1, 1, 1)
                end

                -- 3. Animated GIF frame
                if frameTex then
                    drawer:drawTextureScaled(frameTex, drawX, drawY, size, size, alpha, 1, 1, 1)
                end

                -- 4. Radiant gold outer bezel ring
                if GifEmotes.ringTex then
                    drawer:drawTextureScaled(GifEmotes.ringTex, drawX, drawY, size, size, alpha, 1, 1, 1)
                end
            end
        end

        for i = 1, #toRemove do
            local key = toRemove[i]
            if key then
                GifEmotes.ActiveBubbles[key] = nil
            end
        end
    end)
end

-- Register pure render hook on OnPostUIDraw
Events.OnPostUIDraw.Add(GifEmotes.renderBubbles)
