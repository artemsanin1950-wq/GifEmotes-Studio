-- GifEmotes_NetServer.lua
-- Server-side relay for multiplayer GIF emote bubbles

local function OnClientCommand(module, command, player, args)
    if module ~= "GifEmotes" then return end

    if command == "playGif" and player and args and args.gifId then
        local dur = tonumber(args.duration) or 5.5
        if dur > 6.0 then dur = 6.0 end
        if dur < 1.0 then dur = 5.0 end

        -- Broadcast to all connected clients
        sendServerCommand("GifEmotes", "playGif", {
            playerOnlineId = player:getOnlineID(),
            gifId = tostring(args.gifId),
            duration = dur
        })
    elseif command == "syncGifs" then
        -- Relay live sync notification to all connected clients
        sendServerCommand("GifEmotes", "syncGifs", {})
    end
end

Events.OnClientCommand.Add(OnClientCommand)
