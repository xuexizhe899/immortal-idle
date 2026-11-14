# 外宗人物立绘交付记录

2026-11-14。外宗 13 名弟子与 3 位宗主的图片、配置和战斗展示接入已完成。三张代表试稿经用户确认后才执行其余十三张；新增十三张和实际页面效果仍待用户人工视觉检查。

## 实现结果

- 剑修：4 名弟子、1 位宗主；御守：4 名弟子、1 位宗主；丹修：5 名弟子、1 位宗主。三级开放的九座宗门按流派复用，共 16 张独立人类修士立绘。
- `config/sects.json` 增加弟子模板到图片键的映射及独立宗主图片键；原编成、属性、技能、奖励、材料和随机顺序保持。
- `backend/app/domain/conquest.py` 生成时写入图片键；旧宗门仅替换空键或对应塔敌旧键，保留自定义图片和其他状态。正常入档结算沿既有 CAS 保存，正在进行的征讨与已有战报保留出发时快照。
- `BattleStage.vue` 传递真实战报的 asset_id；`EnemyFigure.vue` 在最终 URL 变化时重置加载状态，缺值沿用旧模板图，加载失败保留占位。宗门预览和征讨面板沿用既有图片解析。
- `tools/validate_config.py` 检查流派映射完整、宗主图独立、安全相对路径和本地 PNG 存在。无需新增存档字段、接口契约或数据库迁移。

## 资产与费用

- 模型：`gpt-image-2.6-sunburst`，公共风格 `0.3.0`。用户授权最多 40 次，实际 **16 次**，全部成功，失败 / 重试 / 尺寸降级均为 0，剩余 24 次。
- manifest 历史起点 84，最终 100；累计硬上限 124。`.env` 仅本地更新累计预算，密钥未写入产物或提交。
- 原图：`assets/masters/sect-conquest/`，均为 1024×1536 RGB，合计 25,281,286 B。
- 运行图：`frontend/public/assets/art-foundation/sects/`，均为高 512px 的透明 RGBA PNG，合计 2,287,984 B。
- 提示词：`assets/prompts/sect-conquest-trial.json` 与 `sect-conquest-batch.json`；完整发送内容在 `assets/manifest.json`。当前 API 无参考图输入，master 仅用于保存、恢复及人工比对。
- 人工审阅页：`artifacts/sect-conquest/review.html`，提供全部 16 人与三张现有基准的 512px / 80px 对照和原图链接。
- 任务账本：`artifacts/sect-conquest/generation-budget.json`；尺寸、alpha 与 SHA-256：同目录 `asset-checks.json`。三张用户已确认的试稿文件指纹保持不变。

## 本次实际验证

| 检查 | 结果 |
|---|---|
| backend 目录 `.venv\Scripts\python.exe -m pytest tests/test_conquest.py -q` | 17 通过，覆盖三级九宗正式映射、旧档仅换图、幂等更新和本局后续战报不变 |
| 根目录 `backend\.venv\Scripts\python.exe -m pytest tools/tests/test_validate_config.py -q` | 95 通过；仅既有 pytest_asyncio fixture loop scope 弃用提示 |
| frontend 目录 `node --test tests/asset-paths.test.mjs tests/battle-playback.test.mjs` | 13 通过，覆盖快照图片优先级与播放数据保持 |
| 根目录 `backend\.venv\Scripts\python.exe tools/validate_config.py` | 正式配置及全部图片引用通过 |
| 根目录 `backend\.venv\Scripts\python.exe tools/check_rng_usage.py` | 通过 |
| frontend 目录 `npm run build` | TypeScript 检查与 Vite 构建通过 |
| PNG / 引用检查 | 16 张可解码、原图与 raw 内容一致、运行图高 512px 且 alpha 非空、正式配置精确覆盖、审阅页 57 条本地图片 / 原图引用存在；无 pending 下载 |
| `git diff --check` | 通过 |

准备阶段先以新增测试复现两项后端和两项前端失败，再完成修复；上表为正式配置接入后本轮实际结果。未做全量回归、浏览器渲染或整批视觉验收，未操作用户真实存档。

生成和处理命令：

```powershell
backend\.venv\Scripts\python.exe -u tools/gen_assets.py --preset sect-conquest-trial --max-attempts 3
backend\.venv\Scripts\python.exe -u tools/gen_assets.py --preset sect-conquest-batch --max-attempts 13
backend\.venv\Scripts\python.exe tools/normalize_assets.py --input-dir assets/raw/sect-conquest --output-dir frontend/public/assets/art-foundation/sects --portrait-height 512 --chroma-key
```

## 提交与后续检查

本轮变更单独提交，保留开始时的无关未跟踪文件。当前 main 在本轮前已有 9 笔未推送提交；本轮提交保存在本地，未推送、未部署。人物内容与游戏内裁切由用户人工确认；已有进行中的征讨暂用旧图，结束后下次出发使用新图。
