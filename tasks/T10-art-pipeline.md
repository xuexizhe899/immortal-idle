# T10 · 美术资产管线

- 里程碑：M3（建议 T00 后立即启动试稿，与开发并行）｜ 依赖：T01 ｜ 对应文档：DESIGN.md 第 8 节

## 目标
用云端生图 API 在开发期批量产出全部静态资产，运行时零依赖、断网可玩。

## 前置阻塞
两枚 API 密钥曾在对话中明文出现，**先作废轮换**；新 key 只放本地 `.env`，不进仓库、不写进任何文档。

## 已锁定决策
1. **不做三视图**；只出正面全身立绘，头像裁切、战斗小人用统一模板、UI 图标用 SVG
2. 主力 `https://frapi.centos.hk/v1/images/generations`（图生图 `/v1/images/edits`），模型 `gpt-image-2.6-sunburst`；备选 `image.mlgb7.com` / `gpt-image-2.5`
3. 开发期一次性批量生成，**运行时绝不调 API**；本机不装 ComfyUI / SD / 生图 venv
4. 先定 style bible，再逐角色出 master 立绘，派生图经 edits 回喂锁身份
5. 生成成功后**立即落盘**，绝不把 URL 写进配置、存档或 Git
6. 脚本本地去重（prompt + 参数 + style 版本 hash）；产物按 `asset_id` 命名归档
7. 每次调用的模型名、prompt、参数、文件名写入 `assets/manifest.json` 并进 Git

## 要做的事
1. 写 `config/style/`：固定 style prompt + 1–2 张风格参考图
2. 试稿：3 张立绘 + 1 张场景，实测并记录
   - 可用模型名（`gpt-image-2.6-sunburst` 与示例里的 `gpt-image-2` 不一致，分别打最小请求）
   - 尺寸上限、图片 URL 有效期、计费与失败是否扣费、`edits` 参数格式
   - 旧端点的 1K / 1800s / `X-Request-Id` 规格**不可继承**
3. `tools/gen_assets.py`：批量生成、立即下载、本地去重、失败重试、manifest 记录、总调用上限（如 300 次）
4. 逐角色出 master 立绘并人工批准，再批量产出 12–20 立绘 + 6–10 场景图
5. 头像裁切、按 `asset_id` 命名放入 `frontend/public/assets/`，移除 T01 的资产白名单

## 产出物
- style bible、`gen_assets.py`、`assets/manifest.json`、`assets/masters/`、全部成品 PNG

## 验收
- [ ] 立绘与场景风格统一，同一角色派生图身份一致
- [ ] 产物命名与 `config/disciples/*.json` 的 `asset_id` 一一对应，T01 校验不再需要白名单
- [ ] manifest 完整可复现；配置与存档中无任何生图 URL 或 base64
- [ ] 断网状态下游戏资产完整可用；运行时不发起任何生图请求
- [ ] 调用次数受上限控制，成本可核对

## 不做
三视图、逐角色战斗小人、AI 生成 UI 图标、运行时生图、本地模型训练。

## 注意
中转站模型版本可能变、服务可能停：靠 manifest + master 图 + style bible 保证后期追加角色仍可复现风格。
