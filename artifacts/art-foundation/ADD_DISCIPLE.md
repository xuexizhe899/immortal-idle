# 后续新增弟子 · 执行指令

本页与 [新增敌人图片](ADD_ENEMY.md) 配套，适用于新增弟子立绘、角色草稿或完整角色接入。先选定范围：只有图片的角色不等于已能招募，工具生成的参考分报告也不等于实战平衡已经通过。

## 可直接交给执行者的任务文本

复制后填写方括号内容；本次范围选一项即可。

```text
为当前修仙游戏新增弟子。

姓名：【姓名】
稳定 ID：【小写英文 snake_case，避免与已有弟子冲突】
人物来源与概念：【三国/神话/历史；身份、性格、3–5个标志性意象】
外观锚点：【年龄感、脸型、发型/头饰、体型、服装轮廓与主色、标志性器物】
本次范围：【仅做立绘储备 / 完整接入可招募弟子】
仅完整接入时填写：品质【1/2/3】、倾向【攻击/防御/辅助/炼制】、
战斗定位【一句话】、主动/被动方向【内容】、羁绊【指定成员或无】、
生产专长【恰好一个已有材料ID；与战斗倾向独立，例如ling_cao】、
首次招募声望【数值；未指定时参考同品质现有角色提出方案】。

先阅读 AGENTS.md、ARCHITECTURE.md、ART_DIRECTION.md、
artifacts/art-foundation/ADD_DISCIPLE.md。
完整接入还要核对 tools/create_disciple.py、其孙悟空示例、
tasks/T15-character-creation.md、T17平衡基线和当前T18培养实现。
历史任务卡与当前实现不一致时说明差异，以最新明确指令与实际能力为准。

沿用风格版本0.3.0和诸葛亮、关羽、嫦娥三张已确认master的材质、比例和光照。
模型使用 gpt-image-2.6-sunburst，本任务最多【N】次调用，失败及尺寸降级也计入。
先检查既有图片、manifest与pending结果；使用项目gen_assets.py去重和恢复机制，
不换模型、不绕缓存、不盲目重试。批量仍遵守现有试稿确认规则。

原图1024×1536，单人全身三分之四站姿，左上暖光，完整保留头饰、袖摆、武器和双脚。
纯洋红#FF00FF底，主体不用粉紫色，不加文字、卡框、场景、光效或地面投影。
保留master与脱敏完整生成记录，处理为高512px透明PNG，不拉伸比例。
明确设置asset_id为trial-v03/<id>，文件为public/assets/trial-v03/<id>.png。
新人物不自行另建风格版本。当前API不支持参考图输入，不宣称已锁定身份。

如果只做立绘储备：只保存素材、身份说明和人工审阅材料，不写正式弟子、技能或羁绊配置。
如果完整接入：先用现有角色创建工具生成草稿，核对属性、主动、被动、可选羁绊和招募费用。
只使用当前服务端已支持的技能动作、被动条件与羁绊修饰；技能文案必须符合真实配置。
需要新机制或改动培养、战斗、存档规则时，先提出原因与方案，获授权后再改。
立绘完成、内容确认后使用--apply接入；不默认使用--force或--allow-pending。
新角色经现有声望首次招募获得，不直接修改用户存档或发放角色。

人物图片沿用presentation/assetPaths.ts的asset_id解析，通常不需要新增ID白名单。
完整接入后检查图鉴/招贤、弟子详情、编队、值守与新出征中的引用；
出征中的固定快照不被新配置改写。视觉由用户人工确认，未检查不能写成通过。

保护其他未提交改动，按AGENTS.md及本次明确指令执行检查。
交付角色卡、素材路径、原图/透明图、脱敏记录、实际调用数，
完整接入另交付配置及平衡依据，并区分草稿、正式接入、测试和人工确认状态。
```

`【N】` 是本次任务独立的授权上限，不沿用敌人美术任务的40次额度。若用户只给人物名，可先整理身份、外观和同品质定位建议；不把未授权的付费生成或玩法变化混入准备工作。

## 立绘制作与资源位置

| 位置 | 用途 |
|---|---|
| `config/style/style.json` | 当前公共风格源，版本 `0.3.0` |
| `assets/masters/trial-v03/` | 同风格人物原图；先核对是否已有合适素材 |
| `assets/prompts/disciples-v03-remaining.json` | 人物生图预设结构参考，不直接重跑整批 |
| `assets/prompts/<本次预设>.json` | 只列本次需要生成的人物 |
| `assets/manifest.json` | 最终发送提示、模型、尺寸、文件与调用记录 |
| `assets/raw/<本次预设>/` | 本次原始输出与下载恢复缓存，不提交敏感恢复响应 |
| `frontend/public/assets/trial-v03/<id>.png` | 网页使用的透明运行图 |
| `artifacts/<本次任务>/` | 身份锚点、对照图和待人工确认的检查记录 |

预设沿用 `kind: portrait`、`background: magenta`、`size: 1024x1536`；主体写在 `subject`。指定唯一 `key`、`file: <id>.png`、本次 `output_subdir` 和 `master_dir: assets/masters/trial-v03`。不要将完整 `prompt` 塞入预设绕过公共风格，也不要把草稿 `art-prompt.json` 原样当作可执行预设：两者结构和用途不同。

