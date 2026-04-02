# AIOS

[English Version](./README.md)

AIOS 是一个面向个人工作的本地优先 AI 操作系统。

当前仓库包含三部分核心内容：

- FastAPI 后端内核
- 基于 manifest 的 runtime / capability / workflow / plugin 装配系统
- 面向用户的 macOS 客户端

当前产品目标是：

- 用户用自然语言描述需求
- AIOS 自动判断应该如何处理
- 在安全前提下自动创建、规划、执行、验证任务
- 只有在真正需要确认或策略复核时才停下来

## 当前架构

代码已经不再围绕一个超大的 `services.py` 单体文件组织，而是拆成以下层次：

- `ai_os/domain/`
  - 系统核心数据模型，包括任务、记忆、运行时、策略、插件、工作流、关系、使用情况等
- `ai_os/repositories/`
  - 持久化与仓储边界
- `ai_os/kernel_execution.py`
  - 意图识别、认知分析、任务状态机、执行计划生成
- `ai_os/kernel_services.py`
  - self、goals、memory、relations、execution run 支撑服务
- `ai_os/capabilities/`
  - capability 注册与具体处理器，例如 `local_files`、`notes`、`messaging`、`reminders`、`calendar`
- `ai_os/runtimes/`
  - runtime 注册与适配器，目前包括 `claude-code`
- `ai_os/workflows.py`
  - intake 与 delivery 编排
- `ai_os/policy.py`
  - 生命周期 hook、规则、策略注入
- `ai_os/plugin_registry.py`
  - 插件发现与装配
- `ai_os/api.py`
  - FastAPI 接口层
- `main.py`
  - 仅保留极薄入口

## Manifest 驱动装配

AIOS 现在支持声明式发现：

- runtimes
- capabilities
- workflows
- plugins

对应位置示例：

- runtime manifest: [runtimes/claude-code/runtime.json](/Users/liuxiaofeng/AI%20OS/runtimes/claude-code/runtime.json)
- capability manifests: [ai_os/capabilities/manifests](/Users/liuxiaofeng/AI%20OS/ai_os/capabilities/manifests)
- workflow manifests: [ai_os/workflows/manifests](/Users/liuxiaofeng/AI%20OS/ai_os/workflows/manifests)
- plugin manifests: [plugins](/Users/liuxiaofeng/AI%20OS/plugins)

也就是说，系统已经从“硬编码能力集合”转向：

`kernel + policy + runtime/capability/workflow/plugin discovery`

## Runtime 体系

`claude-code` 在 AIOS 中被定位为 runtime，而不是内核本身。

当前 runtime 层已经支持：

- runtime 列表
- runtime preview
- runtime invocation 描述
- runtime-aware task planning
- 在 `ExecutionRun` 上记录 runtime 执行元数据
- 本机具备 `claude` CLI 时执行真实 `claude -p`
- 本机缺少 CLI 时退回安全的 handoff / artifact 方案

参考设计文档见 [docs/claude-code-integration.md](/Users/liuxiaofeng/AI%20OS/docs/claude-code-integration.md)。

## Policy / Governance

策略层现在已经不是简单的 if/else 硬编码。

`PolicyEngine` 当前支持：

- 生命周期 hook，例如 `before_execute`、`before_external_side_effect`
- 规则模型
- runtime 注入规则
- 显式确认 override
- 将策略决策写入 `ExecutionRun.metadata`

这为后续更完整的治理系统打下了基础。

## 当前后端能力

后端目前已经支持：

- self profile 与持久化上下文
- 分层 memory
- task planning / execution / verification / reflection
- execution run 与 relation graph
- reminders 与 calendar events
- candidates 发现、接受、延后
- scheduler tick 与停滞任务升级
- runtime-aware execution
- capability / runtime / plugin usage 统计

当前的主用户路径是：

1. `POST /inbox/process`
2. 如果请求应该变成任务，则创建任务
3. `plan`
4. `start`
5. `verify`
6. 可选 `reflect`

