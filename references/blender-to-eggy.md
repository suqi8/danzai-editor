# 把 Blender 模型放进蛋仔

组件拼不出写实效果，所以写实造型要在 Blender 里做好，再作为自定义模型导入蛋仔。导入这一步目前没法全自动，开始前先把门槛讲清楚，免得做完才发现传不上去。

## 1. 先确认三道门槛

| 门槛 | 内容 | 来源 |
|---|---|---|
| 权限 | 上传自定义模型需要**工匠等级 7 级以上**（上传自定义图片需要 10000 工匠点），不够可以找「地图蛋」申请 | `docs search "上传自定义模型" --docset fs-manual` |
| 面数 | 组件模型最多 **10000 面**，生物模型最多 **20000 面** | 同上 |
| 导入入口 | PC 编辑器：资源管理器 → 模型分类 →「选择模型」→ 选本地文件。FS 地图里没有 `editor` 全局对象，`PublishService` 用不了，所以这一步要**用户自己在界面里点** | fs-manual「人形生物2.0使用指南」；本机实测 |

其他：
- 2026-11-05 版本起，上传时有【使用LOD】选项，会自动生成两级低面数模型。
- 每个上传的模型都有资源 ID。个人上传、没有公开的资源，别人拿到 ID 也用不了。

SE 地图的文档里写了 `editor:GetService('PublishService'):PublishSync(fbx路径, {Name=...})` 可以用脚本上传，但本机没在 SE 地图上验证过。要用的话，先用 `eggy.py probe` 确认 `editor_global=yes`，再小规模试一次。

## 2. Blender 里的准备（用 Blender MCP 的 execute_blender_code）

### 2.1 量面数

```python
import bpy
dg = bpy.context.evaluated_depsgraph_get()
tot = 0
for o in bpy.data.objects:
    if o.type == 'MESH' and not o.hide_render and not o.hide_get():
        m = o.evaluated_get(dg).to_mesh()
        n = sum(len(p.vertices) - 2 for p in m.polygons)  # 三角面数
        o.evaluated_get(dg).to_mesh_clear()
        tot += n
        print(n, o.name)
print('total tris', tot)
```

按三角面算，留出余量：组件目标 9000 以内，生物目标 18000 以内。

### 2.2 减面

1. **先删看不见的东西**：被衣服盖住的身体、背面的小部件、地面、背景、旗杆这类场景道具。
2. **合并重复的小件**：成百上千片羽毛、珠串这种东西，换成一层带贴图的壳体，比逐个减面有效得多。
3. **按重要性分配预算**：脸、手、标志性轮廓分得多一些，躯干内侧、底面分得少一些。
4. **对每个物体加 Decimate**（Collapse 模式），`ratio = 分到的预算 / 当前面数`，然后应用修改器。减完用 `look` 从几个角度看一遍，轮廓崩了就把预算调回来。

### 2.3 材质烘焙

程序化材质（节点噪波、颜色渐变、按顶点着色）导出 FBX 后不会保留，必须烘焙成贴图：

1. 合并成一个或少数几个网格，用 Smart UV Project 展 UV。
2. 新建一张图片，比如 2048×2048，Cycles 下只烘焙 Diffuse 的 Color（关掉直接光和间接光）。
3. 把材质换成只接这张贴图的 Principled BSDF。

### 2.4 导出

- 应用所有变换（Ctrl+A），原点放在模型底面中心，这样在蛋仔里放到地面上更好算位置。
- 导出 FBX：只选网格，应用修改器，Path Mode 选 Copy 并勾选内嵌贴图。
- 导出后重新导入一次，检查面数和贴图有没有丢。

## 3. 导入后在蛋仔里摆放

1. 请用户在编辑器里导入 FBX，按需勾选【使用LOD】，然后把模型放进场景一次。
2. 用 `eggy.py find "<模型名>"` 找到它，再用 `lua` 脚本改位置、缩放和朝向，最后 `shot editor` 截图确认。
3. 需要很多份时，用 `clone_unit(id, pos, rot, scale)` 复制。它在实时元数据里有，但还没实测过，用前先 `cli api get-editor clone_unit` 看签名。

## 4. 从旧对话复原 Blender 场景

如果 Blender 场景是之前的 Claude 对话用脚本生成、而且没有保存的，可以从对话记录里把脚本取出来重放：

- 对话记录在 `~/.claude/projects/<项目目录名>/<会话 id>.jsonl`。
- 找出其中所有 `mcp__blender__execute_blender_code` 调用的 `code`，按顺序执行。
- 跳过只读的检查、截图、渲染那几步。
- 重放完按记录里打印的数字（顶点数、尺寸）逐项核对，再立刻 `save_as_mainfile` 存盘。
