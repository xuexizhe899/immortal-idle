# 外宗弟子与宗主立绘实施计划

**目标：** 为剑修、御守、丹修建立 13 个弟子造型和 3 个独立宗主造型，接入宗门预览与真实战报；三级九座宗门按流派复用。

**实现方式：** 继续使用 Vue 3 展示、Python 生成管线和本地透明 PNG。宗门配置指定图片键，服务端写入既有 BattleUnit.asset_id；不新增接口字段、不改敌人能力、数值、抽选与战斗状态。

**当前阶段：** 用户已批准本轮使用 `gpt-image-2.6-sunburst`，最多 40 次请求。三代表试稿已由用户人工确认，随后十三张已全部生成，16 张均已接入正式配置。共使用 16 次，无失败、重试或尺寸降级，剩余 24 次；后续十三张及实际页面视觉效果仍待用户人工审阅。

## 1. 资产清单与身份锚点

运行键统一为 `art-foundation/sects/<文件名，不带扩展名>`。同一个战斗模板在不同流派使用不同人物；宗主不得复用弟子图。

| 流派 | 战斗模板 / 身份 | 文件名 | 主要轮廓与标志物 |
|---|---|---|---|
| 剑修 | bamboo_swordsman | sword_swordsman.png | 精瘦青年、束发、窄袖青白袍、直剑；代表试稿，用户已确认 |
| 剑修 | cinder_blade | sword_saber.png | 壮年刀修、短发半束、斜披肩甲、宽刃刀 |
| 剑修 | cloud_archer | sword_archer.png | 高挑女弓修、高马尾、分摆短袍、长弓 |
| 剑修 | stone_guard | sword_guard.png | 方脸护卫、低盔、紧凑甲衣、方盾短剑 |
| 剑修 | 宗主（cinder_blade） | sword_master.png | 灰鬓宗主、剑形冠、长披肩礼袍、重剑 |
| 御守 | stone_guard | ward_guard.png | 壮硕人类、露面重盔、块状铁甲、方头锤；代表试稿，用户已确认 |
| 御守 | jade_warden | ward_warden.png | 成熟女护阵者、盘发、玉甲分裙、大盾 |
| 御守 | cloud_archer | ward_archer.png | 敦实男弓修、头巾、铜护臂、短复合弓 |
| 御守 | lantern_wraith | ward_lantern.png | 瘦高器修、束髻、硬挺围裙式外袍、笼式铜灯 |
| 御守 | 宗主（jade_warden） | ward_master.png | 老年锻造宗主、短灰须、方冠、礼制重甲、锻锤 |
| 丹修 | bamboo_swordsman | herbal_swordsman.png | 精干女护法、发辫、交领绿袍、药囊直剑 |
| 丹修 | frost_crane | herbal_healer.png | 温和医修、圆脸、双髻、短披肩、药葫芦 |
| 丹修 | cloud_archer | herbal_archer.png | 灵巧青年、短束发、叶形披肩、木弓箭囊 |
| 丹修 | stone_guard | herbal_guard.png | 壮实女护卫、包髻、藤木护甲、圆盾短棍 |
| 丹修 | lantern_wraith | herbal_lantern.png | 消瘦中年药师、垂髻、长直袍、莲瓣药灯 |
| 丹修 | 宗主（lantern_wraith） | herbal_master.png | 年长女宗主、银白发髻、玉冠、宽袖长袍、药杖；代表试稿，用户已确认 |

以上全是人类修士。名字仅是美术身份说明，不改存档显示名或技能。每个人固定年龄感、脸型、发型、体型、服饰、道具与站姿，不只换色。

## 2. 生图及人工确认

