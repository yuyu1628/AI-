import os
import json
import re
import sys
import time
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty

# 初始化终端控制台
console = Console()

## ================= 配置区 =================
# 1. 原有 API 配置 (用于 DeepSeek / Qwen 等)
API_KEY_BASE = ""
BASE_URL_BASE = ""
client = OpenAI(api_key=API_KEY_BASE, base_url=BASE_URL_BASE)




MODEL_GLOBAL_PLANNER = ""
MODEL_VOLUME_PLANNER = ""
MODEL_CONTEXT_RAG = ""
MODEL_WRITER = ""
MODEL_STYLE_EDITOR = ""
MODEL_LOGIC_EDITOR = ""
MODEL_LINE_EDITOR = ""
MODEL_STATE_MACHINE = ""
MODEL_CODER_JSON = ""

# 终端颜色
C_SYS, C_PLAN, C_RAG, C_WRITE, C_EDIT, C_STATE = "\033[95m", "\033[92m", "\033[96m", "\033[94m", "\033[93m", "\033[95m"
C_RESET = "\033[0m"


# ================= 状态机与记忆系统 =================
# 用于本地持久化存储，防止断电丢失
STATE_FILE = "world_bible.json"
MEMORY_FILE = "rolling_memory.json"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "characters": {},  # 人物档案（生死、境界、性格、当前位置）
        "items": {},  # 核心道具与归属
        "factions": {},  # 势力与门派状态
        "world_rules": []  # 挖掘出的世界观法则
    }


def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "rolling_summaries": [],  # 存放最近 5 章的极简摘要（滑动窗口）
        "last_chapter_tail": ""  # 存放上一章结尾最后 300 字（用于情绪无缝衔接）
    }


def save_state(bible, memory):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(bible, f, ensure_ascii=False, indent=2)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


# ================= 辅助工具函数 =================
def clean_think_tags(text):
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    elif "<think>" in text:
        text = text.split("<think>")[0].strip()
    text = re.sub(r'```thought\n.*?\n```', '', text, flags=re.DOTALL).strip()
    return text


def call_llm(model, sys_prompt, user_prompt, temperature=0.7, color=C_RESET):
    """带重试机制的串行阻塞调用（引入 rich 状态动画）"""
    with console.status(f"{color}[系统] 正在呼叫 {model} 思考中...{C_RESET}", spinner="dots12"):
        while True:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=temperature
                )
                content = clean_think_tags(response.choices[0].message.content)
                console.print(f"{color}↳ 调用完成，获取文本长度: {len(content)} 字{C_RESET}", highlight=False)
                return content
            except Exception as e:
                console.print(f"{C_SYS}[错误] {model} 调用失败: {e}。10秒后重试...{C_RESET}")
                time.sleep(10)


def extract_json(text, model=MODEL_CODER_JSON):
    """双保险 JSON 提取：正则 -> 备用 Coder 模型清洗"""
    match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL | re.IGNORECASE)
    raw_json = match.group(1).strip() if match else text.strip()
    try:
        return json.loads(raw_json)
    except:
        console.print(f"{C_SYS}[警告] 格式受损，正在呼叫 Coder 模型进行修复...{C_RESET}")
        fix_sys = "你是一个无情的JSON修复器。提取并修复用户的文本，只输出合法纯JSON，绝不包含```json标记或废话。"
        fixed_text = call_llm(model, fix_sys, raw_json, temperature=0.0)
        try:
            return json.loads(fixed_text)
        except Exception as e:
            console.print(f"{C_SYS}[致命错误] JSON 彻底解析失败: {e}{C_RESET}")
            sys.exit(1)


def human_confirm(prompt_msg):
    """核心熔断机制：等待人类确认"""
    console.print(f"\n[bold red]>>> 🚦 熔断确认点 🚦 <<<[/bold red]")
    console.print(f"[bold yellow]{prompt_msg}[/bold yellow]")
    while True:
        ans = input("请输入 Y 继续执行，或手动修改对应文件后输入 Y (输入 N 退出): ").strip().upper()
        if ans == 'Y':
            return
        elif ans == 'N':
            sys.exit(0)


