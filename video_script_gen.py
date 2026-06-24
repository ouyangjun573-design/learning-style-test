# -*- coding: utf-8 -*-
"""
视频脚本生成器 —— 从每日任务包 (tasks.json) 生成短视频口播脚本

从 daily_publisher.py 输出的标准化 JSON 中读取任务列表，
为每个任务生成一条 60 秒短视频口播脚本，保存为独立 txt 文件。

用法:
  python video_script_gen.py                              # 今天所有任务
  python video_script_gen.py --date 2026-06-22            # 指定日期
  python video_script_gen.py --date 2026-06-22 --task t-xxx  # 指定单个任务

输出:
  C:\\projects\\content\\daily\\YYYY-MM-DD\\scripts\\{task_id}_script.txt
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

# 确保 stdout 支持 UTF-8 (Windows GBK 终端下避免 emoji 报错)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ============================================================
# 常量
# ============================================================

OUTPUT_BASE = r"C:\projects\content\daily"
SCRIPT_DIR_NAME = "scripts"

# 各段落情绪池 (根据内容情感自动匹配，此处作为兜底)
EMOTION_HOOK = ["焦虑", "共鸣", "疑惑", "惊讶", "扎心"]
EMOTION_BODY_PROBLEM = ["沮丧", "无奈", "崩溃", "自责"]
EMOTION_BODY_TURN = ["恍然大悟", "希望", "好奇", "期待"]
EMOTION_BODY_SOLUTION = ["信心", "释然", "兴奋", "笃定"]
EMOTION_CTA = ["紧迫感", "期待", "鼓励"]

# 问题触发词 —— 用于识别 body 中的"问题描述"段落
PROBLEM_KEYWORDS = [
    "崩溃", "吼", "哭", "怕", "烦", "焦虑", "着急", "生气",
    "磨蹭", "坐不住", "走神", "不会", "成绩", "差", "倒数",
    "投诉", "微信", "不敢", "放弃", "坚持", "报班",
]

# 转折触发词 —— 用于定位 "后来发现/测了/才知道"
# 注意: 优先匹配"后来"，避免"做了""测了"等泛词误触
TURN_KEYWORDS_PRIMARY = ["后来"]
TURN_KEYWORDS_SECONDARY = ["测了", "才发现", "才知道", "然后"]

# 测评引导短语模板 (用于 body 末尾桥接 CTA)
TEST_INTRO_TEMPLATES = [
    "你家孩子是不是也这样？花5分钟做一下这个测评，马上就知道答案了。",
    "想知道问题出在哪？点击下方链接，免费测一测就知道了。",
    "别再自己瞎琢磨了，10道题帮你搞清楚。",
    "不要凭感觉猜，用科学的方法测一下，结果一目了然。",
]

# CTA 口播模板 (测评链接 + 微信引导)
CTA_TEMPLATES = [
    "测评链接放在评论区了，测完加我微信，领一份专属的个性化报告。",
    "点评论区链接就能测，测完记得加微信，送你一份详细的解读。",
    "链接在评论区，免费测试不要钱。加微信还能拿到专属建议。",
]


# ============================================================
# 工具函数
# ============================================================

def log(msg: str) -> None:
    """带时间戳的日志输出。"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def strip_link(text: str) -> str:
    """移除 body 末尾或中间出现的 {link} 或纯 URL 行。"""
    text = re.sub(r"\{link\}", "", text)
    text = re.sub(r"https?://\S+", "", text)
    return text


def detect_keyword(text: str, keywords: list) -> bool:
    """检查文本是否包含任意关键词。"""
    for kw in keywords:
        if kw in text:
            return True
    return False


def select_emotion(text: str, pool: list, default: str = "中性") -> str:
    """根据文本情感倾向从情绪池中选择，无匹配则返回兜底。"""
    # 简单的情感映射
    emotion_map = {
        "崩溃": "崩溃", "吼": "愤怒", "哭": "悲伤", "怕": "恐惧",
        "焦虑": "焦虑", "着急": "焦虑", "生气": "愤怒",
        "发现": "恍然大悟", "知道": "恍然大悟", "原来": "恍然大悟",
        "希望": "希望", "信心": "信心", "兴奋": "兴奋",
        "免费": "期待", "立即": "紧迫感", "马上": "紧迫感",
        "鼓励": "鼓励", "加油": "鼓励",
    }
    for word, emotion in emotion_map.items():
        if word in text:
            if emotion in pool:
                return emotion
    return default


