---
name: danzai-editor
description: 不碰屏幕、通过官方 editor-cli 操控本机「蛋仔派对」PC 编辑器（乐园 / 原点 / 帧同步编辑器）：查状态、执行编辑器 Lua、按组件编号批量搭建和修改场景（位置、缩放、旋转、颜色、命名）、删除组件、保存地图、试玩与输入注入、截图看效果、读日志、查官方文档和编辑器实时 API；还包括把 Blender 模型减面后导入蛋仔的流程。用户提到蛋仔、蛋仔派对、Eggy Party、蛋仔编辑器、乐园编辑器、editor-cli、eggitor，或者想在蛋仔地图里搭东西、摆组件、改颜色、做关卡、试玩测试、写地图 Lua、做 UI，或者要把 3D 模型放进蛋仔时，都要用这个技能。即使用户没提 CLI 也要用，也不要改用截屏点击（computer use）去操作编辑器。
---

# 蛋仔编辑器无屏幕控制

蛋仔派对 PC 编辑器运行时会在本机 127.0.0.1 开一个控制服务（EditorMcpProxy）。网易官方的 `editor-cli` 就是它的命令行入口，能读写场景、执行 Lua、试玩、截图和读日志。所以凡是操作编辑器的事都走 CLI，不要去点屏幕：CLI 结果确定、可以回读校验，也不会抢用户的鼠标。

本技能只做入口。具体 API 的用法以官方技能原文和编辑器的实时 API 元数据为准（见 `references/official-docs.md`），它们会随编辑器自动更新。这里补的是 Claude Code 在 Windows 上的调用方式、本机实测过的行为，以及官方没覆盖的 Blender 导入流程。

## 1. 开工三步

