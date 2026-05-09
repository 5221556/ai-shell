# AI Shell

> 会写字就会编程。txt即代码，AI即执行者。

一个极简的AI编程助手，通过自然语言与AI对话，自动执行文件操作、系统命令、代码生成等任务。支持自我进化——AI可以修改自己的代码和配置。

## 特性

- **双AI架构**：聊天AI理解意图 + 工具AI精准执行，三层审核确保准确
- **四个原语**：read / write / exec / search_context，所有复杂操作都是它们的组合
- **自我更新**：AI可以修改自己的代码、提示词、配置，实现自我进化
- **创造空间**：AI可以在 `creative_space/` 目录开发新工具，热插拔加载
- **上下文管理**：活跃上下文 + 本地归档，支持长期记忆和搜索
- **错误日志**：自动收集错误，AI自我分析并修复
- **版本管理**：自动备份、版本归档、失败回滚
- **零依赖**：仅需 `requests` + `pyyaml`，单文件可执行

## 快速开始

### 方式一：直接运行

```bash
# 安装依赖
pip install requests pyyaml

# 设置API密钥
export DEEPSEEK_API_KEY=your_key  # Linux/Mac
set DEEPSEEK_API_KEY=your_key     # Windows CMD
$env:DEEPSEEK_API_KEY="your_key"  # PowerShell

# 启动
python main.py              # Web服务
python main.py shell        # 终端版
```

### 方式二：可执行文件

```bash
# 下载 dist/ai-shell.exe
ai-shell.exe                # 首次运行 → 交互式配置
ai-shell.exe shell          # 终端版
ai-shell.exe setup          # 重新配置
```

### 方式三：从源码构建

```bash
pip install pyinstaller
python build.py
# 生成 dist/ai-shell.exe
```

## 使用方式

### Web界面

启动后访问 `http://127.0.0.1:18080`，直接对话。

### 终端版

```bash
python main.py shell

# 命令
/self-update    错误日志自我分析
/context        查看上下文统计
/errors         查看错误日志
/reload-tools   热加载创造空间工具
/quit           退出
```

### 对话示例

```
🧑 帮我看看当前目录有什么文件
🤖 [自动调用 exec("ls")] 当前目录有以下文件...

🧑 帮我写一个Python脚本统计行数，保存到 count.py
🤖 [自动调用 write("count.py", ...)] 脚本已创建

🧑 给系统添加一个搜索工具
🤖 [自动读取 tools.py → 写入新工具 → 测试] 已添加 grep 工具

🧑 之前聊过什么关于Python的内容？
🤖 [自动调用 search_context("Python")] 找到3条相关记录...
```

## 架构

```
用户输入
    │
    ▼
┌─────────────┐
│  Chat AI    │ ← 理解意图，判断是否需要工具
│  (对话助手)  │
└──────┬──────┘
       │ 任务指令
       ▼
┌─────────────┐
│  Tool AI    │ ← 执行工具，核对结果
│  (执行引擎)  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│  工具层                             │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌────┐│
│  │ read │ │ write│ │ exec │ │ ctx ││
│  └──────┘ └──────┘ └──────┘ └────┘│
│  ┌──────────────────────────────┐  │
│  │ creative_space/tools/*.py    │  │
│  │ (AI开发的动态工具，热插拔)    │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
```

## 项目结构

```
ai-shell-v1/
├── main.py              统一入口
├── server.py            Web后端
├── shell.py             终端版
├── llm.py               LLM客户端
├── tools.py             工具层 + 动态加载
├── context.py           上下文管理
├── self_update.py       自我更新模块
├── config.py            配置加载
├── paths.py             路径管理
├── setup.py             交互式配置
├── build.py             PyInstaller构建脚本
├── config.yaml          配置文件
├── prompts/
│   ├── chat.txt         聊天AI提示词
│   └── tool.txt         工具AI提示词
├── web/
│   └── index.html       前端界面
├── creative_space/
│   ├── tools/           AI开发的工具
│   ├── scripts/         AI编写的脚本
│   └── notes/           AI记录的用户习惯
├── examples/
│   ├── count_lines.txt  示例：统计行数
│   └── sysinfo.txt      示例：系统信息
└── NEXT_PLAN/
    ├── ROADMAP.md       版本路线图
    └── TECH_DOC.md      技术文档
```

## 配置

### 首次配置

首次运行会自动进入交互式配置，按提示操作即可：

