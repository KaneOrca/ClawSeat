# TODO — SCAN-034 (scan_environment.py 扩展 + OpenClaw home 动态发现)

```
task_id: SCAN-034
source: planner (architect)
reply_to: planner (architect)
target: builder-codex (codex-chatgpt-coding)
repo: /Users/ywf/ClawSeat (experimental)
priority: P0
subagent-mode: OK (建议 2 个 subagent：A=scanner 扩展，B=machine_config + bootstrap)
scope: 3 处代码改动 + 1 个新脚本 + 测试
```

## Context

采纳**方向 B（hybrid）**：scanner 做确定性 bootstrap 产出 `machine/openclaw.json`，memory LLM 做 on-demand 查询层。
当前 `scan_openclaw()` 两大缺陷：
1. `home = HOME / ".openclaw"` **硬编码**（不同用户路径不一样会炸）
2. **不扫 agent 列表**（KODER-033 apply-koder-overlay.sh 菜单靠 `machine.toml` tenants，但 fresh 机器 TOML 是空的）

## OpenClaw home 发现链（planner 已验证可用）

1. `OPENCLAW_HOME` 环境变量（显式覆盖，最高）
2. `dirname $(openclaw config file)` —— 权威方式；CLI 会打印 `~/.openclaw/openclaw.json`，取其目录即 home
3. fallback `~/.openclaw/`（最后保底）

## Subagent A — `scan_environment.py::scan_openclaw()` 扩展

改 [scan_environment.py](/Users/ywf/ClawSeat/core/skills/memory-oracle/scripts/scan_environment.py) 的 `scan_openclaw()` 函数（第 263 行起）：

### A.1 — home 动态发现（替换当前硬编码）

```python
def _discover_openclaw_home() -> Path:
    # 1) env var
    env = os.environ.get("OPENCLAW_HOME")
    if env:
        return Path(env).expanduser()
    # 2) openclaw CLI
    try:
        r = subprocess.run(
            ["openclaw", "config", "file"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            # Output includes ~/, expand it
            path_line = r.stdout.strip().splitlines()[-1].strip()
            if path_line:
                return Path(path_line.replace("~", str(HOME))).parent
    except (FileNotFoundError, subprocess.TimeoutExpired):  # silent-ok
        pass
    # 3) fallback
    return HOME / ".openclaw"
```

### A.2 — 扫 agent 列表

在 `scan_openclaw()` 内加字段：

```python
data["agents"] = []
if data["exists"]:
    # Agent = 带 WORKSPACE_CONTRACT.toml 的 workspace-<name> 目录
    home = Path(data["home"])
    for d in sorted(home.iterdir()):
        if not d.is_dir():
            continue
        name = d.name
        # 兼容两种命名：workspace-<name> 或直接 <name>
        if name.startswith("workspace-"):
            agent_name = name[len("workspace-"):]
        elif (d / "WORKSPACE_CONTRACT.toml").exists():
            agent_name = name
        else:
            continue
        contract = d / "WORKSPACE_CONTRACT.toml"
        data["agents"].append({
            "name": agent_name,
            "workspace": str(d),
            "has_contract": contract.exists(),
        })
```

### A.3 — `home` 改用发现结果，而非硬编码

```python
home = _discover_openclaw_home()
data = {
    "scanned_at": now_iso(),
    "home": str(home),
    "exists": home.exists(),
    ...
}
```

### 测试

`tests/test_scan_openclaw.py`（新建或扩展现有）：
- mock `OPENCLAW_HOME=/tmp/fake-oc` → 验证产出 home=/tmp/fake-oc
- mock `openclaw` CLI 不存在 → 回退 `~/.openclaw/`
- mock 目录下有 `workspace-a` / `workspace-b` / 空 → 产出 agents 列表 2 项
- 空目录 → agents=[]

---

## Subagent B — `machine_config._openclaw_workspace_root()` 同步 + bootstrap 脚本

### B.1 — 统一 home 发现

把 `core/lib/machine_config.py:77` 的 `_openclaw_workspace_root()` 改为调用 scanner 的 `_discover_openclaw_home()`（可能需要把发现函数提到共享位置如 `core/lib/paths.py`）。避免两处逻辑各改各的。

### B.2 — 新建 `core/scripts/bootstrap_machine_tenants.py`

用途：读 `machine/openclaw.json.agents` → 写入 `~/.clawseat/machine.toml [openclaw_tenants.*]`。

```python
#!/usr/bin/env python3
"""Bootstrap ~/.clawseat/machine.toml tenants from memory scan output.

Called by ancestor Phase-A B1.6 after memory has produced machine/openclaw.json.
Idempotent: existing tenants stay if their workspace still exists; new agents appended.
"""
import json, sys
from pathlib import Path
from core.lib.machine_config import load_machine, save_machine, OpenClawTenant

def main(machine_memory_path: Path):
    oc_json = machine_memory_path / "machine" / "openclaw.json"
    if not oc_json.exists():
        print(f"ERR_NO_SCAN: {oc_json} not found", file=sys.stderr); return 2
    data = json.loads(oc_json.read_text())
    agents = data.get("agents", [])
    cfg = load_machine()
    added = 0
    for a in agents:
        name = a["name"]
        ws = Path(a["workspace"])
        if not ws.exists():
            continue
        if name in cfg.tenants:
            continue  # don't overwrite existing
        cfg.tenants[name] = OpenClawTenant(name=name, workspace=ws, description="auto-registered by scan")
        added += 1
    save_machine(cfg)
    print(f"OK: {added} tenant(s) added; {len(cfg.tenants)} total")
    return 0

if __name__ == "__main__":
    memory_root = Path(sys.argv[1] if len(sys.argv) > 1 else "~/.agents/memory").expanduser()
    sys.exit(main(memory_root))
```

### B.3 — 测试

`tests/test_bootstrap_machine_tenants.py`:
- mock memory 有 openclaw.json.agents=[a,b,c] → machine.toml 应有 3 tenants
- 已有 tenant 不被覆盖
- workspace 不存在的 skip

---

## Verification

```bash
bash -n <all modified files>
pytest tests/test_scan_openclaw.py tests/test_bootstrap_machine_tenants.py -v
# 真跑一次确认我的机器（已有 13 tenants）的 agents 字段正确
python3 core/skills/memory-oracle/scripts/scan_environment.py --only openclaw --output /tmp/scan-test/
cat /tmp/scan-test/machine/openclaw.json | jq '.home, .agents | length'
```

## 约束

- **不碰 memory-oracle/SKILL.md**——那走 SKILL-031 综合任务改
- **不改 apply-koder-overlay.sh**——已有 list_openclaw_tenants() 读 machine.toml 就够了，bootstrap 跑完就有数据
- 所有改动幂等

## Deliverable

`DELIVERY-SCAN-034.md`：

```
task_id: SCAN-034
owner: builder-codex
target: planner
FrontstageDisposition: AUTO_ADVANCE
UserSummary: <一句话>

## Subagent A — scan_openclaw() 扩展
<home 发现逻辑 / agents 字段 / 测试通过摘录>

## Subagent B — machine_config 同步 + bootstrap
<_openclaw_workspace_root 改动 / bootstrap_machine_tenants.py / 测试通过摘录>

## Verification
<bash -n / pytest / 真跑一次输出>

## Notes
<未解决项>
```

**不 commit，留给 planner 审。**
