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
- [ ] 合法配置全部通过
- [ ] 四类悬空引用分别能被检出，且报错含文件路径与字段名
- [ ] 缺少资产文件时给出待生成清单，而非静默通过
- [ ] 校验在 CI 中执行，失败可阻断合并

## 不做
写完整内容包（T08/T09）、数据库表、生图。

## 注意
资产白名单只是过渡手段，T10 完成后应移除；不要让"跳过校验"变成永久豁免。
