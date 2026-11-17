# my_ai_town 源码借鉴调研

调研日期：2026-11-17（北京时间）。本文保留源码静态调研事实；调研后的主城迁移进展、验证和授权状态见第7节。

## 1. 下载与结论

- 来源：<https://github.com/mewamew/my_ai_town>。
- 独立下载目录：`D:\imm\my_ai_town`，不放入本游戏运行目录，也不复制到本仓库提交。
- 下载方式：`git clone --depth 1 https://github.com/mewamew/my_ai_town.git D:\imm\my_ai_town`；只取当前快照，不含完整历史。
- 对方快照：`5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1`，2026-11-17，`fix: protect town saves and recover interrupted setup`；本游戏对照快照：`a67d4067175c04dcec669907c60a2dd554ae59fd`。
- 当前源码是 Rust 世界内核、TypeScript/Vite 客户端与 Three.js HD-2D 场景，不是历史 Godot 版本；运行时模型是居民决策的核心。[S10]

最值得借鉴的是让玩家看见“谁在做什么、发生过什么、现在可以做什么”。我们已有设施经营、成长目标、服务端真实战报和末战复盘，适合在这些入口上补充人物活动与事件表达。对方的多 Agent 模型和完整自由生活模拟仍不适合当前范围；最初对 HD-2D 的成本判断已被用户选择 Three.js 主城的决定取代，七建筑代码首版现已接入，战斗场景仍未迁移。

以下“对方已实现”均指代码中存在相应路径；本次没有启动对方游戏，不代表功能或观感已通过实机验收。表中的其他玩法建议仍未实施；主城表现已在不改变玩法、存档和接口契约的范围内落地。

| 建议顺序 | 玩家能得到什么 | 相对成本 |
|---|---|---|
| 1. 主城弟子状态演出 | 看见谁在值守、谁有伤、谁已出征，人物可点开详情 | 已完成代码首版；用户人工视觉验收待做 |
| 2. 宗门纪事 | 招募、突破、升级、攻克留下记录，可回到相关人物和设施 | 中，涉及有限结构化事件及契约 |
| 3. 状态短句与人物履历 | 不同弟子有身份感，也能看到与自己有关的真实经历 | 短句低至中，持久履历中 |
| 4. 场景音景 | 宗门昼夜、问道、宗主决战的氛围更有区别 | 中，用户已授权素材复用，播放器尚未接入 |
| 5. 有取舍的宗门事件 | 选择产生可理解的收益与代价 | 高，属于另行设计的玩法变化 |

## 2. 已核实的能力与适配价值

