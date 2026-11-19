# 游戏页面鲜活度优化实现记录

日期：2026-11-19。目标：深度优化现有游戏页面，让真实人物、经营与历练状态更鲜明，同时保留上一轮解决长页面的交互。

方案见[页面鲜活度优化](../plans/2026-11-19-living-ui.md)。本记录区分代码实现、自动检查、人工体验与部署，不将构建通过视为视觉验收。

## 实现范围

| 页面与入口 | 代码改动 | 保留的行为 |
|---|---|---|
| 公共主题、弹窗、主城与底栏 | `style.css`、`App.vue`、`PanelModal.vue`、`CityView.vue`、`CityDock.vue`：青玉与木刻层次、真实资源快照反馈、时产、当前存档状态和天色标识 | 主城渲染器、资源与收益权威、底栏入口、嵌套弹窗焦点、Escape、滚动锁 |
| 弟子堂、招贤与详情 | `CodexPanel.vue`、`DiscipleCard.vue`：名册、立绘框、身份与状态签；编队默认收起，摘要显示当前人数 | 显式打开详情、左右切换、筛选、招募、编队调整与原锁定条件 |
| 个人培养、装备与道法 | `DiscipleTraining.vue`、`DiscipleEquipment.vue`、`SkillDetails.vue`：真实境界进度、四槽器物、主动与被动印记 | 原培养成本、换装、专武、预览、加载与只读行为 |
| 主殿、设施、挂机与值守 | `SectPanel.vue`、`FacilitiesSection.vue`、`DutyPanel.vue`：门务摘要、真实设施等级与备料、岗位和产出识别 | 六个独立栏目、后台累计收益、岗位安排、同步锁与材料跳转 |
| 炼丹、炼器、装备与材料 | `CraftPanel.vue`、`EquipmentPanel.vue`、`MaterialSources.vue`：丹房与器阁区别、配方效果与可炼数量、穿戴摘要、材料图标与可前往筛选 | 原数量和品级参数、强化洗练、锁定熔炼确认、精确来源目标；筛选只属于本地界面，切档清空 |
| 存档 | `SaveSlotsPanel.vue`：当前档印记、摘要、长名称排版 | 新建与导入默认折叠、原切档和风险确认 |
| 山河与宗门征讨 | `WorldPanel.vue`、`ExpeditionPanel.vue`、`ConquestRun.vue`：静态地形纹样、节点形状与图例、真实地区完成计数与战册页头 | 地图局部滚动、原坐标与图层、精确宗门目标、驻守和论道、主要行动在战场前 |
| 问道整备与路线历练 | `PreparePanel.vue`、`RunView.vue`、`PartyStrip.vue`、`PartyHealing.vue`：队伍立绘和状态、整备刻线、结算前置、当前逐人气血 | 路线和道法弹窗、战场下方记录页签、真实战报、原操作参数、疗伤及出发限制 |

没有修改后端、接口、存档结构、玩法数值、依赖或正式美术图片；没有调用生图、接触真实存档或部署服务器。

## 审查后修正

- 消费请求结果不确定且恢复查询失败时，关闭错误气泡不代表已确认新状态。空闲提示改用“存档已载入”，避免把旧快照称作“进度已同步”。窄屏保留存档名与状态，只隐藏行程说明。
- 弟子编队使用原生默认折叠的 `details`，保留换位与调整入口，减少名册前的固定占高；摘要保留键盘操作与可见焦点。
- 领悟气血道法会改变本局气血，出发快照的 `health` 不能作为当前逐人上限。逐人只展示后台记录的当前气血，队伍总气血仍展示真实 `hp / max_hp`，移除失真的逐人分母和血条。
- 装备筛选保持至少 44px 点击高度；新开启动画和资源反馈尊重减少动态效果偏好。

## 本次自动检查

在 `frontend` 目录执行：

```powershell
node --test --test-reporter=spec tests/city-scene.test.mjs tests/page-interaction.test.mjs tests/disciple-dialog.test.mjs tests/craft-dialog.test.mjs tests/sect-panel-navigation.test.mjs tests/sect-management.test.mjs tests/duty-expedition-navigation.test.mjs tests/equipment.test.mjs tests/world-dialog.test.mjs tests/world-navigation.test.mjs tests/run-dialog.test.mjs tests/expedition.test.mjs tests/goal-chain.test.mjs tests/idle-record.test.mjs tests/ui-shell.test.mjs
npm run build
```

- 15 个相关测试文件：**105 / 105 通过，退出 0**。覆盖弟子切换、嵌套弹窗、经营分栏、材料筛选与切档重置、存档操作、地图入口、战斗决策、只读与 busy 限制、挂机记录和不确定请求状态文案。
- 新气血回归先复现“107 / 100”，修正后 `run-dialog.test.mjs` 的 **12 / 12 通过**；断言真实逐人气血、总气血、不出现错误分母或逐人比例条，且不改写存档与战利品。
- 最终窄屏样式调整后，`npm run build`（`vue-tsc -b` 与 Vite 构建）**退出 0**，136 个模块构建完成。主城动态分包 554.04 kB，仍有超过 500 kB 的非阻塞提示，本轮未扩展到分包重构。
- 仓库根目录执行 `git diff --check` **退出 0**，无空白错误。未运行后端、工具或无关全量测试；没有接口改动，未重新生成契约。

## 人工待验收与已知限制

按仓库约定没有运行浏览器、渲染截图或视觉验收。请在桌面与 390px 宽度人工确认：

1. 资源栏与长存档名、存档状态是否清楚且不挤占主城；底栏和主要行动是否始终便于触达。
2. 弟子名册、默认收起的编队、四槽装备、培养进度及左右切换是否顺手；嵌套弹窗返回与键盘焦点是否符合预期。
3. 主殿、值守、丹房、器阁的栏目层次、长名称、材料筛选和空态入口是否清楚。
4. 地图局部滚动与节点识别、路线弹窗、战利品页签、交锋后结算入口是否易用。
5. 加载、失败、处理中与减少动态效果偏好下是否有遮挡、闪烁或文案误导。

只读审查另外发现存量问题：第二地区从独立问道塔入口开启一阶塔时，`RunView.vue` 的最高记录仍可能读取第一地区的 `tower_floor`，而 `PreparePanel.vue` 已按地区读取。这不是本轮新改动，未扩大范围修复，后续应单独校正并补回归。

本轮代码提交与推送不代表已部署，也不代表用户已确认画风或操作体验。
