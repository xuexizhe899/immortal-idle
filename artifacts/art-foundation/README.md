# 美术前置 · 代表素材审阅

2026-11-12（北京时间）。状态：四件器物候选与十种敌人原图已制作；T19 已接入丹药与专武，T20 已接入十种敌人的战斗定义与层段编成。审阅页与游戏展示仍等待用户人工审阅；不以文件存在或生成成功代替视觉验收。

## 用途与范围

本轮制作四件器物与十种敌人外观，确定丹药、武器与敌人的轮廓、材质、光照和小尺寸可读性。十种敌人均已有战斗定义与层段编成；审阅页只检查外观与轮廓，不代替 T20 的玩法、数值或平衡验收。

`frontend/public/art-foundation.html` 是开发审阅页，不加入正式游戏导航。页面只加载本地图片，不读取存档，不请求游戏接口，也不会调用生图服务；资源未到位或加载失败时直接标记“缺图 · 待素材”。

## 查看方式

在现有 Vite 服务的同一地址打开 `/art-foundation.html`。例如原游戏地址是 `http://localhost:5173/`，审阅页就是 `http://localhost:5173/art-foundation.html`；若服务使用其他端口，沿用实际端口。无需新建存档或进入战斗。

也可直接打开 `frontend/public/art-foundation.html`，页面不使用 `fetch` 或模块导入。游戏内的背景融合、弹窗布局与战斗遮挡仍需要在实际页面人工查看。

## 素材映射

| 对象 | 小图 / 运行图 | 展示图 | 审阅尺寸 |
|---|---|---|---|
| 疗伤丹 | `frontend/public/assets/art-foundation/items/liao_shang_dan.svg` | 同目录 `liao_shang_dan_display.svg` | 24 / 32 / 48 / 144px |
| 破境丹 | `frontend/public/assets/art-foundation/items/po_jing_dan.svg` | 同目录 `po_jing_dan_display.svg` | 24 / 32 / 48 / 144px |
| 青锋剑 | `frontend/public/assets/art-foundation/items/qing_feng_jian.svg` | 同目录 `qing_feng_jian_display.svg` | 24 / 32 / 48 / 144px |
| 关羽专武外观概念 | `frontend/public/assets/art-foundation/items/guanyu_signature.svg` | 同目录 `guanyu_signature_display.svg` | 24 / 32 / 48 / 144px |
| 石甲灵卫 | `frontend/public/assets/art-foundation/enemies/stone_guard.png` | 同一透明 PNG | 80 / 94 / 112 / 192px |
| 流云弓卫 | `frontend/public/assets/art-foundation/enemies/cloud_archer.png` | 同一透明 PNG | 80 / 94 / 112 / 192px |
| 玉衡守将 | `frontend/public/assets/art-foundation/enemies/jade_warden.png` | 同一透明 PNG | 80 / 94 / 112 / 192px |
| 赤炉刀卫（T20 已接入） | `frontend/public/assets/art-foundation/enemies/cinder_blade.png` | 同一透明 PNG | 80 / 94 / 112 / 192px |
| 竹隐剑客（T20 已接入） | `frontend/public/assets/art-foundation/enemies/bamboo_swordsman.png` | 同一透明 PNG | 80 / 94 / 112 / 192px |
| 霜羽鹤灵（T20 已接入） | `frontend/public/assets/art-foundation/enemies/frost_crane.png` | 同一透明 PNG | 80 / 94 / 112 / 192px |
| 青藤木魈（T20 已接入） | `frontend/public/assets/art-foundation/enemies/vine_spirit.png` | 同一透明 PNG | 80 / 94 / 112 / 192px |
| 铜角镇兽（T20 已接入） | `frontend/public/assets/art-foundation/enemies/bronze_beast.png` | 同一透明 PNG | 80 / 94 / 112 / 192px |
| 引魂灯使（T20 已接入） | `frontend/public/assets/art-foundation/enemies/lantern_wraith.png` | 同一透明 PNG | 80 / 94 / 112 / 192px |
| 问道真灵 | `frontend/public/assets/art-foundation/enemies/tower_master.png` | 同一透明 PNG | 80 / 94 / 112 / 192px |