- 已批准模型：`gpt-image-2.6-sunburst`；本任务总上限：40 次请求，覆盖首次生成、有理由的调整和明确尺寸降级，失败请求同样占用次数。批准额度不等于批准跳过试稿确认。
- 风格为 `config/style/style.json` 的 `0.3.0`。预设只提供 `subject`，保留公共风格和 Avoid；不使用完整 prompt 覆盖。
- `assets/prompts/sect-conquest-trial.json` 三代表试稿已经用户人工确认；随后通过 `assets/prompts/sect-conquest-batch.json` 完成其余十三张，批量结果仍待用户人工审阅。
- 1024×1536 洋红底原图，保存至 `assets/masters/sect-conquest/`；透明运行图高 512px，保存至 `frontend/public/assets/art-foundation/sects/`。
- 当前 API 不支持参考图输入，master 用于保存与人工比对，不宣称身份锁定。
- 本轮历史起点 `manifest.calls` 为 `C0=84`，授权上限 `N=40`；执行前再次核对，并单独记录于 `artifacts/sect-conquest/generation-budget.json`。保留历史账本，每次启动计算 `40-(calls-84)`，`--max-attempts` 不超过剩余额度；请求串行，失败与降级均计数。累计硬上限可限定为 `124`，不使用历史剩余额度。
- 成功立即落盘；pending 下载恢复不重新生图。不使用 `--force` 或 `--retry-failed` 盲目重发。
- 按 AGENTS 最新约定，不做浏览器渲染和视觉验收；提供本地原图、透明图及审阅说明，由用户人工确认。试稿未确认前不批量、不把未生成文件接入正式配置。
- 人工审阅页为 `artifacts/sect-conquest/review.html`，按剑修、御守、丹修列出完整十六人，分别标记三代表“用户已确认”与后续十三张“待用户人工审阅”；另保留诸葛亮、关羽、嫦娥基准区。每张图以 512px 和 80px 两种高度展示同一透明图，并链接原图；全部文件已生成、处理并落盘，页面展示不构成整批视觉验收记录。

```powershell
# 仓库根目录：不产生付费调用
backend\.venv\Scripts\python.exe tools/gen_assets.py --preset sect-conquest-trial --dry-run
backend\.venv\Scripts\python.exe tools/gen_assets.py --preset sect-conquest-batch --dry-run

# 已获本轮授权，先生成三代表；任何失败先核对记录
backend\.venv\Scripts\python.exe tools/gen_assets.py --preset sect-conquest-trial --max-attempts 3

# 试稿成功后本地处理；后续批量也复用此命令
backend\.venv\Scripts\python.exe tools/normalize_assets.py --input-dir assets/raw/sect-conquest --output-dir frontend/public/assets/art-foundation/sects --portrait-height 512 --chroma-key
```

## 3. 接入与旧档保护

1. `frontend/src/presentation/assetPaths.ts` 的敌图解析优先使用战报 asset_id，空值回退原模板映射；`EnemyFigure.vue` 接收 assetId，最终 URL 变化时重置加载状态；`BattleStage.vue` 传入快照图片键。
2. 在 `frontend/tests/asset-paths.test.mjs` 验证同一战斗模板可显示不同流派与宗主图片，缺键继续显示旧图。
3. 素材完成后在 `config/sects.json` 增加弟子资产映射及宗主独立图片键；`backend/app/domain/conquest.py` 在生成时写入既有 asset_id。
4. 为旧 `state.sects` 仅替换空图片键或对应旧塔敌图片键，不覆盖自定义新图。保留身份、编成顺序、能力、奖励、驻守与征服状态，不重抽 RNG。
5. `active_run.party_snapshot` 与已保存战报完整保留；当前征讨继续用旧快照，下一次出发使用新美术。无需数据库迁移或修改契约。
6. `backend/tests/test_conquest.py` 验证新图映射、旧档仅换图、幂等更新、进行中的征讨与战报不变；`tools/validate_config.py` 与对应测试校验覆盖全部编成、独立宗主图及本地引用存在。

## 4. 定向验证与交付

- 前端：在 frontend 执行 `node --test tests/asset-paths.test.mjs tests/battle-playback.test.mjs`、`npm run build`。
- 后端修改后：在 backend 执行 `.venv\Scripts\python.exe -m pytest tests/test_conquest.py -q`。
- 配置与校验器修改后：根目录执行 `backend\.venv\Scripts\python.exe -m pytest tools/tests/test_validate_config.py -q` 和 `backend\.venv\Scripts\python.exe tools/validate_config.py`。
- 图片检查仅记录尺寸、alpha、文件存在、哈希和提示词对应，不以此替代人工风格确认。
- 记录本轮实际请求数、模型、批准情况和失败结果。只提交本轮源码、提示词、正式资产与说明；不纳入既有临时文件，不部署。
