# -*- coding: utf-8 -*-
import random, os, sys, json, urllib.request
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = r"E:\小红书项目生成的笔记\每日"
LINK = "https://ouyangjun573-design.github.io/learning-style-test/"
WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=06889387-47ee-4f00-a70e-3ef9cbc39067"
os.makedirs(OUT, exist_ok=True)

STYLES = [
    ["视觉","画图看视频用颜色标注来学"],
    ["言语","大声读出来讨论讲给别人听来学"],
    ["活跃","动手做边走边学把知识演出来"],
    ["反思","安静思考自己消化不被打扰"],
    ["感觉","用真实例子按步骤反复练习来学"],
    ["直觉","先看全局自由探索建立自己的理解"],
    ["循序","按部就班一步一个脚印来学"],
    ["整体","先看全貌再深入跳着学自然连接"],
]

TAGS = [
    "#学习方法 #育儿 #宝妈 #辅导作业 #学习风格测评",
    "#小学生 #育儿干货 #专注力 #学习方法 #宝妈",
    "#亲子教育 #辅导作业 #育儿经验 #学习方法 #家庭教育",
    "#因材施教 #育儿知识 #学习方法 #宝妈 #孩子教育",
]

HOOKS = {
"辅导崩溃": [
    {"title":"每天晚上8点到10点，是我家最安静也最崩溃的时间",
     "body":"安静是因为：谁都不敢出声。\n崩溃是因为：我憋着。\n\n这道题不是刚讲过吗？！\n你上课到底有没有在听？！\n\n然后孩子哭了。我也哭了。\n\n后来才知道，我家孩子是【{style}型】。他需要{method}，而我一直在用我的方式教他。\n\n像用开车的技巧去开飞机。不炸才怪。\n\n5分钟20道题，知道答案比吼100遍管用。"},
],
"老师投诉": [
    {"title":"又收到老师微信了。我都不敢点开",
     "body":"每次手机一震，心就一紧。\n\nxxx妈妈，孩子今天上课又走神了。\n\n我都怕了。怕接老师微信。怕去开家长会。\n\n然后测了学习风格。发现他是【{style}型】。\n\n不是不认真。是他接收信息的方式跟老师教的方式对不上。\n\n按测评结果给老师发了段话。第二天老师说：今天他举手了。\n\n就一天。就一段话。\n\n你家孩子不是问题儿童。只是频道没对上。"},
],
"报班浪费": [
    {"title":"花了2万报补习班，成绩纹丝不动。我到底错在哪",
     "body":"暑假报数学。开学报英语。周末报作文。\n\n一年两万多。成绩单拿回来，跟去年一样。\n\n我问他老师讲的听懂了吗。他说听懂了，做题就不会。\n\n后来测了学习风格。他是【{style}型】。补习班坐着听讲的方式，对他效率最低。\n\n不是补习班不好。是你孩子可能根本不适合那种学法。\n\n连他怎么学的都不知道，花再多钱也是打水漂。"},
],
"跟人比较": [
    {"title":"闺蜜女儿考了全班第一。我家倒数。回家路上我一句话没说",
     "body":"闺蜜群晒成绩单。我默默把手机翻过去。\n\n不是嫉妒。是难受。\n\n一样大的孩子。一样的学校老师。为什么差这么多。\n\n测了学习风格。闺蜜女儿是【循序型】，我家是【整体型】。完全不同的学习方式。\n\n学校按一种方式教。只适合一种类型的孩子。\n\n不是你孩子不行。是学校没给他适配的方式。\n\n5分钟。看懂你家孩子该走哪条路。"},
],
"亲子关系": [
    {"title":"以前回家第一句话是作业写完了吗。现在不敢问了",
     "body":"我问完他就烦。他烦我就吼。吼完他摔门。摔完我哭。\n\n我们对话越来越少。除了作业和成绩没有别的话题。\n\n我怀念他小时候。每天黏着我妈妈妈妈喊不停。\n\n测了学习风格才明白，以前我是监工。每天只有催查纠。\n\n现在按报告里的方法做。从监工变成了啦啦队长。\n\n昨晚他主动说：妈，我今天学了个很有意思的东西。\n\n三个月了。第一次。\n\n这个测试，救的不只是成绩。"},
],
"怀疑智商": [
    {"title":"我偷偷带他测过智商。结果是正常的。那我到底该怎么办",
     "body":"是的。我干过这事。\n\n带他去医院挂儿保健科。做了一堆测试。医生说一切正常。\n\n那为什么学不会？为什么跟不上？为什么看到作业就哭？\n\n后来测了学习风格。结果是【{style}型】。\n\n按报告里的方法改了。两周后他自己主动坐到书桌前。\n\n不是智商问题。不是态度问题。是方法问题。\n\n你孩子不需要看医生。他需要你看懂他。"},
],
}

SCHEDULE = {0:"辅导崩溃",1:"报班浪费",2:"老师投诉",3:"跟人比较",4:"亲子关系",5:"怀疑智商",6:"辅导崩溃"}
WEEKDAYS = ["周一","周二","周三","周四","周五","周六","周日"]

def push_to_wecom(title, content, tag):
    text = title + "\n\n" + content + "\n\n测试链接: " + LINK + "\n" + tag
    payload = json.dumps({
        "msgtype": "text",
        "text": {"content": text}
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(WEBHOOK, data=payload,
        headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        return result.get("errcode") == 0
    except Exception as e:
        print("  推送失败: " + str(e))
        return False

def run():
    today = datetime.now()
    wd = today.weekday()
    ds = today.strftime("%Y%m%d")
    cat = SCHEDULE[wd]
    idx = today.day % len(HOOKS[cat])
    hook = HOOKS[cat][idx]
    sty = random.choice(STYLES)
    tag = random.choice(TAGS)

    title = hook["title"].replace("{style}", sty[0])
    body = hook["body"].replace("{style}", sty[0]).replace("{method}", sty[1])
    today_str = today.strftime("%Y年%m月%d日")

    sep = "=" * 40
    note = sep + "\n"
    note += "[" + today_str + "] " + cat + " | 学习风格测评\n"
    note += sep + "\n\n"
    note += title + "\n\n"
    note += body + "\n\n"
    note += "测试链接: " + LINK + "\n\n"
    note += tag + "\n"

    # 写文件
    f1 = os.path.join(OUT, ds + "_" + cat + ".txt")
    with open(f1, "w", encoding="utf-8") as f: f.write(note)

    f2 = os.path.join(r"E:\小红书项目", "今日笔记_" + ds + ".txt")
    with open(f2, "w", encoding="utf-8") as f: f.write(note)

    # 推企微
    pushed = push_to_wecom(title, body, tag)

    print("[OK] " + ds + " | " + cat)
    print("    文件: " + f2)
    print("    企微: " + ("已推送" if pushed else "推送失败"))
    print(sep)
    print(note)
    print(sep)
    print("本周排期:")
    for d, c in SCHEDULE.items():
        m = " <==" if d == wd else ""
        print("  " + WEEKDAYS[d] + ": " + c + " (" + str(len(HOOKS[c])) + "条)" + m)

if __name__ == "__main__":
    run()
