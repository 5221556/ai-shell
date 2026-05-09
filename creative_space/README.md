# Creative Space - AI 创造空间

这是 AI 的专属工作区。AI 可以在这里：
- 开发新工具，扩展系统能力
- 编写脚本，自动化重复任务
- 记录用户行为模式，定制个性化功能

## 工具开发格式

在 `tools/` 目录下创建 `.py` 文件，格式如下：

```python
"""
工具名称: xxx
描述: 这个工具做什么
"""

TOOL_DEFINITION = {
    "name": "tool_name",
    "description": "工具描述（给AI看的）",
    "parameters": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "参数说明"},
            "param2": {"type": "integer", "description": "参数说明", "default": 10}
        },
        "required": ["param1"]
    }
}

def handler(param1: str, param2: int = 10) -> dict:
    """
    工具执行函数。
    返回: {"success": bool, "data": Any, "error": str}
    """
    try:
        # 你的实现
        result = f"处理了 {param1}"
        return {"success": True, "data": result, "error": ""}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
```

## 规则

1. 每个工具一个文件，文件名即工具名
2. 必须导出 `TOOL_DEFINITION` 和 `handler`
3. `handler` 返回 `{"success": bool, "data": Any, "error": str}`
4. 写完后用 `/reload-tools` 热加载，无需重启

## 热插拔

- 写入新工具文件 → `/reload-tools` → 立即可用
- 删除工具文件 → `/reload-tools` → 工具移除
- 修改工具文件 → `/reload-tools` → 更新生效
