# AI Shell — 研发方向

## 版本规划

```
v1 (当前)     v2            v3            v4
终端版        Web版         屏幕交互      生态
─────────    ─────────    ─────────    ─────────
基础对话      Web界面       边框提取      插件系统
双AI架构      流式输出       OCR识别      多模型支持
三个原语      历史记录       UI Tree      本地模型
轻量编程      用户系统       模拟点击      社区共享
```

---

## v1 — 终端版（已完成）

### 目标
验证核心架构：双AI + 三个原语

### 已实现
- [x] 双AI架构（聊天AI + 工具AI）
- [x] 三个原语工具（read/write/exec）
- [x] 执行-核对循环
- [x] 轻量编程验证（自然语言→代码→保存）
- [x] DeepSeek API接入

### 代码量
```
shell.py    ~120行
llm.py      ~70行
tools.py    ~110行
config.py   ~20行
总计        ~320行Python
```

---

## v2 — 框架自我更新

### 目标
框架能自我进化：收集错误日志 → 自我分析 → 编写新版本 → 转接

### 核心机制

```
运行中收集错误日志
  ↓
错误量达到阈值
  ↓
AI自我分析："这些错误能修吗？值得修吗？"
  ↓
判断需要更新 → 在子目录写新版本
  ↓
写完 → 转接 → 新版本接管
  ↓
继续运行，继续收集日志...
```

### 设计原则

- **不硬编码逻辑**：阈值、判断标准、更新范围全部由AI自行决定
- **子目录隔离**：新版本写入子目录，不影响当前运行版本
- **整体转接**：不是热更新，而是停止旧版本、启动新版本
- **可回滚**：保留历史版本，新版本有问题可切回

### 任务清单
- [ ] 错误日志收集（工具执行失败、AI理解错误、用户纠正）
- [ ] 自我分析提示词（AI读日志 → 判断是否需要更新）
- [ ] 子目录版本管理（v1/ v2/ v3/ ...）
- [ ] 转接机制（停止旧版本 → 启动新版本）
- [ ] 自动备份（更新前备份当前版本）

### 目录结构
```
ai-shell/
├── current/          ← 当前运行版本（软链接指向某个vN）
├── v1/               ← 历史版本
├── v2/               ← 历史版本
├── logs/             ← 错误日志
│   └── errors.jsonl
└── current -> v3/    ← 软链接指向当前版本
```

---

## v3 — Web版 + 流式输出

### 目标
提供Web聊天界面，支持流式输出

### 任务清单
- [ ] Web前端（单文件HTML）
- [ ] 流式SSE输出
- [ ] 对话历史持久化（本地文件）
- [ ] 多轮上下文支持
- [ ] exec命令白名单
- [ ] 用户配置界面

### 技术方案
```
前端：单个 index.html（HTML+JS+CSS）
后端：ThreadingHTTPServer（Python内置）
通信：SSE（Server-Sent Events）流式输出
```

### 预计代码量
```
前端  ~300行
后端  ~200行（在shell.py基础上扩展）
总计  ~500行新增
```

---

## v3 — 屏幕交互

### 目标
AI能「看屏幕」和「操作GUI」

### 3.1 屏幕理解

#### 边框提取模型
- **原理**：OpenCV边缘检测，去除大面积色块，只保留UI边框线条
- **训练数据**：截取各种应用界面截图 + 人工标注边框
- **模型**：轻量CNN，输入截图，输出边框图
- **接口**：
  ```python
  class EdgeDetector:
      def detect(self, screenshot: Image) -> EdgeMap
  ```

#### OCR模型
- **原理**：文字区域检测 + 文字识别
- **方案A**：自训练（需要大量标注数据）
- **方案B**：Tesseract/PaddleOCR 兜底
- **接口**：
  ```python
  class OCRDetector:
      def detect(self, screenshot: Image) -> list[TextRegion]
  ```

#### UI Tree解析
- **Windows**：UI Automation API
- **Linux**：AT-SPI / xdotool
- **macOS**：Accessibility API
- **接口**：
  ```python
  class UITreeParser:
      def parse(self) -> UIElement
  ```

### 3.2 GUI操作

#### 模拟点击
- **库**：pyautogui / xdotool / pywin32
- **输入**：坐标(x, y) 或 元素ID
- **输出**：是否成功