| 对方源码中的事实 | 对我们有用的部分 | 当前游戏对照与接入代价 |
|---|---|---|
| 动作回执有动作/动作组编号、起止时间、成功/失败/中断状态、真实变化、原因和来源事件；交谈明确作为“某人说过”，不自动当成已验证事实。[S1] | 宗门动态使用可追溯事件，而非只有一段无来源文字；按弟子、培养、征讨、经营筛选并跳转原入口。 | 当前 `GameState.logs` 是字符串数组，总览只展示最近五条；战斗已有结构化回执/摘要。优先复用现有事实，若加入通用事件字段，需要最小存档与契约改动。[O1][O2] |
| 记忆记录含事件引用、对象、观察/转述/推断来源、置信度和状态；失败经验写“再次尝试前检查条件”，不写成永远不可能。[S2] | 弟子详情增加有限履历，例如首次突破、专武锻成、参与某次攻克；让人物与玩家操作建立联系。 | 不必复制模型记忆检索、笔记归档或关系数值。永久履历是新存档语义，应先定记录上限、旧档缺失显示和覆盖规则。当前只有最近一次出征复盘，不能据此伪造旧履历。[O1] |
| 模型的动作草案先做静态检查，实际开始时再查使用条件和占用；工具执行入口调用世界命令。[S3] | 将来若加入弟子建议/台词，台词只提议，资源和成功判定继续由原服务端命令负责。 | 我们已有补算、版本校验和 CAS 提交入口，不需要另建 AI 结算层。[O3] 当前没有引入模型的必要。 |
| 霜灯镇劳动用真实动作账本证明“前往、劳动、返回”成功后才发资源与计贡献；中断退还预留物资且不计贡献。[S4] | 演出应解释既有结算：谁被派出、谁回岗、谁贡献了哪些真实收益；停止播放或刷新不能再发奖励。 | 我们已有值守/驻守/出征互斥和自动回岗，适合把调度过程表现出来，不改为走路完成才产材。[O4] |
| 霜灯镇对客户端投影同时提供阶段、资源、风险积累、供热与政策、每人的当前工作/贡献以及结局。[S5] | 经营面板把“当前状态—影响—可采取操作”放在同一阅读路径。 | 我们已有设施升级收益、材料缺口和来源导航，适合补充岗位与建筑的联动；无需再造独立任务系统。[O5] |
| 玩法独立保存状态，统一暴露推进边界、结算、只读视图、角色动作及玩家管理入口；居民选择和玩家管理权限分开。[S6] | 征讨的擂台/宗主/待结算各阶段，应有明确的阶段说明和真实可用操作；未来新模式单独封装规则。 | 我们已有征讨与塔局内状态和快照，不宜为了模仿抽象而改写引擎。只在新增模式确有重复时考虑提取。[O6] |
| 角色姿态从结构化名册生成，只表现有数据支持的伤势、动作和交谈；微动作按人物 ID 错开，减少动画时停用细节。[U1] | 状态不仅写在面板里，也能在主城被看见。 | 原方案曾考虑在静态城图叠加人物；用户随后选择固定斜俯视 Three.js 场景，现由 `rendering/hd2d/` 实现状态投影和轻微驻足，不引入整套像素骨骼。[O7][O8] |
| 动态列表可筛选，客户端最多保留300条；只因新内容冒气泡，首次读档不把旧台词重播为新事件。[U2][U3] | 重要结果更容易被注意，也能回查；刷新不会让旧事不断刷屏。 | 限量原则值得借鉴，但300条只是对方前端缓存，不直接作为我方存档上限。我们应先确定事件范围和体积。 |

## 3. 建议优先级

### 优先：宗门里看得见弟子

初次调研时，主城是背景图、建筑热区与昼夜云雾，没有弟子活动层。调研后已接入固定斜俯视 HD-2D：值守者在演武场附近驻足，伤势来自真实响应，出征或驻守者从本宗过滤，点击人物打开原弟子详情。[O7] 对方点击人物可同时查看资料和定位，手机直接打开角色卡；本轮复用详情入口，没有加入镜头跟随。[U4]

首版只映射真实在岗/出征状态，不增加自主换岗、额外生产、饥饿、睡眠或情绪数值。对方同样明确“表情只跟着有数据的状态走”。[U1] 我们当前是单幅透明立绘，没有可直接套用其骨骼演出的分层人物；先做固定锚点和少量轻动作，完整行走与寻路后排。需要新增动作资产时按本游戏美术规范另行试稿，不把缩小大立绘当作小尺寸已验收。[O8]

**成本判断：中。** 主要成本是场景布局、遮挡和小尺寸角色表现，以及手机端点击目标；并非需要重写世界模拟。七建筑已接入代码，人物是否可辨识、是否遮挡建筑仍由用户人工检查。

### 优先：宗门纪事连接到人物和操作

把已有招募、培养、升级、攻克、回岗失败等真实结果整理成有来源的动态。先覆盖重要事件，避免每次挂机补算都刷一条。点击“某弟子突破”到详情，点击“外宗攻克”到对应宗门；旧记录缺结构化字段时保留原文，不从文字猜测人物和奖励。

首页只露一两条，完整内容继续放宗门总览，按经营/出征/重要筛选。对方根据服务端 `alert` 共用同一套标题与详情，不在事件栏、提示卡和日志里各写一套判断；玩家上翻阅读时也不会被新事件强行拉回底部。[U2]

**成本判断：中。** 仅优化现有文字样式成本较低；事件分类、身份和时间、导航对象若需要持久化，就涉及 Pydantic 模型、契约生成、有限保留与切档归属。建议先选少量事件，不保存无限战报或按游戏日持续增长的日志。[S1][O1][O2]