# ================= 七大核心模块 =================

def phase1_global_outline(idea):
    """模块1：全书大纲和节奏把控"""
    console.print(f"{C_PLAN}========== 阶段1：全书总纲生成 =========={C_RESET}")
    sys_prompt = """你是网文顶尖总架构师，精通百万字长线小说的黄金节奏。
请根据用户的脑洞，推演一本分为【10卷】的长篇大纲。
必须输出纯JSON，格式：
{
  "book_title": "书名",
  "core_hook": "一句话核心卖点（贯穿全书）",
  "power_system": "力量体系或升级路线",
  "main_characters": [{"name": "主角名", "role": "定位", "personality": "性格"}],
  "volumes": [
    {"vol_num": 1, "vol_name": "卷名", "word_count_estimate": "约20万字", "main_conflict": "本卷核心冲突", "ending_hook": "卷末悬念/高潮"}
  ]
}"""
    raw_outline = call_llm(MODEL_GLOBAL_PLANNER, sys_prompt, idea, temperature=0.9, color=C_PLAN)
    global_data = extract_json(raw_outline)

    with open("global_outline.json", "w", encoding="utf-8") as f:
        json.dump(global_data, f, ensure_ascii=False, indent=2)

    human_confirm("全书总纲已生成并保存至 global_outline.json。请检查大方向是否偏离！")
    return global_data


def phase1_5_expand_world_bible(global_data, bible, memory):
    """模块1.5：世界观与设定扩充师（防瞎编设定）"""
    console.print(f"{C_PLAN}========== 阶段1.5：深度设定挖掘与扩充 =========={C_RESET}")
    sys_prompt = """你是顶级的网文设定扩充师。请根据提供的全书大纲，深度扩写世界观细节。
必须输出纯JSON，格式如下：
{
  "characters": {"主角/重要配角名": "功法、武器、性格底色、当前境界等详细设定"},
  "items": {"核心道具/神器名": "功能描述与当前状态/归属"},
  "factions": {"势力/门派名": "势力分布、底蕴与核心人物"},
  "world_rules": ["力量体系详细阶层结构（必须清晰）", "世界核心运转法则1", "法则2"]
}"""
    user_prompt = f"请基于以下大纲进行深度扩充：\n{json.dumps(global_data, ensure_ascii=False)}"

    raw_expansion = call_llm(MODEL_GLOBAL_PLANNER, sys_prompt, user_prompt, temperature=0.8, color=C_PLAN)
    expanded_data = extract_json(raw_expansion)

    # 注入到初始的世界设定集中
    bible["characters"].update(expanded_data.get("characters", {}))
    bible["items"].update(expanded_data.get("items", {}))
    bible["factions"].update(expanded_data.get("factions", {}))
    bible["world_rules"].extend(expanded_data.get("world_rules", []))

    save_state(bible, memory)

    # 用 Rich 呈现生成的设定
    console.print(Panel("[green]设定集扩充完成！[/green] 以下为初始注入数据：\n" +
                        f"- 人物档案：{len(bible['characters'])} 条\n" +
                        f"- 道具档案：{len(bible['items'])} 条\n" +
                        f"- 势力档案：{len(bible['factions'])} 条\n" +
                        f"- 世界法则：{len(bible['world_rules'])} 条",
                        title="[bold cyan]🌍 World Bible 初始化[/bold cyan]", border_style="cyan"))

    human_confirm("世界观已扩充并保存至 world_bible.json。请检查并修改不合理的设定！")
    return bible


