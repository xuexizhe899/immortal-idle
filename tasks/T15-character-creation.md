# T15 · 角色快速创建与数值平衡

- 目标：输入一个角色名或角色概念，快速产出一份可校验、可上线的弟子内容包，保证数值不超模、技能文案贴合角色。
- 产物：`config/disciples/<id>.json`、两条技能、可选羁绊、立绘提示、数值报告、自动校验结果。
- 执行工具：`tools/create_disciple.py`（只用标准库，复用 `tools/validate_config.py`）。

## 一、输入：角色卡

角色卡是一个 JSON。用户只需给出角色名和大致概念，执行者负责补齐以下字段：

```json
{
  "id": "sunwukong",
  "name": "孙悟空",
  "title": "齐天",
  "origin": "myth",
  "rarity": 3,
  "lean": "attack",
  "profile": "burst",
  "concept": "花果山猴王，桀骜不驯却重情重义，一根金箍棒打上天庭，也在取经路上学会守护同伴。",
  "motifs": [
    "金箍棒",
    "筋斗云",
    "火眼金睛",
    "七十二变"
  ],
  "visual": "身形精瘦矫健的猴王，头戴金箍，火眼金睛，虎皮短裙与赤红披帛，手持如意金箍棒，脚踏筋斗云，桀骜张扬。",
  "visual_prompt": "Sun Wukong the Monkey King, lean agile monkey warrior, golden fillet, fiery golden eyes, tiger-skin skirt, crimson scarf, holding the golden cudgel, standing on a somersault cloud, proud defiant expression, dynamic pose",
  "active": {
    "name": "大闹天宫",
    "description": "孙悟空抡起金箍棒，一棒扫开天兵阵势，对前方两名敌人各造成140%攻击的伤害。",
    "cooldown": 3,
    "vfx": "slash",
    "actions": [
      {
        "kind": "damage",
        "target": "enemy_first",
        "count": 2,
        "coefficient": 1.4
      }
    ]
  },
  "passive": {
    "name": "七十二变",
    "description": "孙悟空仗着火眼金睛看破敌招，对已被降低防御的目标造成伤害提高12%。",
    "bonuses": {
      "damage": 0.12
    },
    "condition": "target_weakened"
  },
  "bond": {
    "id": "qitian",
    "name": "齐天大圣",
    "description": "与哪吒同阵时，大闹天宫对已降防目标的伤害系数提高15%。",
    "members": [
      "sunwukong",
      "nezha"
    ],
    "requires": 2,
    "effects": [],
    "modifiers": [
      {
        "skill": "sunwukong-art",
        "condition": "target_weakened",
        "coefficient_bonus": 0.15
      }
    ]
  },
  "unlock_cost": {
    "reputation": 220
  },
  "asset_id": "trial-v04/sunwukong"
}
```

必填：`id/name/title/origin/rarity/lean/concept/motifs/visual/active/passive`。
可选：`profile`、技能效果覆盖、`bond`、`unlock_cost`、`asset_id`、`power_target`。

### 从一句话到角色卡

用户只需要说“做一个孙悟空，神话，攻击型”，执行者按以下顺序补齐：

1. 查角色出处与 3–5 个标志性意象，写入 `concept` 和 `motifs`。
2. 按角色气质选品质/倾向/形态：莽撞爆发用 `attack/burst`，沉稳守护用 `defense/guardian`，谋士用 `support/strategist`，匠人用 `craft/artisan`。
3. 用母题写两条**角色专属**技能文案，避免“提升攻击”这类通用描述。
4. 写中文视觉描述与英文 `visual_prompt`，保证立绘风格可落地。
5. 运行生成器；先看报告再决定是否上线。

## 二、执行流程

```powershell
# 1. 生成草稿 + 临时配置校验，不碰正式 config
backend\.venv\Scripts\python.exe tools/create_disciple.py --brief tools/examples/disciple-brief-sunwukong.json

# 2. 审阅数值报告
artifacts/character-drafts/sunwukong/balance-report.md

# 3. 立绘完成并保存到 frontend/public/assets/trial-v04/sunwukong.png 后上线
backend\.venv\Scripts\python.exe tools/create_disciple.py --brief tools/examples/disciple-brief-sunwukong.json --apply

# 4. 全量校验
backend\.venv\Scripts\python.exe tools/validate_config.py
backend\.venv\Scripts\python.exe -m pytest tools/tests -q

# 5. 前端类型/测试/构建
cd frontend
npm test
npm run build
```

- 默认只写 `artifacts/character-drafts/<id>/`，不改正式名单。
- 立绘缺失时 `--apply` 会拒绝；确需先接线可显式 `--allow-pending`，但图鉴会出现缺图，必须后续补图。
- `--force` 只用于覆盖本角色自己的弟子/技能文件，并保留角色已有的羁绊列表；不会覆盖既有羁绊配置，既有羁绊需要手动合并成员。
- 资产 ID 仅接受由字母、数字、下划线和短横线组成的相对路径片段；拒绝盘符、绝对路径、上级目录和 URL 参数。羁绊成员不可重复。
- 重生成同名草稿且取消羁绊时，会移除上次生成的 `bond.json`。

