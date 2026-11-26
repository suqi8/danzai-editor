# 本机实测的接口行为

环境：editor-cli 0.20.17、eggy_api 0.0.9、FS（帧同步）地图，2026-11-26 实测。

换了编辑器版本，或者遇到和这里不一致的情况，按文末的方法重新探测，以探测结果为准。

## EditorAPI（`exec --platform editor`）

| 函数 | 状态 | 实测要点 |
|---|---|---|
| `create_obstacle(key, math.Vector3(x,y,z))` | 可用 | 返回新 UnitID。签名还有第 3 个可选参数 `parent_uid` |
| `destroy_obstacle(unit_id)` | 可用 | 删除后 `query_unit_ids` 查不到，总数减 1 |
| `set_unit_attr(id, key, value)` | 可用 | 见下方属性写法 |
| `get_unit_attr(id, key)` | 可用 | `paint_area1` 返回整数 |
| `get_scene_unit_data(id)` | 可用 | 返回对象可按字段读（`d.name`、`d.position[1]`），不能 `pairs` 遍历。`model_angle` 读回来是**角度** |
| `get_unit_space_info(id)` | 可用 | 返回 position、model_angle（**弧度**）、scale、size、aabb_center、aabb_size，都是 Vector3，要用 `.x`、`.y`、`.z` 取值，不能用 `[1]`。**`aabb_center` 不算缩放和旋转**，等于 position 加上未缩放的中心偏移；`aabb_size` 和 `size` 是对的 |
| `query_unit_ids(name, use_regex)` | 可用 | `use_regex=false` 是**包含**匹配。`use_regex=true` 是**从名字开头匹配**：`出生点` 匹配不到「分阵营出生点1」，要写 `.*出生点`；`地砖\|出生点` 只会命中地砖。返回表可 `ipairs` |
| `get_all_unit_ids()` | 可用 | 含相机、天空等非组件对象，这些对象没有名字 |
| `get_first_unit_key_by_prefab_name(name, 'unit')` | 可用 | 组件名转编号。第二个参数必须是 `'unit'`，写 `'obstacle'` 等都返回 0。同名只返回第一个，比如「球」得到 1301080，而文档里的球是 1701160。查不到返回 0 |
| `get_unit_prefab_key(id)` | 可用 | 读已有组件的编号 |
| `get_units_by_unit_key(key)` | 可用 | 地图里所有用了这个编号的组件，可以用来确认地图自定义预设的编号有效 |
| `focus_unit(id)` | 可用 | 编辑器视口镜头对准这个组件，截图前用 |
| `get_selected_unit_ids()`、`get_unit_kv`、`set_unit_kv`、`take_screenshot`、`log` | 存在 | 未逐个深测 |
| `output_unit_prefab(eid, path)` | 存在 | 会把预设导出成文件，不要拿来查询 |
| `clone_unit`、`get_all_scene_unit_data`、`pick_units` | 实时元数据里有 | 未实测 |
| `get_unit_json`、`edit_unit_attrs`、`get_unit_attr_schema`、`list_units_by_template` | **不存在** | 官方 `unit-attr-json.md` 写了，但这个版本调用会报 `attempt to call a nil value` |

### 属性写法

| 属性 | 写入 | 备注 |
|---|---|---|
| `position` | `math.Vector3(x, y, z)` | Y 轴朝上 |
| `scale` | `math.Vector3(sx, sy, sz)` | 相对预设原始大小的倍数 |
| `model_angle` | `math.Vector3(rx, ry, rz)`，**弧度** | 应用顺序 Z→X→Y |
| `paint_area1`（以及 2–4） | **整数** `R*65536 + G*256 + B` | 写数组或 Vector3 时 Lua 不报错，但值被忽略，编辑器日志里会记一条 `set_unit_attr, Internal error`；`get_scene_unit_data` 读回 `[r,g,b]`。多数组件有不止一个染色区，比如冰刺，只改第 1 区会剩下原色；半透明材质染色后看起来偏浅 |
| `name` | 字符串 | 用来做批次前缀 |

## 不能动的对象

