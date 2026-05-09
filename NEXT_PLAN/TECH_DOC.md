# AI Shell — 技术文档

## 一、项目概述

### 1.1 理念

> 会写字就会编程。txt即代码，AI即执行者。

所有代码本质上都是文本文件。AI时代，不需要学语法、装依赖、配环境。
打开文件、写字、保存——这就是编程。

### 1.2 核心概念

| 概念 | 说明 |
|------|------|
| txt文件 = 程序 | 创作者通过编辑txt文件来"编程"AI的行为 |
| 说明书 = 框架 | README.md告诉AI它能干什么、怎么干 |
| AI = 解释器 | 读取txt，理解意图，调用工具，返回结果 |
| 聊天 = 交互 | 用户通过终端/对话界面使用，无需接触底层 |

### 1.3 两个角色

| 角色 | 做什么 | 界面 |
|------|--------|------|
| 创作者 | 编辑txt文件，定义AI行为和能力 | 文件编辑器（任意文本编辑器） |
| 用户 | 和AI对话，提需求，看结果 | 终端 / Web聊天界面 |

---

## 二、系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────┐
│                 AI Shell v1                      │
│                                                 │
│  用户输入                                        │
│     │                                           │
│     ▼                                           │
│ ┌──────────┐                                    │
│ │ shell.py │ ← 终端入口，处理输入输出            │
│ └────┬─────┘                                    │
│      │                                          │
│      ▼                                          │
│ ┌──────────────────────────────────────────┐    │
│ │            双AI引擎                       │    │
│ │                                          │    │
│ │  聊天AI (deepseek-chat)                  │    │
│ │  · 理解需求                               │    │
│ │  · 判断是否调工具                         │    │
│ │  · 审核结果                               │    │
│ │  · 回复用户                               │    │
│ │      │                                   │    │
│ │      │ 任务指令                           │    │
│ │      ▼                                   │    │
│ │  工具AI (deepseek-chat)                  │    │
│ │  · 读说明书                               │    │
│ │  · 调用工具                               │    │
│ │  · 核对结果                               │    │
│ │  · 汇报给聊天AI                           │    │
│ └──────────┬───────────────────────────────┘    │
│            │                                    │
│            ▼                                    │
│ ┌──────────────────┐                            │
│ │ tools.py         │                            │
│ │ · read  (读文件) │                            │
│ │ · write (写文件) │                            │
│ │ · exec  (执行)  │                            │
│ └──────────────────┘                            │
│                                                 │
│ ┌──────────────────┐                            │
│ │ config.yaml      │ ← 模型配置                 │
│ │ prompts/*.txt    │ ← 系统提示词               │
│ │ README.md        │ ← 说明书（工具AI读）       │
│ └──────────────────┘                            │
└─────────────────────────────────────────────────┘
```

### 2.2 双AI架构

系统包含两个独立的AI上下文，分工明确：

```
用户 ←──→ 聊天AI（前台） ←──→ 工具AI（后台） ←──→ 工具
```

| | 聊天AI | 工具AI |
|--|--------|--------|
| **职责** | 和用户对话 | 执行工具调用 |
| **上下文** | 用户对话历史 | 说明书 + 工具状态 |
| **系统提示** | 友好的助手角色 | 精准的执行器角色 |
| **模型选择** | 可用轻量模型 | 可用强力模型 |
| **输入** | 用户自然语言 | 结构化任务指令 |
| **输出** | 自然语言回复 | 工具调用 + 结果 |

### 2.3 工作流程

```
用户输入
  │
  ▼
聊天AI：理解用户需求
  │ ② 传达任务
  ▼
工具AI：读说明书 → 调用工具 → 执行 → 核对
  │ ③ 汇报结果
  ▼
聊天AI：审核结果是否符合需求
  │ ⑤ 审核通过 → 组织语言回复用户
  │      不通过 → 打回重做
  ▼
用户
```

### 2.4 执行-核对循环

工具执行完不直接返回用户，而是交回AI核对：

```
AI判断 → 调用工具 → 拿到结果 → AI核对 → 通过 → 返回用户
                                 ↓ 不通过
                              重试/调整 → 再次执行
```

- AI不只是执行器，有自我纠错能力
- 核对失败可自动重试，也可向用户确认
- 三层审核：工具AI自检 → 聊天AI审核 → 用户最终确认

---

## 三、核心能力

### 3.1 三个原语

就像人操作电脑一样：看、改、确认。

| 能力 | 工具名 | 说明 |
|------|--------|------|
| 读 | `read` | 阅读文件内容 / 读取屏幕信息 |
| 写 | `write` | 编辑/创建文件 / 模拟点击输入 |
| 执行 | `exec` | 确认后执行系统命令 |

所有复杂操作都是这三个原语的组合。

### 3.2 屏幕交互能力（v2-v3迭代）

AI不仅要能操作文件，还要能「看屏幕」和「操作GUI」，就像人一样。

#### 屏幕理解（v2）

不依赖完整截图+视觉模型，而是对屏幕进行预处理。
所有预处理模型留出**可替换接口**，支持自训练模型或第三方模型替换。

```
截图 → 边框提取模型 → 结构化描述
截图 → OCR模型 → 文本内容
平台支持时 → UI Automation Tree（最精准）
```

模型接口设计：
```python
class ScreenPreprocessor:
    """屏幕预处理接口 - 可替换"""
    def detect_edges(self, screenshot) -> EdgeMap: ...
    def extract_text(self, screenshot) -> list[TextRegion]: ...
    def parse_ui_tree(self, screenshot) -> UIElement: ...
```

- **边框提取模型**：自训练，去除大面积色块，只保留UI边框线条
- **OCR模型**：自训练，提取屏幕上的文字内容
- **UI Tree解析**：通过平台Accessibility API获取控件树
- 三层递进：有API用最精准的，没有就用模型兜底
- 模型可替换：同一接口，不同实现（自训练/开源/商业API）

#### GUI操作（v3）

基于屏幕理解结果，模拟用户操作：
- **点击**：根据坐标/元素位置模拟鼠标点击
- **输入**：模拟键盘输入文字
- **滚动/拖拽**：模拟其他鼠标操作

---

## 四、文件结构

```
ai-shell/
├── shell.py         # 终端入口（~120行）
├── server.py        # Web版（备用）
├── llm.py           # LLM调用（~70行）
├── tools.py         # 工具层（~110行）
├── config.py        # 配置加载
├── config.yaml      # 配置文件
├── prompts/
│   ├── chat.txt     # 聊天AI提示词
│   └── tool.txt     # 工具AI提示词
├── README.md        # 说明书
├── TECH_DOC.md      # 本文档
├── ROADMAP.md       # 研发方向
├── models/          # 自训练模型（v2）
└── examples/        # 示例txt
```

---

## 五、技术栈

| 层 | 选型 | 理由 |
|---|------|------|
| **后端** | Python | AI生态最丰富 |
| **HTTP客户端** | requests | 同步、简单、稳定 |
| **前端（v1）** | 终端 | 零依赖，极简 |
| **前端（v2）** | Web界面 | 浏览器访问 |
| **AI接入** | OpenAI兼容API | 可接DeepSeek/OpenAI/本地模型 |
| **屏幕处理（v2）** | 自训练模型 | 边框提取、OCR |
| **GUI操作（v3）** | pyautogui + 平台API | 跨平台模拟输入 |

### 依赖

```
requests         # HTTP客户端（唯一必须依赖）
pyyaml           # 配置文件解析
```

---

## 六、API设计

### 6.1 LLM调用接口

```python
class LLMClient:
    def __init__(self, config: dict):
        # config: {base_url, api_key, model, temperature, max_tokens}
        
    def chat(self, messages: list, tools: list = None) -> dict:
        # 非流式调用，返回完整响应
        
    def stream(self, messages: list, tools: list = None):
        # 流式调用，yield每个token
```

### 6.2 工具接口

```python
class ToolResult:
    success: bool       # 是否成功
    data: Any           # 返回数据
    error: str          # 错误信息

class Tool:
    name: str           # 工具名
    description: str    # 给AI看的描述
    parameters: dict    # 参数定义
    handler: callable   # 执行函数

def get_tool_definitions() -> list:
    # 获取所有工具的OpenAI格式定义

def execute_tool(name: str, args: dict) -> ToolResult:
    # 执行指定工具
```

### 6.3 添加自定义工具

在 `tools.py` 中注册新工具：

```python
TOOLS["my_tool"] = Tool(
    name="my_tool",
    description="我的自定义工具",
    parameters={
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "参数说明"}
        },
        "required": ["param1"],
    },
    handler=my_handler,  # def my_handler(param1: str) -> ToolResult
)
```

---

## 七、配置说明

```yaml
# config.yaml
server:
  host: "127.0.0.1"
  port: 8080

chat_ai:
  base_url: "https://api.deepseek.com"   # API地址
  api_key: "${DEEPSEEK_API_KEY}"          # 支持环境变量
  model: "deepseek-chat"                  # 模型名
  temperature: 0.7                        # 温度（越高越随机）
  max_tokens: 2048                        # 最大token数

tool_ai:
  base_url: "https://api.deepseek.com"
  api_key: "${DEEPSEEK_API_KEY}"
  model: "deepseek-chat"
  temperature: 0.1                        # 低温度=更精准
  max_tokens: 4096
```

---

## 八、测试验证

### 8.1 基础对话

```
🧑 你好
🤖 你好！有什么我可以帮你的吗？
```

### 8.2 工具调用

```
🧑 帮我看看当前目录有什么文件
  ⏳ 执行任务...
  🔧 exec({'command': 'ls -la'})
  ✅ 完成
  🔍 核对中...
🤖 当前目录有以下文件：...
```

### 8.3 轻量编程

```
🧑 帮我写一个Python脚本，统计行数，保存到 count.py
  ⏳ 执行任务...
  🔧 write({'path': 'count.py', 'content': '...'})
  ✅ 完成
  🔍 核对中...
🤖 脚本已创建，运行 python count.py 即可
```

验证：
```bash
python3 count.py
# 输出：每个文件的行数 + 总计
```

---

## 九、性能设计

### 9.1 短路优化

简单问题（问候、闲聊）不调工具AI，直接回答：
- 80%的简单问题延迟减半
- 节省工具AI的API调用成本

### 9.2 CPU并行

```python
# 进程池处理CPU密集型任务
from concurrent.futures import ProcessPoolExecutor
cpu_pool = ProcessPoolExecutor(max_workers=os.cpu_count())
```

### 9.3 线程安全

```python
# 每个线程独立的LLM客户端
_thread_local = threading.local()

def get_chat_llm():
    if not hasattr(_thread_local, "chat_llm"):
        _thread_local.chat_llm = LLMClient(config["chat_ai"])
    return _thread_local.chat_llm
```

---

## 十、自我更新机制

### 10.1 设计理念

框架能自我进化。不硬编码更新逻辑，由双AI架构自行判断何时更新、如何更新。

```
运行 → 收集错误 → AI分析 → 写新版本 → 转接 → 继续运行
```

### 10.2 错误日志收集

记录到 `logs/errors.jsonl`，每行一条：

```json
{"time": "2026-05-10T00:30:00", "type": "tool_error", "tool": "exec", "error": "command not found", "input": {"command": "xxx"}}
{"time": "2026-05-10T00:31:00", "type": "ai_correction", "user_said": "不对，应该是...", "ai_reply": "..."}
```

收集的错误类型：
- `tool_error`：工具执行失败
- `ai_correction`：用户纠正了AI的回答
- `parse_error`：AI输出格式错误
- `timeout`：超时

### 10.3 自我分析

双AI架构自行判断：

```
聊天AI：读取错误日志，分析错误模式
  ↓
判断：
  - 是代码bug？→ 需要更新tools.py
  - 是AI理解问题？→ 需要更新prompts
  - 是配置问题？→ 需要更新config.yaml
  - 是偶发错误？→ 不需要更新
  ↓
决定：需要更新 → 生成更新任务
```

### 10.4 子目录版本管理

```
ai-shell/
├── current/          ← 当前运行版本（软链接）
├── v1/               ← 历史版本
├── v2/               ← 历史版本
├── logs/
│   └── errors.jsonl
└── current -> v3/    ← 软链接指向当前版本
```

- 新版本写入 `v(N+1)/`
- 写完后测试通过 → 转接：`current -> v(N+1)/`
- 保留历史版本，可回滚

### 10.5 转接流程

```
1. 在 v(N+1)/ 写好新版本代码
2. 测试新版本（启动 → 执行测试任务 → 关闭）
3. 测试通过 → 更新软链接：current -> v(N+1)/
4. 重启进程（新版本接管）
5. 失败 → 删除 v(N+1)/，保持 current 不变
```

### 10.6 触发机制

不硬编码阈值，由AI自行判断。AI读取日志后决定：
- 错误模式是否一致？
- 是否有明确的修复方案？
- 修复收益是否大于风险？

### 10.7 更新范围

AI可修改的文件：
- `tools.py` — 工具实现
- `prompts/*.txt` — 提示词
- `config.yaml` — 配置
- `llm.py` — LLM调用逻辑
- `shell.py` — 主程序逻辑

AI自行决定改哪些文件。

---

## 十一、已知限制

1. **单轮对话**：不支持多轮上下文（v2改进）
2. **无历史持久化**：对话历史仅在内存中
3. **无流式输出**：终端版目前非流式（v2改进）
4. **工具白名单**：exec命令无白名单限制（v2改进）
5. **无屏幕交互**：v2版本加入
