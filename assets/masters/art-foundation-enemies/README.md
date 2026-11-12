# 守塔群像 · 十种敌人美术

2026-11-12。沿用公共风格 `0.3.0`，模型 `gpt-image-2.6-sunburst`。本任务授权上限40次，首批2张与扩展8张共10次，全部成功，无失败、重试或尺寸降级。状态：候选接入，待用户人工审阅。

现有四种敌人（石甲灵卫、流云弓卫、玉衡守将、问道真灵）已有战斗定义，本轮只替换形象；其他六种为美术储备，尚无能力、技能、掉落或遭遇投放。

| ID / 名称 | 类型 | 原图 | 运行图 | 运行图体积 |
|---|---|---|---|---|
| `stone_guard` / 石甲灵卫 | 现有敌人 | 1024×1536，洋红底 | 450×512，RGBA | 254,917 B |
| `cloud_archer` / 流云弓卫 | 现有敌人 | 1024×1536，洋红底 | 237×512，RGBA | 129,885 B |
| `jade_warden` / 玉衡守将 | 现有敌人 | 1024×1536，洋红底 | 311×512，RGBA | 137,166 B |
| `cinder_blade` / 赤炉刀卫 | 美术储备 | 1024×1536，洋红底 | 279×512，RGBA | 150,264 B |
| `bamboo_swordsman` / 竹隐剑客 | 美术储备 | 1024×1536，洋红底 | 270×512，RGBA | 132,229 B |
| `frost_crane` / 霜羽鹤灵 | 美术储备 | 1024×1536，洋红底 | 249×512，RGBA | 81,940 B |
| `vine_spirit` / 青藤木魈 | 美术储备 | 1024×1536，洋红底 | 284×512，RGBA | 156,441 B |
| `bronze_beast` / 铜角镇兽 | 美术储备 | 1024×1536，洋红底 | 414×512，RGBA | 249,784 B |
| `lantern_wraith` / 引魂灯使 | 美术储备 | 1024×1536，洋红底 | 214×512，RGBA | 104,836 B |
| `tower_master` / 问道真灵 | 现有敌人 | 1024×1536，洋红底 | 278×512，RGBA | 194,036 B |

## 原图与运行时映射

每个 ID 对应本目录 `<id>.png` 原图；网页运行文件为 `frontend/public/assets/art-foundation/enemies/<id>.png`。完整提示、请求与落盘记录见根目录 `assets/manifest.json`，原始恢复输出在忽略目录 `assets/raw/art-foundation-enemies/`。本轮未使用图生图或参考图输入。

生成预设：

- 首批：`assets/prompts/art-foundation-enemies.json`。
- 扩展：`assets/prompts/art-foundation-enemies-expanded.json`。

生成命令会产生付费调用，已有同预设结果优先复用，不能因清理 raw 而重复付费；新任务必须有自己的模型与调用上限。

```powershell
backend\.venv\Scripts\python.exe tools/gen_assets.py --preset art-foundation-enemies-expanded --max-attempts 10
```

## 本地处理

```powershell
backend\.venv\Scripts\python.exe tools/normalize_assets.py --input-dir assets/raw/art-foundation-enemies --output-dir frontend/public/assets/art-foundation/enemies --portrait-height 512 --chroma-key
backend\.venv\Scripts\python.exe tools/prepare_art_foundation_review.py
```

处理复用 `chroma_key.key_out` 去洋红底与外部连通溢色，保留 alpha，裁边留出余量，再最近邻缩放到512px高；维持鹤、四足兽等非人形的自然比例。原图未量化或改写。若 raw 缺失，先复制 master 到对应 input-dir 后处理。

## 后续新增

复用执行指令见 `artifacts/art-foundation/ADD_ENEMY.md`；方向与审阅说明见 `DIRECTION.md` 和 `README.md`。静态对照页为 `/art-foundation.html`，联系图位于 `artifacts/art-foundation/enemy-contact-sheet.png`。

按用户要求未运行测试、类型检查、构建或浏览器检查；素材落盘不等于人工视觉验收通过。
