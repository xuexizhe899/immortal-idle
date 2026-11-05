"""确定性随机源。

整局共用一个 run_seed，消费顺序固定；存档只记 seed 与 cursor 就能完整重放。
不用标准库 random：它的内部状态不可序列化，跨版本也不保证一致。
"""

from __future__ import annotations

MASK64 = (1 << 64) - 1
UINT32_MASK = (1 << 32) - 1
UINT32_SPAN = 1 << 32
MULT = 6364136223846793005
DEFAULT_INC = 1442695040888963407


class Pcg32:
    """PCG32 生成器；相同 seed 必得相同序列。"""

    def __init__(self, seed: int) -> None:
        """按 seed 初始化并预热两轮，避免小种子出现偏斜。"""
        self._state = 0
        self._inc = (DEFAULT_INC << 1) | 1
        self.cursor = 0
        self.next_u32()
        self._state = (self._state + seed) & MASK64
        self.next_u32()

    def next_u32(self) -> int:
        """返回一个 32 位无符号随机数并推进游标。"""
        old = self._state
        self._state = (old * MULT + self._inc) & MASK64
        xorshifted = (((old >> 18) ^ old) >> 27) & UINT32_MASK
        rot = old >> 59
        self.cursor += 1
        return ((xorshifted >> rot) | (xorshifted << ((-rot) & 31))) & UINT32_MASK

    def advance_to(self, cursor: int) -> None:
        """推进到指定游标，用于从存档恢复序列。"""
        while self.cursor < cursor:
            self.next_u32()

    def randint(self, low: int, high: int) -> int:
        """返回闭区间 [low, high] 内的整数。"""
        return low + self.next_u32() % (high - low + 1)

    def pick(self, items: list[str]) -> str:
        """从列表中等概率取一个。"""
        return items[self.next_u32() % len(items)]
