# -*- coding: utf-8 -*-
"""
Claude 端 —— 每日标准化任务包生成器
输出标准化 JSON 供马维斯消费。

用法:
  python daily_publisher.py                     # 生成今天的任务包
  python daily_publisher.py --date 2026-06-23   # 指定日期
  python daily_publisher.py --mode single       # 只生成1条(测试用)
  python daily_publisher.py --dry-run           # 只打印不写文件

输出:
  C:\projects\content\daily\YYYY-MM-DD\tasks.json
"""

import sys, os, random, argparse
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from task_schema import TaskPackage, make_task

BASE_URL = os.environ.get("BASE_URL", "https://ouyangjun573-design.github.io/learning-style-test")
WECHAT_ID = os.environ.get("WECHAT_ID", "ww1987870012")
OUTPUT_DIR = r"C:\projects\content\daily"
IMAGE_DIR = r"C:\projects\content"

PLATFORMS = ["xiaohongshu"]
PUBLISH_TIMES = ["08:00", "10:30", "12:00", "15:00", "17:30", "20:00"]

PRODUCTS = [
    {"id":"learning_style","name":"学习风格测评","slug":"learning-style","page":"","tags":["#学习方法","#育儿","#宝妈","#辅导作业"],
     "hooks":[
        {"title":"每天晚上8点到10点，是我家最安静也最崩溃的时间","body":"安静是因为谁都不敢出声。\n崩溃是因为我憋着。\n\n那道题不是刚讲过吗？！你上课到底有没有在听？！\n\n后来才知道，我家孩子是{style}型。他需要{method}，而我一直在用我的方式教他。\n\n像用开车的技巧去开飞机。不炸才怪。\n\n5分钟20道题，知道答案比吼100遍管用。\n\n{link}"},
        {"title":"花了2万报补习班，成绩纹丝不动。我到底错在哪","body":"暑假报数学。开学报英语。周末报作文。\n\n一年两万多。成绩单拿回来，跟去年一样。\n\n测了学习风格，他是{style}型。补习班坐着听讲的方式，对他效率最低。\n\n不是补习班不好。是你孩子可能根本不适合那种学法。\n\n连他怎么学的都不知道，花再多钱也是打水漂。\n\n{link}"},
        {"title":"又收到老师微信了。我都不敢点开","body":"每次手机一震，心就一紧。\n\nxxx妈妈，孩子今天上课又走神了。\n\n我都怕了。怕接老师微信。怕去开家长会。\n\n测了学习风格发现他是{style}型。不是不认真，是他接收信息的方式跟老师教的对不上。\n\n按测评结果给老师发了段话，第二天老师说：今天他举手了。\n\n你家孩子不是问题儿童，只是频道没对上。\n\n{link}"},
     ],
     "reply":"育儿先懂孩子🧠 测一下你家娃是哪种学习风格？免费5分钟 {link} 测完加v：{wechat} 领专属学习方案～"},
    {"id":"focus","name":"专注力评估","slug":"focus","page":"focus.html","tags":["#专注力","#育儿干货","#小学生","#宝妈"],
     "hooks":[
        {"title":"老师第5次暗示我带孩子去看多动症。我去了，结果不是","body":"从一年级开始老师就暗示。说他坐不住上课东摸西摸注意力集中不了5分钟。\n\n我真的带他去儿童医院了。挂专家号做了全套评估。医生说不是多动症。\n\n那为什么坐不住？\n\n后来做了专注力类型评估，发现他是体觉型——需要身体参与才能集中注意力。手里捏个橡皮泥反而能专心听讲。\n\n不是病。是他的专注方式跟别人不一样。\n\n10道题，搞清楚你家孩子到底什么情况。\n\n{link}"},
        {"title":"半小时的作业写了3小时。不是磨蹭，是专注力开关没找对","body":"每天放学回来打开作业本。写两个字发呆，再写一行起来上厕所，又写三个字开始找橡皮。\n\n我坐旁边盯着催着。半小时的作业从4点写到7点。\n\n后来做了专注力评估，才发现他的专注力开关是身体参与。让他站着写边走边背，15分钟就搞定了之前1小时的量。\n\n不是你孩子磨蹭。是你的方法和他的专注类型对不上。\n\n10道题，找到他的专注力开关。\n\n{link}"},
     ],
     "reply":"别再吼孩子了🎯 先测一下他的专注力类型，免费10题 {link} 测完加v：{wechat} 领专属训练方案～"},
    {"id":"parenting","name":"亲子沟通测试","slug":"parenting","page":"parenting.html","tags":["#亲子沟通","#家庭教育","#育儿经验","#宝妈"],
     "hooks":[
        {"title":"我明明想好好说话，一开口就变成了吼","body":"每天早上跟自己说今天不发火。晚上8点准时破功。\n\n不是我想吼。是说了三遍他当没听见，说了五遍还在磨蹭，说到第十遍嗓子自己就上去了。\n\n后来做了一个教养方式测试，发现我是高压型家长。不是脾气差，是我从小也只学过这一种沟通方式。\n\n测完还有配套的话术模板。改了一周他竟主动跟我说学校的事了。\n\n不是你不会沟通，是你没学过别的方式。10道题，看清楚自己是哪种家长。\n\n{link}"},
        {"title":"我跟老公为教育孩子的事冷战三天了","body":"他说我太惯着孩子，我说他太严厉。一个要松一个要紧，孩子夹在中间谁的话都不听。\n\n后来我们俩各做了一份教养方式测试。他是严厉型，我是溺爱型。我们俩不是有矛盾，是互补的短板。\n\n现在分工：学习习惯他管，生活关怀我来管。不打架了。\n\n两口子一起测，各做各的，结果对比着看。\n\n{link}"},
     ],
     "reply":"你是哪种家长？💬 免费10题测一下，结果可能让你吓一跳 {link} 测完加v：{wechat} 领沟通话术模板～"},
    {"id":"talent","name":"天赋发现","slug":"talent","page":"talent.html","tags":["#天赋发现","#兴趣班","#育儿知识","#宝妈"],
     "hooks":[
        {"title":"钢琴画画编程跆拳道围棋。5个班全放弃了。是没毅力吗","body":"每个班都是我精挑细选的。钢琴培养气质画画培养审美编程跟上时代。\n\n一个都没坚持下来。我以为是孩子没毅力。\n\n后来做了天赋测评，他的优势智能是人际智能和语言智能。那些单打独坐的兴趣班刚好踩在他的短板上了。\n\n换成小主持人班和辩论队，每次下课都兴奋得不行。\n\n不是他不坚持。是我一直给他选错了方向。\n\n8道题，科学发现孩子的天赋在哪。\n\n{link}"},
        {"title":"给娃报班就像开盲盒。这个测评让你别再瞎蒙了","body":"报过班的家长都懂。听别人推荐就去报，试听一节觉得还行就交钱，上到一半孩子不想去了——沉没成本几千块。\n\n从幼儿园到现在换了11个班，坚持下来的就2个。\n\n后来学乖了：先做天赋测评，根据他的智能结构去匹配兴趣班，最多试3个就能找到真爱。\n\n先测天赋再报班，少花冤枉钱。\n\n{link}"},
     ],
     "reply":"别瞎报班了🌟 先测天赋再选方向，免费8题 {link} 测完加v：{wechat} 领兴趣班匹配表～"},
    {"id":"growth_mindset","name":"成长型思维","slug":"growth-mindset","page":"growth-mindset.html","tags":["#成长型思维","#家庭教育","#育儿干货","#宝妈"],
     "hooks":[
        {"title":"每次遇到不会的题就哭。不是玻璃心，是思维模式没建立","body":"考试遇到没见过的题型直接空着不写。做作业碰到难的笔一扔说我不会。\n\n我以前只会说你加油，没用。\n\n后来学了一招：不说你可以，说你还没会，但上次那道题你也是从不会到会的。\n\n就这一句话，他开始愿意试了。\n\n这个测试能帮你判断孩子的思维模式，还配套了怎么引导他的话术。\n\n{link}"},
        {"title":"为什么有些孩子越挫越勇，有些一挫就躺平","body":"心理学家Carol Dweck研究了30年。她发现区别不在于聪明不聪明——在于孩子怎么理解失败。\n\n固定型思维的孩子认为：失败=我笨，所以逃避挑战。\n\n成长型思维的孩子认为：失败=我在学，所以越难越想试。\n\n好消息是：思维模式可以重塑。从我我不会变成我还没会，就这一句话的改变。\n\n测一下你家孩子目前在哪种思维模式里。\n\n{link}"},
     ],
     "reply":"一句话改变孩子的态度🌱 免费8题测思维模式 {link} 测完加v：{wechat} 领话术转换表～"},
    {"id":"reading","name":"阅读能力","slug":"reading","page":"reading.html","tags":["#阅读能力","#亲子阅读","#育儿干货","#小学生"],
     "hooks":[
        {"title":"给他买的书堆成山。翻过的没几本。全在书架上吃灰","body":"每次看到博主推荐书单就下单。国际大奖绘本教育部推荐书目清华附小书单……全买了，花了好几千。\n\n大多数翻都没翻过。每天抱着iPad不撒手。\n\n后来做了阅读能力评估，他的阅读水平还没到能看那些书的阶段。书太难了，打开全是挫败感。\n\n降了两级选书，从绘本重新开始，现在每天自己拿书看。\n\n不是孩子不爱读书。是你买的书不适合他现在的水平。\n\n{link}"},
        {"title":"3岁就该开始的阅读习惯，我家8岁了还没养成。还来得及吗","body":"当然来得及。但你不能再按3岁的方法引导了。\n\n8岁的孩子需要：自己选书的权利、不被打断的阅读时间、读完有人跟他聊书里的内容、适合他当前阅读水平的书。\n\n这个评估能告诉你孩子目前的阅读级别在哪，应该看什么难度的书，用什么方式引导他。\n\n习惯养成什么时候都不晚。怕的是用错方法反复失败。\n\n{link}"},
     ],
     "reply":"书买了不少孩子不看？📖 先测阅读能力再选书，免费10题 {link} 测完加v：{wechat} 领分级书单～"},
]

