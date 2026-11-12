# 2026-11-12 修改汇总：六人技能与羁绊

## 实现结果

问道塔从原型总战力判定升级为服务端自动回合战斗。玩家可以带 1–6 人，按顺序换位，围绕护盾、降防、治疗和技能羁绊组队；六人为人数上限，无需满编。

- 现有 16 名弟子的 16 主动、16 被动已执行。五虎、封神、奔月、三分天下强化对应成员技能；诗圣仍只影响值守。
- 每轮按身法与稳定槽位排序，主动按自身行动冷却，缺少有效目标时普攻。一次施法最多四条效果、每条六目标，附加效果不产生递归行动。
- 每人气血跨层保留，倒下不复活；临时状态、盾与冷却每场重新开始。最多二十轮，回合耗尽显式失败并保留实际气血。
- 护盾同源取较大值，不同源共存且总量不超过最大气血；无实际增量不刷新期限或消耗主动冷却。目标在本次技能开始固定，倒下后不将后续效果转打他人。
- 出发固化角色属性、伤势、完整技能、羁绊、模式、敌人及词条定义。战斗不消费随机数；已有确定性节点和词条随机、revision CAS、并发锁与不确定响应只查询原则保留。
- 战报记录实际伤害、恢复、护盾吸收、属性变化、羁绊来源及各单位状态，满足 `入场气血 − 实际承伤 + 实际恢复 = 离场气血`。

## 界面与美术

六人编队、弟子详情、出征准备与图鉴同步新技能规则，区分战斗羁绊和值守羁绊。出征中编队锁定，返回宗门、刷新和切档可继续原局。

战场使用 Vue、SVG 与 CSS 播放服务端战报，显示逐人气血、护盾、冷却、状态和真实数字。支持最多十帧的关键招式演出、完整交锋、1×/2×、跳过、重播及完整战报。后台切换、减少动态效果、缺图和超时都能释放演出锁。

人物与塔背景复用已有资产；石甲重锤、玉盾冠矛、长弓背箭、法杖层袍四类敌人及剑气、箭矢、火焰、治疗、护盾、风、水、石、玉等特效用代码绘制。非首屏人物图片懒加载。本期生图 API 调用 **0 次**，新增游戏位图 **0 张**，保留既定模型与最多 100 张的任务授权供确有需要时使用。

实际检查后修正六人编队头像裁切和敌人轮廓近似。桌面与 390px 手机端截图、故障模拟方式见 [验收记录](artifacts/t16/验收记录.md)。

## 内容工具与主要文件

| 范围 | 文件 |
|---|---|
| 战斗规则与契约 | `backend/app/domain/battle.py`、`domain/run_engine.py`、`models/battle.py`、`models/save.py`、`models/api.py` |
| 接口与快照 | `backend/app/api/run.py`、`api/state.py`、`api/catalog.py`、`config_loader.py` |
| 正式内容 | `config/skills/`、四组 `config/bonds/`、四个 `config/enemies/`、`config/modes/tower.json` |
| 编队与演出 | `frontend/src/stores/game.ts`、`PartyStrip.vue`、`BattleStage.vue`、`EnemyFigure.vue`、`SkillVfx.vue`、`SkillDetails.vue`、`battlePlayback.ts`、相关 views |
| 配置与角色工具 | `tools/validate_config.py`、`tools/create_disciple.py`、孙悟空示例与草稿、相关工具测试 |
| 测量 | `tools/measure_battles.py`、`artifacts/t16/benchmark.json` |
| 说明 | `README.md`、`DESIGN.md` 7.10、`AGENTS.md` 的战斗规则、`tasks/T15-character-creation.md`、`tasks/T16-skills-and-bonds.md` |

角色工具改用可执行 `actions/bonuses/modifiers`，校验引用、目标、动作数量、有限数、冷却、持续时间和生成预算，拒绝递归及未实现效果。条件被动只允许伤害/治疗/护盾修正，`atk/def/hp/spd` 必须常驻，避免生成无效定义。孙悟空仍是未应用草稿，正式名单没有扩充。

## 本次验证

以下命令均在本次交付代码上实际执行，退出状态均为 0：

| 命令 | 实际结果 |
|---|---|
| `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` | 118 passed，3.43s |
| `backend/.venv/Scripts/python.exe -m pytest tools/tests -q` | 102 passed，4.60s |
| `backend/.venv/Scripts/python.exe tools/validate_config.py` | 配置校验通过：32 技能、16 人、5 羁绊 |
| `backend/.venv/Scripts/python.exe tools/check_rng_usage.py` | RNG 使用检查通过 |
| `backend/.venv/Scripts/python.exe backend/scripts/export_openapi.py` | 契约导出成功 |
| `npm run gen:api`（frontend） | TypeScript 契约生成成功，无手改生成产物 |
| `npm test`（frontend） | 13 passed |
| `npm run build`（frontend） | vue-tsc 类型检查及 Vite 生产构建通过 |
| `git diff --check` | 通过；仅存在 Git 行尾转换提示 |

后端有一条既有 Starlette/httpx 弃用警告；工具测试有 pytest-asyncio 默认 fixture loop scope 未设置的弃用提示。本期未为处理依赖警告修改技术栈。

自动测试覆盖冷却及跨场重置、盾到期/吸收、过量治疗、目标死亡、条件时点、六人/七人/重复、回合耗尽、气血词条不复活、固定快照与配置变动、CAS 冲突及响应丢失等风险。浏览器实际检查正常、等待、网络错误、失败结算、弹窗、键盘关闭、完整战报、重播、跳过、刷新、切档、缺图和减少动态效果。

## 测量与限制

36 次固定种子阵容出征保存在 benchmark。人工 6v6、二十轮达到 240 次主行动，五次模拟含序列化中位 **177.844ms**，整档约 **2.14MB**；真实阵容样本整档峰值约 **373KB**。人工夹具不代表真实平衡或所有配置的最大字节数，耗时只代表当前机器。

最终生产 JS **175.63kB / gzip 64.46kB**，CSS **60.09kB / gzip 12.99kB**。现有主用 16 人及塔背景约 3.17MiB，按需加载，本期未增加图片包体。

平衡仅完成初始样本对照，尚未穷举组合与词条；后续依据试玩继续打磨。极限战报载荷仍有优化空间，当前只保存最近一场完整战报。旧 `start_hp/damage_scale` 配置字段仍保留为原型资料，新的战斗结算不使用它们。

## 存档与交付边界

按用户决定，不提供旧出征结构转换或双引擎兼容；不自动删除本地数据，使用新档体验新规则。数据库表结构未变，没有运行真实数据库迁移、重建或降级。视觉验证只使用隔离数据库。

本次实现、配置、测试、截图和说明作为同一任务提交；允许提交与推送，具体提交号和远端结果见交付消息。**未部署或变更真实服务器**。