#### 模拟输入
- **键盘输入**：pyautogui.write()
- **快捷键**：pyautogui.hotkey()
- **鼠标操作**：click / double_click / scroll / drag

### 3.3 完整流程

```
用户："帮我打开Chrome，搜索AI Shell"
  │
  ▼
聊天AI理解意图
  │
  ▼
工具AI执行：
  1. exec("google-chrome")        ← 启动Chrome
  2. screen_capture()              ← 截图
  3. edge_detect(screenshot)       ← 边框提取
  4. ocr_detect(screenshot)        ← 文字识别
  5. click(搜索框坐标)              ← 模拟点击
  6. type("AI Shell")              ← 模拟输入
  7. key_press("Enter")            ← 模拟回车
  │
  ▼
聊天AI审核 → 回复用户
```

### 预计代码量
```
screen/edge_detector.py  ~200行
screen/ocr.py            ~150行
screen/ui_tree.py        ~100行
gui/click.py             ~100行
gui/type.py              ~80行
模型训练脚本             ~300行
总计                     ~930行
```

---

## v4 — 生态建设

### 目标
建立插件生态，支持多模型

### 4.1 插件系统

```python
# 插件接口
class Plugin:
    name: str
    description: str
    
    def get_tools(self) -> list[Tool]:
        """返回插件提供的工具"""
        pass
    
    def on_init(self, config: dict):
        """初始化时调用"""
        pass

# 插件目录
plugins/
├── web_search/        # 网页搜索插件
│   ├── __init__.py
│   └── plugin.yaml
├── file_manager/      # 文件管理插件
│   ├── __init__.py
│   └── plugin.yaml
└── code_runner/       # 代码运行插件
    ├── __init__.py
    └── plugin.yaml
```

### 4.2 多模型支持

```yaml
# config.yaml
models:
  deepseek:
    base_url: "https://api.deepseek.com"
    api_key: "${DEEPSEEK_API_KEY}"
  
  openai:
    base_url: "https://api.openai.com/v1"
    api_key: "${OPENAI_API_KEY}"
  
  ollama:
    base_url: "http://localhost:11434/v1"
    api_key: ""
  
  local:
    base_url: "http://localhost:8000/v1"
    api_key: ""

# 为不同任务选择不同模型
routing:
  chat: "deepseek"      # 聊天用便宜的
  tool: "openai"        # 工具调用用强的
  code: "deepseek"      # 代码生成用专用的
```

### 4.3 本地模型支持

```
支持的本地推理引擎：
- Ollama（最简单）
- vLLM（高性能）
- llama.cpp（最轻量）
- text-generation-webui（功能全）
```

### 4.4 社区共享

```
平台：clawhub.ai 或 GitHub

共享内容：
- 工具包（tools/）
- 插件（plugins/）
- 提示词模板（prompts/）
- 预训练模型（models/）
- 示例工作流（examples/）
```

---

## 长期愿景

### 从工具到操作系统

```
v1: 工具库（read/write/exec）
     ↓
v2: AI助手（聊天+执行）
     ↓
v3: AI操作系统（屏幕交互+GUI操作）
     ↓
v4: AI生态系统（插件+社区+多模型）
```

### 核心理念不变

> **会写字就会编程。txt即代码，AI即执行者。**

无论功能怎么扩展，核心永远是：
- **极简**：能删就删
- **txt优先**：一切配置和编程都通过文本文件
- **AI即运行时**：不需要传统意义上的解释器/编译器
- **用户无感**：终端用户只需要会聊天

---

## 时间线

| 版本 | 预计周期 | 核心交付 |
|------|---------|---------|
| v1 | ✅ 已完成 | 终端版 + 双AI架构 |
| v2 | 1-2周 | Web界面 + 流式输出 |
| v3 | 2-4周 | 屏幕理解 + GUI操作 |
| v4 | 1-2月 | 插件系统 + 多模型 |

---

## 风险与挑战

| 风险 | 影响 | 应对 |
|------|------|------|
| API成本高 | 用户流失 | 本地模型支持、短路优化 |
| 屏幕识别不准 | 操作失败 | 多层兜底、人工确认 |
| 安全风险 | 命令注入 | 白名单、沙箱、权限控制 |
| 跨平台兼容 | 功能受限 | 平台抽象层、渐进支持 |
