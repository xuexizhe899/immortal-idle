# T23/T24 与远行码头实施计划

状态：代码与样板已实现，实际验收记录见 `docs/reviews/2026-11-14-t22-t24-delivery.md`；视觉与人工体验待用户确认。

**Goal:** 在完成 T22 选路收尾后，把战斗复盘信息和公共视觉基准落到现有流程，并开放一个可验证的远行码头远征闭环。

**Architecture:** 远征复用现有 `ActiveRun`、服务端自动战斗、确定性 RNG、CAS 存档和 `RunView`，通过出征模式参数选择固化的模式配置；不复制第二套战斗状态机。远征单独记录最高完成节点，节点、奖励和敌人仍由服务端生成并保存，前端只展示真实快照。T23 复用现有 `last_battle` 与宗门目标入口，补充可持久化的最近出征摘要前先确认结算边界；T24 只调整公共样式，交付宗门总览和丹药/专武详情两种独立开发样板。

**Tech Stack:** Python 3.11、FastAPI、Pydantic v2、SQLite JSON 存档、Vue 3、TypeScript、Vite、现有 SVG/CSS 资产。

---

### Task 1: 收尾 T22 的配置与契约

**Files:**
- Modify: `config/modes/tower.json`
- Modify: `tools/validate_config.py`
- Test: `tools/tests/test_validate_config.py`
- Verify: `backend/tests/test_t22_routes.py`, `backend/tests/test_t22_api.py`

**Steps:**

1. 为塔模式写入奖励缩放上下限，并让配置校验拒绝缺字段、非有限数和逆序范围。
2. 增加合法、缺字段和越界回归测试。
3. 执行 T22 后端、工具、配置、RNG 检查；重新导出 OpenAPI 并生成前端类型。
4. 运行前端相关测试和构建，更新 T22 任务卡的实际验收状态与限制。

### Task 2: 参数化远行码头的服务端出征

**Files:**
- Modify: `config/modes/expedition.json`
- Modify: `backend/app/models/save.py`
- Modify: `backend/app/models/api.py`
- Modify: `backend/app/api/run.py`
- Modify: `backend/app/api/catalog.py`
- Modify: `backend/app/domain/run_engine.py`
- Modify: `tools/validate_config.py`
- Test: `backend/tests/test_expedition_api.py`

**Steps:**

1. 定义 12 节点、末节点首领、普通/精英路线、材料偏重奖励和 2 点行动力成本；只引用已有敌人、材料和规则。
2. 为 `GameState` 增加独立 `expedition_floor`，为启动请求增加受限模式枚举，默认仍为问道塔；服务端拒绝未开放模式和未知模式。
3. 让结算按 `run.mode` 复用快照配置，并分别更新塔/远征最高完成节点；不改变已有塔 API 默认行为。
4. 目录接口同时返回已开放模式的简化配置，前端不读取未开放模式。
5. 用临时 SQLite 覆盖远征启动、候选固定、配置变更后仍按快照战斗、结算进度、旧档默认字段和 CAS 重放。

### Task 3: 远行码头前端闭环

**Files:**
- Create: `frontend/src/views/ExpeditionPanel.vue`
- Modify: `frontend/src/views/CityView.vue`
- Modify: `frontend/src/stores/game.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/views/RunView.vue`
- Modify: `frontend/src/components/game/CityDock.vue`
- Test: `frontend/tests/expedition.test.mjs`

**Steps:**

1. 在码头面板展示远征规则、最高节点、行动力成本、队伍选择和互斥/伤势提示。
2. 让启动命令带模式，复用同一出征页面；运行中显示当前模式、节点总数和真实路线奖励。
3. 主城建筑和底栏显示“远征/码头”真实状态；未开放的入侵继续保持占位。
4. 测试模式参数传递、远征文案和没有活动远征时的空状态；执行类型检查和构建。

### Task 4: T23 失败复盘与目标回流

**Files:**
- Modify: `backend/app/models/save.py`, `backend/app/domain/run_engine.py`, `backend/app/api/run.py`
- Modify: `frontend/src/stores/game.ts`, `frontend/src/views/SectPanel.vue`, `frontend/src/views/RunView.vue`
- Test: `backend/tests/test_run_review.py`, `frontend/tests/expedition.test.mjs`
- Update: `tasks/T23-battle-review-and-growth-goals.md`, `artifacts/t23/review-and-goals.md`

**Steps:**

1. 只保存最近一次已结算出征的真实摘要（终止原因、到达节点、关键战报指标和实际战利品），不复制战斗判定。
2. 在宗门总览和出征结束页给出下一步可执行入口，复用培养、炼丹、炼器和阵容调整接口；不加入新货币、任务系统或胜率预测。
3. 用专用状态覆盖胜利、失败、回合耗尽、刷新恢复和摘要不被新存档覆盖的边界。

### Task 5: T24 公共视觉基准样板

**Files:**
- Create: `artifacts/t24/visual-baseline.md`
- Modify: `frontend/src/style.css`, `frontend/src/components/ui/PanelModal.vue`, `frontend/src/components/ui/NoticeBubble.vue`
- Create: `artifacts/t24/preview.html`
- Verify: 资源引用、差异检查与前端构建；不为 CSS 细节新增静态镜像测试

**Steps:**

1. 根据真实页面和现有资产记录保留、修整、补制清单，固定细像素修仙的颜色、边框、间距、文字和气泡反馈规则。
2. 将公共样式和弹窗/提示气泡的可读性落地到两种代表样板：宗门总览与丹药/专武高密度详情。
3. 只做桌面和 390px 的静态结构检查与构建；浏览器视觉由用户人工验收，交付中明确未验收项。

每个任务完成后只暂存属于该任务的文件，先通过受影响验证，再提交；部署和推送等外部动作另行遵循用户明确指令。
