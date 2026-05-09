"""
context.py - 轻量上下文管理
活跃上下文（API调用） + 本地归档（JSONL持久化） + 搜索工具（AI按需检索）
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from paths import BASE_DIR


class ContextManager:
    """
    上下文分层管理：

    活跃层（内存）：最近 N 条消息，直接用于 API 调用
    归档层（磁盘）：超出活跃窗口的消息，按日保存到 JSONL 文件
    搜索层（工具）：AI 通过 search_context 工具按关键词检索归档

    当活跃上下文满时，最旧的消息自动归档到 context/archives/YYYY-MM-DD.jsonl
    """

    def __init__(self, project_root: Path = None, max_active: int = 20):
        self.active: list[dict] = []
        self.max_active = max_active
        root = Path(project_root) if project_root else BASE_DIR
        self.archive_dir = root / "context" / "archives"
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def add(self, role: str, content: str):
        """添加一条消息，超出上限时自动归档"""
        with self._lock:
            self.active.append({"role": role, "content": content})
            if len(self.active) > self.max_active:
                self._archive_overflow()

    def add_pair(self, user_msg: str, assistant_msg: str):
        """添加一对用户-助手消息"""
        self.add("user", user_msg)
        self.add("assistant", assistant_msg)

    def get_messages(self) -> list:
        """获取活跃上下文（用于 API 调用）"""
        with self._lock:
            return self.active.copy()

    def clear(self):
        """清空活跃上下文（不删归档）"""
        with self._lock:
            self.active.clear()

    def search(self, query: str, n: int = 10) -> list:
        """搜索归档上下文，返回匹配的消息"""
        results = []
        query_lower = query.lower()
        # 按日期倒序搜索（最新的优先）
        for archive_file in sorted(self.archive_dir.glob("*.jsonl"), reverse=True):
            try:
                with open(archive_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            msg = json.loads(line)
                            content = msg.get("content", "")
                            if query_lower in content.lower():
                                results.append({
                                    "role": msg.get("role", ""),
                                    "content": content[:500],
                                    "date": archive_file.stem,
                                })
                                if len(results) >= n:
                                    return results
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue
        return results

    def get_stats(self) -> dict:
        """获取上下文统计"""
        with self._lock:
            active_count = len(self.active)
        archive_count = 0
        archive_files = 0
        for f in self.archive_dir.glob("*.jsonl"):
            archive_files += 1
            try:
                with open(f, encoding="utf-8") as fh:
                    archive_count += sum(1 for line in fh if line.strip())
            except Exception:
                pass
        return {
            "active": active_count,
            "archived": archive_count,
            "archive_files": archive_files,
            "max_active": self.max_active,
        }

    def _archive_overflow(self):
        """将超出活跃窗口的消息归档到磁盘（调用方需持有锁）"""
        n = len(self.active) - self.max_active
        if n <= 0:
            return
        overflow = self.active[:n]
        self.active = self.active[n:]

        today = datetime.now().strftime("%Y-%m-%d")
        archive_file = self.archive_dir / f"{today}.jsonl"
        try:
            with open(archive_file, "a", encoding="utf-8") as f:
                for msg in overflow:
                    f.write(json.dumps(msg, ensure_ascii=False) + "\n")
        except Exception:
            pass  # 归档失败不影响主流程
