# -*- coding: utf-8 -*-
"""
马维斯端 —— 任务执行器 v1.0
部署在服务器 (106.55.164.251), 轮询文件夹, 调用 app-agent 执行发布/监控任务。

用法:
  python task_runner.py                    # 前台运行, 每60秒轮询一次
  python task_runner.py --once             # 只执行一次, 处理完就退出
  python task_runner.py --date 2026-06-22  # 执行指定日期
  python task_runner.py --webhook          # 启动 Webhook 接收模式 (端口8901)

文件夹结构:
  C:\projects\content\daily\              <- 马维斯轮询此目录
      2026-06-22\
          tasks.json                        <- Claude 写入
          report.json                       <- 马维斯回写
      archive\                              <- 已完成归档

环境变量:
  CONTENT_DIR     任务包根目录
  APPGENT_EXE     app-agent 可执行文件路径
  WEBHOOK_PORT    Webhook 监听端口 (默认8901)
  WEBHOOK_TOKEN   Webhook 验证 token
"""

import sys, os, json, time, signal, argparse, subprocess
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from task_schema import TaskPackage, PlatformTask, ExecutionReport

CONTENT_DIR = os.environ.get("CONTENT_DIR", r"C:\projects\content\daily")
APPGENT_EXE = os.environ.get("APPGENT_EXE", "app-agent")
ARCHIVE_DIR = os.path.join(CONTENT_DIR, "archive")
WEBHOOK_PORT = int(os.environ.get("WEBHOOK_PORT", "8901"))
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "")
POLL_INTERVAL = 60


def find_pending():
    if not os.path.exists(CONTENT_DIR):
        return []
    pending = []
    for name in sorted(os.listdir(CONTENT_DIR)):
        d = os.path.join(CONTENT_DIR, name)
        if not os.path.isdir(d) or name == "archive":
            continue
        if os.path.exists(os.path.join(d, "tasks.json")) and not os.path.exists(os.path.join(d, "report.json")):
            pending.append(name)
    return pending


def load_pkg(date_str):
    fp = os.path.join(CONTENT_DIR, date_str, "tasks.json")
    if not os.path.exists(fp):
        return None
    with open(fp, "r", encoding="utf-8") as f:
        data = json.load(f)
    pkg = TaskPackage()
    for k, v in data.items():
        if k == "tasks":
            pkg.tasks = []
            for td in v:
                t = PlatformTask()
                for tk, tv in td.items():
                    if hasattr(t, tk):
                        setattr(t, tk, tv)
                pkg.tasks.append(t)
        elif hasattr(pkg, k):
            setattr(pkg, k, v)
    return pkg


def save_report(report, date_str):
    report.date = date_str
    return report.save(base_dir=CONTENT_DIR)


def archive(date_str):
    src = os.path.join(CONTENT_DIR, date_str)
    dst = os.path.join(ARCHIVE_DIR, date_str)
    if os.path.exists(src) and os.path.exists(os.path.join(src, "report.json")):
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        if os.path.exists(dst):
            import shutil
            shutil.rmtree(dst)
        os.rename(src, dst)
        print("[Marvis] 已归档: {d}".format(d=date_str))


def run_task(task, date_str):
    task.status = "running"
    print("[Marvis] [{tid}] {action} -> {plat} {title}".format(
        tid=task.id, action=task.action, plat=task.platform, title=task.content.title[:40]
    ))

    if task.action == "publish":
        cmd = [APPGENT_EXE, "publish", "--platform", task.platform, "--title", task.content.title, "--text", task.content.text, "--tags", ",".join(task.content.tags)]
        for img in task.content.images:
            if os.path.exists(img.path):
                cmd += ["--image", img.path]
        if task.auto_reply.enabled and task.auto_reply.keywords:
            rc = os.path.join(CONTENT_DIR, date_str, "{tid}_reply.json".format(tid=task.id))
            with open(rc, "w", encoding="utf-8") as f:
                json.dump({"keywords":task.auto_reply.keywords,"reply_text":task.auto_reply.reply_text,"max_per_hour":task.auto_reply.max_replies_per_hour}, f, ensure_ascii=False)
            cmd += ["--auto-reply-config", rc]
    elif task.action == "monitor_comments":
        if not task.post_id:
            print("[Marvis] [{tid}] 缺少 post_id, 跳过".format(tid=task.id))
            task.status = "failed"
            return False
        cmd = [APPGENT_EXE, "monitor", "--platform", task.platform, "--post-id", task.post_id, "--keywords", ",".join(task.auto_reply.keywords), "--reply-text", task.auto_reply.reply_text, "--max-per-hour", str(task.auto_reply.max_replies_per_hour)]
    else:
        print("[Marvis] [{tid}] 未知 action: {a}".format(tid=task.id, a=task.action))
        task.status = "failed"
        return False

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            for line in r.stdout.split("\n"):
                if "post_id=" in line:
                    task.post_id = line.split("post_id=")[-1].strip()
                if "post_url=" in line:
                    task.post_url = line.split("post_url=")[-1].strip()
            if task.action == "monitor_comments":
                # 监控是长期任务, 后台运行
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            task.status = "done"
            print("[Marvis] [{tid}] 成功! pid={pid}".format(tid=task.id, pid=task.post_id))
            return True
        else:
            task.status = "failed"
            print("[Marvis] [{tid}] 失败: {e}".format(tid=task.id, e=r.stderr[:200]))
            return False
    except subprocess.TimeoutExpired:
        task.status = "failed"
        print("[Marvis] [{tid}] 超时".format(tid=task.id))
        return False
    except Exception as e:
        task.status = "failed"
        print("[Marvis] [{tid}] 异常: {e}".format(tid=task.id, e=str(e)))
        return False


