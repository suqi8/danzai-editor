# 用组件搭建场景

## 目录
1. 坐标系
2. 找组件编号
3. 摆放计算（落地、贴合）
4. build spec 格式
5. 完整流程示例
6. 做得好看的几条经验

## 1. 坐标系

左手坐标系，Y 轴朝上。

| 轴 | position / scale | model_angle（弧度） |
|---|---|---|
| X | 右为正 | 俯仰，正值为低头 |
| Y | 上为正 | 偏航，正值为右转 |
| Z | 前为正 | 翻滚，正值为逆时针 |

旋转按 Z → X → Y 的顺序应用。`eggy.py build` 里的 `angle_deg` 写角度，脚本会自动换成弧度。

## 2. 找组件编号

```text
python <skill>/scripts/eggy.py cli docs search "球体" --docset fs-component --limit 5
```

每个结果里要记下三样：

- `编号（prefab_key）`：创建时用的 key。
- `模型尺寸（包围盒半长，相对于中心点）`：半长 (hx, hy, hz)。
- `模型中心点（相对于模型实际位置）`：中心偏移 (cx, cy, cz)。大多数组件是 (0, hy, 0)，也就是原点在底面中心。

关键词要换几种说法试，比如「树」可以搜「树木」「植物」。优先选外观符合描述、尺寸合适、不是机关的组件，避开弹射、传送、陷阱这类功能组件，除非用户就是要它们。在 fs-component 里实测查到过的基础形状：

| 名称 | 编号 | 半长 | 中心点 |
|---|---|---|---|
| 球 | 1701160 | (2.98, 3.0, 2.98) | (0, 3.0, 0) |
| 基础圆柱 | 105210 | (1.5, 1.5, 1.5) | (0, 1.5, 0) |

「基础方块」「基础几何_圆锥」等条目的格式不一样，搜索结果里可能没有显示编号，要换关键词再查。找不到编号就告诉用户，不要猜。

## 3. 摆放计算

没有旋转时，组件包围盒在世界坐标里是：

```text
底面 y = pos.y + (cy - hy) * sy
顶面 y = pos.y + (cy + hy) * sy
中心   = pos + (cx*sx, cy*sy, cz*sz)
尺寸   = 2 * (hx*sx, hy*sy, hz*sz)
```

要让 A 落在 B 的顶面上：先算出 B 的顶面 y，再让 A 的底面 y 等于它。

想用实测值代替文档数字时，可以读 `get_unit_space_info`，但要注意它返回的 **`aabb_center` 不算缩放和旋转**：它只是 position 加上未缩放的中心偏移，直接拿来用会算错。`aabb_size` 是对的。没有旋转时这样换算：

```lua
local s = EditorAPI.get_unit_space_info(<B 的 id>)      -- 字段是 Vector3，用 .x .y .z 取值
local cy = (s.aabb_center.y - s.position.y) * s.scale.y  -- 缩放后的中心偏移
local top = s.position.y + cy + s.aabb_size.y / 2         -- B 的顶面
return top
```

比如新建地图模板里自带的「地砖0」：position.y = 0，scale.y = 1，aabb_center.y = 1，aabb_size.y = 2，算出顶面 y = 2。

有旋转时，用旋转后的 AABB 近似：把三个半轴向量分别旋转，再取 8 个角点的最小值和最大值。

旋转之后部件「朝哪边」很难靠心算判断，比如鼻子、手臂、尖角朝向。先用一个部件试一下，截图确认方向对了，再批量套用同样的角度。

## 4. build spec 格式