def split_body_sections(body: str) -> dict:
    """
    将 body 文本解析为三个段落:
      - problem:   问题描述 (痛点场景)
      - turn:      转折点 (测了/发现/后来知道)
      - solution:  解决方案 + 价值主张

    返回 dict {problem, turn, solution, test_intro}。
    如果 body 中没有明显的转折词，则按 40%/20%/40% 比例分割。
    """
    cleaned = strip_link(body)
    paragraphs = [p.strip() for p in cleaned.split("\n") if p.strip()]

    result = {"problem": "", "turn": "", "solution": "", "test_intro": ""}

    if not paragraphs:
        return result

    # 尝试定位转折点 (优先级: 后来 > 测了/才发现/才知道 > 然后)
    turn_idx = -1
    for i, para in enumerate(paragraphs):
        if detect_keyword(para, TURN_KEYWORDS_PRIMARY):
            turn_idx = i
            break
    if turn_idx < 0:
        for i, para in enumerate(paragraphs):
            if detect_keyword(para, TURN_KEYWORDS_SECONDARY):
                # 次要关键词必须至少出现在第2段之后（避免把开头的"测了"当成转折）
                if i >= 1:
                    turn_idx = i
                    break

    if turn_idx > 0:
        # 转折点之前全是问题
        result["problem"] = "\n".join(paragraphs[:turn_idx])
        # 转折点本身是 "turn"
        result["turn"] = paragraphs[turn_idx]
        # 转折点之后是解决方案 (最后一行可能是测试介绍)
        solution_paras = paragraphs[turn_idx + 1:]
        if solution_paras:
            # 如果最后一行包含数字题量或"测"字，视作 test_intro
            last = solution_paras[-1]
            if re.search(r"\d+道题|\d+分钟|测[一试]", last):
                result["test_intro"] = last
                result["solution"] = "\n".join(solution_paras[:-1])
            else:
                result["solution"] = "\n".join(solution_paras)
    else:
        # 无明显的转折词，按比例分割
        total = len(paragraphs)
        if total == 1:
            result["problem"] = paragraphs[0]
        elif total == 2:
            result["problem"] = paragraphs[0]
            result["solution"] = paragraphs[1]
        else:
            split1 = max(1, int(total * 0.4))
            split2 = max(split1 + 1, int(total * 0.6))
            result["problem"] = "\n".join(paragraphs[:split1])
            result["solution"] = "\n".join(paragraphs[split1:split2])
            if split2 < total:
                result["test_intro"] = "\n".join(paragraphs[split2:])

    return result


def format_script_section(timing_label: str, duration_label: str,
                          scene: str, emotion: str,
                          lines: list, subtitle: str = "") -> list:
    """
    生成一个脚本 section 的格式化行列表。
    """
    out = [
        f"--- {timing_label} ({duration_label}) ---",
        f"🎬 画面: {scene}",
        f"🎭 情绪: {emotion}",
    ]
    for line in lines:
        out.append(f"💬 口播: {line}")
    if subtitle:
        out.append(f"📝 字幕建议: {subtitle}")
    out.append("")
    return out


# ============================================================
# 核心生成函数
# ============================================================

