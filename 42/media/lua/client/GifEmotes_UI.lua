-- GifEmotes_UI.lua
-- Stay Gold Edition UI Manager for GIF Emotes in Project Zomboid
-- Features:
-- - Assign any GIF to Radial Slots 1, 2, 3, or 4 with 1 click
-- - Live slot badges in available GIFs list ([1], [2], [3], [4])
-- - Dynamic refresh button and auto-discovery of newly dropped GIFs / MP4s
-- - Native Explorer folder opener via showFolderInDesktop()
-- - All text localized via getText() to eliminate Cyrillic mojibake

require "ISUI/ISCollapsableWindow"
require "ISUI/ISScrollingListBox"
require "ISUI/ISButton"
require "ISUI/ISLabel"
require "GifEmotes_Registry"
require "GifEmotes_Core"

GifEmotes_UI = ISCollapsableWindow:derive("GifEmotes_UI")

function GifEmotes_UI:new(x, y, width, height, character)
    local o = ISCollapsableWindow.new(self, x, y, width, height)
    o.character = character or getSpecificPlayer(0)
    o.title = getText("UI_GifEmotes_Title")
    o.resizable = false
    o.backgroundColor = {r=0.06, g=0.06, b=0.08, a=0.96}
    o.borderColor = {r=0.96, g=0.62, b=0.07, a=0.85}
    o.backTex = getTexture("media/textures/ui/bubble_back.png")
    o.ringTex = getTexture("media/textures/ui/bubble_ring.png")
    local firstSlotGif = GifEmotes.Slots and GifEmotes.Slots[1]
    o.selectedGif = (firstSlotGif and GifEmotes.Registry and GifEmotes.Registry[firstSlotGif]) or (GifEmotes.Registry and GifEmotes.Registry["remielle_dance"])
    return o
end

function GifEmotes_UI:onMouseWheel(del)
    if self.listBox and self.listBox.onMouseWheel then
        return self.listBox:onMouseWheel(del)
    end
    return false
end

