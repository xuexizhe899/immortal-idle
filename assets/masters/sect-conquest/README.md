# 外宗人物 · 十六张立绘

2026-11-14。13 名弟子和 3 位宗主已生成并接入宗门预览、擂台和宗主战。剑修、御守、丹修各有自己的弟子造型和独立宗主，三级九座宗门按流派复用。模型 `gpt-image-2.6-sunburst`，公共风格 `0.3.0`。

用户确认三代表后才执行其余十三张。授权最多 40 次请求，实际使用 **16 次**，全部成功，无失败、重试或尺寸降级，剩余 24 次。manifest 累计由 84 增至 100，累计硬上限为 124；历史账本未清零。任务额度见 `artifacts/sect-conquest/generation-budget.json`，完整提示与脱敏生成记录见 `assets/manifest.json`。

所有原图均为 1024×1536 RGB，原样保存在本目录；运行图为高 512px 的透明 RGBA PNG。

| 人物 / 文件名 | 运行尺寸 | 体积 | 视觉状态 |
|---|---|---|---|
| 剑修持剑弟子 `sword_swordsman` | 250×512 | 117229 B | 试稿用户已确认 |
| 剑修刀修弟子 `sword_saber` | 284×512 | 166423 B | 待用户人工审阅 |
| 剑修女弓修 `sword_archer` | 221×512 | 116125 B | 待用户人工审阅 |
| 剑修护卫 `sword_guard` | 307×512 | 150133 B | 待用户人工审阅 |
| 剑宗宗主 `sword_master` | 314×512 | 150376 B | 待用户人工审阅 |
| 御守重甲弟子 `ward_guard` | 348×512 | 167132 B | 试稿用户已确认 |
| 御守女护阵者 `ward_warden` | 241×512 | 161509 B | 待用户人工审阅 |
| 御守男弓修 `ward_archer` | 301×512 | 162813 B | 待用户人工审阅 |
| 御守持灯器修 `ward_lantern` | 198×512 | 118707 B | 待用户人工审阅 |
| 器宗宗主 `ward_master` | 330×512 | 183831 B | 待用户人工审阅 |
| 丹修女护法 `herbal_swordsman` | 236×512 | 116362 B | 待用户人工审阅 |
| 丹修医修 `herbal_healer` | 183×512 | 112666 B | 待用户人工审阅 |
| 丹修弓修 `herbal_archer` | 235×512 | 123967 B | 待用户人工审阅 |
| 丹修女护卫 `herbal_guard` | 272×512 | 159891 B | 待用户人工审阅 |
| 丹修持灯药师 `herbal_lantern` | 206×512 | 115692 B | 待用户人工审阅 |
| 丹宗女宗主 `herbal_master` | 221×512 | 165128 B | 试稿用户已确认 |

## 文件与接入

- 原图 / master：本目录 `<文件名>.png`；恢复缓存：`assets/raw/sect-conquest/`。
- 正式运行图：`frontend/public/assets/art-foundation/sects/<文件名>.png`，总计 2,287,984 B。
- 预设：`assets/prompts/sect-conquest-trial.json` 三张，`sect-conquest-batch.json` 十三张；仅通过 subject 继承公共风格和反向约束。
- 配置：`config/sects.json` 的 disciple_assets / leader_asset_id；服务端写入 BattleUnit.asset_id，真实战报携带该键，前端统一解析本地路径。
- 旧宗门只替换空图或对应塔敌旧图，自定义图保持；进行中的征讨与历史战报保留固定快照，下次出发使用新图。
- 审阅页：`artifacts/sect-conquest/review.html`，16 人与三张现有基准，提供 512px／80px 对照及原图链接。

当前 API 只有文生图，没有参考图输入；保存 master 不等于图生图身份锁定。整个页面运行时不调用生图 API。

## 实际生成和本地处理

```powershell
backend\.venv\Scripts\python.exe -u tools/gen_assets.py --preset sect-conquest-trial --max-attempts 3
backend\.venv\Scripts\python.exe -u tools/gen_assets.py --preset sect-conquest-batch --max-attempts 13
backend\.venv\Scripts\python.exe tools/normalize_assets.py --input-dir assets/raw/sect-conquest --output-dir frontend/public/assets/art-foundation/sects --portrait-height 512 --chroma-key
```

沿用现有洋红去底、裁切与最近邻缩放，master 保持原样。PNG 解码、尺寸、非空透明通道、raw/master 一致性、完整配置引用和审阅页本地链接均已检查，三张已确认试稿的 SHA-256 未变。详细文件指纹见 `artifacts/sect-conquest/asset-checks.json`。未进行浏览器或整批视觉验收，新增十三张及实际页面效果由用户人工确认。

再次执行同预设时先 dry-run，已有相同结果会复用；不使用 force 绕过去重，不因 raw 缺失重复付费。后续新任务须另有自己的模型与调用上限。