def generate_script(task: dict) -> str:
    """
    为单个 task 生成完整 60 秒视频脚本文本。

    Args:
        task: tasks.json 中的单条任务字典

    Returns:
        格式化的脚本文本 (含换行符)
    """
    content = task.get("content", {})
    title = content.get("title", "")
    body = content.get("text", "")
    tags = content.get("tags", [])
    task_id = task.get("id", "unknown")
    platform = task.get("platform", "unknown")
    auto_reply = task.get("auto_reply", {})
    reply_text = auto_reply.get("reply_text", "")

    # 解析 body 段落
    sections = split_body_sections(body)

    # 准备口播文本
    problem_text = sections["problem"] or body[:100]
    turn_text = sections["turn"] or ""
    solution_text = sections["solution"] or ""
    test_intro_text = sections["test_intro"] or ""

    # 构建测评引导 (优先使用 body 中自带的，否则用模板)
    if not test_intro_text:
        test_intro_text = TEST_INTRO_TEMPLATES[len(task_id) % len(TEST_INTRO_TEMPLATES)]

    # 构建 CTA (使用 auto_reply 的内容，若无则用模板)
    if reply_text:
        # 从回复文本中提取链接 + 微信号
        cta_text = reply_text
    else:
        cta_text = CTA_TEMPLATES[len(task_id) % len(CTA_TEMPLATES)]

    # -- 标签处理 --
    tag_str = " ".join(tags) if tags else "#育儿"

    # ================================================================
    # 组装脚本
    # ================================================================
    script_lines = []

    # 页头
    script_lines.append("=" * 56)
    script_lines.append(f"📹 短视频脚本")
    script_lines.append(f"   时长: 60秒 | 平台: {platform}")
    script_lines.append(f"   任务: {task_id}")
    script_lines.append("=" * 56)
    script_lines.append("")

    # ==================== Hook (0-3s) ====================
    hook_emotion = select_emotion(
        title + " " + problem_text,
        EMOTION_HOOK,
        default="共鸣"
    )
    hook_lines = [title] if title else ["你是不是也遇到这个问题了？"]
    script_lines.extend(format_script_section(
        "Hook", "0:00-0:03 ｜ 3秒",
        "特写表情 / 痛点场景瞬间 / 文字冲击",
        hook_emotion,
        hook_lines,
        subtitle="大字标题: " + (title[:20] if title else "你中招了吗？"),
    ))

    # ==================== Body 第一部分: 问题深入 (0:03-0:18, 15s) ====================
    prob_emotion = select_emotion(
        problem_text, EMOTION_BODY_PROBLEM, default="无奈"
    )
    # 问题段落拆成短句
    prob_sentences = [s.strip() for s in re.split(r"[。！？\n]", problem_text) if s.strip()]
    if not prob_sentences:
        prob_sentences = [problem_text]
    script_lines.extend(format_script_section(
        "Body · 问题挖痛", "0:03-0:18 ｜ 15秒",
        "生活场景还原 / 家长辅导作业 / 孩子上课走神",
        prob_emotion,
        prob_sentences[:4],
        subtitle='屏幕出现痛点关键词，如「你是不是也这样？」',
    ))

    # ==================== Body 第二部分: 转折 / 发现 (0:18-0:33, 15s) ====================
    turn_emotion = select_emotion(
        turn_text + solution_text, EMOTION_BODY_TURN, default="恍然大悟"
    )
    turn_sentences = []
    if turn_text:
        turn_sentences.append(turn_text)
    if solution_text:
        sol_sentences = [s.strip() for s in re.split(r"[。！？\n]", solution_text) if s.strip()]
        turn_sentences.extend(sol_sentences[:3])
    if not turn_sentences:
        turn_sentences = ["后来才发现，原来是方法不对。"]
    script_lines.extend(format_script_section(
        "Body · 转折发现", "0:18-0:33 ｜ 15秒",
        "对比画面 / 测评卡片露出 / 数据或结果展示",
        turn_emotion,
        turn_sentences[:4],
        subtitle='关键词高亮显示，如「原来如此」「科学测评」',
    ))

    # ==================== Body 第三部分: 测评引导 (0:33-0:48, 15s) ====================
    guide_emotion = "期待"
    guide_lines = [test_intro_text] if test_intro_text else [
        "想知道你家孩子是哪一种情况？",
        "花5分钟测一下，马上就能看到结果。"
    ]
    script_lines.extend(format_script_section(
        "Body · 测评引导", "0:33-0:48 ｜ 15秒",
        "手机展示测评页面 / 测评卡片 / 二维码浮窗",
        guide_emotion,
        guide_lines,
        subtitle='显示「点击下方链接」 「免费测试」',
    ))

    # ==================== CTA (0:48-0:60, 12s) ====================
    cta_emotion = select_emotion(cta_text, EMOTION_CTA, default="鼓励")
    cta_lines = [cta_text] if cta_text else [
        "测评链接在评论区，测完加我微信领报告。"
    ]
    script_lines.extend(format_script_section(
        "CTA", "0:48-1:00 ｜ 12秒",
        "测评链接浮现 + 微信二维码 + 关注引导",
        cta_emotion,
        cta_lines,
        subtitle="显示测评链接 + 微信号，引导评论区互动",
    ))

    # ==================== 底部 ====================
    # 从 auto_reply 提取关键词作为引导互动
    keywords = auto_reply.get("keywords", [])
    if keywords:
        kw_str = " / ".join(keywords[:4])
        script_lines.append(f"📢 评论引导: 评论区回复 {kw_str} 获取测评链接")
        script_lines.append("")

    script_lines.append(f"[标签] {tag_str}")
    script_lines.append("")
    script_lines.append(f"-- 任务ID: {task_id}")
    script_lines.append(f"-- 平台: {platform}")
    script_lines.append(f"-- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    script_lines.append("=" * 56)

    return "\n".join(script_lines)


# ============================================================
# 主流程
# ============================================================

def load_tasks(date_str: str) -> tuple:
    """
    从 tasks.json 加载任务列表。

    Returns:
        (tasks_list, raw_data_dict)
    """
    fp = os.path.join(OUTPUT_BASE, date_str, "tasks.json")
    if not os.path.exists(fp):
        log(f"错误: 未找到任务文件 — {fp}")
        log(f"请先运行 daily_publisher.py 生成今日任务包，或确认 --date 参数正确。")
        sys.exit(1)
    with open(fp, "r", encoding="utf-8") as f:
        data = json.load(f)
    tasks = data.get("tasks", [])
    log(f"已加载 {len(tasks)} 个任务，来自 {fp}")
    return tasks, data


def ensure_output_dir(date_str: str) -> str:
    """确保脚本输出目录存在，返回目录路径。"""
    out_dir = os.path.join(OUTPUT_BASE, date_str, SCRIPT_DIR_NAME)
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def save_script(task: dict, date_str: str, out_dir: str) -> str:
    """生成并保存单个任务的脚本文件。"""
    script = generate_script(task)
    task_id = task.get("id", "unknown")
    filename = f"{task_id}_script.txt"
    fp = os.path.join(out_dir, filename)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(script)
    log(f"  ✅ {filename}")
    return fp


def main():
    parser = argparse.ArgumentParser(
        description="从每日任务包 (tasks.json) 生成短视频口播脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python video_script_gen.py
  python video_script_gen.py --date 2026-06-22
  python video_script_gen.py --date 2026-06-22 --task task-20260622-focus-001
  python video_script_gen.py --date 2026-06-22 --task t-xxx
        """,
    )
    parser.add_argument(
        "--date",
        default=None,
        help="日期 YYYY-MM-DD (默认今天)",
    )
    parser.add_argument(
        "--task",
        default=None,
        help="指定任务ID (默认生成所有任务)",
    )
    args = parser.parse_args()

    # 确定日期
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    # 加载任务
    log(f"📂 读取任务包: {date_str}")
    tasks, data = load_tasks(date_str)

    if not tasks:
        log("⚠️  任务列表为空，无需生成脚本。")
        return

    # 过滤任务 (--task)
    if args.task:
        filtered = [t for t in tasks if t.get("id") == args.task]
        if not filtered:
            log(f"⚠️  未找到任务 ID: {args.task}")
            log(f"    当前任务列表:")
            for t in tasks:
                log(f"      - {t.get('id')} ｜ {t.get('content',{}).get('title','')[:30]}")
            return
        tasks = filtered
        log(f"🔍 已过滤，仅处理任务: {args.task}")

    # 确保输出目录
    out_dir = ensure_output_dir(date_str)

    # 批量生成
    log(f"🎬 开始生成 {len(tasks)} 个视频脚本...")
    log(f"📁 输出目录: {out_dir}")
    print()

    saved = []
    for task in tasks:
        fp = save_script(task, date_str, out_dir)
        saved.append(fp)

    print()
    log(f"✅ 完成! 共生成 {len(saved)} 个脚本:")
    for fp in saved:
        log(f"   📄 {fp}")

    # 打印摘要
    print()
    print("-" * 56)
    print(f"  日期:        {date_str}")
    print(f"  平台:        {data.get('platforms', [])}")
    print(f"  总任务数:    {len(saved)}")
    print(f"  输出目录:    {out_dir}")
    print("-" * 56)


if __name__ == "__main__":
    main()