function GifEmotes_UI:createChildren()
    ISCollapsableWindow.createChildren(self)

    local padding = 15
    local topY = 35
    local colW = 200

    -- 1. Left Column: Available GIFs List
    self.listLabel = ISLabel:new(padding, topY, 18, getText("UI_GifEmotes_AvailableList"), 0.95, 0.75, 0.15, 1, UIFont.Small, true)
    self:addChild(self.listLabel)

    -- Refresh button to instantly discover new GIFs dropped into folder
    self.refreshBtn = ISButton:new(padding + colW - 24, topY - 2, 24, 20, "🔄", self, self.onRefreshList)
    self.refreshBtn:initialise()
    self.refreshBtn:instantiate()
    self.refreshBtn.borderColor = {r=0.96, g=0.62, b=0.07, a=0.5}
    self.refreshBtn.backgroundColor = {r=0.15, g=0.15, b=0.18, a=0.9}
    self:addChild(self.refreshBtn)

    local listH = 300
    self.listBox = ISScrollingListBox:new(padding, topY + 22, colW, listH)
    self.listBox:initialise()
    self.listBox:instantiate()
    self.listBox.itemheight = 28
    self.listBox.font = UIFont.Small
    self.listBox.drawBorder = true
    self.listBox.borderColor = {r=0.96, g=0.62, b=0.07, a=0.4}
    self.listBox.backgroundColor = {r=0.03, g=0.03, b=0.04, a=0.8}
    self.listBox.textColor = {r=0.92, g=0.92, b=0.95, a=1.0}
    self.listBox.selectedTextColor = {r=1.0, g=0.85, b=0.25, a=1.0}
    self.listBox:setOnMouseDownFunction(self, self.onSelectGif)

    -- Dedicated Stay Gold smooth & responsive mouse wheel scrolling
    self.listBox.onMouseWheel = function(_self, del)
        local totalH = #_self.items * _self.itemheight
        local maxScroll = math.max(0, totalH - _self:getHeight())
        local cur = _self:getYScroll() or 0
        local nextY = cur - (del * 35)
        if nextY > 0 then nextY = 0 end
        if nextY < -maxScroll then nextY = -maxScroll end
        _self:setYScroll(nextY)
        return true
    end

    -- Dedicated Stay Gold scrollbar styling
    if self.listBox.vscroll then
        self.listBox.vscroll.background = true
        self.listBox.vscroll.backgroundColor = {r=0.06, g=0.06, b=0.09, a=0.95}
        self.listBox.vscroll.borderColor = {r=0.96, g=0.62, b=0.07, a=0.5}
        self.listBox.vscroll:setX(colW - 16)
        self.listBox.vscroll:setWidth(16)
        self.listBox.vscroll:setHeight(listH)
    end

    self:addChild(self.listBox)

    self:populateGifList()
    GifEmotes_UI.instance = self
    GifEmotes.instance = self

    -- 2. Right Column: Preview & Action Controls
    local rightX = padding + colW + 15
    local rightW = self.width - rightX - padding
    local previewSize = 96
    self.previewX = rightX + math.floor((rightW - previewSize) / 2)
    self.previewY = topY + 15
    self.previewSize = previewSize

    -- Play Button (Immediate test overhead)
    local btnW = rightW
    local btnH = 26
    local playY = topY + 160

    self.playBtn = ISButton:new(rightX, playY, btnW, btnH, getText("UI_GifEmotes_Play"), self, self.onPlayEmote)
    self.playBtn:initialise()
    self.playBtn:instantiate()
    self.playBtn.borderColor = {r=0.96, g=0.62, b=0.07, a=0.7}
    self.playBtn.backgroundColor = {r=0.18, g=0.14, b=0.05, a=0.9}
    self:addChild(self.playBtn)

    -- Slot Assignment Section (Slots 1, 2, 3, 4)
    local slotLabelY = playY + btnH + 10
    self.slotLabel = ISLabel:new(rightX, slotLabelY, 18, getText("UI_GifEmotes_AssignToSlot"), 0.95, 0.75, 0.15, 1, UIFont.Small, true)
    self:addChild(self.slotLabel)

    local halfW = math.floor((btnW - 8) / 2)
    local slotBtnH = 25
    local row1Y = slotLabelY + 20
    local row2Y = row1Y + slotBtnH + 6

    self.slot1Btn = ISButton:new(rightX, row1Y, halfW, slotBtnH, getText("UI_GifEmotes_Slot1"), self, function() self:onAssignSlot(1) end)
    self.slot1Btn:initialise()
    self.slot1Btn:instantiate()
    self.slot1Btn.borderColor = {r=0.96, g=0.62, b=0.07, a=0.6}
    self.slot1Btn.backgroundColor = {r=0.12, g=0.12, b=0.15, a=0.9}
    self:addChild(self.slot1Btn)

    self.slot2Btn = ISButton:new(rightX + halfW + 8, row1Y, halfW, slotBtnH, getText("UI_GifEmotes_Slot2"), self, function() self:onAssignSlot(2) end)
    self.slot2Btn:initialise()
    self.slot2Btn:instantiate()
    self.slot2Btn.borderColor = {r=0.96, g=0.62, b=0.07, a=0.6}
    self.slot2Btn.backgroundColor = {r=0.12, g=0.12, b=0.15, a=0.9}
    self:addChild(self.slot2Btn)

    self.slot3Btn = ISButton:new(rightX, row2Y, halfW, slotBtnH, getText("UI_GifEmotes_Slot3"), self, function() self:onAssignSlot(3) end)
    self.slot3Btn:initialise()
    self.slot3Btn:instantiate()
    self.slot3Btn.borderColor = {r=0.96, g=0.62, b=0.07, a=0.6}
    self.slot3Btn.backgroundColor = {r=0.12, g=0.12, b=0.15, a=0.9}
    self:addChild(self.slot3Btn)

    self.slot4Btn = ISButton:new(rightX + halfW + 8, row2Y, halfW, slotBtnH, getText("UI_GifEmotes_Slot4"), self, function() self:onAssignSlot(4) end)
    self.slot4Btn:initialise()
    self.slot4Btn:instantiate()
    self.slot4Btn.borderColor = {r=0.96, g=0.62, b=0.07, a=0.6}
    self.slot4Btn.backgroundColor = {r=0.12, g=0.12, b=0.15, a=0.9}
    self:addChild(self.slot4Btn)

    -- Open GIFs Folder Button
    local folderY = row2Y + slotBtnH + 12
    self.openFolderBtn = ISButton:new(rightX, folderY, btnW, btnH, getText("UI_GifEmotes_OpenFolder"), self, self.onOpenFolder)
    self.openFolderBtn:initialise()
    self.openFolderBtn:instantiate()
    self.openFolderBtn.borderColor = {r=0.5, g=0.5, b=0.6, a=0.7}
    self.openFolderBtn.backgroundColor = {r=0.10, g=0.10, b=0.12, a=0.9}
    self:addChild(self.openFolderBtn)

    -- Close Button
    local bottomY = self.height - 35
    self.closeBtn = ISButton:new(self.width - 90 - padding, bottomY - 5, 90, 24, getText("UI_GifEmotes_Close"), self, self.onClose)
    self.closeBtn:initialise()
    self.closeBtn:instantiate()
    self.closeBtn.borderColor = {r=0.6, g=0.6, b=0.6, a=0.4}
    self:addChild(self.closeBtn)

    self.statusText = ""
    self.statusTime = 0
