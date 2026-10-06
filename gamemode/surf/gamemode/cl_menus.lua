-- Menus the server opens (SURF.Menu.Open, net message surf.Menu): each kind
-- is a function in SURF.Menus. The main menu's pages are in cl_hub.lua, the
-- shop and VIP in cl_shop.lua, the admin panel in cl_admin.lua.
local Menus = {}
SURF.Menus = Menus

net.Receive("surf.Menu", function()
	local kind = net.ReadString()
	local data = net.ReadTable()
	if Menus[kind] then Menus[kind](data) end
end)
