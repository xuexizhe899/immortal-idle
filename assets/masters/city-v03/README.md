# 完整七建筑宗门主城

2026-11-11 使用 `gpt-image-2.6-sunburst` 生成，沿用 `config/style/style.json` 的 `0.3.0` 细像素、青瓦暖木、左上暖光风格。完整 prompt 位于 `assets/prompts/city-v03-complete.json`，覆盖旧版包含额外市场 / 酒馆语义的主城 prompt。

- 原始 master：本目录 `scene_city_complete.png`，1536×1024。
- 运行时：`frontend/public/assets/city-v03/scene_city_complete.png`，1536×1024、256 色 PNG，949,924 B。
- 图中已经完整绘制藏经阁、主殿、码头、演武场、问道塔、炼器炉和炼丹房，中央保留白玉广场。前端不再叠加旧版独立建筑图，只依据实图调整点击热区。
- 主城与人物统一的命名映射见 `assets/masters/trial-v03/README.md`。

本地处理命令：

```powershell
.\backend\.venv\Scripts\python.exe tools/normalize_assets.py --input-dir assets/raw/city-v03 --output-dir frontend/public/assets/city-v03 --scene-width 1536 --scene-colors 256 --flat-scenes
```

原图不经量化，运行时压缩图用于网页加载。未生成额外主城变体。