## 三、数值平衡规则

属性参考分沿用原型公式 `atk + 0.5 × def + 0.1 × hp`，只用于生成时约束基础属性区间，不能预测新版自动战斗的胜负或技能强度。`spd` 限制在 7–15 区间，新战斗中决定出手顺序。

| 品质 | 攻击 | 防御 | 辅助 | 炼制 |
|---|---|---|---|---|
| 1 品 | 27.0 | 27.5 | 26.5 | 26.0 |
| 2 品 | 34.0 | 36.0 | 30.5 | 28.5 |
| 3 品 | 38.0 | 40.5 | 34.5 | 34.0 |

- 基准按现有 16 人的同品质/倾向中位数校准；辅助/炼制保留较低战斗、较高值守价值的定位，但不复制诸葛亮 26.1 的低战力异常。
- 每个倾向有两种形态（爆发/耐战、守护/反击、谋略/续航、丹术/器作），只改变属性形状，缩放后总战力仍回到同一基准。
- 生成结果要求：与目标偏差 ≤0.6，且落在同品质现有区间 ±2 内；超出直接拒绝。
- 属性安全范围：气血 80–170、攻击 10–26、防御 6–24、身法 7–15。
- 招募声望：1 品 80；2 品 130–150；3 品 180–200，可按角色定位在 40–300 内覆盖。
- 主动使用 `actions`、`cooldown` 和 `vfx`，支持直接伤害、治疗、护盾、属性增减；被动使用 `bonuses` 与 `condition`。旧 `stat/mode/value/scope` 技能字段直接拒绝。
- `atk/def/hp/spd` 被动只支持 `always`，在出发时折入自身属性；条件被动只支持本次行动的 `damage/healing/shielding`，条件属性加成会被拒绝，避免生成实际无效的技能。
- 生成安全预算：主动间隔 2–5 次自身行动，单个效果系数不超过 3，总目标效果预算不超过 10；被动单属性不超过 30%，合计不超过 40%。这些是输入约束，实际平衡仍需同等条件战斗对照。
- 出征羁绊使用 `modifiers` 指向成员技能，可调整目标数、系数、持续轮数或追加有限效果；值守羁绊仅接受已实现的产出属性，`pill_rate` 不可上线。
- 报告会列出同组角色、同品质区间、值守产出百分比加成、招募成本和战力偏差，供上线前人工复核。

## 四、风格与技能文案规则

- `concept` 至少 20 字，说明人物关系、性格与核心冲突。
- `motifs` 2–6 个，必须是该角色可辨识的物件、能力或称号。
- 主动/被动描述至少各命中一个母题；工具会拒绝没有母题的通用文案。
- 主动/被动名称不能是“攻击/技能/被动/大招”等通用词，也不能同名。
- `visual` 至少 30 字且命中母题；`visual_prompt` 与全局 `config/style/style.json` 合并成立绘提示，保证细像素修仙风一致。
- 技能定义供服务端自动战斗执行；新增角色只能使用 T16 已实现的动作、条件和修饰，不通过任意表达式、脚本或递归追击扩展规则。

## 五、自动校验

生成器会在临时配置副本上执行：

1. `tools/validate_config.py` 的结构与跨文件引用校验；
2. 弟子/技能/羁绊引用、技能类型、asset/pending、id 与文件名一致；
3. 战力偏差、同品质区间、属性安全范围；
4. 母题命中、通用名称、描述长度；
5. `--apply` 前再次校验，失败不写正式配置。

临时校验通过但正式写入后仍失败时，命令会报错；此时检查是否有并发改动，不要盲目重试覆盖。

## 六、样例与验收

样例：`tools/examples/disciple-brief-sunwukong.json`，输出在 `artifacts/character-drafts/sunwukong/`。

- [x] 孙悟空样例：3 品攻击/爆发，目标 38.0，实际 38.0；气血 110 / 攻击 22 / 防御 10 / 身法 14。
- [x] 同组对照：哪吒 33.0、赵云 37.0、杨戬 38.8、关羽 40.0；未超过同品质上限。
- [x] 主动「大闹天宫」是双目标伤害，被动「七十二变」强化对降防目标的伤害，羁绊「齐天大圣」修改对应技能；均命中角色母题。
- [x] 临时配置校验通过；立绘标记为待生成，未写入正式 16 人名单。
- [x] 工具测试覆盖属性预算、确定性、形态差异、文案母题、重复 id、错误羁绊、apply 安全及新版执行字段。

## 七、边界

- 不调用生图 API；立绘需要单独授权后生成，工具只产出风格一致的提示。
- 新增弟子仍走 T16 的配置驱动，不因单个角色增加另一套战斗规则、存档结构或接口契约。
- 不把新角色自动塞进既有羁绊；要加入现有羁绊，手动改 `members` 并跑校验。新建羁绊涉及既有角色时，`--apply` 会把这些角色的图鉴羁绊列表同步加上新羁绊 id。
- 不把暂存样例当作已上线内容；只有 `--apply` 且校验通过才算进入游戏。