def run_date(date_str):
    print("\n" + "=" * 60)
    print("[Marvis] 执行日期: {d}".format(d=date_str))
    print("=" * 60)
    pkg = load_pkg(date_str)
    if pkg is None:
        report = ExecutionReport(date=date_str, error_details=["任务包不存在"], notes="未找到 tasks.json")
        save_report(report, date_str)
        return report

    pkg.tasks.sort(key=lambda t: t.time)
    total = len(pkg.tasks)
    done = 0
    failed = 0
    errors = []

    for task in pkg.tasks:
        if task.depends_on:
            dep = next((t for t in pkg.tasks if t.id == task.depends_on), None)
            if dep and dep.status != "done":
                print("[Marvis] [{tid}] 依赖未完成, 跳过".format(tid=task.id))
                continue
        ok = run_task(task, date_str)
        if ok:
            done += 1
        else:
            failed += 1
            errors.append("[{tid}] 失败".format(tid=task.id))
        time.sleep(30)

    report = ExecutionReport(
        date=date_str, tasks_total=total, tasks_done=done, tasks_failed=failed,
        error_details=errors,
        platforms={p:{"published":0,"failed":0} for p in pkg.platforms},
        notes="全部完成" if failed == 0 else "{n}个失败, 需检查".format(n=failed),
    )
    for task in pkg.tasks:
        p = task.platform
        if p not in report.platforms:
            report.platforms[p] = {"published":0,"failed":0}
        if task.status == "done":
            report.platforms[p]["published"] += 1
        elif task.status == "failed":
            report.platforms[p]["failed"] += 1
    save_report(report, date_str)
    return report


def run_once(date_str=None):
    pending = find_pending()
    if not pending:
        if date_str:
            pending = [date_str]
        else:
            print("[Marvis] 没有待处理的任务包")
            return
    for d in pending:
        r = run_date(d)
        if r.tasks_failed == 0:
            archive(d)
        print("\n[Marvis] 完成: {done}/{total}".format(done=r.tasks_done, total=r.tasks_total))


def run_poll():
    print("[Marvis] 轮询模式, 间隔{s}s, 目录: {d}".format(s=POLL_INTERVAL, d=CONTENT_DIR))
    processed = set()
    def handler(sig, frame):
        print("\n[Marvis] 退出")
        sys.exit(0)
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    while True:
        try:
            for d in find_pending():
                if d in processed:
                    continue
                print("\n[Marvis] 发现新任务: {d}".format(d=d))
                r = run_date(d)
                if r.tasks_failed == 0:
                    archive(d)
                processed.add(d)
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("[Marvis] 异常: {e}".format(e=str(e)))
            time.sleep(POLL_INTERVAL)


def run_webhook():
    from http.server import HTTPServer, BaseHTTPRequestHandler
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            cl = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(cl).decode("utf-8")
            token = self.headers.get("X-Marvis-Token", "")
            if WEBHOOK_TOKEN and token != WEBHOOK_TOKEN:
                self.send_response(403); self.end_headers(); self.wfile.write(b'{"error":"invalid token"}')
                return
            try:
                data = json.loads(body)
                d = data.get("date", datetime.now().strftime("%Y-%m-%d"))
                print("\n[Marvis Webhook] 触发: {d}".format(d=d))
                report = run_date(d)
                if report.tasks_failed == 0:
                    archive(d)
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({"status":"ok","date":d,"done":report.tasks_done,"failed":report.tasks_failed}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500); self.end_headers()
                self.wfile.write(json.dumps({"error":str(e)}).encode("utf-8"))
        def do_GET(self):
            p = find_pending()
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps({"status":"running","pending":len(p),"dates":p}, ensure_ascii=False).encode("utf-8"))
    srv = HTTPServer(("0.0.0.0", WEBHOOK_PORT), H)
    print("[Marvis] Webhook 模式, 端口: {p}".format(p=WEBHOOK_PORT))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
        print("\n[Marvis] 已停止")


def main():
    global POLL_INTERVAL
    p = argparse.ArgumentParser(description="马维斯任务执行器")
    p.add_argument("--once", action="store_true")
    p.add_argument("--date", default=None)
    p.add_argument("--webhook", action="store_true")
    p.add_argument("--interval", type=int, default=POLL_INTERVAL)
    args = p.parse_args()
    POLL_INTERVAL = args.interval
    if args.webhook:
        run_webhook()
    elif args.once:
        run_once(date_str=args.date)
    else:
        run_poll()


if __name__ == "__main__":
    main()
