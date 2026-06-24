# -*- coding: utf-8 -*-
"""
Claude <-> 马维斯 标准化任务包接口 v1.0
Claude 产出 JSON, 马维斯消费 JSON, 两边共用此 Schema。
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
from datetime import datetime
import json, os


# ============================================================
# 数据结构
# ============================================================

@dataclass
class ImageAsset:
    path: str                    # 本地绝对路径
    alt: str = ""                # 图片描述
    source: str = "ai"           # ai | manual

@dataclass
class PostContent:
    title: str                   # 标题 (<=20字)
    text: str                    # 正文 (<=1000字, 带段落)
    images: List[ImageAsset] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

@dataclass
class AutoReply:
    keywords: List[str]          # ["扣1","求链接","怎么测"]
    reply_text: str              # 回复内容(含测评链接+微信)
    max_replies_per_hour: int = 10
    enabled: bool = True

@dataclass
class PlatformTask:
    id: str                      # "task-20260622-focus-001"
    time: str                    # "08:00" 北京时间
    platform: str                # xiaohongshu | douyin
    action: str                  # publish | monitor_comments
    note_type: str = "图文"
    content: PostContent = field(default_factory=PostContent)
    auto_reply: AutoReply = field(default_factory=AutoReply)
    depends_on: Optional[str] = None
    post_url: str = ""           # 马维斯回填
    post_id: str = ""            # 马维斯回填
    status: str = "pending"      # pending -> running -> done | failed


# ============================================================
# 任务包 (Claude -> 马维斯)
# ============================================================

@dataclass
class TaskPackage:
    version: str = "1.0"
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    generated_by: str = "claude"
    platforms: List[str] = field(default_factory=list)
    tasks: List[PlatformTask] = field(default_factory=list)
    notes: str = ""

    def to_json(self, indent=2):
        return json.dumps(asdict(self), ensure_ascii=False, indent=indent)

    def save(self, base_dir=r"C:\projects\content\daily"):
        folder = os.path.join(base_dir, self.date)
        os.makedirs(folder, exist_ok=True)
        fp = os.path.join(folder, "tasks.json")
        with open(fp, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        return fp


# ============================================================
# 执行报告 (马维斯 -> Claude)
# ============================================================

@dataclass
class ExecutionReport:
    version: str = "1.0"
    date: str = ""
    executed_by: str = "marvis"
    tasks_total: int = 0
    tasks_done: int = 0
    tasks_failed: int = 0
    platforms: Dict[str, dict] = field(default_factory=dict)
    error_details: List[str] = field(default_factory=list)
    engagement: dict = field(default_factory=dict)
    notes: str = ""

    def to_json(self, indent=2):
        return json.dumps(asdict(self), ensure_ascii=False, indent=indent)

    def save(self, base_dir=r"C:\projects\content\daily"):
        folder = os.path.join(base_dir, self.date)
        os.makedirs(folder, exist_ok=True)
        fp = os.path.join(folder, "report.json")
        with open(fp, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        return fp

    @classmethod
    def load(cls, date_str, base_dir=r"C:\projects\content\daily"):
        fp = os.path.join(base_dir, date_str, "report.json")
        if not os.path.exists(fp):
            return None
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        r = cls()
        for k, v in data.items():
            if hasattr(r, k):
                setattr(r, k, v)
        return r


# ============================================================
# 快捷工厂
# ============================================================

def make_task(task_id, time, platform, action, title, body, tags, keywords, reply, note_type="图文", images=None):
    imgs = []
    if images:
        for p in images:
            imgs.append(ImageAsset(path=p))
    return PlatformTask(
        id=task_id, time=time, platform=platform, action=action, note_type=note_type,
        content=PostContent(title=title, text=body, images=imgs, tags=tags),
        auto_reply=AutoReply(keywords=keywords, reply_text=reply),
    )


if __name__ == "__main__":
    pkg = TaskPackage(
        platforms=["xiaohongshu", "douyin"],
        tasks=[
            make_task(
                task_id="task-20260622-focus-001",
                time="08:00", platform="xiaohongshu", action="publish",
                title="孩子写作业磨蹭？先别吼，测一下专注力类型",
                body="很多家长以为孩子磨蹭是懒……其实是专注力类型不对。先测再对症下药👇\n\n测评入口👉 https://ouyangjun573-design.github.io/learning-style-test/focus.html\n\n测完加v：ww1987870012 领专属报告～",
                tags=["#专注力","#育儿干货","#小学生","#宝妈"],
                keywords=["扣1","求链接","怎么测","在哪里测"],
                reply="测评入口👉 https://ouyangjun573-design.github.io/learning-style-test/focus.html 测完加v：ww1987870012 领专属报告～",
            ),
        ],
        notes="第一天测试, 图放 C:\\projects\\content\\2026-06-22\\images\\focus_*.png, 共3张",
    )
    path = pkg.save()
    print(f"Schema 样本已写入: {path}")
    print(pkg.to_json())