前三件道具保留原 `frontend/public/assets/items/` 版本作对照。关羽专武外观概念仅用于讨论偃月刀造型与人物关联；T19 已另行实现专武获取、装备与加成，本页不承担玩法验收。本页不编造稀有度、掉落与数值。

现有敌人为石甲灵卫、流云弓卫、玉衡守将与问道真灵；赤炉刀卫、竹隐剑客、霜羽鹤灵、青藤木魈、铜角镇兽与引魂灯使已在 T20 接入战斗。素材的装甲、武器或灯具描述不能视为额外技能承诺，具体技能与目标规则以 `config/enemies/` 为准。

## 制作与生成记录

- 本地物品绘图源码：`tools/generate_art_foundation_items.py`；大小图分别组织细节，不依赖位图嵌入 SVG。
- 敌人提示预设：首批 `assets/prompts/art-foundation-enemies.json`，扩展批 `assets/prompts/art-foundation-enemies-expanded.json`；原图保存到 `assets/masters/art-foundation-enemies/`，完整调用记录见 `assets/manifest.json`。
- 敌人模型：`gpt-image-2.6-sunburst`；用户授权本任务最多 40 次调用。实际累计 10 次：首批 2 次、扩展批 8 次，全部成功，无重试或尺寸降级。历史 manifest 累计值为 58 → 68，不作为后续任务额度。
- 图片生成与本地处理不等于人工批准。未审阅的素材保持“待人工审阅”，不把保存 master 描述为已实现参考图锁定。

## 用户人工检查清单

- [ ] 小图不读名字，能区分两种丹药、普通剑与关羽专武；区别不只依赖颜色。
- [ ] 丹药容器、封口与丹纹在各尺寸下有层次；武器刃、脊、护手和柄结构合理。
- [ ] 144px 展示图有明确材质，细节没有变成随机装饰或平滑插画效果。
- [ ] 四种现有敌人与六种储备外观有可辨认轮廓；石甲灵卫显得厚重，问道真灵有清楚的首领身份。
- [ ] 80 / 94 / 112px 下人形的头、武器和姿态，以及鹤灵、木魈、镇兽的体型仍清楚，非人形没有被强行拉伸成人物比例。
- [ ] 素材边缘完整，透明底无洋红残留，脚底与视觉重心稳定，光照和现有人物相符。
- [ ] 浅底与深底均可读，没有依赖背景掩盖的杂边或过暗区域。
- [ ] 桌面和 390px 宽度下审阅页可查看全部尺寸，长文字与图片不推动整个页面横向溢出。
- [ ] 实际炼制页、战斗页中的大小、裁切、血条/技能遮挡与缺图回退由用户另行查看。

本轮按用户指令不运行测试、类型检查、构建或浏览器渲染检查。本清单未勾选，不表示已经通过。

## 本轮制作记录

- 模型 `gpt-image-2.6-sunburst`；用户授权上限 40 次，首批 2 张加扩展批 8 张，实际新增 10 次（历史累计 58 → 68），全部成功，没有重试或尺寸降级。
- 十张原图已保存在 `assets/masters/art-foundation-enemies/`。运行图采用本地抠图与最近邻缩放，高 512px；未调用图生图。
- 三件既有物品接入新 SVG；关羽专武只在本页作为外观概念。四种现有敌人使用候选 PNG，加载前和失败后保留原 SVG；六种美术储备仅在本页展示，未加入战斗配置或关卡。
- 炼制详情展示 128px；战斗容器桌面 112px、手机 94px。
- 方向、资源边界与人工审阅标准见 [DIRECTION.md](DIRECTION.md)。
- 按用户要求未运行测试、类型检查、构建或浏览器渲染检查，未提交、推送或部署。

## 联系图与文件指纹

- [道具联系图](item-contact-sheet.svg)：四件展示图的矢量拼版。
- [敌人联系图](enemy-contact-sheet.png)：透明 PNG 的浅底拼版，不是游戏截图。
- [素材清单](assets.json)：运行图与 master 的路径、尺寸、体积和 SHA-256；状态为待人工审阅。
- 可用以下本地制作命令重新整理联系图，不产生生图调用：

```powershell
backend\.venv\Scripts\python.exe tools/prepare_art_foundation_review.py
```