```
==================================================
  AI Shell - 首次配置
==================================================

选择服务商：
  1) DeepSeek
  2) OpenAI
  3) Moonshot (月之暗面)
  4) OpenRouter (聚合平台，支持Claude/Gemini等)
  5) 通义千问 (阿里)
  6) GLM (智谱)
  7) Ollama (本地)
  8) 其他（自定义地址）

选择 [1]: 1

已选：DeepSeek (https://api.deepseek.com)

可用模型：
  1) deepseek-v4-flash
  2) deepseek-v4-pro

选择模型: 1
API Key: sk-xxxxxxxxxxxxxxxx
模型名称确认 [deepseek-v4-flash]:
Web 服务监听地址 [127.0.0.1]:
Web 服务端口 [18080]:

==================================================
  配置已保存
==================================================
```

### 获取 API Key

| 服务商 | 申请地址 |
|--------|----------|
| DeepSeek | https://platform.deepseek.com/api_keys | 
| OpenAI | https://platform.openai.com/api-keys |
| Moonshot | https://platform.moonshot.cn/console/api-key |
| 通义千问 | https://dashscope.console.aliyun.com/apiKey |
| GLM | https://open.bigmodel.cn/usercenter/apikeys |
| Ollama | 无需 key |
| OpenRouter | https://openrouter.ai/keys |

### 修改配置

配置文件 `config.yaml` 可随时手动修改，修改后重启生效：

```yaml
server:
  host: "127.0.0.1"      # 监听地址，0.0.0.0 表示允许外部访问
  port: 18080             # 端口号

chat_ai:                  # 聊天AI（理解意图、审核结果）
  base_url: "https://api.deepseek.com/v1"
  api_key: "sk-xxx"       # 你的 API Key
  model: "deepseek-v4-flash"
  temperature: 0.7        # 创造性：0=精确，1=随机
  max_tokens: 16384       # 单次回复最大长度

tool_ai:                  # 工具AI（执行任务、核对结果）
  base_url: "https://api.deepseek.com/v1"
  api_key: "sk-xxx"       # 可以和 chat_ai 用不同的 key
  model: "deepseek-v4-flash"
  temperature: 0.1        # 工具执行需要精确，设低一些
  max_tokens: 65536       # 工具输出可能很长（如写大文件）

context:
  max_active: 20          # 活跃上下文条数，越大越占 token
```

### 切换服务商

只需修改 `base_url` 和 `model`，API 格式兼容：

```yaml
# 切换到 OpenAI
chat_ai:
  base_url: "https://api.openai.com/v1"
  api_key: "sk-xxx"
  model: "gpt-4o-mini"

# 切换到本地 Ollama
chat_ai:
  base_url: "http://localhost:11434/v1"
  api_key: "ollama"       # Ollama 不需要真实 key
  model: "llama3"
```

### 重新配置

```bash
python main.py setup      # 源码版
ai-shell.exe setup         # 可执行文件版
```

### 配置说明

| 参数 | 说明 | 建议值 |
|------|------|--------|
| `temperature` | 创造性，0=精确，1=随机 | chat: 0.7, tool: 0.1 |
| `max_tokens` | 单次回复最大 token 数 | 根据模型和任务调整 |
| `max_active` | 活跃上下文条数 | 20-50 |
| `host` | 监听地址 | `127.0.0.1` 仅本机，`0.0.0.0` 允许外部 |
| `port` | 端口号 | 避免 80/443/8080 等常用端口 |

## 创造空间

AI可以在 `creative_space/tools/` 目录下开发新工具，无需重启即可热加载：

```python
# creative_space/tools/my_tool.py
TOOL_DEFINITION = {
    "name": "my_tool",
    "description": "工具描述",
    "parameters": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "参数说明"}
        },
        "required": ["param1"]
    }
}

def handler(param1: str) -> dict:
    return {"success": True, "data": "结果", "error": ""}
```

输入 `/reload-tools` 或访问 `/api/reload-tools` 即可热加载。

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web前端 |
| `/api/chat` | POST | 对话接口（SSE流式） |
| `/api/errors` | GET | 错误日志 |
| `/api/context` | GET | 上下文统计 |
| `/api/reload-tools` | GET | 热加载工具 |
| `/api/self-update` | POST | 自我更新 |

## 依赖

```
requests
pyyaml
```

## 许可证

MIT License

## 理念

> 会写字就会编程。txt即代码，AI即执行者。

- **极简**：能删就删
- **txt优先**：一切配置和编程都通过文本文件
- **AI即运行时**：不需要传统意义上的解释器/编译器
- **用户无感**：终端用户只需要会聊天