def phase2_volume_outline(global_data, vol_num):
    """模块2：卷大纲和卷节奏把控"""
    console.print(f"{C_PLAN}\n========== 阶段2：第 {vol_num} 卷大纲拆解 =========={C_RESET}")
    vol_info = next((v for v in global_data['volumes'] if v['vol_num'] == vol_num), None)

    sys_prompt = """你是细节掌控力极强的分卷导演。请将本卷拆解为【20章】的详细章节大纲。
每一章必须有明确的爽点、动作线和信息量。
输出纯 JSON 数组：
[
  {
    "chapter": 1, 
    "core_plot": "本章核心动作与对话剧情（不少于300字详细推演）", 
    "emotion_flow": "情绪起伏变化", 
    "hook_or_ending": "结尾卡点（必须戛然而止在冲突爆发处）"
  }
]"""
    user_prompt = f"【全书核心】：{global_data['core_hook']}\n【本卷主线】：{json.dumps(vol_info, ensure_ascii=False)}\n请开始推演第{vol_num}卷的20章大纲。"

    raw_vol = call_llm(MODEL_VOLUME_PLANNER, sys_prompt, user_prompt, temperature=0.8, color=C_PLAN)
    vol_data = extract_json(raw_vol)

    with open(f"vol_{vol_num}_outline.json", "w", encoding="utf-8") as f:
        json.dump(vol_data, f, ensure_ascii=False, indent=2)

    human_confirm(f"第 {vol_num} 卷详细大纲已保存至 vol_{vol_num}_outline.json。请确认章节节奏是否完美！")
    return vol_data


def phase3_context_retrieval(chapter_plot, world_bible):
    """模块3：战前情报提取（动态记忆包组装前半段）"""
    console.print(f"{C_RAG}>> 正在为本章按需提取《设定集》情报...{C_RESET}")
    sys_prompt = """你是战前情报员。用户的输入包含【本章剧情大纲】和【庞大的世界设定集】。
请你仔细阅读剧情大纲，从设定集中**精准提取出只与本章有关的人物状态、道具和地点法则**。无关的绝对不要提取！
以紧凑的 Markdown 文本输出提取结果，字数控制在400字以内，重点标出人物当前的‘重伤/健康/境界’等状态。"""

    user_prompt = f"【本章剧情大纲】：\n{chapter_plot}\n\n【全局设定集（请提取子集）】：\n{json.dumps(world_bible, ensure_ascii=False)}"
    return call_llm(MODEL_CONTEXT_RAG, sys_prompt, user_prompt, temperature=0.3, color=C_RAG)


def phase4_writer(global_data, vol_num, chap_num, chap_outline, relevant_lore, memory):
    """模块4：核心写手（最关键的 Prompt 设计）"""
    console.print(f"\n{C_WRITE}========== 阶段4：核心写手创作 第 {vol_num} 卷 第 {chap_num} 章 =========={C_RESET}")

    # 组装滑动窗口摘要
    rolling_text = "\n".join([f"前情 {i + 1}: {text}" for i, text in enumerate(memory['rolling_summaries'])])
    if not rolling_text: rolling_text = "这是全书或本卷的开篇。"

    sys_prompt = """作为一名深谙番茄短篇小说爆款逻辑的网文大神，请严格按照以下要求撰写：
    1. 【排版节奏】（最重要！）长短句错落有致！绝对禁止通篇“一句话一段”的极端碎玻璃渣排版。同样禁止通篇都是长句堆在一起的大段落排版，正常叙事段落保持在1-3句话，尽量多的保证是短句成段居多，能保持手机阅读的呼吸感。
    2. 【视角】全文必须严格使用第三人称。
    3. 【高级爽点】展现降维打击的压迫感，但**严禁通篇使用“冷笑”、“轻笑”、“挑眉”**！主角的强大应通过从容的动作、平静却极具杀伤力的台词、以及对历史底蕴的信手拈来来体现。反派的破防要有层次（傲慢 -> 错愕 -> 怀疑人生 -> 彻底崩溃），不要一出场就只会“惊恐发抖”。
    4. 【画面感与去菜名化】Show, don't tell。高密度对话推动剧情。**严禁像“报菜名”一样机械堆砌文物或典籍名称**！当文物或神明出场时，着重描写其展现的史诗画面、能量碰撞的视觉奇观和历史厚重感。
    5. 【收尾】本章结尾必须停在冲突爆发的瞬间，立刻戛然而止！
    6. 【去AI味/禁数据】严禁使用像写报告一样的精确数据！用感官描写代替数据，比如用“微乎其微”代替“0.03%”。严禁出现“宛如、不禁、深邃”等滥用的网文词。
    7. 每个部分至少2500字。
    不要输出任何解释性废话，直接生成小说正文。"""

    user_prompt = f"""====== 📦 动态记忆包 📦 ======
【全局基调】：{global_data['core_hook']}
【本卷目标】：第{vol_num}卷的主线
【本章设定约束（严格遵守）】：\n{relevant_lore}

【近期剧情回顾（供你了解来龙去脉）】：\n{rolling_text}

【🔥🔥🔥 上一章结尾最后300字（必须无缝接着写！）🔥🔥🔥】：
{memory['last_chapter_tail'] if memory['last_chapter_tail'] else "(无，直接开篇)"}

====== 🎯 本章绝对任务 🎯 ======
剧情：{chap_outline['core_plot']}
情绪：{chap_outline['emotion_flow']}
结尾：必须停在 -> {chap_outline['hook_or_ending']}

请开始撰写正文（约2500字）："""

    return call_llm(MODEL_WRITER, sys_prompt, user_prompt, temperature=1.1, color=C_WRITE)


