-- GifEmotes_NetClient.lua
-- Client-side network receiver for overhead GIF emote bubbles

require "GifEmotes_Registry"
require "GifEmotes_Core"

local function OnServerCommand(module, command, args)
    if module ~= "GifEmotes" then return end

    if command == "playGif" and args and args.playerOnlineId and args.gifId then
        local remoteChar = getPlayerByOnlineID(args.playerOnlineId)
        if remoteChar and not remoteChar:isLocalPlayer() then
            GifEmotes.triggerEmoteRemote(remoteChar, args.gifId, args.duration)
        end
    elseif command == "syncGifs" then
        pcall(function()
            if GifEmotes.hotReload then
                GifEmotes.hotReload(true)
            end
        end)
    end
end

Events.OnServerCommand.Add(OnServerCommand)
