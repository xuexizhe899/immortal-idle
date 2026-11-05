# T01 · 配置 schema 与悬空引用校验

- 里程碑：M0 ｜ 依赖：T00 ｜ 对应文档：DESIGN.md 第 3、4.1 节

## 目标
静态内容全部走 `config/*.json`，并有一个能在 CI 里强制执行的引用完整性校验器。

## 已锁定决策
1. 配置按实体拆文件：每个弟子一个 JSON，词条/配方/材料/敌人/事件/羁绊/模式分目录
2. 配置进 Git、不进数据库；运行期只读
3. **任何悬空引用都必须让 CI 失败**，错误信息要指到具体文件与字段
4. 三种出征模式只是配置不同：`modes/tower.json`、`expedition.json`、`invasion.json`

## 要做的事
1. 定义 schema：disciple（见下）、affix、recipe、material、enemy、event、bond、mode
2. `config/disciples/zhugeliang.json` 作为样板，字段含 `id/name/origin/rarity/lean/asset_id/base_stats/skill/passive/bonds`
3. `tools/validate_config.py`：
   - JSON 语法与必填字段校验
   - `skill.id` 必须存在于技能表
   - `bonds[*]` 必须存在于 `config/bonds/`
   - `lean` 只能是 `attack/defense/support/craft` 之一
   - `asset_id` 必须对应 `frontend/public/assets/` 下的文件（资产未生成时允许白名单跳过，但要打印清单）
   - mode 配置里的敌人表、奖励表、词条权重引用的 ID 必须存在
4. 在 CI 中接入；故意制造一个坏引用验证会失败，再修复

## 产出物
- `config/` 全目录与样板文件、`tools/validate_config.py`、schema 说明

## 验收
- [x] 合法配置全部通过（skills=6, disciples=3, modes=1）
- [x] 四类悬空引用分别能被检出，报错含文件路径与字段名（skill / bond / asset / mode pool 均有单测）
- [x] 缺少资产时逐个报出缺失路径，不静默通过
- [x] 校验在 CI 中执行（config job：validate + validator 单测），失败可阻断合并

## 不做
写完整内容包（T08/T09）、数据库表、生图。

## 注意
资产白名单只是过渡手段，T10 完成后应移除；不要让"跳过校验"变成永久豁免。

## 执行记录（2026-11-05）
- 新增 `config/skills/`：弟子通过字符串 `skill` / `passive` 引用技能表，避免内联重复；DESIGN 4.1 示例已同步
- 样板内容：6 个技能、3 个弟子（诸葛亮 / 哪吒 / 李白，对应试稿资产）、1 个模式占位 `modes/tower.json`；bonds / 材料 / 配方 / 敌人 / 事件暂空
- 校验 9 类集合：id 与文件名一致、枚举、base_stats 正数、skill 类型匹配、bonds 成员引用、asset_id 对应 PNG、配方材料引用、模式池引用
- 校验器 11 个单测（`tools/tests/test_validate_config.py`），CI config job 增加 pytest 步骤
- 按用户开发准则重写：372 行 → 277 行，删掉 9 个单次调用函数、重复的字段存在性检查、路径相对化的 try/except；每个函数带 docstring
- 已知余量：materials / recipes / 模式池三块当前无数据，属提前实现，可再删约 60 行，等 T09 有内容时再加回