def phase5_double_blind_review(draft, chap_outline, memory, relevant_lore):
    """模块5：双盲审核与熔断（已升级润色修改工与设定核对）"""
    console.print(f"{C_EDIT}>> 启动双盲审判庭...{C_RESET}")
    max_retries = 15
    current_draft = draft

    for attempt in range(max_retries):
        word_count = len(current_draft)
        if word_count < 2500:  # 长篇单章字数底线
            console.print(f"{C_EDIT}>> 字数仅 {word_count}，打回扩写！{C_RESET}")
            rewrite_sys = "原稿字数不达标，请补充心理博弈、动作细节与场景环境描写，直接输出扩写后的全文。"
            current_draft = call_llm(MODEL_WRITER, rewrite_sys, current_draft, temperature=1.1)
            continue

        # 排版审
        style_sys = """你是极其严苛的番茄网文文字编辑，拥有顶级的中文语感。请对照以下标准，用人类编辑的直觉审核草稿：

                1. 【排版呼吸感】严查极端的排版！如果发现通篇都是“一句话一段”的碎玻璃渣排版，或者发现超过5句以上不分段的大泥石流段落，必须打回！要求长短句结合，正常段落1-3句，尽量保证大部分是短句成段，保证阅读时候的体验。
                2. 【词汇丰富度】严查重复的微表情词汇！如果文中高频出现“冷笑”、“轻笑”、“挑眉”、“惊恐”、“发抖”，必须打回！要求写手用具体的动作和神态细节来替换这些干瘪的词汇。
                3. 【去AI味】严查浓重的AI翻译腔和套路词（如“不禁”、“宛如”、“勾起一抹弧度”、“深邃的眼眸”）。绝对禁止出现“量子、底层逻辑、代码、机制”等强AI/现代违和词汇，一旦出现立刻打回！
                4. 【互动密度】是否通过高频的对话交锋和微表情/动作描写来推动了剧情？不要全篇内心碎碎念。

                如果完全符合上述所有标准，毫无修改必要，请只回复纯文本：PASS（不要任何标点，不要解释）。
                如果有任何不符合，请以“【排版修改建议】”开头，直接指出具体是哪一段/哪里的剧情出了问题，并明确告诉写手该如何合并段落、拆分段落或替换重复词汇。"""
        style_feed = call_llm(MODEL_STYLE_EDITOR, style_sys, current_draft, temperature=0.3, color=C_EDIT)

        # 逻辑审（新增设定一致性校验）
        logic_sys = """你是铁面无私的剧情逻辑编辑。请严格根据大纲和世界观设定审核草稿：
                1. 【设定一致性】是否违背了设定集中的人物设定、力量体系或道具状态？写手是否写错了武器名或功法效果？
                2. 【连贯与铺垫】剧情是否与前文衔接自然？大招和文物的出现是否有合理的场景触发，还是生硬的“报菜名”？如果有强行堆砌设定的感觉，打回重写。
                3. 【爽感层次】主角的降维打击是否展现出了从容不迫的压迫感？反派的情绪转变是否符合逻辑（必须有层次递进，不能一招还没出就开始害怕）？
                4. 【断章】结尾是否成功停在了冲突爆发的瞬间（卡点）？

                如果毫无破绽且设定完全吻合，请只回复纯文本：PASS（不要任何标点）。
                如果有任何逻辑漏洞、爽感不足或设定崩塌，请以“【剧情修改建议】”开头，明确指出错误并提供修改方向。"""
        logic_user = f"【本章设定约束】：\n{relevant_lore}\n\n大纲：{chap_outline}\n上章结尾：{memory['last_chapter_tail']}\n草稿：{current_draft}"
        logic_feed = call_llm(MODEL_LOGIC_EDITOR, logic_sys, logic_user, temperature=0.3, color=C_EDIT)

        style_pass = style_feed.strip().upper().startswith("PASS") and "建议" not in style_feed
        logic_pass = logic_feed.strip().upper().startswith("PASS") and "建议" not in logic_feed

        if style_pass and logic_pass:
            console.print(f"{C_SYS}>> [双审通过] 第 {attempt + 1} 次审核过关！{C_RESET}")
            return current_draft
        else:
            console.print(f"{C_EDIT}>> [打回重修] 第 {attempt + 1} 次被打回，正在呼叫专职润色修改工...{C_RESET}")

            # 使用指令遵循极强且幻觉少的模型做局部精准润色，而不是重写全文
            rewrite_sys = "你是顶级网文精修师。请根据主编的修改意见，对原稿进行【局部替换和精准润色】。严禁随意改动没有被批评的优秀段落，只修复排版或逻辑指出的具体问题。直接输出修改后的完整正文，不要有任何废话。"
            rewrite_prompt = f"主编退稿意见：\n排版：{style_feed}\n逻辑：{logic_feed}\n\n需要修改的原稿全文：\n{current_draft}"
            current_draft = call_llm(MODEL_LINE_EDITOR, rewrite_sys, rewrite_prompt, temperature=0.5, color=C_WRITE)

    console.print(f"[bold red]!!! 警告：超过 {max_retries} 次盲审未过，触发死循环熔断 !!![/bold red]")
    human_confirm("本章极难处理，请阅读终端输出，或者直接按 Y 强行放行当前草稿。")
    return current_draft


