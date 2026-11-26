#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 suqi8
"""蛋仔派对编辑器 editor-cli 封装（只依赖标准库）。

子命令：
  status                     读编辑器状态（摘要），不可编辑时退出码 2
  lua FILE|-                 执行 Lua（文件或 stdin），默认 --platform editor
  probe [NAME ...]           探测 EditorAPI 函数是否存在
  find PATTERN [--regex]     按名字查组件：id、名字、位置
  build SPEC.json            按 spec 批量创建组件（--dry-run 只打印 Lua）
  delete PATTERN             按名字正则删组件；默认只预览，--yes 才删
  shot [editor|game]         截图，打印 PNG 路径
  cli ARGS...                其余命令原样透传给 editor-cli

环境变量 EGGY_CLI 可覆盖 editor-cli 路径。
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------- CLI 调用

def cli_path() -> Path:
    env = os.environ.get("EGGY_CLI")
    if env:
        return Path(env)
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    name = "editor-cli.exe" if os.name == "nt" else "editor-cli"
    return home / ".eggitor" / "cli" / name


def run_cli(args, timeout=60):
    """在 CLI 所在目录执行，返回 (退出码, stdout, stderr)。"""
    exe = cli_path()
    if not exe.exists():
        sys.exit(f"未找到 editor-cli：{exe}\n请先启动一次蛋仔编辑器（它会把 CLI 下载到这里），或用 EGGY_CLI 指定路径。")
    p = subprocess.run([str(exe)] + list(args), cwd=str(exe.parent),
                       capture_output=True, timeout=timeout)
    return (p.returncode,
            p.stdout.decode("utf-8", "replace"),
            p.stderr.decode("utf-8", "replace"))


def exec_lua(code: str, platform="editor", timeout=30):
    """把 Lua 写进 UTF-8 临时文件，用 exec --file 执行。返回 (退出码, 输出文本)。"""
    fd, path = tempfile.mkstemp(suffix=".lua", prefix="eggy_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(code)
        rc, out, err = run_cli(["exec", "--platform", platform, "--file", path,
                                "--timeout", str(timeout)], timeout=timeout + 30)
        return rc, (out + err).strip()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def lua_str(s: str) -> str:
    """Python 字符串 → Lua 双引号字面量（保留中文原样）。"""
    s = str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
    return f'"{s}"'


def lua_num(x) -> str:
    if x is None:
        return "nil"
    f = float(x)
    return str(int(f)) if f.is_integer() and abs(f) < 1e15 else repr(f)


def unwrap_lua_string(out: str) -> str:
    """editor 平台返回字符串时，CLI 打印的是带引号的 Lua 字面量，这里去掉外层引号和转义。"""
    t = out.strip()
    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        t = t[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return t


def parse_color(c):
    """'#RRGGBB' / 'RRGGBB' / [r,g,b] / 整数 → 0xRRGGBB 整数（paint_area1 只认整数）。"""
    if c is None:
        return None
    if isinstance(c, int):
        return c
    if isinstance(c, (list, tuple)) and len(c) == 3:
        r, g, b = (int(v) for v in c)
        return r * 65536 + g * 256 + b
    s = str(c).strip().lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{6}", s):
        return int(s, 16)
    raise ValueError(f"无法识别的颜色：{c!r}（用 #RRGGBB、[r,g,b] 或整数）")


# ---------------------------------------------------------------- 子命令

def cmd_status(a):
    rc, out, err = run_cli(["--json", "status"], timeout=a.timeout + 10)
    try:
        st = json.loads(out)
    except json.JSONDecodeError:
        print((out + err).strip() or f"editor-cli 退出码 {rc}，无输出")
        print("\n连不上编辑器：请打开蛋仔编辑器并进入地图后重试。")
        return 1
    keys = ["running", "ready", "editor_mode", "editor_state", "edit_mode", "in_game_runtime",
            "map_name", "map_id", "play_session", "log_file"]
    for k in keys:
        if k in st:
            print(f"{k:16s} {st[k]}")
    editable = st.get("running") and st.get("ready") and st.get("edit_mode") and st.get("editor_state") == "idle"
    print(f"{'editable':16s} {bool(editable)}")
    return 0 if editable else 2


def read_text_any(data: bytes) -> str:
    """Windows 管道可能是 UTF-8 也可能是 GBK：先按 UTF-8（去 BOM），失败再退回 GBK。"""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("gbk", "replace")


def cmd_lua(a):
    data = sys.stdin.buffer.read() if a.file == "-" else Path(a.file).read_bytes()
    code = read_text_any(data)
    rc, out = exec_lua(code, a.platform, a.timeout)
    print(out)
    return rc


DEFAULT_PROBE = [
    "create_obstacle", "destroy_obstacle", "clone_unit", "set_unit_attr", "get_unit_attr",
    "get_scene_unit_data", "get_all_scene_unit_data", "query_unit_ids", "get_all_unit_ids",
    "get_selected_unit_ids", "get_unit_space_info", "get_unit_kv", "set_unit_kv", "focus_unit",
    "take_screenshot", "log",
    # 官方文档提到、但部分版本缺失的
    "get_unit_json", "edit_unit_attrs", "get_unit_attr_schema", "list_units_by_template",
]


def cmd_probe(a):
    names = a.names or DEFAULT_PROBE
    body = ";".join(
        f"do local ok, f = pcall(function() return EditorAPI[{lua_str(n)}] end) "
        f"r[#r+1] = {lua_str(n)} .. '=' .. ((ok and f ~= nil) and 'yes' or 'no') end"
        for n in names)
    code = f"local r = {{}}; {body}; r[#r+1] = 'editor_global=' .. ((editor ~= nil) and 'yes' or 'no'); return table.concat(r, ';')"
    rc, out = exec_lua(code, "editor", a.timeout)
    if rc != 0:
        print(out)
        return rc
    for item in unwrap_lua_string(out).split(";"):
        print(item.replace("=", "  ", 1))
    return 0


def _find_lua(pattern, regex):
    return f"""