### 其次：状态短句与有限弟子履历

可先用有限固定短句回应真实结果：某弟子突破、伤势治愈或完成回岗时，以符合身份的语气说一句。它们作为演出，不增加关系值、任务或奖励。例如诸葛亮的值守文案偏筹划，关羽偏演武；这是我方可创作的方向，不是对方现成的修仙内容。参考其最多两个气泡、按阅读量保留3–6秒、首次读档不重播旧句的节制方式，避免和全局操作提示同时堆满屏幕。[U3]

从新发生且可验证的里程碑记录“这名弟子跟我经历过什么”，先做人物详情中的少量履历。已有战斗羁绊是固定组合，不自动等于两名弟子之间有动态友好、冲突和关系记忆。

**成本判断：中。** 有情感回报，但记录规则、存档大小、历史缺失、复制/导入/恢复语义都需要设计。初版可用规则模板表达真实事实，不必调用模型；更不能凭一次共战自动添加未经设计的属性加成。[S2]

### 其次：少量场景音景

对方按剧情、玩法、天气、时段选择音乐，紧张升级立即切换，恢复平静时等当前曲结束；播放器淡入淡出，并处理用户手势、后台标签页及资源释放。[U5] 我们可以只取几种明确场景：宗门昼/夜、问道战斗、宗主决战，再配少量炼制与结算短音效。复用已有昼夜与真实战斗阶段，不新增玩法时钟。

**成本判断：中。** 播放逻辑可以简化；用户已明确授权本项目直接复用对方音乐并承担法律风险。后续接入时仍需处理静音/音量、浏览器首次播放和后台行为。本轮没有导入或播放音乐。[L2]

### 后续：有明确取舍的事件

霜灯镇不是只有资源条：供热强度影响燃料和压力，政策同时有收益与代价，风险持续积累，阶段与结局有明确条件。[S4][S5] 可借鉴这种“可读的选择后果”设计少量修仙事件，例如短期偏重炼丹还是练武，而非只换一段文字后固定加资源。

**成本判断：高。** 这是新玩法，会改变收益、时间推进、RNG 或存档，当前只作为设计方向。不要直接加入实时灾害、居民死亡、不可逆法令或错过即损失的在线压力；这些规则不符合本游戏现有温和失败和离线放置边界。

## 4. 不建议直接照搬

- **常驻模型驱动每名弟子。** 对方有独立的预算、上下文压缩、并发、过时回复与模型失败暂停机制；默认额度包含每次唤醒最多 6 次调用、每居民每游戏日 400 次/200 万 token、全局在途 12 个。[S7] 这是配置上限，不是本次测得的实际花费。引入后会新增延迟、费用和恢复复杂度，不能用“接个聊天接口”概括。
- **完整饥饿、口渴、天气、生理和自由寻路模拟。** 这些系统服务于 AI 居民生活；我们目前更需要让已有经营与战斗选择清楚可见。只取表现原则，避免让离线玩家回来处理一批生活惩罚。
- **替换后端技术栈或拆整档存档。** 对方把当前状态、追加历史和居民文件分开，这是其无限生活记录的需求。[S8] 我们的 FastAPI、整档 CAS 和有限复盘是现有边界；本轮只新增 Three.js 渲染，不迁移 Rust 内核或复制一套流水存储。
- **直接迁移整套源文件或模拟系统。** 上游原创代码与文档采用 PolyForm Noncommercial 1.0.0，分发代码副本需附许可或其URL以及 `Required Notice`；本轮因此保留许可、通知和改作记录。[L1] 上游图片、音效与音乐的授权范围按其原始素材说明记录；用户已明确授权本游戏直接复用并承担相应法律风险，该用户决定已作为本轮执行依据，不再作为阻断项。[L2] 本轮仅改作一个 `uprightDepth` 立牌深度片段，没有导入上游图片或音频；Kenney脚步声仍按其CC0来源记录。[L2]

## 5. 接入边界与后续验证

主城弟子活动已形成“真实状态投影 + 人物详情入口”闭环：出征、忙碌和外宗驻守者从本宗场景过滤，真实值守者优先呈现，点击弟子打开其详情。宗门纪事和持久履历仍是后续独立设计方向。