```json
{
  "group": "PIG",
  "items": [
    {"key": 1701160, "pos": [0, 2, 10], "scale": [1.2, 0.9, 1.6], "color": "#F2A6B4", "name": "body"},
    {"key": 1701160, "pos": [0, 4.6, 13.6], "scale": 0.55, "color": "#F2A6B4", "name": "head"},
    {"key": 105210, "pos": [0.9, 0, 8.6], "scale": [0.25, 0.7, 0.25], "angle_deg": [0, 0, 0], "color": [230, 150, 165], "name": "leg_fl"}
  ]
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `group` | 建议填 | 名字前缀。生成的名字是 `<group>_<序号三位>_<name>`，以后查找和删除都按它 |
| `key` | `key` 和 `prefab` 二选一 | 组件编号（prefab_key）。创建前会校验，在官方文档和当前地图里都查不到就整批停止；确认是地图自定义预设时加 `--trust-keys` |
| `prefab` | `key` 和 `prefab` 二选一 | 组件名，比如 `"中式大鼎"`，由编辑器解析成编号。同名只取第一个，解析不到就整批停止 |
| `pos` | 是 | 世界坐标 [x, y, z]，是组件原点的位置，不是包围盒中心 |
| `scale` | 否 | [sx, sy, sz]，或一个数表示等比缩放 |
| `angle_deg` | 否 | [rx, ry, rz]，单位是度 |
| `color` | 否 | `#RRGGBB`、`[r,g,b]` 或整数，写进第 1 个染色区 `paint_area1` |
| `colors` | 否 | 最多 4 个，依次写进 `paint_area1` 到 `paint_area4`，写 `null` 的区不改。很多组件不止一个染色区，比如冰刺，只设 `color` 会剩下原色。各区默认色可以在 docs search 结果的「染色1–4」里看到 |
| `name` | 否 | 部件名 |

运行：

```text
python <skill>/scripts/eggy.py build spec.json --dry-run   # 只看生成的 Lua
python <skill>/scripts/eggy.py build spec.json             # 真正创建，每批 10 个，批间隔 0.2 秒
```

输出 JSON 里的 `created` 列出每个新组件的 id 和名字，`errors` 列出失败项。失败项如果带了 id，说明组件已经建出来，只是某个属性没设成功，要么补设，要么删掉。

## 5. 完整流程示例

```text
python eggy.py status                                   # editable 必须为 True
python eggy.py find "出生点"                            # 普通模式是包含匹配
python eggy.py find ".*(地砖|出生点)" --regex           # 正则从名字开头匹配，所以前面要加 .*
python eggy.py cli docs search "球体" --docset fs-component --limit 5
# 写 spec.json（坐标按第 3 节算好）
python eggy.py build spec.json --dry-run
python eggy.py build spec.json
python eggy.py shot editor                              # 然后用 Read 打开 PNG 看
# 不满意：改 spec，先删整组再重建
python eggy.py delete "^PIG_"                           # 预览
python eggy.py delete "^PIG_" --yes
python eggy.py build spec.json
# 用户满意后
python eggy.py cli map save
```

编辑器视口的截图角度由用户当前的镜头决定。要从特定角度看，可以用 `focus_unit(id)` 把镜头对准某个组件，或者让用户转一下镜头。刚建好的组件会被自动选中，所以截图上会带选框，属于正常现象。

## 6. 做得好看的几条经验

- **由大到小**：先放大形体（身体、地面、主建筑），再放中等部件，最后放细节装饰。每一层都截图看一次，比一次放完再改省事得多。
- **别完全对称**：左右稍微错开一点位置、角度或大小，看起来更自然。
- **配色**：一个主色，配一两个辅色，再用少量强调色。同一材质的部件颜色可以有轻微明暗差，会更有体积感。
- **能用现成组件就别硬拼**：先在 fs-component 里搜有没有接近的成品，比如树、宝座、中式大鼎，再决定是否用基础形状拼。
- **注意数量**：每个组件都占用值（地图有上限，实测一张默认地图是 25000）。拼一个复杂造型通常几十个组件，超过 50 个要先告诉用户。
- **写实风格有上限**：基础形状拼出来的是积木或雕塑感。真要写实，需要导入自定义模型，见 `blender-to-eggy.md`。
