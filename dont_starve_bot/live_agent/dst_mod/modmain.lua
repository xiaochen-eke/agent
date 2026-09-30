-- ============================================================
-- Dify Live Co-pilot Collector (modmain.lua)
-- 功能：
--   1) 每 COLLECT_INTERVAL 秒采集主机玩家的实时状态 → print 到服务端日志
--      （DST 的 io 沙箱是只读的、写不了文件，日志是唯一可靠的对外通道）
--   2) 每 ADVICE_INTERVAL 秒读 data/dify_advice.json → 游戏内播报 AI 建议
-- 说明：不依赖 require("json")，自带纯 Lua JSON 编码器；建议文件用
--       "id\nmessage" 两行格式（第一行 id，其余为消息体），避免 Lua 解码。
-- ============================================================

-- 建议/动作文件：用 MODROOT（mod 自身目录）的绝对路径，不靠相对路径的 CWD 解析。
-- 实测 DST 里 io.open("dify_advice.json") 相对路径读不到 data/ 下的文件（CWD 解析不可靠），
-- 而 MODROOT 是 mod 加载器注入的绝对路径（指向 <游戏>/mods/DifyCollector/），稳定可靠。
-- bridge.py 是普通进程、不受沙箱限制，负责把 AI 建议/动作写进 mod 目录，mod 只负责读。
local function join_path(dir, name)
    if dir == "" then return name end
    if dir:sub(-1) == "/" or dir:sub(-1) == "\\" then return dir .. name end
    return dir .. "/" .. name
end
local ADVICE_PATH = join_path(MODROOT or "", "dify_advice.json")
-- 动作文件：格式 "id\nverb prefab\nrisk"（第一行 id，第二行 动词+空格+prefab，第三行风险）。
local ACTION_PATH = join_path(MODROOT or "", "dify_action.json")

local COLLECT_INTERVAL = 2   -- 状态采集间隔（秒）
local ADVICE_INTERVAL  = 2   -- 建议轮询间隔（秒）
local ACTION_INTERVAL  = 1   -- 动作轮询间隔（秒，比建议更勤，降低动作延迟）
local NEARBY_RADIUS    = 12  -- 附近实体扫描半径（游戏单位）

local last_advice_id = nil    -- 已播报的建议 id，用于去重
local last_action_id = nil    -- 已执行的动作 id，用于去重

-- 动作风险分级：low 自动执行 / medium 自动执行+警告 / high 弹 Y/N 确认。
-- risk 由 state_api 的 classify_risk 算好、随动作文件第三行下发；此表仅作旧格式兜底。
local HIGH_RISK_VERBS = { attack = true }
local PENDING_TIMEOUT = 10    -- 高风险动作等玩家确认的秒数，超时取消
local pending_action = nil    -- 等待确认的高风险动作 {verb, prefab}
local pending_since  = nil    -- 等待确认的起始时间

-- DST mod 沙箱会把 os/io/pcall 等"危险库"从全局环境置为 nil，
-- 必须从 GLOBAL 显式取用（GLOBAL 才是游戏真正的全局表）。
local os = GLOBAL.os
local io = GLOBAL.io
local string = GLOBAL.string
local table = GLOBAL.table

-- ------------------------------------------------------------
-- 纯 Lua JSON 编码器（字符串/数字/布尔/nil/表，支持嵌套）
-- ------------------------------------------------------------
local function escape_string(s)
    s = s:gsub("\\", "\\\\")
    s = s:gsub('"', '\\"')
    s = s:gsub("\n", "\\n")
    s = s:gsub("\r", "\\r")
    s = s:gsub("\t", "\\t")
    -- 其余控制字符统一转 \u00xx
    s = s:gsub("[%z\1-\8\11\12\14-\31]", function(c)
        return string.format("\\u%04x", string.byte(c))
    end)
    return s
end