演出归 `frontend/src/rendering/`，文案映射归 `presentation/`，操作仍走 `stores/game.ts → api`。若新增真实事件，由服务端在原补算/命令/CAS 流程中产生；前端不能在动画结束时补发资源、回岗或推进任务。[O3][O4]

验证围绕实际变更选择：角色映射与切档做受影响前端测试；增加事件/履历时做相应后端、存档、重复命令与恢复测试，再重新生成契约；视觉和390px观感交由用户人工检查。对方已有劳动交付、存档恢复、中断退还及大步时间推进等行为测试源码，可参考测试情景，但本次未运行。[S9]

调研阶段只下载和静态阅读上游源码。随后主城实现安装了 Three.js 依赖并更新锁文件，未启动模型、修改真实存档或执行浏览器渲染验收。当前代码验证见第7节；视觉效果仍待用户人工检查。

文档对照注意：`DESIGN.md` 标明自己是历史初版，仍有旧十二段远征与单阶塔描述；当前规则按宗门擂台征讨、驻守、三阶问道实现及2026-11-14实施基线理解。`tasks/README.md` 中部分任务状态滞后，不据此把已有目标、复盘和设施预览判成缺失。此次只记录差异，不顺带修改历史文档。[O9]

## 6. 源码索引

以下链接固定到所下载提交，避免 `main` 更新后结论失去对应关系。

