-- GifEmotes_RadialHook.lua
-- Dedicated configurable keybind (default: G) and 5-Slice Radial Menu for GIF Emotes
-- Features:
-- - Exactly 5 radial slices: [⚙️] Menu + Slots [1], [2], [3], [4]
-- - Radial slices display slot numbers [1]-[4] and can be triggered via mouse, gamepad or keys 1, 2, 3, 4!
-- - Uses native Build 42 PZAPI.ModOptions for in-game settings key remapping under "Моды" tab.

require "ISUI/ISRadialMenu"
pcall(function() require "PZAPI/ModOptions" end)
require "GifEmotes_Registry"
require "GifEmotes_Core"

GifEmotes = GifEmotes or {}
GifEmotes.KEYBIND_ID = "OpenMenuKey"
GifEmotes.DEFAULT_KEY = Keyboard.KEY_G

-- ─── 1. Register B42 ModOptions Keybind in "Моды" tab ───────────────
local modOptionsInstance = nil
pcall(function()
    if PZAPI and PZAPI.ModOptions then
        local bindName = getText("UI_GifEmotes_KeyBindName")
        local modTitle = getText("UI_GifEmotes_ModTitle")
        modOptionsInstance = PZAPI.ModOptions:create("GifEmotes", modTitle)
        modOptionsInstance:addTitle(modTitle)
        modOptionsInstance:addKeyBind(
            GifEmotes.KEYBIND_ID,
            bindName,
            GifEmotes.DEFAULT_KEY,
            "UI_GifEmotes_KeyBindTooltip"
        )
    end
end)

-- Retrieve currently bound key
function GifEmotes.getBoundKey()
    local bound = nil
    pcall(function()
        if PZAPI and PZAPI.ModOptions and PZAPI.ModOptions.Dict and PZAPI.ModOptions.Dict["GifEmotes"] then
            local opt = PZAPI.ModOptions.Dict["GifEmotes"].dict[GifEmotes.KEYBIND_ID]
            if opt then
                local k = opt.element and opt.element.keyCode or opt.key
                if k and k > 0 then
                    bound = k
                end
            end
        end
    end)
    if bound and bound > 0 then return bound end

    if getCore() and getCore().getKey then
        local k = getCore():getKey("GIF Emotes")
        if k and k > 0 then return k end
    end
    return GifEmotes.DEFAULT_KEY
end

-- ─── 2. 5-Slice Radial Menu Display ─────────────────────────────────

function GifEmotes.showRadialMenu(playerObj)
    if not playerObj or playerObj:isDead() then return end

    -- Check for freshly added GIFs so wheel is always updated
    pcall(function()
        if GifEmotes.checkSync then
            GifEmotes.checkSync(false)
        end
    end)

    local playerIndex = playerObj:getPlayerNum()
    local menu = getPlayerRadialMenu(playerIndex)
    if not menu then return end

    -- Toggle behavior: if already open, close it
    if menu:isReallyVisible() then
        if menu.joyfocus then
            setJoypadFocus(playerIndex, nil)
        end
        menu:undisplay()
        return
    end

    menu:clear()

    local defaultIcon = getTexture("media/textures/ui/bubble_ring.png")
    local gearIcon = getTexture("media/textures/ui/gif_icon.png") or defaultIcon

    -- Slot 0: Open Full GIF Management UI
    menu:addSlice(getText("UI_GifEmotes_RadialSettings"), gearIcon, GifEmotes.onOpenGuiSlice, playerObj)

    -- Slots 1 to 4: The 4 Quick Emote Slices
    for i = 1, 4 do
        local gifId = GifEmotes.Slots and GifEmotes.Slots[i]
        local gif = gifId and GifEmotes.Registry and GifEmotes.Registry[gifId]
        local title = string.format("[%d] %s", i, gif and gif.name or getText("UI_GifEmotes_EmptySlot"))
        local icon = defaultIcon

        if gif and gif.basePath then
            if GifEmotes.getOrLoadTexture then
                icon = GifEmotes.getOrLoadTexture(gif.basePath .. "0.png") or defaultIcon
            else
                icon = getTexture(gif.basePath .. "0.png") or defaultIcon
            end
        end

        menu:addSlice(title, icon, GifEmotes.onSelectGifSlotSlice, playerObj, i)
    end

    -- Dismiss on right click anywhere
    menu.onRightMouseDown = function(self) self:undisplay() end
    menu.onRightMouseDownOutside = function(self) self:undisplay() end

    -- Center on screen and display
    menu:center()
    menu:addToUIManager()

    if JoypadState and JoypadState.players and JoypadState.players[playerIndex + 1] then
        setJoypadFocus(playerIndex, menu)
    end
end

function GifEmotes.onSelectGifSlotSlice(playerObj, slotNum)
    if not playerObj or not slotNum then return end
    local gifId = GifEmotes.Slots and GifEmotes.Slots[slotNum]
    if gifId and GifEmotes.Registry and GifEmotes.Registry[gifId] then
        GifEmotes.triggerEmote(playerObj, gifId)
    else
        -- If slot is empty, open UI to assign
        GifEmotes.openUI(playerObj)
    end
end

function GifEmotes.onOpenGuiSlice(playerObj)
    if GifEmotes.openUI then
        GifEmotes.openUI(playerObj)
    end
end

-- ─── 3. Key Press Listener & Number Key (1-4) Shortcuts ─────────────

local function onKeyPressed(key)
    local player = getSpecificPlayer(0)
    if not player or player:isDead() then return end

    local menu = getPlayerRadialMenu(0)

    -- If radial menu is currently open: allow triggering slots 1, 2, 3, 4 directly via keyboard
    if menu and menu:isReallyVisible() then
        if key == Keyboard.KEY_1 then
            menu:undisplay()
            GifEmotes.onSelectGifSlotSlice(player, 1)
            return
        elseif key == Keyboard.KEY_2 then
            menu:undisplay()
            GifEmotes.onSelectGifSlotSlice(player, 2)
            return
        elseif key == Keyboard.KEY_3 then
            menu:undisplay()
            GifEmotes.onSelectGifSlotSlice(player, 3)
            return
        elseif key == Keyboard.KEY_4 then
            menu:undisplay()
            GifEmotes.onSelectGifSlotSlice(player, 4)
            return
        elseif key == Keyboard.KEY_0 or key == Keyboard.KEY_5 then
            menu:undisplay()
            GifEmotes.onOpenGuiSlice(player)
            return
        elseif key == Keyboard.KEY_ESCAPE or key == GifEmotes.getBoundKey() then
            menu:undisplay()
            return
        end
    end

    local boundKey = GifEmotes.getBoundKey()
    if key ~= boundKey then return end

    -- Don't trigger when game is paused or typing in text/chat
    if UIManager.getSpeedControls() and (UIManager.getSpeedControls():getCurrentGameSpeed() == 0) then
        return
    end

    GifEmotes.showRadialMenu(player)
end

Events.OnKeyPressed.Add(onKeyPressed)

-- Register legacy key for B41 only if PZAPI is not available
Events.OnGameStart.Add(function()
    pcall(function()
        if not (PZAPI and PZAPI.ModOptions) and getCore() and getCore().addKey then
            getCore():addKey("GIF Emotes", GifEmotes.DEFAULT_KEY)
        end
    end)
    print("[GifEmotes] Loaded successfully. Bound key code: " .. tostring(GifEmotes.getBoundKey()))
end)
