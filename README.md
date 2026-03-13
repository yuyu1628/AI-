# 多Agent长篇小说生成流水线 (Multi-Agent Novel Pipeline)

本项目是一个高度工程化的 AI 长篇小说创作框架，旨在通过**多智能体（Multi-Agent）协作**与**状态机管理**，实现百万字级别网文小说的工业级流水线生产。

区别于传统的单次 Prompt 续写，本项目模拟了真实的人类创作团队和编辑部流转过程。通过全局状态机与动态记忆提取，彻底解决大模型长文本生成的“记忆遗忘”、“设定崩塌”以及“AI味浓重”等痛点。

## ✨ 核心技术特性

* **🧠 全局状态机 (World Bible)：** 动态维护 `world_bible.json`，实时更新人物档案（生死/境界/性格）、核心道具归属、势力状态与世界观法则。
* **🗂️ 动态滑动记忆 (Rolling Memory)：** 采用 `rolling_memory.json` 维持最近 5 章的极简摘要，并提取上一章末尾 300 字作为情绪无缝衔接的锚点。
* **🕵️‍♂️ 战前情报提取 (Context RAG)：** 动笔前精准抽取设定集中与本章强相关的出场人物与法则，拒绝无效“报菜名”和幻觉设定。
* **⚖️ 双盲审判庭 (Double-blind Review)：** * **排版编辑**：严查行文呼吸感与长短句节奏，剔除“冷笑、轻笑”等高频网文套路词及 AI 翻译腔。
  * **逻辑编辑**：校验设定一致性，确保主角降维打击的压迫感与反派破防的层次感。
  * **定向精修**：针对打回意见，调用专职修改模型进行局部替换与润色，而非盲目重写全文。
* **🚦 人类熔断机制 (Human-in-the-loop)：** 在总纲生成、设定扩充、卷大纲生成以及死循环打回等关键节点触发等待，允许人类作者手动介入修改 JSON 设定后放行。

## ⚙️ 七大核心模块 (Workflow)

1. **阶段 1：全书大纲** (`Global Planner`) - 推演 10 卷百万字长线大纲。
2. **阶段 1.5：深度设定扩充** (`World Expansion`) - 补全人物、道具、势力等初始世界观。
3. **阶段 2：卷大纲拆解** (`Volume Planner`) - 拆解单卷 20 章详细动作线、情绪流与结尾卡点。
4. **阶段 3：战前情报 RAG** (`Context RAG`) - 按需提取设定集切片。
5. **阶段 4：核心写手创作** (`Core Writer`) - 融合前情提要、动态约束与强迫症级 Prompt 输出正文初稿。
6. **阶段 5：双盲审核与精修** (`Editors`) - 排版审与逻辑审双重把关，不达标则打回精修。
7. **阶段 6：状态机流转** (`State Machine`) - 提取本章新增事实，烙印至全局档案库，并更新滑动记忆。

## 🚀 安装与配置

**1. 克隆项目**
```bash
git clone [https://github.com/你的用户名/你的仓库名.git](https://github.com/你的用户名/你的仓库名.git)
cd 你的仓库名

2. 安装依赖
pip install -r requirements.txt

3. 配置环境变量
在项目根目录创建一个 .env 文件，填入你的 API 配置与模型选择（支持兼容 OpenAI 格式的各大模型 API，如 DeepSeek, Qwen 等）：
API_KEY_BASE=sk-xxxxxxxxxxxxxxxxxxxxxxxx
BASE_URL_BASE=[https://api.your-provider.com/v1](https://api.your-provider.com/v1)

# 可选：配置不同环节使用的专属模型（不配则使用代码默认值）
MODEL_GLOBAL_PLANNER=deepseek-chat
MODEL_VOLUME_PLANNER=deepseek-chat
MODEL_CONTEXT_RAG=deepseek-chat
MODEL_WRITER=deepseek-chat
MODEL_STYLE_EDITOR=deepseek-chat
MODEL_LOGIC_EDITOR=deepseek-chat
MODEL_LINE_EDITOR=deepseek-chat
MODEL_STATE_MACHINE=deepseek-chat
MODEL_CODER_JSON=deepseek-chat

💻 运行使用
启动项目：
python main.py
初始化脑洞：首次运行时，在终端输入你的核心脑洞设定。
跟随提示操作：观察终端（基于 rich 库的高颜值输出）的运转状态。
熔断确认：在提示 >>> 🚦 熔断确认点 🚦 <<< 时，你可以打开本地生成的 .json 文件审阅或修改，确认无误后在终端输入 Y 继续流水线。

📂 目录与文件产物说明
运行后，项目会自动生成并维护以下文件：
world_bible.json：全局状态机文件（随时可人为干预修改）。
rolling_memory.json：滑动窗口记忆缓存。
global_outline.json：全书总纲。
vol_X_outline.json：各分卷详细大纲。
Novel_VolX_ChapY.txt：最终审核通过的单章小说正文实体。
