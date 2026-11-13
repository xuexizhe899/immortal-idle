# 开发工具与测量口径

`tools/` 放离线内容制作、配置校验、契约辅助及测量脚本；`tools/tests/` 放这些工具的回归测试。工具不作为游戏运行时状态来源。目录和依赖边界见根目录 `ARCHITECTURE.md`。

## 战斗测量

`measure_battles.py` 在内存中建立固定阵容、培养、投入、种子与策略，调用正式服务端战斗及出征逻辑；不连接数据库、不读取真实存档。`--suite t17/t18/t19/t20` 指定样本矩阵，**不切换到历史版本的代码**。在当前工作区运行 `--suite t20`，结果包含当前全部玩法改动，不能归因成单独的 T20 敌人改动。

新观测另存文件，保留历史基线，例如：

```powershell
backend\.venv\Scripts\python.exe tools/measure_battles.py --suite t20 --output artifacts/t20/review-current.json
backend\.venv\Scripts\python.exe -m pytest tools/tests/test_measure_battles.py -q
```

新输出带 `metric_schema_version: 2`。`effective_healing` / `heal_effects` 只表示我方实际恢复量 / 治疗效果次数；`effective_healing_on_enemies` / `heal_effects_on_enemies` 单列敌方。归属由战报单位的 `side` 决定。治疗溢出没有原始数据，保持 `null`。历史 JSON 的混合治疗总量不能当成我方治疗；缺分阵营数据时，历史对照把治疗差值标为 `null`，并在 `unavailable_comparisons` 中说明不可比较。

## 同候选道法对照

`compare_affix_choices.py` 推进到指定决策点，再克隆同一状态分别选择各个真实候选。后续都取首个路线、首个道法。`--owned` 是人工注入的构筑夹具；`--hp-ratio` 只按比例压低存活成员的当前气血，已阵亡成员仍为 0，不代表真实玩家获得这些状态的过程。

```powershell
backend\.venv\Scripts\python.exe tools/compare_affix_choices.py --seed 3 --step 6 --level 4 --realm 2 --hp-ratio 0.45 --output artifacts/t21/review-a-hurt.json
```

`healed` / `absorbed` 分别是我方实际治疗 / 我方盾吸收；`enemy_healed` / `enemy_absorbed` 单列敌方。`dealt` 是敌方实际掉血，`taken` 是我方实际掉血，均不含护盾吸收。新输出保存代码与配置指纹、比较工具指纹、决策前逐人气血和已选道法，便于核对样本。

`termination` 使用真实结束原因区分通关、全员倒下与回合耗尽。层数包含最后一次失败遭遇，不等于通关。相同层数不能证明收益相同，盾吸收更高不能证明更早击杀；总掉血会受敌人治疗、护盾、失败时存活单位以及到达层数影响，也不恒等于敌人初始总气血。判断触发来源或击杀先后需要真实行动事件，不能由汇总反推。样本数量、路线策略和人工改动必须随结论说明。