def phase6_state_machine_update(chapter_text, bible, memory):
    """模块6：更新状态机与记忆池（使用 Rich Panel 呈现）"""
    console.print(f"{C_STATE}>> 正在将本章事实烙印至全局状态机...{C_RESET}")

    # 动作A：更新 World Bible
    sys_bible = """你是世界观维护神。请阅读最新一章正文，提取以下信息（包括但不限于以下信息）并输出纯JSON：
{
  "new_or_updated_characters": {"人物名": "人物特点性格/最新状态/生/死/境界变化"},
  "new_or_updated_items": {"道具名": "当前在谁手上/损坏/激活"},
  "important_lore_facts": ["新增的世界观事实1", "事实2"]
}
如果没有变化，请输出空字典。纯JSON格式。"""
    updates_raw = call_llm(MODEL_STATE_MACHINE, sys_bible, chapter_text, temperature=0.1)
    updates = extract_json(updates_raw)

    if updates:
        if "new_or_updated_characters" in updates:
            bible["characters"].update(updates["new_or_updated_characters"])
        if "new_or_updated_items" in updates:
            bible["items"].update(updates["new_or_updated_items"])
        if "important_lore_facts" in updates:
            bible["world_rules"].extend(updates["important_lore_facts"])

        # [补充 Rich 状态机展示]
        console.print(Panel(
            Pretty(updates),
            title="[bold magenta]🔄 状态机流转 (World Bible Updated) 🔄[/bold magenta]",
            border_style="magenta",
            expand=False
        ))

    # 动作B：生成浓缩记忆
    sys_sum = "将这章核心剧情浓缩为不超过150字的极简第一人称摘要。只保留动作、因果和关键对话事实。"
    summary = call_llm(MODEL_CODER_JSON, sys_sum, chapter_text, temperature=0.3)

    memory["rolling_summaries"].append(summary)
    if len(memory["rolling_summaries"]) > 5:  # 永远只记住最近5章的摘要
        memory["rolling_summaries"].pop(0)

    # 提取最后300字作为尾巴
    memory["last_chapter_tail"] = chapter_text[-300:] if len(chapter_text) > 300 else chapter_text

    save_state(bible, memory)


