# T10 · 美术资产管线

> 历史任务记录：保留早期试稿与管线背景。后续人物、场景生图以 [ART_DIRECTION.md](../ART_DIRECTION.md) 为现行风格和验收规范；本文原有勾选仅描述当时交付，不证明当前脚本支持 master 图生图。

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
- [x] 16 名弟子 + 1 张场景风格统一（像素风），同一角色可复现
- [x] 产物命名为 `<asset_id>.png`，与 `config/disciples/*.json` 一一对应；白名单已删除
- [x] manifest 完整可复现；配置与存档中无生图 URL 或 base64
- [x] 断网可用：资产是本地静态文件，运行时不发起任何生图请求
- [x] 调用次数受上限控制（23/300），成本可核对

## 不做
三视图、逐角色战斗小人、AI 生成 UI 图标、运行时生图、本地模型训练。

## 注意
中转站模型版本可能变、服务可能停：靠 manifest + master 图 + style bible 保证后期追加角色仍可复现风格。

## 试稿记录（2026-11-05，5 次调用）

### 端点实测
- 文生图 `POST https://frapi.centos.hk/v1/images/generations`，Bearer 认证，OpenAI 兼容请求体
- 模型 `gpt-image-2.6-sunburst` 直接可用，不必退回 `gpt-image-2`
- **返回 `b64_json` 而非 URL**：不存在链接过期问题，但单张响应 2.3–2.9MB，必须解码后立刻落盘
- 尺寸 `1024x1536`（立绘）与 `1024x1024`（场景）均被接受；代码里的降级链（→`1024x1024`）已实现但未触发
- 耗时波动大：立绘 104–129 秒/张；场景首版 104 秒，修正 prompt 后 243 秒
- 计费按 token 计（input/output tokens），非按张；5 次调用 output 图片 token 约 162–205/张
- **`negative_prompt` 没有独立字段**，必须合进正向 prompt 的 `Avoid:` 段才生效——这是场景首版跑偏的根因

### 产出
- `assets/raw/disciple_zhugeliang.png`（1024x1536，2.6MB）
- `assets/raw/disciple_nezha.png`（1024x1536，2.5MB）
- `assets/raw/disciple_libai.png`（1024x1536，2.9MB）
- `assets/raw/scene_tower_01.png`（1024x1024，2.3MB）
- `assets/manifest.json` 记录每次调用的 model / size / prompt / bytes / elapsed / usage

### 风格结论
- `style_prompt` 有效压住了模型的写实倾向，三张立绘统一为半写实水墨淡彩、浅暖灰底、全身正面构图
- 场景必须单独写死 `scene_prompt` + `scene_avoid`：缺 `low saturation / overcast / avoid sunset` 就会跑成暖色 CG 概念图（已实测）
- 本地去重（prompt+size+model hash）有效：改场景 prompt 后重跑，3 张立绘全部跳过

### 尚未验证 / 待办
- `/v1/images/edits` 的 master 回喂与身份一致性未测
- `1536x1024` 横版场景未测
- 生成失败是否计费未测
- 产物仍在 `assets/raw/`，尚未按 `asset_id` 迁入 `frontend/public/assets/`
- 头像裁切、批量 12–20 张、移除 T01 资产白名单