local function json_encode(value)
    local t = type(value)
    if value == nil then
        return "null"
    elseif t == "boolean" then
        return value and "true" or "false"
    elseif t == "number" then
        return tostring(value)
    elseif t == "string" then
        return '"' .. escape_string(value) .. '"'
    elseif t == "table" then
        local is_array = true
        local max_idx = 0
        for k in pairs(value) do
            if type(k) ~= "number" or k < 1 or k % 1 ~= 0 then
                is_array = false
                break
            end
            if k > max_idx then max_idx = k end
        end
        if is_array and max_idx > 0 then
            local parts = {}
            for i = 1, max_idx do
                parts[#parts + 1] = json_encode(value[i])
            end
            return "[" .. table.concat(parts, ",") .. "]"
        else
            -- 空表或映射表都编码为对象
            local parts = {}
            for k, v in pairs(value) do
                parts[#parts + 1] = '"' .. tostring(k) .. '":' .. json_encode(v)
            end
            return "{" .. table.concat(parts, ",") .. "}"
        end
    end
    return "null"
end

-- ------------------------------------------------------------
-- 采集单个玩家状态
-- ------------------------------------------------------------
local function collect_player(player)
    local p = {
        prefab = player.prefab,
        name = player.name,
        health = nil, maxhealth = nil, hunger = nil, sanity = nil,
        temperature = nil, moisture = nil,
        position = { x = 0, y = 0, z = 0 },
        inventory = {},
        equipped = {},
        nearby = {},
    }

    if player.components.health then
        p.health = player.components.health.currenthealth
        p.maxhealth = player.components.health.maxhealth
    end
    if player.components.hunger then
        p.hunger = player.components.hunger.current
    end
    if player.components.sanity then
        p.sanity = player.components.sanity.current
    end
    if player.components.temperature then
        p.temperature = player.components.temperature.current
    end
    if player.components.moisture then
        p.moisture = player.components.moisture:GetMoisture()
    end

    if player.Transform then
        local x, y, z = player.Transform:GetWorldPosition()
        p.position = { x = x, y = y, z = z }
    end

    local inv = player.components.inventory
    if inv then
        if inv.itemslots then
            local counts = {}
            for _, item in pairs(inv.itemslots) do
                if item and item.prefab then
                    counts[item.prefab] = (counts[item.prefab] or 0) + 1
                end
            end
            p.inventory = counts
        end
        if inv.equipslots then
            local eq = {}
            for slot, item in pairs(inv.equipslots) do
                if item and item.prefab then
                    eq[tostring(slot)] = item.prefab
                end
            end
            p.equipped = eq
        end
    end

    -- 附近实体（按 prefab 计数；用 4 参 FindEntities 最稳妥，Lua 侧过滤）
    if player.Transform then
        local x, y, z = player.Transform:GetWorldPosition()
        local ents = GLOBAL.TheSim:FindEntities(x, y, z, NEARBY_RADIUS)
        local nearby = {}
        for _, e in ipairs(ents) do
            -- 排除 limbo（已入包/装备的玩家子实体），只统计真正在地上的东西，
            -- 否则 FindEntities 会把玩家自己背包里的物品也算进「附近」。
            if e and e.prefab and e.prefab ~= player.prefab and not e:IsInLimbo() then
                nearby[e.prefab] = (nearby[e.prefab] or 0) + 1
            end
        end
        p.nearby = nearby
    end

    return p
end

-- ------------------------------------------------------------
-- 采集并把状态"发"到日志（io 沙箱只读，不能写盘）
-- ------------------------------------------------------------
local function write_state()
    local payload = { ts = os.time(), world = {}, players = {} }

    local world = GLOBAL.TheWorld
    if world and world.state then
        payload.world = {
            season = world.state.season,
            phase = world.state.phase,
            day = world.state.cycles,
            remaining_in_season = world.state.remainingdaysinseason,
        }
    end

    -- 注意：DST 沙箱不提供 pcall，全部用防御式判空
    for _, player in pairs(GLOBAL.AllPlayers or {}) do
        if player and player.components then
            table.insert(payload.players, collect_player(player))
        end
    end

    -- io 沙箱只读，这里改用 print 打到服务端日志；bridge.py 抓取 [DIFY_STATE] 行
    print("[DIFY_STATE]" .. json_encode(payload))
end

-- ------------------------------------------------------------
-- 读取 advice.json（格式：第一行 id，其余为 message）
-- ------------------------------------------------------------
local function read_advice()
    local f = io.open(ADVICE_PATH, "r")
    if not f then return nil end
    local content = f:read("*a")
    f:close()
    if not content or content == "" then return nil end
    local newline = content:find("\n", 1, true)
    if not newline then return nil end
    local id = content:sub(1, newline - 1)
    local message = content:sub(newline + 1)
    if id == "" or message == "" then return nil end
    return { id = id, message = message }
end

local function poll_advice()
    local advice = read_advice()
    if not advice then return end
    if advice.id == last_advice_id then return end
    last_advice_id = advice.id

    local msg = "[AI 助手] " .. advice.message
    if GLOBAL.TheNet and GLOBAL.TheNet.Announce then
        GLOBAL.TheNet:Announce(msg)
    end
    for _, player in pairs(GLOBAL.AllPlayers or {}) do
        if player and player.components and player.components.talker then
            player.components.talker:Say(advice.message)
            break
        end
    end
end

-- ------------------------------------------------------------
-- 半自动动作执行（Phase 3：AI 代替玩家控制角色）
-- ------------------------------------------------------------
-- 播报：公屏公告 + 主机玩家气泡（与建议播报一致）
local function announce(msg)
    if GLOBAL.TheNet and GLOBAL.TheNet.Announce then
        GLOBAL.TheNet:Announce(msg)
    end
    for _, player in pairs(GLOBAL.AllPlayers or {}) do
        if player and player.components and player.components.talker then
            player.components.talker:Say(msg)
            break
        end
    end
end

-- 取「本地主机玩家」：优先找带 playercontroller 的（本地主机的角色），
-- 找不到就退回第一个有生命值的玩家。
local function get_local_player()
    for _, p in pairs(GLOBAL.AllPlayers or {}) do
        if p and p.components and p.components.playercontroller then
            return p
        end
    end
    for _, p in pairs(GLOBAL.AllPlayers or {}) do
        if p and p.components and p.components.health then
            return p
        end
    end
    return nil
end

-- 在背包里按 prefab 找一件物品
local function find_inventory_item(player, prefab)
    local inv = player.components.inventory
    if not inv or not inv.FindItem then return nil end
    return inv:FindItem(function(item) return item and item.prefab == prefab end)
end

-- 在附近按 prefab 找一个可攻击实体（有生命值、非自己）
local function find_nearby_entity(player, prefab)
    if not player.Transform then return nil end
    local x, y, z = player.Transform:GetWorldPosition()
    local ents = GLOBAL.TheSim:FindEntities(x, y, z, NEARBY_RADIUS)
    for _, e in ipairs(ents) do
        if e and e.prefab == prefab and e ~= player and e.components and e.components.health then
            return e
        end
    end
    return nil
end

-- 在附近按 prefab 找一个可拾取的地面物品（有 inventoryitem 组件）
local function find_nearby_item(player, prefab)
    if not player.Transform then return nil end
    local x, y, z = player.Transform:GetWorldPosition()
    local ents = GLOBAL.TheSim:FindEntities(x, y, z, NEARBY_RADIUS)
    for _, e in ipairs(ents) do
        -- 只捡「在地上」的物品：排除 limbo（已入包/装备，成为玩家子实体）和已有主人的，
        -- 否则会把刚拾取的东西再捡一遍，同一实体出现在两个背包槽 = 真复制。
        if e and e.prefab == prefab and e ~= player
            and e.components and e.components.inventoryitem
            and e:IsValid() and not e:IsInLimbo()
            and not e.components.inventoryitem:IsHeld() then
            return e
        end
    end
    return nil
end

-- 在附近找一个带指定组件的实体（如 sleepingbag 用于睡觉）
local function find_nearby_with_component(player, compname)
    if not player.Transform then return nil end
    local x, y, z = player.Transform:GetWorldPosition()
    local ents = GLOBAL.TheSim:FindEntities(x, y, z, NEARBY_RADIUS)
    for _, e in ipairs(ents) do
        if e and e ~= player and e.components and e.components[compname] then
            return e
        end
    end
    return nil
end

-- 在附近按 prefab 找一个可采集目标（真实动作：角色会走过去 + 播工作动画）：
--   chop/mine → 带 workable 组件且 action 匹配（树 CHOP / 矿 MINE）
--   harvest   → 带 pickable 组件且可采摘（草/浆果/花 PICK）
local function find_nearby_harvestable(player, prefab, verb)
    if not player.Transform then return nil end
    local x, y, z = player.Transform:GetWorldPosition()
    local ents = GLOBAL.TheSim:FindEntities(x, y, z, NEARBY_RADIUS)
    local want_action = nil
    if verb == "chop" then
        want_action = GLOBAL.ACTIONS.CHOP
    elseif verb == "mine" then
        want_action = GLOBAL.ACTIONS.MINE
    end
    for _, e in ipairs(ents) do
        if e and e.prefab == prefab and e ~= player and not e:IsInLimbo() then
            if verb == "harvest" then
                if e.components.pickable and e.components.pickable:CanBePicked() then
                    return e
                end
            elseif e.components.workable and e.components.workable:CanBeWorked() then
                if want_action == nil or e.components.workable.action == want_action then
                    return e
                end
            end
        end
    end
    return nil
end

-- 找一件能执行指定 action 的工具（装备栏优先，背包其次）。
-- 斧头含 CHOP、镐子含 MINE、斧镐两者都有（tool.actions 是 {[ACTION]=true} 映射）。
local function find_tool_for(player, action)
    local inv = player.components.inventory
    if not inv then return nil end
    local function is_tool(item)
        return item and item.components.tool and item.components.tool.actions
            and item.components.tool.actions[action]
    end
    if inv.equipslots and inv.equipslots[GLOBAL.EQUIPSLOTS.HANDS] then
        local held = inv.equipslots[GLOBAL.EQUIPSLOTS.HANDS]
        if is_tool(held) then return held end
    end
    return inv:FindItem(is_tool)
end

-- 读取动作文件（格式：第一行 id，第二行 "verb prefab"，第三行 risk）
local function read_action()
    local f = io.open(ACTION_PATH, "r")
    if not f then return nil end
    local content = f:read("*a")
    f:close()
    if not content or content == "" then return nil end
    local lines = {}
    for line in content:gmatch("[^\n]+") do
        table.insert(lines, line)
    end
    if #lines < 2 then return nil end
    local verb, prefab = lines[2]:match("^(%S+)%s*(%S*)")
    if not verb or verb == "" then return nil end
    return { id = lines[1], verb = verb, prefab = prefab or "", risk = lines[3] or "" }
end

-- 真正执行动作（低风险自动 / 高风险已确认后调用）
-- 返回值约定：设置 ok(布尔) + reason(字符串)，末尾统一播报 + 打印 [DIFY_ACT_RESULT]，
-- 供 bridge 解析后回传给 state_api /action/result，面板据此显示执行结果。
local function exec_action(a)
    local player = get_local_player()
    if not player then
        announce("[AI 助手] 找不到主机玩家，动作未执行")
        print("[DIFY_ACT_RESULT]" .. json_encode({id=a.id, verb=a.verb, prefab=a.prefab, ok=false, reason="找不到主机玩家"}))
        return
    end

    local ok = false
    local reason = "动作未识别"
    local verb = a.verb

    if verb == "eat" then
        local item = find_inventory_item(player, a.prefab)
        if item and player.components.eater then
            player.components.eater:Eat(item)
            ok, reason = true, "已吃 " .. a.prefab
        else
            reason = "背包里没有可食用的 " .. a.prefab
        end

    elseif verb == "equip" then
        local item = find_inventory_item(player, a.prefab)
        if item and player.components.inventory then
            player.components.inventory:Equip(item)
            ok, reason = true, "已装备 " .. a.prefab
        else
            reason = "背包里没有 " .. a.prefab
        end

    elseif verb == "attack" then
        local target = find_nearby_entity(player, a.prefab)
        if target and player.components.combat then
            player.components.combat:SetTarget(target)
            ok, reason = true, "已锁定攻击目标 " .. a.prefab
        else
            reason = "附近没有 " .. a.prefab
        end

    elseif verb == "drop" then
        local item = find_inventory_item(player, a.prefab)
        if item and player.components.inventory then
            player.components.inventory:DropItem(item)
            ok, reason = true, "已丢弃 " .. a.prefab
        else
            reason = "背包里没有 " .. a.prefab
        end

    elseif verb == "pickup" then
        local item = find_nearby_item(player, a.prefab)
        if item and item.components.inventoryitem then
            local inv = player.components.inventory
            -- 关键修复：给 GiveItem 显式指定一个「空槽」，跳过它内部的堆叠路径。
            -- 不指定槽时，背包里已有同类物品会走 stackable:Put 堆叠，而 Put 里
            -- self.stacksize = ... 是「属性赋值」，会触发 setter onstacksize →
            -- replica.inventoryitem:SetPickupPos → 访问客户端 classified netvar，
            -- hosted 游戏服务端为 nil → 崩溃（inventoryitem_replica.lua:225）。
            -- 指定空槽则走「直放」分支（itemslots[slot]=inst + OnPutInInventory），
            -- OnPutInInventory 内部 RemoveFromScene 正确把物品从世界移除，不崩也不复制。
            local emptyslot = nil
            for k = 1, inv.maxslots do
                if not inv.itemslots[k] then
                    emptyslot = k
                    break
                end
            end
            local src_pos = item:GetPosition()
            if emptyslot then
                inv:GiveItem(item, emptyslot, src_pos)
            else
                inv:GiveItem(item, nil, src_pos) -- 背包满兜底（可能触发堆叠崩溃，但极少）
            end
            ok, reason = true, "已拾取 " .. a.prefab
        else
            reason = "附近没有可拾取的 " .. a.prefab
        end

    elseif verb == "craft" then
        local builder = player.components.builder
        if builder and builder.DoBuild then
            local known = true
            if builder.KnowsRecipe then
                known = builder:KnowsRecipe(a.prefab)
            end
            if known then
                builder:DoBuild(a.prefab)
                ok, reason = true, "已尝试合成 " .. a.prefab .. "（缺材料/未解锁会自动失败）"
            else
                reason = "未解锁配方 " .. a.prefab
            end
        else
            reason = "无法合成（缺少 builder 组件）"
        end

    elseif verb == "sleep" then
        local bed = find_nearby_with_component(player, "sleepingbag")
        if bed and player.components.sleeper then
            player.components.sleeper:GoToSleep(bed)
            ok, reason = true, "已入睡"
        else
            reason = "附近没有可睡觉的床/帐篷"
        end

    elseif verb == "chop" or verb == "mine" then
        local target = find_nearby_harvestable(player, a.prefab, verb)
        if not target then
            reason = "附近没有可" .. (verb == "chop" and "砍" or "挖") .. "的 " .. a.prefab
        else
            local act = verb == "chop" and GLOBAL.ACTIONS.CHOP or GLOBAL.ACTIONS.MINE
            local tool = find_tool_for(player, act)
            if not tool then
                reason = "没有" .. (verb == "chop" and "斧头" or "镐子") .. "，无法" .. verb
            else
                player.components.playercontroller:DoAction(GLOBAL.BufferedAction(player, target, act, tool))
                ok, reason = true, "已前往" .. (verb == "chop" and "砍" or "挖") .. " " .. a.prefab
            end
        end

    elseif verb == "harvest" then
        local target = find_nearby_harvestable(player, a.prefab, verb)
        if not target then
            reason = "附近没有可采集的 " .. a.prefab
        else
            player.components.playercontroller:DoAction(GLOBAL.BufferedAction(player, target, GLOBAL.ACTIONS.PICK))
            ok, reason = true, "已前往采集 " .. a.prefab
        end

    elseif verb == "cook" then
        -- 烹饪：把背包里的食材放到附近的火源上烤熟
        local item = find_inventory_item(player, a.prefab)
        local cooker = find_nearby_with_component(player, "cooker")
        if item and cooker and player.components.playercontroller then
            player.components.playercontroller:DoAction(GLOBAL.BufferedAction(player, cooker, GLOBAL.ACTIONS.COOK, item))
            ok, reason = true, "已烹饪 " .. a.prefab
        else
            reason = "附近没有火源或背包没有可烹饪的 " .. a.prefab
        end

    elseif verb == "plant" then
        -- 种植：把背包里可种植的物件（松果/树苗/草/浆果丛）种到脚下
        local item = find_inventory_item(player, a.prefab)
        if item and item.components.deployable then
            item.components.deployable:Deploy(player:GetPosition(), player)
            ok, reason = true, "已种植 " .. a.prefab
        else
            reason = "背包里没有可种植的 " .. a.prefab
        end

    elseif verb == "build" then
        -- 建造/放置建筑：用 builder 把配方放置到玩家位置
        local builder = player.components.builder
        if builder and builder.DoBuild then
            local known = true
            if builder.KnowsRecipe then
                known = builder:KnowsRecipe(a.prefab)
            end
            if known then
                builder:DoBuild(a.prefab, player:GetPosition())
                ok, reason = true, "已尝试建造 " .. a.prefab .. "（缺材料/未解锁会自动失败）"
            else
                reason = "未解锁配方 " .. a.prefab
            end
        else
            reason = "无法建造（缺少 builder 组件）"
        end

    elseif verb == "explore" then
        -- 探索：朝随机方向走一段路（prefab 可空）
        if player.components.locomotor and player.Transform then
            local x, y, z = player.Transform:GetWorldPosition()
            local ang = math.random() * 2 * math.pi
            local dist = 15
            player.components.locomotor:WalkToPoint(GLOBAL.Vector3(x + math.cos(ang) * dist, 0, z + math.sin(ang) * dist), false)
            ok, reason = true, "已开始探索（朝随机方向移动）"
        else
            reason = "无法移动"
        end
    end

    announce("[AI 助手] " .. reason)
    print("[DIFY_ACT_RESULT]" .. json_encode({id=a.id, verb=a.verb, prefab=a.prefab, ok=ok, reason=reason}))
end

-- 动作轮询（状态机：低风险立即执行；高风险等 Y/N 确认，超时取消）
local function poll_action()
    -- 有等待确认的高风险动作：查 Y/N / 超时
    if pending_action then
        local inp = GLOBAL.TheInput
        if inp and inp.IsKeyDown then
            if inp:IsKeyDown(GLOBAL.KEY_Y) then
                exec_action(pending_action)
                pending_action, pending_since = nil, nil
                return
            elseif inp:IsKeyDown(GLOBAL.KEY_N) then
                announce("[AI 助手] 已取消动作 " .. pending_action.verb)
                print("[DIFY_ACT_RESULT]" .. json_encode({id=pending_action.id, verb=pending_action.verb, prefab=pending_action.prefab, ok=false, reason="玩家取消"}))
                pending_action, pending_since = nil, nil
                return
            end
        end
        if os.time() - pending_since > PENDING_TIMEOUT then
            announce("[AI 助手] 等待超时，已取消动作 " .. pending_action.verb)
            print("[DIFY_ACT_RESULT]" .. json_encode({id=pending_action.id, verb=pending_action.verb, prefab=pending_action.prefab, ok=false, reason="确认超时"}))
            pending_action, pending_since = nil, nil
        end
        return
    end

    -- 无待确认：读新动作
    local a = read_action()
    if not a then return end
    if a.id == last_action_id then return end
    last_action_id = a.id
    print("[DIFY_ACT] 收到动作 id=" .. a.id .. " verb=" .. a.verb .. " prefab=" .. (a.prefab or "") .. " risk=" .. (a.risk or ""))

    -- 风险分级：low 自动 / medium 自动+警告 / high 弹 Y/N（空则按动词兜底）
    local risk = a.risk
    if risk == "" then
        risk = HIGH_RISK_VERBS[a.verb] and "high" or "low"
    end

    if risk == "high" then
        pending_action = a
        pending_since = os.time()
        announce("[AI 助手] 想执行「" .. a.verb .. " " .. a.prefab
            .. "」，按 Y 确认 / N 取消（" .. PENDING_TIMEOUT .. " 秒内）")
    else
        if risk == "medium" then
            announce("[AI 助手] ⚠️ 中风险动作，已自动执行：" .. a.verb .. " " .. a.prefab)
        end
        exec_action(a)
    end
end

-- ------------------------------------------------------------
-- 初始物资：角色刚 spawn 时发「斧头×1 + 树枝×3 + 浆果×5」
-- （解决待办 1：背包空/无斧头 → chop/eat 测不通）
-- 只发一次（_dify_startkit_done 标记）；给物品时显式指定空槽走「直放」分支，
-- 避开可堆叠物品的 stacksize setter 崩溃（同 pickup 动作的修法）。
-- ------------------------------------------------------------
local function give_startkit(player)
    if player._dify_startkit_done then return end
    player._dify_startkit_done = true

    local inv = player.components.inventory
    if not inv then return end

    local kit = {
        "axe",
        "twigs", "twigs", "twigs",
        "berries", "berries", "berries", "berries", "berries",
    }

    local function give_into_empty_slot(item)
        for k = 1, inv.maxslots do
            if not inv.itemslots[k] then
                inv:GiveItem(item, k, player:GetPosition())
                return true
            end
        end
        return false
    end

    local given = {}
    for _, prefab in ipairs(kit) do
        local item = GLOBAL.SpawnPrefab(prefab)
        if item and give_into_empty_slot(item) then
            given[prefab] = (given[prefab] or 0) + 1
        end
    end

    announce(string.format(
        "[AI 助手] 已发放初始物资：斧头×%d、树枝×%d、浆果×%d",
        given["axe"] or 0, given["twigs"] or 0, given["berries"] or 0))
end

AddPlayerPostInit(function(inst)
    inst:ListenForEvent("ms_playerspawn", function(inst)
        if not (GLOBAL.TheWorld and GLOBAL.TheWorld.ismastersim) then return end
        -- 等 1 帧再发，确保 components.inventory 已就绪
        inst:DoTaskInTime(0.5, function() give_startkit(inst) end)
    end)
end)

-- ------------------------------------------------------------
-- 启动：仅在服务端（含本地主机）运行，等待世界初始化完成
-- ------------------------------------------------------------
AddSimPostInit(function()
    if not GLOBAL.TheNet:GetIsServer() then return end
    GLOBAL.TheWorld:DoPeriodicTask(COLLECT_INTERVAL, write_state)
    GLOBAL.TheWorld:DoPeriodicTask(ADVICE_INTERVAL, poll_advice)
    GLOBAL.TheWorld:DoPeriodicTask(ACTION_INTERVAL, poll_action)
    print("[DifyCollector] started. advice=" .. ADVICE_PATH .. " action=" .. ACTION_PATH)
end)
