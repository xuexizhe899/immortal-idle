# T25 论道经济验证记录

2026-11-18（北京时间）。隔离 GameState 模拟，队伍为 20 级/境界 3 的六人测试队；不访问用户存档。

## 案例 A · 零建设资源压力测试

假设：三座一级外宗已攻克（模拟此前征讨，不计首胜库存），库存与灵石为 0，行动力 6；三次论道全胜，疗伤成本 0。

起始：行动力 6.0，持有 {'spirit_stone': 0}
论道 剑修（听雨剑宗·下院）胜：+{'chi_tong': 4, 'spirit_stone': 10.0}；行动力 4.0，持有 {'spirit_stone': 10.0, 'chi_tong': 4}
论道 御守（赤霞器宗·下院）胜：+{'qing_shi': 14, 'spirit_stone': 11.0}；行动力 2.0，持有 {'spirit_stone': 21.0, 'chi_tong': 4, 'qing_shi': 14}
论道 丹修（玄月丹宗·下院）胜：+{'ling_mu': 8, 'spirit_stone': 11.0}；行动力 0.0，持有 {'spirit_stone': 32.0, 'chi_tong': 4, 'ling_mu': 8, 'qing_shi': 14}
升级主殿至 2 级成功；剩余 {'spirit_stone': 12.0, 'chi_tong': 4, 'qing_shi': 6}
升级问道塔至 2 级成功；剩余 {'spirit_stone': 0.0}，设施 {'hall': 2, 'forge': 1, 'alchemy': 1, 'tower': 2, 'training': 1}
一阶已通关（tower_floor=20）且行动力足够时，二阶问道可实际出发；仅升设施未通关一阶仍会被塔阶门槛拒绝（见 test_run_engine 回归）。

结论：三次论道固定奖励合计 灵石32/灵木8/青石14/赤铜4，恰好覆盖二级主殿+二级问道塔，无必须等待现实时间的卡点。

## 案例 B · 正常游玩流水

起始：行动力 6.0，持有 {'spirit_stone': 0.0}
征讨 听雨剑宗·下院 首胜：+{'cultivation': 40.0, 'spirit_stone': 30.0, 'reputation': 60.0, 'han_tie': 8, 'gong_fa_qi_pei': 3}；行动力 4.0，持有 {'spirit_stone': 30.0, 'gong_fa_qi_pei': 3, 'han_tie': 8}
论道 听雨剑宗·下院 胜：+{'chi_tong': 4, 'spirit_stone': 10.0}；行动力 2.0，持有 {'spirit_stone': 40.0, 'chi_tong': 4, 'gong_fa_qi_pei': 3, 'han_tie': 8}
再次论道胜：+{'chi_tong': 4, 'spirit_stone': 10.0}；行动力 0.0，持有 {'spirit_stone': 50.0, 'chi_tong': 8, 'gong_fa_qi_pei': 3, 'han_tie': 8}

结论：首胜奖只发一次；论道奖励按固定表重复发放，不叠加首胜倍率；行动力每次扣 2，失败分支零奖励与参战者伤势由后端回归覆盖。
