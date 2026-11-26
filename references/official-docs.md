# 官方资料地图

编辑器在本机放了一整套给 AI 用的官方资料，由编辑器的预检脚本下载，用 `editor-cli env-res update` 更新。这些资料是唯一的事实来源，本技能只告诉你去哪里读。

读 `.md`、`.mdc` 一律按 UTF-8 解码：PowerShell 5.1 的 `Get-Content` 默认按 ANSI 解码，会读出乱码。用 Read 工具或 `cat` 读就没问题。

## 1. 先按地图模式选目录

`eggy.py status` 里的 `editor_mode` 决定读哪套：

| 模式 | 规则文件 | 技能目录 |
|---|---|---|
| `fs`（帧同步，大多数乐园地图） | `~/.eggitor/codex/fs/rules/eggy-fs.mdc` | `~/.eggitor/codex/fs/skills/` |
| `se`（状态同步） | `~/.eggitor/codex/se/rules/eggy-se.mdc` | `~/.eggitor/codex/se/skills/` |

两套 API 不通用：FS 用 `EditorAPI.*` 和 `GameAPI.*`，SE 用 `editor:GetService(...)`。只读当前模式那一套。`~/.eggitor/<模式>/.codemaker/` 是给 VSCode 插件用的副本，不要当成来源。

## 2. FS 技能各管什么

路径前缀都是 `~/.eggitor/codex/fs/skills/`：

| 技能 | 用途 |
|---|---|
| `eggy-fs-editor-cli/SKILL.md` | CLI 总览：编辑和试玩两种状态、exec 平台、日志命令 |
| `.../references/editing/scene-editing.md` | 坐标系、组件预设查询、包围盒计算 |
| `.../references/editing/unit-attr-json.md` | 属性批量读写（**部分函数在本机版本不存在**，见 verified-api.md） |
| `.../references/editing/motor-overwrite.md` | 运动器 MotorList，用来做摆动、旋转、移动的组件 |
| `.../references/playtesting/player-control.md` | 试玩中操控玩家 |
| `.../references/state-awareness.md` | 状态判断、连接失败时的标准提示 |
| `.../references/code-sync.md` | `code init/diff/push/pull` 机制 |
| `.../references/features/eggy-editor-cli-eui/` | UI 界面（EUI）编辑 |
| `.../references/features/eggy-editor-cli-montage/` | 剧情动画 |
| `eggy-fs-lua-coding/` | 写地图玩法 Lua（运行时 GameAPI） |
| `eggy-fs-playtest/` | 试玩跑测 |
| `eggy-fs-log-triage/` | 日志排错 |
| `eggy-fs-qa/` | 功能测试 |
| `eggy-fs-design/`、`eggy-fs-dev-plan/` | 玩法设计文档、开发计划 |

SE 这一套多了 `eggy-se-plugin-dev`（编辑器插件）、`eggy-se-perf`（性能）、`eggy-se-editor-cli/.../eggy-se-editor-cli-publish`（发布）等。

运行时 Lua 的类型定义：`~/.eggitor/eggy_api/api_lua_doc/EggyAPI.lua`（8000 多行，用 grep 按函数名查，不要整个读进来）。

## 3. 动态查询（随编辑器版本走，最准）

| 想知道 | 命令 |
|---|---|
| 某个编辑时 API 的签名 | `cli api get-editor <名字>` |
| 按关键词找编辑时 API | `cli api search-editor <关键词>` |
| 全部编辑时 API | `cli api list-editor` |
| 运行时 API | `cli api get <名字>`、`cli api search <关键词>` |
| 组件编号、外观、尺寸 | `cli docs search "<物品>" --docset fs-component` |
| 编辑器机制和做法 | `cli docs search "<问题>" --docset fs-manual` |
| CLI 子命令的详细说明 | `cli <命令> --help`；`cli help detail <命令>`（只覆盖部分命令） |
| 环境是否健康 | `cli doctor`（只读） |

`docs search` 的结果要看「标题」：命中的是组件条目还是操作说明，和你要找的不对时换 docset 或换关键词。结果没有官方链接时，用前最好再用 `api get-editor` 或实测确认一下。

## 4. 官方的 Claude 接入方式（可选）

`editor-cli env-res guide --target claude --mode fs` 会打印官方的接入教程，内容是把 `~/.eggitor/codex/<模式>/skills/*` 用 junction 链接进 Claude 的技能目录，再注入规则。这样做之后每个会话都会加载十几个 `eggy-*` 技能的描述，会多占一些上下文。

本技能采用的是按需去读原文的方式，效果相同，但不常驻。只有用户明确想要官方技能直接出现在技能列表里时，才按那份教程去链接；链接前先给用户看要改哪些目录。
