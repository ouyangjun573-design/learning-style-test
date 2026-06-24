# -*- coding: utf-8 -*-
"""
视频总装流水线 v1.0
读取脚本 -> TTS配音 -> 生成字幕 -> 合成视频

用法:
  python video_composer.py --date 2026-06-21           # 合成当天全部视频
  python video_composer.py --task {task_id}            # 单个任务
  python video_composer.py --date 2026-06-21 --dry-run # 只检查环境

依赖:
  - node-edge-tts (npm install -g node-edge-tts)
  - ffmpeg (PATH 中可用)

输出:
  C:\projects\content\daily\YYYY-MM-DD\videos\{task_id}.mp4
"""

import sys, os, re, argparse, subprocess, shutil, math
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CONTENT_DIR = r"C:\projects\content\daily"
TTS_VOICE = "zh-CN-XiaoyiNeural"
TTS_RATE = "-10%"
VIDEO_W, VIDEO_H = 1080, 1920
VIDEO_FPS = 25
BG_COLOR = "#FFF8F5"
TEXT_COLOR = "#4A3530"
CHARS_PER_SEC = 4.0
FONT_FILE = r"C:/Windows/Fonts/simhei.ttf"


def parse_script(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    segments = []
    cur = {"type":"","lines":[],"emotion":"","visual":"","duration":0}
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.search(r"--- (\w+).*?\([^)]*(\d+)秒", line)
        if m:
            if cur["lines"]:
                segments.append(cur)
            cur = {"type":m.group(1),"lines":[],"emotion":"","visual":"","duration":int(m.group(2))}
            continue
        if line.startswith("💬 "):
            cur["lines"].append(line[3:].strip())
    if cur["lines"]:
        segments.append(cur)
    return segments


def extract_text(segments):
    return "\n".join([" ".join(s["lines"]) for s in segments])


def tts_generate(text, out_mp3):
    """TTS 配音, 带重试和降级"""
    import asyncio, time
    for attempt in range(3):
        print(f"  🎤 TTS ({attempt+1}/3)...")
        try:
            async def _run():
                import edge_tts
                c = edge_tts.Communicate(text, TTS_VOICE)
                await c.save(out_mp3)
            asyncio.run(_run())
            if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 100:
                print(f"  ✅ 配音: {os.path.getsize(out_mp3)//1024}KB")
                return True
        except Exception as e:
            print(f"  ⚠️ 尝试{attempt+1}失败: {str(e)[:80]}")
            if attempt < 2:
                time.sleep(3 * (attempt+1))
    # 降级: 生成静音占位文件, 不阻断视频生产
    print("  ⚠️ TTS全部失败, 生成静音占位")
    try:
        subprocess.run(["ffmpeg","-y","-f","lavfi","-i","anullsrc=r=24000:cl=mono","-t","20","-q:a","2",out_mp3], capture_output=True, timeout=10)
        return os.path.exists(out_mp3)
    except:
        return False


def gen_srt(segments, out_srt):
    lines = []
    seq = 0; t = 0.0
    for seg in segments:
        text = " ".join(seg["lines"])
        if not text.strip():
            continue
        dur = seg.get("duration", 0) or max(1.0, len(text.replace(" ",""))/CHARS_PER_SEC)
        s = int(t); e = int(t+dur)
        lines.append(f"{seq+1}\n{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d},{int((s%1)*1000):03d} --> {e//3600:02d}:{(e%3600)//60:02d}:{e%60:02d},{int((e%1)*1000):03d}\n{text}\n")
        seq += 1; t += dur
    os.makedirs(os.path.dirname(out_srt), exist_ok=True)
    with open(out_srt,"w",encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  📝 字幕: {out_srt} ({seq}条)")


def gen_placeholder_imgs(segments, out_dir, task_id):
    os.makedirs(out_dir, exist_ok=True)
    imgs = []
    for i, seg in enumerate(segments):
        text = (seg["lines"][0] if seg["lines"] else seg["type"])[:40]
        text = text.replace("'", "'").replace(":", "：")
        fp = os.path.join(out_dir, f"{task_id}_img{i:02d}.png")
        # 使用双引号包裹 drawtext 参数避免转义问题
        vf = f"drawtext=text='{text}':fontfile={FONT_FILE}:fontcolor={TEXT_COLOR}:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=white@0.8:boxborderw=16"
        cmd = ["ffmpeg","-y","-f","lavfi","-i",f"color=c={BG_COLOR}:s={VIDEO_W}x{VIDEO_H}:d=1","-vf",vf,"-frames:v","1","-update","1",fp]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode != 0 or not os.path.exists(fp):
            # 降级: 纯背景色无文字
            subprocess.run(["ffmpeg","-y","-f","lavfi","-i",f"color=c={BG_COLOR}:s={VIDEO_W}x{VIDEO_H}:d=1","-frames:v","1","-update","1",fp], capture_output=True, timeout=10)
        if os.path.exists(fp):
            imgs.append(fp)
    print(f"  🖼️  占位图: {len(imgs)}张 -> {out_dir}")
    return imgs


def compose(images, audio, srt, out_mp4, total_dur):
    if not images:
        return False
    per_dur = total_dur / len(images)
    cf = out_mp4.replace(".mp4","_c.txt")
    with open(cf,"w",encoding="utf-8") as f:
        for img in images:
            f.write(f"file '{img}'\nduration {per_dur}\n")
        f.write(f"file '{images[-1]}'\n")
    env = os.environ.copy()
    env["FONTCONFIG_PATH"] = "C:/Windows/Fonts"
    print(f"  🎬 合成中...")
    cmd = ["ffmpeg","-y","-f","concat","-safe","0","-i",cf,"-i",audio,"-c:v","libx264","-preset","fast","-crf","23","-c:a","aac","-b:a","128k","-pix_fmt","yuv420p","-shortest","-movflags","+faststart",out_mp4]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
    ok = r.returncode == 0 and os.path.exists(out_mp4)
    os.remove(cf)
    if ok:
        print(f"  ✅ 视频: {out_mp4} ({os.path.getsize(out_mp4)/1024/1024:.1f}MB)")
        print(f"  📝 字幕(独立文件): {srt}")
    else:
        print(f"  ❌ 合成失败: {r.stderr.strip()[-200:]}")
    return ok


def compose_one(task_id, date_str):
    sd = os.path.join(CONTENT_DIR, date_str, "scripts")
    vd = os.path.join(CONTENT_DIR, date_str, "videos")
    os.makedirs(vd, exist_ok=True)
    sf = os.path.join(sd, f"{task_id}_script.txt")
    if not os.path.exists(sf):
        print(f"  ❌ 脚本不存在: {sf}")
        return False
    print(f"\n{'='*60}\n🎬 {task_id}\n{'='*60}")
    segs = parse_script(sf)
    text = extract_text(segs)
    td = sum(s.get("duration", max(1.0, len(" ".join(s["lines"]).replace(" ",""))/CHARS_PER_SEC)) for s in segs)
    print(f"  📐 {len(segs)}段, ~{td:.0f}秒")

    ap = os.path.join(vd, f"{task_id}_audio.mp3")
    tts_generate(text, ap)
    sp = os.path.join(vd, f"{task_id}.srt")
    gen_srt(segs, sp)
    idir = os.path.join(CONTENT_DIR, date_str, "images")
    imgs = sorted([os.path.join(idir,f) for f in os.listdir(idir) if f.endswith(('.png','.jpg','.jpeg'))]) if os.path.exists(idir) and os.listdir(idir) else gen_placeholder_imgs(segs, idir, task_id)
    op = os.path.join(vd, f"{task_id}.mp4")
    return compose(imgs, ap, sp, op, td)


def main():
    p = argparse.ArgumentParser(description="视频总装流水线")
    p.add_argument("--date", default=None)
    p.add_argument("--task", default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if args.dry_run:
        print("🔍 环境检查:")
        ff = shutil.which("ffmpeg")
        tts = shutil.which("node-edge-tts") or shutil.which("npx")
        print(f"  ffmpeg: {'✅' if ff else '❌'} {ff or ''}")
        print(f"  TTS: {'✅' if tts else '❌ npm install -g node-edge-tts'}")
        print(f"  目录: {'✅' if os.path.exists(CONTENT_DIR) else '❌'} {CONTENT_DIR}")
        return
    ds = args.date or datetime.now().strftime("%Y-%m-%d")
    if args.task:
        compose_one(args.task, ds)
    else:
        sd = os.path.join(CONTENT_DIR, ds, "scripts")
        if not os.path.exists(sd):
            print(f"❌ {sd} 不存在, 请先运行 video_script_gen.py")
            return
        scripts = sorted([f for f in os.listdir(sd) if f.endswith("_script.txt")])
        ok = 0
        for sf in scripts:
            if compose_one(sf.replace("_script.txt",""), ds):
                ok += 1
        print(f"\n{'='*60}\n✅ {ok}/{len(scripts)} 完成\n📁 {os.path.join(CONTENT_DIR,ds,'videos')}\n{'='*60}")


if __name__ == "__main__":
    main()