def phase7_volume_review(vol_num, vol_chapters_text):
    """模块7：卷审核（宏观纠偏）"""
    console.print(f"\n{C_SYS}========== 阶段7：第 {vol_num} 卷结卷复盘 =========={C_RESET}")
    console.print(f"第 {vol_num} 卷撰写完毕！累计总字数约：{len(vol_chapters_text)} 字。")
    human_confirm(f"第 {vol_num} 卷收尾完毕，准备开启下一卷？")


# ================= 主控制流 =================
if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    console.print(f"[bold cyan]🚀 百万字长篇 AI 工业化流水线 启动 🚀[/bold cyan]\n")

    # 1. 加载或初始化本地档案库
    world_bible = load_state()
    rolling_memory = load_memory()

    # 2. 全书总纲
    if os.path.exists("global_outline.json"):
        with open("global_outline.json", "r", encoding="utf-8") as f:
            global_outline = json.load(f)
        console.print("[成功] 已加载现有全书大纲。")
    else:
        idea = input("请输入你的长篇核心脑洞设定（越详细越好）：")
        global_outline = phase1_global_outline(idea)

    # [新增] 1.5 设定集初始化与扩充（只有当人物档案为空时才触发，避免重复扩写）
    if not world_bible.get("characters") and not world_bible.get("factions"):
        world_bible = phase1_5_expand_world_bible(global_outline, world_bible, rolling_memory)

    # 3. 逐卷推演执行
    TOTAL_VOLUMES = len(global_outline.get("volumes", []))

    for vol in global_outline.get("volumes", []):
        vol_num = vol["vol_num"]

        # 卷大纲
        vol_file = f"vol_{vol_num}_outline.json"
        if os.path.exists(vol_file):
            with open(vol_file, "r", encoding="utf-8") as f:
                vol_outline = json.load(f)
        else:
            vol_outline = phase2_volume_outline(global_outline, vol_num)

        vol_text_collection = ""

        # 逐章生产
        for chapter in vol_outline:
            chap_num = chapter["chapter"]

            # 模块3：战前情报 RAG
            relevant_lore = phase3_context_retrieval(chapter["core_plot"], world_bible)

            # 模块4：写手初稿
            draft = phase4_writer(global_outline, vol_num, chap_num, chapter, relevant_lore, rolling_memory)

            # 模块5：双盲审判（传入 relevant_lore 以便逻辑编辑比对设定）
            final_chapter_text = phase5_double_blind_review(draft, chapter, rolling_memory, relevant_lore)

            # 保存到本地
            with open(f"Novel_Vol{vol_num}_Chap{chap_num}.txt", "w", encoding="utf-8") as f:
                f.write(final_chapter_text)

            vol_text_collection += f"\n\n【第{chap_num}章】\n" + final_chapter_text

            # 模块6：更新档案与状态机
            phase6_state_machine_update(final_chapter_text, world_bible, rolling_memory)

        # 模块7：卷结语
        phase7_volume_review(vol_num, vol_text_collection)

    console.print("[bold green]🎉 全书完结！百万字神作已诞生！🎉[/bold green]")