end

local function getSlotForGif(gifId)
    if not GifEmotes.Slots or not gifId then return nil end
    for i = 1, 4 do
        if GifEmotes.Slots[i] == gifId then
            return i
        end
    end
    return nil
end

function GifEmotes_UI:onRefreshList()
    if GifEmotes.hotReload then
        GifEmotes.hotReload(true)
    end
    self:populateGifList()
    self.statusText = getText("UI_GifEmotes_Refreshed") or "Список и текстуры обновлены!"
    self.statusTime = getTimestampMs()
end

function GifEmotes_UI:populateGifList()
    if not self.listBox then return end
    local curScroll = self.listBox:getYScroll() or 0
    self.listBox:clear()

    -- Collect and sort all registered gifs alphabetically by display name
    local sortedList = {}
    if GifEmotes.Registry then
        for id, gif in pairs(GifEmotes.Registry) do
            table.insert(sortedList, { id = id, gif = gif, name = gif.name or id })
        end
    end
    table.sort(sortedList, function(a, b)
        return tostring(a.name):lower() < tostring(b.name):lower()
    end)

    local targetIdx = 1
    for idx, entry in ipairs(sortedList) do
        local id = entry.id
        local gif = entry.gif
        local slotNum = getSlotForGif(id)
        local badge = slotNum and string.format("[%d] ", slotNum) or "    "
        local displayName = badge .. (gif.name or id)
        self.listBox:addItem(displayName, gif)
        if self.selectedGif and self.selectedGif.id == id then
            targetIdx = idx
        end
    end

    local totalH = #self.listBox.items * self.listBox.itemheight
    self.listBox:setScrollHeight(totalH)
    self.listBox.selected = targetIdx

    -- Restore and clamp scroll position
    local maxScroll = math.max(0, totalH - self.listBox:getHeight())
    if curScroll > 0 then curScroll = 0 end
    if curScroll < -maxScroll then curScroll = -maxScroll end
    self.listBox:setYScroll(curScroll)

    if self.listBox.vscroll then
        self.listBox.vscroll:updatePos()
    end
end

function GifEmotes_UI:onSelectGif(item)
    if item then
        self.selectedGif = item
    end
end

function GifEmotes_UI:onPlayEmote()
    if self.selectedGif and self.character then
        GifEmotes.triggerEmote(self.character, self.selectedGif.id)
        self.statusText = getText("UI_GifEmotes_PlayedSuccess")
        self.statusTime = getTimestampMs()
    end
end

function GifEmotes_UI:onAssignSlot(slotNum)
    if not self.selectedGif or not slotNum then return end
    GifEmotes.Slots = GifEmotes.Slots or {}
    GifEmotes.Slots[slotNum] = self.selectedGif.id
    GifEmotes.saveSlots()

    self:populateGifList()
    self.statusText = getText("UI_GifEmotes_SlotAssigned") .. tostring(slotNum) .. ": " .. tostring(self.selectedGif.name)
    self.statusTime = getTimestampMs()
end

function GifEmotes_UI:onOpenFolder()
    local docFolder = (getMyDocumentFolder and getMyDocumentFolder()) or "Zomboid"
    local sep = (getFileSeparator and getFileSeparator()) or "/"
    local folderPath = docFolder .. sep .. "mods" .. sep .. "GifEmotes"

    local fs = getZomboidFileSystem and getZomboidFileSystem()
    if fs and fs.getModDir then
        local ok, md = pcall(fs.getModDir, fs, "GifEmotes")
        if ok and md and md ~= "" then
            folderPath = md
        end
    end

    if folderPath then
        folderPath = folderPath:gsub("/", "\\")
    end

    if showFolderInDesktop then
        pcall(function()
            showFolderInDesktop(folderPath)
        end)
    end

    if Clipboard and Clipboard.setClipboard then
        Clipboard.setClipboard(folderPath)
    end

    pcall(function()
        local fw = getFileWriter("gif_action.txt", true, false)
        if fw then
            fw:write("OPEN_MOD_FOLDER\r\n")
            fw:close()
        end
    end)

    self.statusText = getText("UI_GifEmotes_PathCopied") .. folderPath
    self.statusTime = getTimestampMs()