STYLES = [
    ("视觉","画图看视频用颜色标注来学"),
    ("言语","大声读出来讨论讲给别人听来学"),
    ("活跃","动手做边走边学把知识演出来"),
    ("反思","安静思考自己消化不被打扰"),
    ("感觉","用真实例子按步骤反复练习来学"),
    ("直觉","先看全局自由探索建立自己的理解"),
    ("循序","按部就班一步一个脚印来学"),
    ("整体","先看全貌再深入跳着学自然连接"),
]


def daily_generate(date_str=None, mode="full", platforms=None):
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    date = datetime.strptime(date_str, "%Y-%m-%d")
    if platforms is None:
        platforms = PLATFORMS

    tasks = []
    n = 0

    for prod in PRODUCTS:
        link = BASE_URL + "/" + prod["page"] if prod["page"] else BASE_URL + "/"
        reply = prod["reply"].replace("{link}", link).replace("{wechat}", WECHAT_ID)
        hook = prod["hooks"][date.day % len(prod["hooks"])]
        body = hook["body"]
        if "{style}" in body:
            sty = random.choice(STYLES)
            body = body.replace("{style}", sty[0]).replace("{method}", sty[1])
        body = body.replace("{link}", link)

        for plat in platforms:
            n += 1
            tid = "{d}-{prod}-{plat}-{n:03d}".format(d=date_str, prod=prod["id"], plat=plat, n=n)
            time_slot = PUBLISH_TIMES[(n - 1) % len(PUBLISH_TIMES)]
            imgs = [os.path.join(IMAGE_DIR, date_str, "images", "{s}_{j}.png".format(s=prod["slug"], j=j)) for j in range(1,4)]

            task = make_task(
                task_id=tid, time=time_slot, platform=plat, action="publish",
                title=hook["title"], body=body,
                tags=random.sample(prod["tags"], min(4, len(prod["tags"]))),
                keywords=["扣1","求链接","怎么测","在哪里测",prod["name"]],
                reply=reply, images=imgs,
            )
            tasks.append(task)

    pkg = TaskPackage(platforms=platforms, tasks=tasks, notes="共{t}个任务, {p}产品 x {pl}平台. 图片由马维斯生成.".format(t=len(tasks), p=len(PRODUCTS), pl=len(platforms)))
    pkg.date = date_str
    return pkg


def main():
    p = argparse.ArgumentParser(description="Claude 每日标准化任务包生成器")
    p.add_argument("--date", default=None)
    p.add_argument("--mode", default="full", choices=["full","single"])
    p.add_argument("--platforms", default="xiaohongshu")
    p.add_argument("--out", default=OUTPUT_DIR)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    plats = [x.strip() for x in args.platforms.split(",")]
    if args.mode == "single":
        global PRODUCTS
        PRODUCTS = PRODUCTS[:1]
    pkg = daily_generate(date_str=args.date, mode=args.mode, platforms=plats)
    if args.dry_run:
        print(pkg.to_json())
    else:
        fp = pkg.save(base_dir=args.out)
        print("=" * 60)
        print("任务包已生成: {f}".format(f=fp))
        print("日期: {d} | 平台: {p} | 任务数: {t}".format(d=pkg.date, p=plats, t=len(pkg.tasks)))
        print("=" * 60)
        for t in pkg.tasks:
            print("  [{t}] [{pl}] {title}".format(t=t.time, pl=t.platform, title=t.content.title[:50]))
        print("=" * 60)
        print("备注: " + pkg.notes)


if __name__ == "__main__":
    main()