下列命令从仓库根目录执行，尖括号内容先替换成实际值：

```powershell
# 只核对预设，不发起生图请求
backend\.venv\Scripts\python.exe tools/gen_assets.py --preset <本次预设> --dry-run

# 已获本任务模型与调用上限授权后，才执行实际生成
backend\.venv\Scripts\python.exe tools/gen_assets.py --preset <本次预设> --max-attempts <本次剩余调用上限>

# 只处理本次输入目录，避免覆盖其他人物
backend\.venv\Scripts\python.exe tools/normalize_assets.py --input-dir assets/raw/<本次预设> --output-dir frontend/public/assets/trial-v03 --portrait-height 512 --chroma-key
```

`--max-attempts` 约束单个进程；任务跨进程累计也不能超过授权上限。下载中断时先恢复 pending，raw 缺失先恢复 master，不重新付费生成。只在明确拒绝尺寸时沿用现有降级逻辑，记录实际尺寸；本地处理不消耗生图额度。

人物 `asset_id` 为不含扩展名的相对键，例如 `trial-v03/<id>`，不是 URL、base64 或 master 路径。`characterImage()`、`discipleImage()`、`snapshotDiscipleImage()` 已负责转换，新增人物通常只需配置正确的键，不照搬敌人 `ENEMY_ARTWORK_IDS` 的登记方式。

## 完整接入时的草稿与发布

设施与驻守版本新增必填字段 `production_specialty`：每名正式弟子选择一个 `config/materials/` 中已有的材料 ID，不能填展示名称或数组。基础材料专长影响本宗值守，外宗专材专长在对应宗门驻守时发挥作用。在角色卡中明确填写 `production_specialty`，`tools/create_disciple.py` 会校验材料引用并将其写入弟子配置；工具不会根据战斗倾向自动选择专长。原角色卡未填写时先补齐再生成，不要为了跳过校验删掉设施或宗门配置。

1. 参考 `tools/examples/disciple-brief-sunwukong.json` 编写本次独立角色卡，不覆盖示例或其他草稿。`origin` 为 `sanguo/myth/history`，`lean` 为 `attack/defense/support/craft`。工具和历史示例默认指向 `trial-v04`，本次显式填写 `asset_id: trial-v03/<id>`，继续使用已确认的资源组。
2. 角色卡写明主动 `actions/cooldown/vfx`、被动 `bonuses/condition`；可选羁绊用当前 `modifiers` 或值守 `effects` 表达。参数取值以创建工具、配置校验器和服务端实际执行能力为准。
3. 默认只生成草稿，核对 `balance-report.md` 与同品质定位。报告中的基础参考分不能证明技能、控制、治疗或羁绊的实际强度；复用T17相关测量方法检查本次角色，不擅自重调全体角色。

```powershell
backend\.venv\Scripts\python.exe tools/create_disciple.py --brief <本次角色卡路径>
```

草稿位于 `artifacts/character-drafts/<id>/`：

| 文件 | 内容 |
|---|---|
| `brief.json` | 校验并补齐后的角色卡 |
| `disciple.json` | 弟子模板草稿 |
| `skill-active.json`、`skill-passive.json` | 可执行主动与被动草稿 |
| `bond.json` | 可选的新羁绊草稿，没有羁绊时不生成 |
| `art-prompt.json` | 立绘提示建议与文件就绪状态，不会调用生图 |
| `balance-report.md` | 基础属性、定位和现有同类对照 |

4. 角色内容确认、透明立绘就绪后再写入正式配置：

```powershell
backend\.venv\Scripts\python.exe tools/create_disciple.py --brief <本次角色卡路径> --apply
```

工具会写 `config/disciples/<id>.json`、`config/skills/<id>-art.json`、`config/skills/<id>-passive.json`；存在新羁绊时写 `config/bonds/<bond_id>.json`，并更新其他成员的羁绊引用以及 `config/assets_pending.json`。这些关联文件属于本次角色接入范围，交付时列明。已有羁绊的合并需要核对后单独修改，工具不会自动覆盖它。

5. 当前招贤从配置目录加载弟子，不存在需要另加的抽卡池。`unlock_cost.reputation` 影响首次声望招募；不要修改真实存档、初始资源或培养规则来让角色出现。服务端配置有进程缓存，开发时按实际启动方式重启后端，再刷新前端目录数据；已开始出征继续使用原固定快照。
6. 按当前任务约定完成配置引用与相关工具/业务检查；仅新增现有配置与图片通常不需要改接口契约。只有响应或请求结构发生变化才从Pydantic导出契约并生成前端类型，禁止手改生成文件。人工对照至少包含诸葛亮、关羽、嫦娥和新人物，以及实际卡片、编队、战斗显示尺寸；未获人工确认时保留待审阅状态。

`--apply` 表示写入本地正式配置，不表示已部署；文件就绪也不表示人工确认通过。本页是后续任务指令，本次编写文档没有新增角色、生成图片或调用API。