- **id 1 是试玩出生的蛋仔角色**（资源管理器里叫「蛋仔：试玩出生点」）。它在 `get_scene_unit_data` 里没有名字，编号是 0，但用 `query_unit_ids('出生点', false)` 或 `'.*出生点'` 都能匹配到它。批量删除和修改时要排除「没有名字或编号为 0」的对象，`eggy.py delete` 已经这么做了。

## 编辑器视口的小细节

- 新建的组件会被自动选中，所以 `screenshot editor` 截出来的图上带选框。

## 会卡住编辑器的情况

- **不存在的编号**：`create_obstacle(999999999, ...)` 不报错，返回一个无效 ID（实测 1412423519），日志里有 `set_unit_attr: unit_id ... is invalid or not editable`。之后的调用会让主线程卡住，CLI 报 `editor main thread busy (timeout 10.0s)`。创建后再检查 ID 也不可靠，两次实测里有一次仍然卡住，所以只能在创建前校验：`docs search "prefab_key <编号>" --docset fs-component`，匹配 `编号（prefab_key）: <编号>`。注意查询词必须带 `prefab_key`，只搜数字时前几条会被同编号的皮肤条目占满。
- **超时后的状态**：CLI 报超时或主线程忙的时候，脚本可能已经执行完。实测那批里两个有效组件都建出来了，属性也设好了，只有无效编号那个没有。重试前先按名字查。

## Lua 沙箱

- 全局 `type()` 被 sdk 改写过，会调用不存在的 `LuaAPI.get_value_type` 然后报错，不要用。
- 没有 `tonumber`，字符串也不会隐式转成数字。
- `editor` 全局对象**不存在**（FS 地图），所以 `editor:GetService(...)` 这一类 SE 风格的 API 都用不了，包括 `PublishService`。
- 返回值会被 CLI 打印成 Lua 表的文本，不是 JSON；`--json` 也只是把这段文本包进 `result.representation` 里。需要程序解析时，在 Lua 里拼成约定格式的字符串再返回，`eggy.py` 就是这么做的。
- 遍历 EditorAPI 本身（`pairs(EditorAPI)`）会失败，它不是普通的 Lua 表。要列函数清单用 `cli api list-editor`。

## editor-cli 子命令

| 命令 | FS 地图实测 |
|---|---|
| `status`、`--json status` | 可用 |
| `exec --file`、`exec --json` | 可用；内联 Lua 容易被 shell 引号弄坏，用 `--file` |
| `screenshot editor --json` | 可用，默认存到 `<游戏目录>/Documents/editor_cli_screenshots/editor-<时间>.png` |
| `map dirty`、`map save`、`map current`、`map list` | `dirty` 已实测，其他按帮助说明 |
| `api list-editor`、`api get-editor <名字>`、`api search-editor <关键词>` | 可用，FS 下共 247 个编辑时 API。这是最准的签名来源 |
| `docs search`（`fs-component`、`fs-manual`、`editor-api` 等） | 可用 |
| `editor-unit list`、`editor-unit delete` | **不可用**：`EDITOR_UNIT_SCAN_FAILED: query_scene_units is unavailable` |
| `editor-unit create`、`transform`、`set-property` | 未实测。`capabilities` 声称支持，但同样依赖扫描接口，大概率也不可用，直接用 EditorAPI |
| `help detail <命令>` | 只有部分命令有详细文档，比如 `input`、`env-res` |

## 两个可执行文件

- `~/.eggitor/cli/editor-cli.exe`：0.20.x，编辑器自动下载和更新，用这个。
- `<游戏安装目录>\party_pc\bin\editor-cli.exe`：0.4.0 旧版，只有 status、exec、eval、logs、screenshot 等少数命令。

## 怎么重新探测

```text
python <skill>/scripts/eggy.py probe                 # 常用函数是否存在
python <skill>/scripts/eggy.py cli api list-editor    # 当前编辑器的全部编辑时 API
python <skill>/scripts/eggy.py cli api get-editor <名字>
python <skill>/scripts/eggy.py cli doctor             # 只读环境诊断
python <skill>/scripts/eggy.py cli editor-unit capabilities
```