1. **定位 CLI**：用 `%USERPROFILE%\.eggitor\cli\editor-cli.exe`。游戏安装目录的 `party_pc\bin\` 下也有一个 `editor-cli.exe`，那是 0.4.x 旧版，命令不全，别用。
2. **查状态**：`python <skill>/scripts/eggy.py status`。
   - 返回 `running: true`、`ready: true`、`editor_state: idle` 才能编辑场景。
   - `editor_mode` 是 `fs`（帧同步）还是 `se`（状态同步），决定后面读哪套官方文档。
3. **连不上**（超时、连接被拒、输出为空、退出码非 0）：原样告诉用户「请打开蛋仔编辑器并进入地图后再试」，并附上错误原文。不要自己猜原因，比如端口占用、防火墙之类。

`<skill>` 指本技能所在目录，也就是本文件所在的文件夹。

## 2. 怎么调用

优先用封装脚本 `scripts/eggy.py`（只依赖 Python 3 标准库）。它会自动定位 CLI、切到 CLI 目录执行（EditorAPI 依赖这个工作目录）、用 UTF-8 文件传 Lua，绕开所有 shell 引号问题。

| 用途 | 命令 |
|---|---|
| 状态 | `python eggy.py status` |
| 执行 Lua（文件或 stdin） | `python eggy.py lua script.lua`，`--platform lockstep` 用于试玩中 |
| 探测接口是否存在 | `python eggy.py probe [函数名...]` |
| 按名字找组件 | `python eggy.py find "出生点"`（包含匹配）；`find "^PIG_" --regex`（正则从名字开头匹配，要包含匹配就写 `.*词`） |
| 批量搭建 | `python eggy.py build spec.json`（先加 `--dry-run` 看生成的 Lua） |
| 按组删除 | `python eggy.py delete "^PIG_"`，默认只预览，加 `--yes` 才删 |
| 截图 | `python eggy.py shot editor` 或 `shot game`，输出 PNG 路径，再用 Read 打开看 |
| 其他子命令透传 | `python eggy.py cli map dirty`、`cli play start`、`cli log tail --lines 100` 等 |

直接调 CLI 也行，但 Lua 一律写进 `.lua` 文件再用 `exec --file`。命令行内联 Lua 会被 PowerShell 和 bash 的引号规则弄坏，CLI 自己的错误提示也这么建议。

只有 `--platform editor` 会返回值（写 `return ...`）。`lockstep` 和 `local` 只负责提交，要看结果得在 Lua 里 `print`，再用 `cli log grep <标记>` 读回来。

## 3. 本机实测过的行为（editor-cli 0.20.17，FS 地图，2026-11-26）

官方文档有时比你装的编辑器版本新，下面几条和文档不一致，以实测为准。换了编辑器版本先跑一次 `eggy.py probe` 复核。完整对照表见 `references/verified-api.md`。

- **`editor-unit` 命令族在 FS 地图上不可用**（`list`、`delete` 都报 `query_scene_units is unavailable`）。改用 EditorAPI：创建用 `create_obstacle`，删除用 `destroy_obstacle`，查找用 `query_unit_ids`。
- **官方文档里的 `get_unit_json`、`edit_unit_attrs`、`get_unit_attr_schema`、`list_units_by_template` 在这个版本里不存在**。改用 `get_scene_unit_data`、`get_unit_attr`、`set_unit_attr`。
- **颜色**只能写整数 `0xRRGGBB`：`set_unit_attr(id, 'paint_area1', R*65536 + G*256 + B)`。传数组或 Vector3 不会报错，但会被静默忽略。
- **旋转**写入用弧度（`model_angle`）。`get_scene_unit_data` 读回来是**角度**，`get_unit_space_info` 读回来才是弧度，比较前先统一单位。
- **`get_unit_space_info` 的 `aabb_center` 不算缩放和旋转**，只有 `aabb_size` 是可信的。它返回的是 Vector3，要用 `.x`、`.y`、`.z` 取值。换算方法见 `references/scene-building.md` 第 3 节。
- **id 1 是试玩出生的蛋仔角色**：没有名字、编号为 0，但按「出生点」查名字能匹配到。不要删它，也不要改它。
- `create_obstacle(key, math.Vector3(x,y,z))` 直接返回新组件的 UnitID。缩放、旋转、颜色、名字都要创建后再设置。
- **编号写错会卡住编辑器**：`create_obstacle` 不会报错，而是返回一个无效 ID，接下来的调用会让编辑器主线程卡住 10 秒以上。所以编号要在创建前校验，`eggy.py build` 已经内置了这一步。自己写 Lua 时，也先用 `cli docs search "prefab_key <编号>" --docset fs-component` 确认编号存在。
- **超时不等于没执行**：报 `editor main thread busy` 或超时的时候，脚本可能已经部分甚至全部执行完了。重试前先 `find` 一下，否则会建出重复的组件。
- 编辑器 Lua 沙箱的坑：
  - 全局 `type()` 被改写，调用会报错，不要用。
  - 没有 `tonumber`。
  - `get_scene_unit_data` 返回的对象不能 `pairs` 遍历，但能按字段读，也能直接 `return` 出来。
- FS 地图里**没有** `editor` 全局对象，所以文档里的 `editor:GetService('PublishService')` 上传接口在 FS 地图上用不了。
- UnitID 只在当前这次加载内有效，重开地图或开始试玩后会变。用名字定位，不要把 ID 记下来复用。

## 4. 搭建场景的做法

详细流程、spec 格式和摆放计算见 `references/scene-building.md`，要点：

1. **组件编号只能查，不能编**：用 `python eggy.py cli docs search "<关键词>" --docset fs-component --limit 5`。从结果里取「编号（prefab_key）」「包围盒半长」「模型中心点」，用来算落地高度。spec 里也可以直接写 `"prefab": "中式大鼎"`，由编辑器按名字解析编号；但同名组件只会返回第一个，所以对外观有要求时，还是以文档查到的编号为准。要的东西查不到就如实告诉用户，不要猜编号。
2. **先看现场**：用 `find` 或 `lua` 读现有组件的位置和尺寸，新东西摆在空地上，别和已有组件穿插。
3. **统一命名前缀**：同一批组件用同一个前缀，比如 `PIG_001_body`。因为 UnitID 会变，以后查找、修改、整批删除都靠前缀。名字里的序号按 spec 内顺序编，所以不同的 spec 要用不同的 `group`。改同一个造型时，先整组删掉再重建。
4. **用 `build` 分批创建**：每批不超过 10 个，批间隔 0.2 秒，脚本已经处理好了。超过 50 个先跟用户说一声要等多久。
5. **截图看效果**：`shot editor`，然后用 Read 看图。要看真实光照和氛围，需要先 `cli play start` 再 `shot game`，看完 `cli play stop`。
6. **保存**：改动先停在内存里（`cli map dirty` 会显示 Dirty: yes）。用户确认效果后再 `cli map save`；用户一开始就说了「保存」的，可以直接存。

## 5. 安全边界

这些操作改的是用户自己的地图，有的不能撤销：

- `cli map reopen --force` 会丢掉所有未保存的改动，`cli stop <pid>` 会强杀编辑器。这两个都要用户明确同意才能做。
- 不要替用户发布地图，也不要上传资源。不要读出或回显 `~/.eggitor/cli/tokens.json`，里面是登录凭据。
- 删除前先不带 `--yes` 预览，把要删的名单列给用户看。正则太宽（比如 `.*`）的不要执行。
- 自己为了验证而创建的临时组件，用完要删掉，并且说明地图会因此显示「未保存」。
- 试玩中（`in_game_runtime: true`）编辑态的接口都读不到对象，要先 `cli play stop`，等 `editor_state` 回到 `idle` 再改。

## 6. 其他任务去哪里看

| 任务 | 去读 |
|---|---|
| 某个 API 的签名、参数 | `python eggy.py cli api get-editor <名字>`（编辑时）、`cli api get <名字>`（运行时）。比文档准，因为读的是当前编辑器 |
| 编辑器操作、机制做法 | `cli docs search "<问题>" --docset fs-manual`（SE 地图用 `manual`） |
| 试玩操控玩家、输入注入 | 官方 `eggy-fs-editor-cli/references/playtesting/player-control.md`，以及 `cli help detail input` |
| 写地图玩法 Lua、代码同步 | 官方 `eggy-fs-lua-coding`；同步用 `cli code init/diff/push` |
| UI（EUI） | 官方 `eggy-fs-editor-cli/references/features/eggy-editor-cli-eui/SKILL.md` |
| 剧情动画 | 官方 `.../eggy-editor-cli-montage/SKILL.md` |
| 查报错 | 官方 `eggy-fs-log-triage`，以及 `cli log trace --play-session <id> --text` |
| 玩法设计、开发计划、测试 | 官方 `eggy-fs-design`、`eggy-fs-dev-plan`、`eggy-fs-qa`、`eggy-fs-playtest` |
| Blender 模型放进蛋仔 | `references/blender-to-eggy.md` |

官方技能目录：`~/.eggitor/codex/fs/skills/`（FS）和 `~/.eggitor/codex/se/skills/`（SE）。各文件的用途和读法见 `references/official-docs.md`。读这些 `.md` 和 `.mdc` 要按 UTF-8 解码。

关于代码同步：官方规则区分 codemaker（VSCode 插件，会自动同步）和 Codex（纯 CLI）两种环境。Claude Code 属于纯 CLI 这一类，所以本地写的 Lua 不会自动进地图。试玩前要先 `code diff`；有改动、而且是你这次会话改的，就 `code push`。不是你改的，先问用户。
