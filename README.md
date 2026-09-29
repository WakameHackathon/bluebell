# 售后助手 Agent（本地集成原型）

售后流程 Agent 的可运行本地原型：主 Agent 对话、任务续接、Skill 注册与真实调用、
结构化 Skill 结果落库、SQLite 会话记录、经用户逐轮同意后调用的阶跃星辰 OpenAI 兼容接口，
以及自动显示悬浮球的 Chromium 插件。

11 个 Skill 包已经以文件夹形式放在 [`skills/`](skills/) 下，运行时按中央契约
[`contracts.schema.json`](contracts.schema.json)（`urn:aftercare:skill-contracts:1.0.0`）
组装请求、校验结果。Skill 清单与调用方式见 [SKILLS.md](SKILLS.md)。

## 启动

```powershell
cd aftercare-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
.\Start-Agent.ps1
```

打开 `http://127.0.0.1:8766`。未配置密钥或未勾选单轮传输同意时，只使用有限的本地回复；
勾选后，本轮描述与选填页面文字会传给阶跃星辰模型处理。不要把真实密钥写入代码、聊天记录或提交版本库。
先前曾粘贴到聊天中的密钥应到服务商后台轮换后再使用。

## Skill 是怎么被调用的

Skill 包不是可调用的函数，而是给 Agent 看的操作规程（`SKILL.md` + `references/`）。
因此「调用」在本项目里的含义是：

1. 宿主按契约组装请求信封，把每个输入解析成**已登记产物的引用**并校验
   `$defs.<skill>Request`（`skill_runtime.py`、`app.py:build_inputs`）；
2. 把该 Skill 自己的 `SKILL.md` 连同请求一起交给模型，要求返回 JSON 结果信封；
3. 用 `skill_schema.py`（无第三方依赖的 JSON Schema 子集校验器）校验结果信封**和** `data`
   里的产物是否等于声明的 `output_kind`；
4. 只有 `completed` 且通过校验的产物才登记进 SQLite，供下游 Skill 引用。

未登记的引用一律拒绝（HTTP 409），不会伪造产物。可用的调试接口：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/status` | 模型配置、已加载 Skill 数与清单、未加载项及原因 |
| GET | `/api/skills` | Skill 注册表摘要（`skill_id`、版本、输出产物、所需输入） |
| GET | `/api/skills/<id>` | 单个 Skill 的 `SKILL.md` 正文与契约字段 |
| POST | `/api/artifacts` | 登记宿主产物（`PlatformView`、`UserDecision`、`ExecutionReceipt` 等），登记前先按契约校验 |
| POST | `/api/skills` | 直接调用一个 Skill；不带密钥时只组装并校验请求 |
| POST | `/api/agent/turn` | 主 Agent 一轮对话；模型可通过工具调用触发 Skill |

## 测试

```powershell
.\tests\run-tests.ps1
```

21 个单元测试覆盖契约校验器、请求组装与结果校验；`tests/_e2e_http.py` 用假模型端点
驱动真实 HTTP 服务，验证请求组装、产物登记、未登记引用被拒、以及模型返回非法信封时
不落库；`tests/_smoke_readme.py` 按本文档的启动方式在默认端口 8766 起一次服务，
确认首页、`/api/status` 与 Skill 注册表可用（需要 8766 端口空闲）。测试只依赖 `httpx`。

## 当前范围

- 14 个 Skill ID 都在注册表里；其中 11 个有真实 Skill 包并已接入运行时，
  `platform-main` / `platform-secondary` / `platform-sandbox` 上游从未交付，标记为未实现。
- Chromium 插件在普通 HTTP/HTTPS 网页显示悬浮球；用户可以拖动、隐藏并恢复。
  读取当前页面文字需先在球的权限菜单开启，再于侧栏主动点击读取；内容作为不可信页面证据单独传给模型。
- 单任务只处理一件商品；任务与消息存入本地 SQLite，目前未加密；试用请使用虚构信息，
  不要输入真实订单号、地址、证件或支付资料。
- 模型无法连接时使用保守的本地回复。
- **尚未接入**：网页自动操作、真实平台适配、文件上传/转换、ASR/TTS、授权票据、
  动作队列、提交核实、跨设备加密同步。模式选项目前只记录用户偏好，不代表已能替用户操作网页。
- 因此现在的链路是「能组装、能校验、能落库」，不是「能替用户办事」。任何提交、上传、
  寄件、申诉、发送都仍需用户自己操作，Agent 只能说明步骤并整理草稿。不得把这个原型演示成已经完成真实售后。

Skill 的 I/O 细节以 [`contracts.schema.json`](contracts.schema.json) 为基线，
各 Skill 自带的 `references/*.schema.json` 是同一契约的摘录。