- **S1**：[动作回执和事实类型](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/protocol/src/actions.rs#L36)，`ActionResult` 为第36行，`FactKind` 为第70行，`WorldFact` 为第100行。
- **S2**：[记忆来源、失败认识与增量整理](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/agent/src/memory.rs#L16)；[笔记来源和重复证据校验](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/agent/src/notebook/reflection.rs#L37)。
- **S3**：[动作草案校验](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/kernel/src/action_check.rs#L57)、[执行时条件与占用](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/kernel/src/action_check.rs#L194)、[动作组命令及去重](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/kernel/src/action_commands.rs#L34)、[Agent工具执行边界](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/agent/src/tools.rs#L1)。
- **S4**：[霜灯镇真实工作交付](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/kernel/src/game_mode/frostlight.rs#L330)、[资源消耗与阈值分段](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/kernel/src/game_mode/frostlight.rs#L625)。
- **S5**：[霜灯镇阶段与结局判定](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/kernel/src/game_mode/frostlight.rs#L712)、[客户端状态投影](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/kernel/src/game_mode/frostlight.rs#L827)。
- **S6**：[玩法接口与独立状态](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/kernel/src/game_mode/mod.rs#L23)。
- **S7**：[预算与默认上限](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/agent/src/budget.rs#L107)、[运行状态、压缩及请求上下文](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/agent/src/runtime.rs#L47)。
- **S8**：[当前快照与追加历史拆装](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/kernel/src/history.rs#L1)。
- **S9**：[交付/存档恢复测试](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/kernel/tests/frostlight.rs#L75)、[中断与不可达测试](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/kernel/tests/frostlight.rs#L139)、[时间步边界测试](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/crates/kernel/tests/frostlight.rs#L291)。
- **S10**：[当前版本说明](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/README.md#L7)、[客户端依赖](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/frontend/town-2d/package.json#L12)、[Rust工作区](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/Cargo.toml#L1)。
- **U1**：[真实状态映射表演线索](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/frontend/town-2d/src/map/hd2d/villagerCues.ts#L5)、[微动作与减少动画](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/frontend/town-2d/src/map/hd2d/villagerActing.ts#L20)。
- **U2**：[事件筛选与有限列表](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/frontend/town-shared/src/events.ts#L62)、[追加、重要提示与阅读滚动](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/frontend/town-shared/src/events.ts#L197)、[共用结构化重要事件文案](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/frontend/town-shared/src/importantEvents.ts#L1)。
- **U3**：[气泡去重、阅读时长与数量限制](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/frontend/town-shared/src/bubbles.ts#L1)。
- **U4**：[人物状态与点击导航](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/frontend/town-shared/src/info/strip.ts#L189)。
- **U5**：[场景选曲与切换时机](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/frontend/town-shared/src/audio/scene.ts#L130)、[音频生命周期](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/frontend/town-shared/src/audio/music.ts#L143)。
- **L1**：[代码许可与分发通知](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/LICENSE#L30)、[Required Notice与许可范围](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/NOTICE#L1)。
- **L2**：[美术音效的使用范围](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/licenses/ASSETS.txt#L7)、[音乐同样适用该范围](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/licenses/ASSETS.txt#L16)、[Kenney原始来源与CC0说明](https://github.com/mewamew/my_ai_town/blob/5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1/licenses/ASSETS.txt#L28)。
- **O1**：[我方存档字段](../../backend/app/models/save.py#L192)，`last_run_review` 为第215行，`logs` 为第218行。
- **O2**：[我方宗门总览和复盘](../../frontend/src/views/SectPanel.vue#L19)，末五条日志展示在第52行。
- **O3**：[我方命令补算与CAS提交](../../backend/app/api/state.py#L63)。
- **O4**：[我方原子离岗与回岗](../../backend/app/domain/deployment.py#L8)。
- **O5**：[我方设施收益与缺口导航](../../frontend/src/components/game/FacilitiesSection.vue#L1)、[值守面板](../../frontend/src/views/DutyPanel.vue#L1)。
- **O6**：[我方外宗与擂台规则](../../backend/app/domain/conquest.py#L33)。
- **O7**：[我方主城目标与场景](../../frontend/src/views/CityView.vue#L27)、[当前HD-2D宿主](../../frontend/src/rendering/hd2d/CityScene.vue#L1)。
- **O8**：[我方视觉天色](../../frontend/src/rendering/dayCycle.ts#L1)、[当前人物与场景美术规范](../../ART_DIRECTION.md#L51)。
- **O9**：[历史设计状态](../../DESIGN.md#L3)、[当前实施基线](../plans/2026-11-14-sect-conquest-and-facilities.md#L9)、[任务状态索引](../../tasks/README.md#L1)。

## 7. 调研后实施状态与核查记录

- `git clone --depth 1 … D:\imm\my_ai_town`：退出0，当前快照已下载，1061个跟踪文件；不含完整历史和另行下载的模型权重。
- `git fsck --connectivity-only`：退出0，未报告对象连通性错误；对方工作区无本次修改。
- 调研阶段的源码主张由双方文件核对，引用固定到对方提交。当时使用项目内 Python 核对48个引用的文件与行号及本文尾空格，0错误，`git diff --check` 退出0；该记录仅证明原调研版本，不代替后续修改的检查。
- 用户选择固定斜俯视、可拖动和缩放，并授权复用对方美术和音乐、承担相应法律风险。主城首版接入七建筑、程序地形与像素纹理、已有本地人物立牌、值守/出征/驻守状态投影、点击详情、键盘与触控手势和可选轻景深；战斗尚未迁移。
- 本轮实际改作上游 `frontend/town-2d/src/map/hd2d/standee.ts` 的 `uprightDepth` 深度片段，目标为 `frontend/src/rendering/hd2d/pixelSprites.ts`。建筑由本项目程序生成，人物使用既有本地资产；未复制上游图片、音乐或其他音频。许可、作者通知与修改记录位于 `licenses/my_ai_town/{LICENSE,NOTICE,SOURCE.md}`。
- 前端六个相关测试文件54/54通过：`city-scene.test.mjs`、`scene-gestures.test.mjs`、`asset-paths.test.mjs`、`game-store.test.mjs`、`sect-management.test.mjs`、`city-sprites.test.mjs`。最终 `npm run build` 退出码0，`vue-tsc` 和 Vite 构建成功；异步 `cityScene` chunk 为551.42 kB（gzip 140.82 kB），超过Vite建议阈值，作为后续体积优化提醒。
- 按用户限定没有运行浏览器或视觉验收。七栋建筑代码已接入不等于已确认视觉质量；桌面、390px、人物大小、场景遮挡、昼夜、手势和性能由用户人工检查。
- 未部署；提交与推送状态见本次交付消息。