end

function GifEmotes_UI:onClose()
    GifEmotes_UI.instance = nil
    GifEmotes.instance = nil
    self:setVisible(false)
    self:removeFromUIManager()
end

function GifEmotes_UI:prerender()
    ISCollapsableWindow.prerender(self)
end

function GifEmotes_UI:render()
    ISCollapsableWindow.render(self)

    -- Render Preview Box
    if self.selectedGif then
        local px = self.previewX
        local py = self.previewY
        local psize = self.previewSize

        -- 1. Dark circular glass backdrop
        if self.backTex then
            self:drawTextureScaled(self.backTex, px, py, psize, psize, 0.95, 1, 1, 1)
        end

        -- 2. Animated frame calculation
        local now = getTimestampMs()
        local totalMs = math.max(100, math.floor(self.selectedGif.durationSec * 1000))
        local currentSec = (now % totalMs) / 1000
        local frameIdx = math.floor(currentSec * self.selectedGif.fps) % self.selectedGif.frameCount

        if not self.selectedGif.frames then self.selectedGif.frames = {} end
        local frameTex = self.selectedGif.frames[frameIdx]
        if not frameTex then
            if GifEmotes.getOrLoadTexture then
                frameTex = GifEmotes.getOrLoadTexture(self.selectedGif.basePath .. tostring(frameIdx) .. ".png")
            else
                frameTex = getTexture(self.selectedGif.basePath .. tostring(frameIdx) .. ".png")
            end
            self.selectedGif.frames[frameIdx] = frameTex
        end

        if frameTex then
            self:drawTextureScaled(frameTex, px, py, psize, psize, 1, 1, 1, 1)
        end

        -- 3. Gold ring
        if self.ringTex then
            self:drawTextureScaled(self.ringTex, px, py, psize, psize, 1, 1, 1, 1)
        end

        -- 4. Info text below preview
        local infoY = py + psize + 8
        local currentSlot = getSlotForGif(self.selectedGif.id)
        local titleText = self.selectedGif.name .. (currentSlot and string.format(" (Слот %d)", currentSlot) or "")
        local durText = string.format("%.1f %s (%d %s, %d FPS)", self.selectedGif.durationSec, getText("UI_GifEmotes_Sec"), self.selectedGif.frameCount, getText("UI_GifEmotes_Frames"), self.selectedGif.fps)
        self:drawTextCentre(titleText, px + psize / 2, infoY, 0.96, 0.75, 0.15, 1, UIFont.Small)
        self:drawTextCentre(durText, px + psize / 2, infoY + 16, 0.7, 0.7, 0.7, 1, UIFont.Small)
    end

    -- Status message or instruction tip at bottom
    local bottomY = self.height - 30
    local now = getTimestampMs()
    if self.statusText and (now - self.statusTime < 4500) then
        self:drawText(self.statusText, 15, bottomY, 0.4, 0.9, 0.4, 1, UIFont.Small)
    else
        self:drawText(getText("UI_GifEmotes_Tip"), 15, bottomY, 0.6, 0.6, 0.6, 1, UIFont.Small)
    end
end

-- Global helper to open or toggle the UI window
function GifEmotes.openUI(character)
    pcall(function()
        if GifEmotes.checkSync then
            GifEmotes.checkSync(true)
        else
            pcall(function()
                if type(package) == "table" and type(package.loaded) == "table" then
                    package.loaded["GifEmotes_CustomRegistry"] = nil
                end
            end)
            if reloadLuaFile then
                reloadLuaFile("media/lua/shared/GifEmotes_CustomRegistry.lua")
            else
                require "GifEmotes_CustomRegistry"
            end
        end
    end)

    local activeInstance = GifEmotes_UI.instance or GifEmotes.instance
    if activeInstance and activeInstance:getIsVisible() then
        activeInstance:onClose()
        return
    end

    local sw = getCore():getScreenWidth()
    local sh = getCore():getScreenHeight()
    local winW = 480
    local winH = 430
    local winX = math.floor((sw - winW) / 2)
    local winY = math.floor((sh - winH) / 2)

    local ui = GifEmotes_UI:new(winX, winY, winW, winH, character)
    ui:initialise()
    ui:addToUIManager()
    GifEmotes.instance = ui
    GifEmotes_UI.instance = ui
end
