# 后续新增敌人图片 · 执行指令

本页用于复用当前敌人美术流程。美术登记与可战斗敌人配置分开：图片存在不代表机制、能力、掉落或遭遇已开放。

## 可直接交给执行者的任务文本

```text
为当前修仙游戏新增敌人图片。

敌人名称：【填写名称】
稳定 ID：【填写 snake_case ID；未指定时先根据身份确定，避免撞名】
外观锚点：【体型/物种、头部或面具、装备或标志物、材质、主色】
与现有敌人的区别：【用轮廓和结构说明，不能只换色】
本次范围：图片制作、资源登记和审阅页；机制、属性、技能、掉落和遭遇投放后补。

先读 AGENTS.md、ARCHITECTURE.md、ART_DIRECTION.md，以及
artifacts/art-foundation/DIRECTION.md、ADD_ENEMY.md。

沿用 0.3.0 细像素修仙风、左上暖光和现有敌人材质语言。
模型使用 gpt-image-2.6-sunburst，本任务最多【N】次 API 调用，失败和尺寸降级也计入上限。
使用项目 tools/gen_assets.py 的预设、去重、立即落盘与失败恢复机制；不换模型、不绕过缓存、不盲目重试。
素材只供程序调用本地文件，不引用生成服务 URL。

原图 1024×1536；完整主体与道具留边，三分之四视角，统一纯洋红 #FF00FF 背景，主体不用粉紫色。
保留无损 master。用既有本地处理流程去底、清边、最近邻缩放，输出高 512px 的透明 PNG，保持物种原比例。
非人形必须明确四足、翅膀或根肢结构，不强行拉成人形。

先复用已存在的合适素材；确需新增才调用。批量开始前按当前授权执行试稿确认；已确认的本任务名单可连续制作。
登记美术 ID、中文名和外观锚点，接入 assetPaths.ts 的资源解析、art-foundation.html 的对照与联系图工具。
新增敌人标为“美术储备”，不创建假能力或偷偷加入问道塔。

交付：原图、透明运行图、完整脱敏生成记录、浅深底和80/94/112/192px审阅页、联系图、文件指纹及实际调用次数。
是否运行测试和构建遵从本次明确指令；视觉由用户人工确认，未运行的检查不能写成通过。
保护其他未提交改动，不动无关培养/物品/战斗业务代码。
```

`【N】` 必须替换为本次明确授权的调用上限。美术前置任务的 40 次不是以后新任务自动可用的额度。已经授权的当前任务，仍按该任务累计尝试次数控制，不重复索取许可。

## 当前制作位置与命令

1. 查看 `frontend/public/assets/art-foundation/enemies/index.json` 与 `assets/manifest.json`，检查 ID、已落盘结果、未完成下载和曾失败的请求。
2. 新建 `assets/prompts/<本次预设>.json`。参考 `art-foundation-enemies-expanded.json` 的结构，`kind: portrait`、`background: magenta`；主体写在 `subject`，公共风格由管线拼接，不用完整 `prompt` 绕过公共约束。正式敌人与储备敌人使用一致的资源目录。
3. 运行既有生成脚本；其 `--max-attempts` 只约束本次进程，要同时核对本任务跨进程累计值和 `.env` 中的历史累计总上限，不改密钥或模型配置来绕过限制。

```powershell
backend\.venv\Scripts\python.exe tools/gen_assets.py --preset <本次预设> --max-attempts <本次剩余上限>
```

4. 成功后保留 `assets/masters/art-foundation-enemies/<id>.png`。若下载中断，复用现有 pending 恢复流程，不再次请求生图。处理本地输出：

```powershell
backend\.venv\Scripts\python.exe tools/normalize_assets.py --input-dir assets/raw/art-foundation-enemies --output-dir frontend/public/assets/art-foundation/enemies --portrait-height 512 --chroma-key
```

5. 更新资源和审阅登记：

| 位置 | 更新内容 |
|---|---|
| `frontend/public/assets/art-foundation/enemies/index.json` | ID、中文名、文件名、外观锚点及 `art_reserve` 状态 |
| `frontend/src/presentation/assetPaths.ts` | `ENEMY_ARTWORK_IDS` 新 ID；仍只解析本地资源 |
| `frontend/public/art-foundation.html` | `enemies` 素材卡与适用尺寸；储备标记明确 |
| `tools/prepare_art_foundation_review.py` | 联系图名单；数量变化时同步画布和行列，避免裁切 |
| `assets/masters/art-foundation-enemies/README.md` | master/运行图映射、尺寸与实际调用记录 |

已有 `EnemyFigure.vue` 会在 PNG 加载中或失败时回退程序图；通常无需为每种新敌人修改组件。不要在该组件按 ID 编写战斗规则。

6. 重新整理联系图与素材清单，不产生生图费用：

```powershell
backend\.venv\Scripts\python.exe tools/prepare_art_foundation_review.py
```

7. 在现有游戏地址加 `/art-foundation.html` 交给用户人工审阅。交付时明确区分“原图生成成功、透明图处理完成、展示代码已接入、玩法已实现、人工画面确认”，不能相互代替。

## 转为真正可战斗敌人时

另按玩法任务确认属性、技能、编成、层段、奖励和难度，再进入 `config/enemies/`、`config/modes/tower.json`、校验及固定战斗快照流程。美术任务本身不授权这些规则变化。
