# my_ai_town 源码复用记录

- 上游：<https://github.com/mewamew/my_ai_town>
- 固定提交：`5ddc1a37d287bbc32232ab27cbbfd59ac188ccf1`
- 日期：2026-11-17（北京时间）
- 许可及作者通知：本目录原文保存的 [LICENSE](LICENSE)、[NOTICE](NOTICE)。

| 本地文件 | 上游文件 | 使用及修改 |
|---|---|---|
| `frontend/src/rendering/hd2d/pixelSprites.ts` | `frontend/town-2d/src/map/hd2d/standee.ts`，原 `uprightDepth` 和立牌材质接入片段 | 2026-11-17 曾适配为本地 PNG 立牌的脚底深度修正，去掉上游地图单位、图集、发光贴图和全局采样依赖。2026-11-19 改为实体模型管理，原 shader、立牌材质、透明 mask 与纹理加载片段已移除，文件和本目录保留历史来源及 Required Notice。 |

2026-11-17 的建筑几何与 Canvas 像素纹理由本项目源码生成，人物当时使用本项目已有 `trial-v03` PNG；没有复制上游图片、音频、完整场景或世界模拟代码。

2026-11-19 的 `rendering/characters/cultivatorModel.ts` 及主城、战斗接入为本项目自写的实体关节模型与演出代码，使用程序几何、分层服饰和道具，没有引入上游模型或美术素材。原 PNG 继续服务名册、详情、整备及降级；保留历史 Notice 不表示当前模型使用了原立牌 shader。后续实际引入第三方素材或代码时，在此补充来源、目标路径及修改说明。

Required Notice: Copyright 2026 mewamew and contributors. https://github.com/mewamew/my_ai_town
