# my_ai_town 源码复用记录

- 上游：<https://github.com/mewamew/my_ai_town>
- 固定提交：`5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1`
- 日期：2026-11-17（北京时间）
- 许可及作者通知：本目录原文保存的 [LICENSE](LICENSE)、[NOTICE](NOTICE)。

| 本地文件 | 上游文件 | 使用及修改 |
|---|---|---|
| `frontend/src/rendering/hd2d/pixelSprites.ts` | `frontend/town-2d/src/map/hd2d/standee.ts`，`uprightDepth` 和立牌材质接入片段 | 改作脚底深度修正：保持像素人物朝向固定相机，并按脚底的直立位置计算遮挡。去掉上游地图单位、图集、发光贴图和全局采样依赖，适配现有本地人物 PNG 与固定高度。 |

本轮建筑几何与 Canvas 像素纹理由本项目源码生成，人物继续使用本项目已有 `trial-v03` 资源。没有复制上游图片、音频、完整场景或世界模拟代码；音乐接入与战斗 HD-2D 仍在后续范围。后续实际引入素材时，在此补充源路径、目标路径及修改说明。

Required Notice: Copyright 2026 mewamew and contributors. https://github.com/mewamew/my_ai_town
