# AIOS 快速开始

这份文档面向第一次跑起 AIOS 的使用者。

目标只有三步：

1. 启动后端
2. 打开 macOS 客户端
3. 在“对话”页发出第一条需求

## 1. 启动后端

在仓库根目录执行：

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

如果没有返回 `ok`，先不要打开客户端。

## 2. 打开 macOS 客户端

先构建：

```bash
xcodebuild -project macos/AIOSMac/AIOSMac.xcodeproj \
  -scheme AIOSMac \
  -configuration Debug \
  -derivedDataPath .build/xcode-derived \
  CODE_SIGNING_ALLOWED=NO build
```

再打开：

```bash
open -n ./.build/xcode-derived/Build/Products/Debug/AIOSMac.app
```

如果你只是做快速开发验证，也可以先用：

```bash
swift build
```

## 3. 发出第一条需求

打开客户端后，进入左侧的 `对话` 页面。

直接输入一句自然语言，例如：

- `在日历中增加日程：今天下午 1 点进行产品评审。`
- `把这周最重要的 3 件事整理成任务，并指出今天必须推进的那一件。`
- `帮我看一下今天有哪些提醒和待决事项需要先处理。`

然后点击 `发送需求`。

默认情况下，AIOS 会自动推进：

1. 理解需求
2. 创建任务
3. 规划任务
4. 启动执行
5. 验证结果

只有在以下情况才会停下来：

- 需要你确认
- 命中了策略阻塞
- 涉及高风险外部动作

## 4. 如何判断系统是否正常

如果系统正常：

- 左下角或状态区不会显示“系统未连接”
- `对话` 页发送后会出现 AIOS 的结果说明
- 任务、提醒、候选等页面会自动出现新内容

如果系统异常，优先检查：

1. 后端是否还在 `8787` 端口运行
2. `GET /healthz` 是否返回 `{"status":"ok"}`
3. 客户端里点击一次刷新

## 5. 当前推荐用法

当前版本最适合这几类请求：

- 任务拆解与规划
- 提醒事项管理
- 日历事项创建
- 风险判断与下一步建议
- 软件开发相关任务，通过 `claude-code` runtime 执行

## 6. 当前已知事实

- 后端端口默认是 `8787`
- `main.py` 只是薄入口
- `对话` 页是当前主入口，不推荐用后台式逐步点击完成整条流程
- 候选页已经恢复正常，不应再误报“系统未连接”
- 中文日历请求已经支持进入日历执行链

## 7. 相关文档

- 总览说明：[README.zh-CN.md](/Users/liuxiaofeng/AI%20OS/README.zh-CN.md)
- 英文版说明：[README.md](/Users/liuxiaofeng/AI%20OS/README.md)
- Claude runtime 集成设计：[docs/claude-code-integration.md](/Users/liuxiaofeng/AI%20OS/docs/claude-code-integration.md)