local ids = EditorAPI.query_unit_ids({lua_str(pattern)}, {str(bool(regex)).lower()})
local r = {{}}
for _, id in ipairs(ids) do
  local d = EditorAPI.get_scene_unit_data(id)
  local p = d and d.position
  local s = d and d.scale
  local pos = p and (p[1] .. ',' .. p[2] .. ',' .. p[3]) or '?'
  local sc = s and (s[1] .. ',' .. s[2] .. ',' .. s[3]) or '?'
  local nm = tostring(d and d.name):gsub('[|;]', '_')
  local ok, key = pcall(EditorAPI.get_unit_prefab_key, id)
  r[#r+1] = tostring(id) .. '|' .. nm .. '|' .. pos .. '|' .. sc .. '|' .. tostring(ok and key or 0)
end
return table.concat(r, ';')
"""


def _parse_rows(out):
    t = unwrap_lua_string(out)
    return [row.split("|") for row in t.split(";") if row]


def cmd_find(a):
    rc, out = exec_lua(_find_lua(a.pattern, a.regex), "editor", a.timeout)
    if rc != 0:
        print(out)
        return rc
    rows = _parse_rows(out)
    if a.json:
        print(json.dumps([{"id": int(r[0]), "name": r[1], "position": r[2], "scale": r[3], "key": int(r[4])}
                          for r in rows], ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{r[0]:>12s}  {r[1]}  pos=({r[2]})  scale=({r[3]})  key={r[4]}")
        print(f"共 {len(rows)} 个")
    if not a.regex:
        print("（普通模式是包含匹配；--regex 是从名字开头匹配，要找包含某词请写 '.*词'）", file=sys.stderr)
    return 0


BUILD_HELPER = r"""
local res = {}
local function mk(i, key, x, y, z, sx, sy, sz, ax, ay, az, colors, name)
  local id
  local ok, err = pcall(function()
    id = EditorAPI.create_obstacle(key, math.Vector3(x, y, z))
    if id == nil then error('create_obstacle 返回 nil（编号不存在或当前不可编辑？）') end
    -- 编号不存在时 create_obstacle 不报错而是返回无效 id，此时再 set_unit_attr 会卡住编辑器主线程
    if EditorAPI.get_scene_unit_data(id) == nil then id = nil; error('编号无效：create_obstacle 返回的单位不存在') end
    if sx ~= nil then EditorAPI.set_unit_attr(id, 'scale', math.Vector3(sx, sy, sz)) end
    if ax ~= nil then EditorAPI.set_unit_attr(id, 'model_angle', math.Vector3(ax, ay, az)) end
    if colors ~= nil then
      for area = 1, 4 do
        if colors[area] ~= nil and colors[area] >= 0 then EditorAPI.set_unit_attr(id, 'paint_area' .. area, colors[area]) end
      end
    end
    if name ~= nil then EditorAPI.set_unit_attr(id, 'name', name) end
  end)
  if ok then
    res[#res+1] = 'OK|' .. i .. '|' .. tostring(id)
  else
    local msg = tostring(err):match('[^\n]*'):gsub('%[string "MCP_EVAL"%]:%d+: ', ''):gsub('[|;"]', ' ')
    res[#res+1] = 'ERR|' .. i .. '|' .. tostring(id) .. '|' .. msg
  end
end
"""


def resolve_prefab_names(items, timeout):
    """把 spec 里写 prefab（组件名）的条目解析成编号。名字解析不到时在创建前就报错。
    注意：同名组件可能不止一个，编辑器只返回第一个，和 docs search 查到的编号可能不同。"""
    names = sorted({it["prefab"] for it in items if "key" not in it and it.get("prefab")})
    if not names:
        return {}
    body = " ".join(
        f"r[#r+1] = {lua_str(n)} .. '=' .. tostring(EditorAPI.get_first_unit_key_by_prefab_name({lua_str(n)}, 'unit'))"
        for n in names)
    rc, out = exec_lua(f"local r = {{}} {body} return table.concat(r, '\\n')", "editor", timeout)
    if rc != 0:
        sys.exit(f"解析组件名失败：\n{out}")
    resolved = {}
    for line in unwrap_lua_string(out).replace("\\n", "\n").splitlines():
        n, _, k = line.rpartition("=")
        resolved[n] = int(k) if k.isdigit() else 0
    bad = [n for n in names if resolved.get(n, 0) == 0]
    if bad:
        sys.exit("这些组件名在编辑器里解析不到编号，请改用 docs search 查到的 key：" + "、".join(bad))
    return resolved


def validate_keys(keys, timeout):
    """创建前校验编号。编号不存在时 create_obstacle 不报错，而会让编辑器主线程卡住，所以必须事先拦下。
    1) 官方组件文档里精确命中「编号（prefab_key）: KEY」；2) 否则当前地图里已有同编号组件（地图自定义预设）。
    返回校验不过的编号列表。"""
    bad = []
    for k in sorted(set(keys)):
        # 查询词必须带 prefab_key：只搜裸数字时，前几条会被同编号的皮肤条目（skin=KEY_xxx）占满
        rc, out, err = run_cli(["docs", "search", f"prefab_key {k}", "--docset", "fs-component", "--limit", "5"], timeout=60)
        if rc == 0 and re.search(rf"编号（prefab_key）:\s*{k}\b", out):
            continue
        code = f"local n = 0 for _ in ipairs(EditorAPI.get_units_by_unit_key({k}) or {{}}) do n = n + 1 end return n"
        rc2, out2 = exec_lua(code, "editor", timeout)
        if rc2 == 0 and unwrap_lua_string(out2).strip().isdigit() and int(unwrap_lua_string(out2).strip()) > 0:
            continue
        bad.append(k)
    return bad


def _item_call(i, it, group):
    key = int(it["key"])
    if key <= 0:
        raise ValueError(f"第 {i} 项编号无效：{key}")
    x, y, z = (float(v) for v in it["pos"])
    sc = it.get("scale")
    if sc is not None and not isinstance(sc, (list, tuple)):
        sc = [sc, sc, sc]
    ang = it.get("angle_deg")
    ang = [math.radians(float(v)) for v in ang] if ang is not None else None
    # colors: 最多 4 个染色区 paint_area1..4（null 表示不改）；color 是只改第 1 区的简写
    colors = list(it.get("colors") or [])[:4]
    if it.get("color") is not None:
        colors = [it["color"]] + colors[1:] if colors else [it["color"]]
    colors = [parse_color(c) if c is not None else -1 for c in colors]
    color_lua = "{" + ", ".join(str(c) for c in colors) + "}" if colors else "nil"
    label = it.get("name", "")
    name = f"{group}_{i:03d}" + (f"_{label}" if label else "") if group else (label or None)
    args = [str(i), str(key), lua_num(x), lua_num(y), lua_num(z)]
    args += [lua_num(v) for v in sc] if sc else ["nil"] * 3
    args += [lua_num(v) for v in ang] if ang else ["nil"] * 3
    args += [color_lua, lua_str(name) if name else "nil"]
    return f"mk({', '.join(args)})", name


def cmd_build(a):
    spec = json.loads(read_text_any(Path(a.spec).read_bytes()))
    group = spec.get("group", "")
    items = spec["items"]
    for i, it in enumerate(items, 1):
        if "key" not in it and "prefab" not in it:
            sys.exit(f"第 {i} 项既没有 key 也没有 prefab")
    resolved = resolve_prefab_names(items, a.timeout)  # 只读；预览时也解析，好让预览里的编号是真的
    for it in items:
        if "key" not in it:
            it["key"] = resolved[it["prefab"]]
    if not a.trust_keys:
        bad = validate_keys([int(it["key"]) for it in items if "prefab" not in it], a.timeout)
        if bad:
            sys.exit("这些编号在官方组件文档和当前地图里都找不到，为避免卡住编辑器已停止，什么都没创建："
                     + ", ".join(map(str, bad))
                     + "\n确认是地图自定义预设等有效编号时，可加 --trust-keys 跳过校验。")
    batch = max(1, min(int(a.batch), 10))
    calls = [_item_call(i, it, group) for i, it in enumerate(items, 1)]
    batches = [calls[k:k + batch] for k in range(0, len(calls), batch)]
    if a.dry_run:
        for n, b in enumerate(batches, 1):
            print(f"-- batch {n}\n{BUILD_HELPER}" + "\n".join(c for c, _ in b) + "\nreturn table.concat(res, ';')\n")
        return 0
    created, errors = [], []
    names = {i: nm for i, (_, nm) in enumerate(calls, 1)}
    for n, b in enumerate(batches, 1):
        code = BUILD_HELPER + "\n".join(c for c, _ in b) + "\nreturn table.concat(res, ';')\n"
        rc, out = exec_lua(code, "editor", a.timeout)
        if rc != 0:
            # 超时 / 主线程忙 不等于没执行：按组前缀回查实际建出来的，避免重试时重复创建
            errors.append({"batch": n, "error": out})
            print(f"第 {n} 批返回失败，停止后续批次：\n{out}", file=sys.stderr)
            if group:
                time.sleep(2)
                rc2, out2 = exec_lua(_find_lua(f"^{re.escape(group)}_", True), "editor", a.timeout)
                if rc2 == 0:
                    seen = {r[1]: int(r[0]) for r in _parse_rows(out2)}
                    for i, nm in names.items():
                        if nm in seen and all(c["i"] != i for c in created):
                            created.append({"i": i, "id": seen[nm], "name": nm, "note": "批次报错但实际已创建"})
                    print("已按组前缀回查实际存在的组件；重试前先用 find 确认，避免重复创建。", file=sys.stderr)
            break
        for row in _parse_rows(out):
            i = int(row[1])
            if row[0] == "OK":
                created.append({"i": i, "id": int(row[2]), "name": names[i]})
            else:
                errors.append({"i": i, "id": row[2], "name": names[i], "error": "|".join(row[3:])})
        if n < len(batches):
            time.sleep(0.2)
    print(json.dumps({"group": group, "created": created, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 3


def cmd_delete(a):
    pat = a.pattern
    if not pat or re.fullmatch(r"\^?\.?\*?\$?", pat):
        sys.exit("拒绝执行：正则为空或会匹配全部组件。")
    rc, out = exec_lua(_find_lua(pat, True), "editor", a.timeout)
    if rc != 0:
        print(out)
        return rc
    all_rows = _parse_rows(out)
    # 没有名字或编号为 0 的不是普通组件（实测 id 1 是试玩出生的蛋仔角色），一律不删
    rows = [r for r in all_rows if r[1] != "nil" and r[4] not in ("0", "nil")]
    for r in all_rows:
        if r not in rows:
            print(f"{r[0]:>12s}  {r[1]}  （跳过：不是普通组件）")
    for r in rows:
        print(f"{r[0]:>12s}  {r[1]}  pos=({r[2]})")
    print(f"匹配 {len(rows)} 个")
    if not rows:
        return 0
    if not a.yes:
        print("这是预览；确认无误后加 --yes 执行删除。")
        return 0
    ids = ",".join(r[0] for r in rows)
    code = f"""
local done, fail = 0, {{}}
for _, id in ipairs({{{ids}}}) do
  local ok, err = pcall(EditorAPI.destroy_obstacle, id)
  if ok then done = done + 1 else fail[#fail+1] = tostring(id) .. ':' .. tostring(err) end
end
local left = 0
for _, id in ipairs(EditorAPI.query_unit_ids({lua_str(pat)}, true)) do
  local d = EditorAPI.get_scene_unit_data(id)
  if d and d.name ~= nil then left = left + 1 end
end
return 'deleted=' .. done .. ';left=' .. left .. ';fail=' .. table.concat(fail, ',')
"""
    rc, out = exec_lua(code, "editor", a.timeout)
    print(unwrap_lua_string(out))
    return rc


def cmd_shot(a):
    args = ["screenshot", a.target, "--json", "--timeout", str(a.timeout)]
    if a.out:
        args += ["--output", a.out]
    rc, out, err = run_cli(args, timeout=a.timeout + 30)
    try:
        d = json.loads(out)
        if d.get("path"):
            print(d["path"])
            return 0
    except json.JSONDecodeError:
        pass
    print((out + err).strip())
    if a.target == "game":
        print("提示：screenshot game 要看真实试玩画面需先 `cli play start`。", file=sys.stderr)
    return rc or 1


def cmd_cli(a):
    rc, out, err = run_cli(a.args, timeout=a.timeout + 60)
    sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    return rc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--timeout", type=int, default=30, help="单次请求超时秒数（默认 30）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    p = sub.add_parser("lua"); p.add_argument("file"); p.add_argument("--platform", default="editor",
                                                                      choices=["editor", "lockstep", "local", "server", "client"])
    p = sub.add_parser("probe"); p.add_argument("names", nargs="*")
    p = sub.add_parser("find"); p.add_argument("pattern"); p.add_argument("--regex", action="store_true"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("build"); p.add_argument("spec"); p.add_argument("--dry-run", action="store_true"); p.add_argument("--batch", type=int, default=10)
    p.add_argument("--trust-keys", action="store_true", help="跳过编号校验（仅限确认有效的地图自定义预设编号）")
    p = sub.add_parser("delete"); p.add_argument("pattern"); p.add_argument("--yes", action="store_true")
    p = sub.add_parser("shot"); p.add_argument("target", nargs="?", default="editor", choices=["editor", "game"]); p.add_argument("--out")
    p = sub.add_parser("cli"); p.add_argument("args", nargs=argparse.REMAINDER)

    # cli 子命令后面的参数原样透传（argparse 的 REMAINDER 会吞掉 --version 这类以 - 开头的参数）
    argv = sys.argv[1:]
    if "cli" in argv:
        k = argv.index("cli")
        head, rest = argv[:k + 1], argv[k + 1:]
        a = ap.parse_args(head)
        a.args = rest
        sys.exit(cmd_cli(a) or 0)
    a = ap.parse_args(argv)
    fn = {"status": cmd_status, "lua": cmd_lua, "probe": cmd_probe, "find": cmd_find, "build": cmd_build,
          "delete": cmd_delete, "shot": cmd_shot, "cli": cmd_cli}[a.cmd]
    sys.exit(fn(a) or 0)


if __name__ == "__main__":
    main()