macOS 客户端里的“对话”页已经默认走这条自动推进链路。

## 当前 macOS 客户端

macOS 客户端已经不再只是一个后台管理面板。

当前用户工作区页面包括：

- `Overview`
- `Conversation`
- `Tasks`
- `Memory`
- `Reminders`
- `Candidates`

开发者查看页面包括：

- `Capabilities`
- `Runtimes`
- `Plugins`
- `Workflows`
- `Events`
- `Self`

当前对话页已经尽量按“用户发一次需求，系统自动往下跑”的产品路径设计。

菜单栏也已经支持：

- 后端连接状态
- 快速任务创建
- 刷新与调度入口

## 启动后端

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
.venv/bin/python -m uvicorn main:app --reload --port 8787
```

健康检查：

```bash
curl -s http://127.0.0.1:8787/healthz
```

预期返回：

```json
{"status":"ok"}
```

可选启用 DeepSeek 云端意图理解：

```bash
export DEEPSEEK_API_KEY=your_key
export DEEPSEEK_MODEL=deepseek-chat
```

配置后，AIOS 会用 DeepSeek 理解对话意图；如果 API 不可用，会自动回退到本地规则。

## 构建 macOS App

快速本地构建：

```bash
swift build
```

生成 `.app`：

```bash
xcodebuild -project macos/AIOSMac/AIOSMac.xcodeproj \
  -scheme AIOSMac \
  -configuration Debug \
  -derivedDataPath .build/xcode-derived \
  CODE_SIGNING_ALLOWED=NO build
```

打开应用：

```bash
open -n ./.build/xcode-derived/Build/Products/Debug/AIOSMac.app
```

## 关键接口

核心：

- `GET /healthz`
- `GET /self`
- `PUT /self`
- `GET /self/timeline`
- `POST /intents/evaluate`
- `POST /inbox/process`
- `GET /events`

任务：

- `POST /tasks`
- `GET /tasks`
- `POST /tasks/{task_id}/plan`
- `POST /tasks/{task_id}/start`
- `POST /tasks/{task_id}/advance`
- `POST /tasks/{task_id}/confirm`
- `POST /tasks/{task_id}/verify`
- `POST /tasks/{task_id}/reflect`
- `GET /tasks/{task_id}/timeline`
- `GET /tasks/{task_id}/relations`
- `GET /tasks/{task_id}/runs`

运行记录与关系：

- `GET /runs/{run_id}/events`
- `GET /runs/{run_id}/timeline`
- `GET /memories/{memory_id}/relations`

记忆与目标：

- `POST /memory/facts`
- `GET /memory/facts`
- `GET /memory/recall`
- `GET /goals`
- `POST /goals`
- `POST /goals/{goal_id}`

Capabilities 与 Runtimes：

- `GET /capabilities`
- `POST /capabilities/execute`
- `GET /runtimes`
- `GET /tasks/{task_id}/runtime-preview`
- `GET /tasks/{task_id}/runtime-invocation`

Plugins / Workflows / Policy / Usage：

- `GET /plugins`
- `GET /workflows`
- `GET /policies`
- `GET /capabilities/{name}/usage`
- `GET /runtimes/{name}/usage`
- `GET /plugins/{name}/usage`

Candidates 与 Scheduler：

- `GET /candidates`
- `POST /candidates/accept`
- `POST /candidates/auto-accept`
- `POST /candidates/auto-accept-eligible`
- `POST /candidates/defer`
- `POST /scheduler/tick`

## 当前注意事项

- 后端端口使用 `8787`，不是 `8000`
- `main.py` 是刻意保持极薄的入口文件
- `/candidates` 现在已经恢复正常，候选页不应再误报“系统未连接”
- 中文日历请求已经支持进入 `calendar_event` 执行链路
- 对话页默认是自动推进，不是后台式逐步点击操作

## 验证命令

后端测试：

```bash
.venv/bin/python -m unittest discover -s tests -q
```

Swift 构建验证：

```bash
swift build
```
