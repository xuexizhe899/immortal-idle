# v0.3 美术试稿

2026-11-11 生成。先完成诸葛亮、关羽、嫦娥和一张问道塔场景试稿；用户审阅后授权补齐其余 13 名弟子，现有 16 名弟子已全部统一。模型为 `gpt-image-2.6-sunburst`，采用 `config/style/style.json` 的 `0.3.0` 风格。人物要求见 `assets/prompts/trial-v03.json` 与 `assets/prompts/disciples-v03-remaining.json`；实际完整 prompt、请求尺寸、耗时及模型记录见 `assets/manifest.json`。

风格目标是与现有宗门主城一致的精细像素：青瓦与深青色、暖木与象牙白、左上方午后暖光、清楚的像素边缘和材质明暗。三名弟子分别验证文士、重甲武将与长裙人物的轮廓和细节；场景验证与主城一致的战斗空间。

## 原图与运行时映射

本目录保存服务端返回的原始图像。人物原图为洋红背景，运行时版本经抠图保留透明通道。所有路径均相对于仓库根目录。

| 文件 | 主体 | 原图尺寸 | 运行时文件 | 运行时尺寸 / 大小 |
|---|---|---|---|---|
| `zhugeliang.png` | 诸葛亮，羽扇、冠与青玉色长袍 | 1024×1536 | `frontend/public/assets/trial-v03/zhugeliang.png` | 225×512 / 164,923 B |
| `guanyu.png` | 关羽，红面长须、重甲与长刀 | 1024×1536 | `frontend/public/assets/trial-v03/guanyu.png` | 237×512 / 170,331 B |
| `change.png` | 嫦娥，月饰与象牙白、浅蓝长裙 | 1024×1536 | `frontend/public/assets/trial-v03/change.png` | 221×512 / 156,570 B |
| `scene_tower_trial.png` | 问道塔外云海平台，中央留作战斗区域 | 1536×1024 | `frontend/public/assets/trial-v03/scene_tower_trial.png` | 1536×1024 / 778,421 B |

剩余弟子使用相同文件名映射：`baisuzhen`、`dufu`、`houyi`、`huatuo`、`jingwei`、`libai`、`nezha`、`yangjian`、`yuefei`、`zhangfei`、`zhangheng`、`zhaoyun`、`zhouyu`。每个 id 对应本目录的 `<id>.png` 原图和 `frontend/public/assets/trial-v03/<id>.png` 运行时图，原图均为 1024×1536，运行时均为 512px 高、170–336px 宽的 RGBA PNG。

16 张运行时人物共 2,549,786 B，加问道塔场景共 3,328,207 B。人物采用最近邻缩放，去除洋红底并清理与外部背景连通的深紫溢色，保留服装内部暗红 / 紫色像素纹理；场景量化为 256 色 PNG，从约 2.88MB 压到约 760KiB。原始图像不经量化，继续留作修图和派生依据。

## 本地处理

生成预设会把响应立即保存在被 Git 忽略的 `assets/raw/trial-v03/`，同时复制原图到本目录。已完成且原图或 master 仍存在的项目可直接复用，不需要再次生成。只想检查 prompt 与输出计划时使用 `--dry-run`。

```powershell
.\backend\.venv\Scripts\python.exe tools/gen_assets.py --preset trial-v03 --dry-run
.\backend\.venv\Scripts\python.exe tools/normalize_assets.py --input-dir assets/raw/trial-v03 --output-dir frontend/public/assets/trial-v03 --portrait-height 512 --scene-width 1536 --scene-colors 256 --chroma-key --flat-scenes
```

如本地 raw 目录不存在，可从本目录复制 PNG 到对应 raw 目录后执行处理。联系图 `_review-full-roster.png` 仅用于本地审阅，位于忽略的 raw 目录，前缀 `_` 使处理脚本跳过它。

## 审阅与后续

本轮已检查完整身体与武器边界、人物辨识度、透明边缘、光照方向、场景中央可读空间及运行时体积。全体 16 人已完成，未继续生成其他人物或变体。哪吒保留少年比例；杨戬长武器使人物本体在 512px 画布内相对略小，可在前端展示时按角色调整缩放。

后续从本目录的角色 master 派生头像和战斗缩图，保持身份、身形比例与光照一致。新版完整宗门主城另见 `assets/masters/city-v03/README.md`。UI 图标、按钮、品质框仍由 SVG / CSS 提供。
