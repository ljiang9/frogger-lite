"""frogger-lite: minimal frogger clone.

lanes 布局（从下到上）:
  row 0: 起点岸（安全）
  rows 1..4: 马路（小车，撞到即死）
  row 5: 中间岸（安全）
  rows 6..8: 河流（木头，无木头则淹死；站在木头上随木头漂移）
  row 9: 终点岸（5 个目标位，到达计分）

操作: w/a/s/d 或 方向词，--auto 无头演示（贪心 AI）。
纯标准库: argparse / sys / random。
"""

import argparse
import random
import sys

W = 13          # 宽度
GOALS = [1, 4, 6, 9, 11]  # 终点目标列


class Lane:
    """一条车道/河道。"""

    def __init__(self, kind, speed, pattern):
        # kind: "road" | "river"
        self.kind = kind
        self.speed = speed          # 每 tick 移动格数（正=向右，负=向左）
        self.pattern = pattern      # 障碍物相对位置列表（重复周期 W）
        self.offset = 0

    def tick(self, rnd=None):
        self.offset = (self.offset + self.speed) % W

    def cells(self):
        """返回本行每列是否有物体（True=有车/木头）。"""
        return [((c - self.offset) % W) in self.pattern for c in range(W)]


class Game:
    def __init__(self, seed=None):
        self.rnd = random.Random(seed)
        self.lanes = self._make_lanes()
        self.frog = (W // 2, 0)     # (col, row)，row 0=起点岸，9=终点岸
        self.goals_reached = set()
        self.lives = 3
        self.score = 0
        self.moves = 0
        self.dead = False
        self.won = False
        self.death_reason = ""

    def _make_lanes(self):
        rnd = self.rnd
        lanes = {}
        # 马路 rows 1..4: 车速交替方向
        for row in range(1, 5):
            speed = rnd.choice([1, -1]) * rnd.choice([1, 1, 2])
            n_cars = rnd.randint(2, 4)
            starts = rnd.sample(range(W), n_cars)
            # 让车有长度感：每辆车占 2 格
            pattern = set()
            for s in starts:
                pattern.add(s % W)
                pattern.add((s + 1) % W)
            lanes[row] = Lane("road", speed, pattern)
        # 河流 rows 6..8: 木头
        for row in range(6, 9):
            speed = rnd.choice([1, -1]) * rnd.choice([1, 1, 2])
            n_logs = rnd.randint(2, 3)
            starts = rnd.sample(range(W), n_logs)
            pattern = set()
            for s in starts:
                for k in range(3):   # 木头长 3
                    pattern.add((s + k) % W)
            lanes[row] = Lane("river", speed, pattern)
        return lanes

    # ---------- 核心规则（可测试） ----------

    def move_frog(self, dx, dy):
        """青蛙跳一格。返回事件字符串。"""
        if self.dead or self.won:
            return "end"
        c, r = self.frog
        nc = min(W - 1, max(0, c + dx))
        nr = min(9, max(0, r + dy))
        self.frog = (nc, nr)
        self.moves += 1
        return self._resolve()

    def _resolve(self):
        c, r = self.frog
        if r in (0, 5):
            return "safe"
        if r == 9:
            if c in GOALS and c not in self.goals_reached:
                self.goals_reached.add(c)
                self.score += 100
                self.frog = (W // 2, 0)   # 回到起点继续
                if len(self.goals_reached) == len(GOALS):
                    self.won = True
                    return "win"
                return "goal"
            # 终点岸非目标位：安全但无分
            return "shore"
        lane = self.lanes[r]
        occ = lane.cells()
        if lane.kind == "road":
            if occ[c]:
                return self._die("被小车撞了！")
            return "safe"
        # river
        if not occ[c]:
            return self._die("掉进水里淹死了！")
        return "ride"

    def _die(self, reason):
        self.lives -= 1
        self.death_reason = reason
        self.frog = (W // 2, 0)
        if self.lives <= 0:
            self.dead = True
            return "dead"
        return "hit:" + reason

    def tick(self):
        """时间推进：车道滚动 + 河流漂移青蛙。"""
        for lane in self.lanes.values():
            lane.tick()
        c, r = self.frog
        if self.dead or self.won:
            return
        if 1 <= r <= 4:
            # 车撞到青蛙身上
            if self.lanes[r].cells()[c]:
                self._die("被小车撞了！")
        elif 6 <= r <= 8:
            lane = self.lanes[r]
            if lane.cells()[c]:
                # 随木头漂移
                nc = (c + lane.speed) % W
                self.frog = (nc, r)
                # 漂出边界也算淹死（简化：不处理，因为木头周期覆盖全行）
            else:
                # 木头移走了，脚下空了
                self._die("木头漂走，掉进水里！")

    # ---------- 渲染 ----------

    def render(self):
        rows = []
        header = "   " + "".join(str(c % 10) for c in range(W))
        rows.append(header)
        for r in range(9, -1, -1):
            line = [f"{r:2d} "]
            occ = self.lanes[r].cells() if r in self.lanes else None
            for c in range(W):
                ch = " "
                if r == 0:
                    ch = "░"
                elif r == 5:
                    ch = "░"
                elif r == 9:
                    ch = "★" if c in GOALS and c not in self.goals_reached else ("✦" if c in self.goals_reached else "░")
                elif r in self.lanes:
                    lane = self.lanes[r]
                    if lane.kind == "road":
                        ch = "▓" if occ[c] else "·"
                    else:
                        ch = "≡" if occ[c] else "≈"
                if (c, r) == self.frog and not self.dead:
                    ch = "蛙"
                line.append(ch)
            rows.append("".join(line))
        rows.append(f"命: {self.lives}  分: {self.score}  目标: {len(self.goals_reached)}/{len(GOALS)}  步数: {self.moves}")
        if self.dead:
            rows.append("游戏结束：青蛙用完了。")
        if self.won:
            rows.append("全部目标到达，胜利！")
        return "\n".join(rows)


# ---------- AI ----------

def _score_state(g, ev, lives_before):
    """评估一个模拟后状态的分数。"""
    c, r = g.frog
    score = r * 10 - abs(c - W // 2) * 0.2
    score -= (lives_before - g.lives) * 500   # 掉命重罚
    if ev == "goal":
        score += 200
    if ev == "win":
        score += 1000
    if 6 <= r <= 8:
        occ = g.lanes[r].cells()
        margin = sum(1 for dc in (-1, 1) if 0 <= c + dc < W and occ[c + dc])
        score += margin * 2
    return score


def auto_play(seed=None, max_moves=400, verbose=False):
    """贪心 AI：一步前瞻（走子 + tick 模拟），选最安全且最向上的走法。"""
    import copy
    g = Game(seed)
    DIRS = [(0, 1), (-1, 0), (1, 0), (0, 0), (0, -1)]
    while not g.dead and not g.won and g.moves < max_moves:
        best = None
        for dx, dy in DIRS:
            h = copy.deepcopy(g)
            lb = h.lives
            ev = h.move_frog(dx, dy)
            if h.dead or ev == "dead":
                score = -10000
            else:
                h.tick()
                if h.dead:
                    score = -10000
                else:
                    score = _score_state(h, ev, lb) + dy * 3
            if best is None or score > best[0]:
                best = (score, dx, dy)
        g.move_frog(best[1], best[2])
        g.tick()
        if verbose and g.moves % 20 == 0:
            print(g.render())
            print()
    return g


# ---------- CLI ----------

def play_interactive(seed=None):
    if not sys.stdin.isatty():
        print("交互模式需要终端；请用 --auto 观看演示。", file=sys.stderr)
        return 2
    g = Game(seed)
    print("frogger-lite：w/a/s/d 移动，q 退出。把青蛙送到 ★ 目标！")
    print(g.render())
    keys = {"w": (0, 1), "a": (-1, 0), "s": (0, -1), "d": (1, 0)}
    while not g.dead and not g.won:
        try:
            cmd = input("移动> ").strip().lower()
        except EOFError:
            break
        if cmd in ("q", "quit", "退出"):
            break
        if cmd in keys:
            ev = g.move_frog(*keys[cmd])
            if ev.startswith("hit:"):
                print(ev[4:])
            elif ev == "goal":
                print("到达目标！+100")
            elif ev == "dead":
                print(g.death_reason)
            elif ev == "win":
                print("全部目标到达，胜利！")
            g.tick()
            print(g.render())
        else:
            print("用 w/a/s/d 移动，q 退出。")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="frogger-lite", description="终端青蛙过河：躲车、乘木头、到达 5 个目标。")
    ap.add_argument("--auto", action="store_true", help="无头演示（贪心 AI）")
    ap.add_argument("--seed", type=int, default=None, help="随机种子")
    ap.add_argument("--moves", type=int, default=400, help="--auto 最大步数")
    ap.add_argument("--verbose", action="store_true", help="--auto 时每 20 步打印棋盘")
    args = ap.parse_args(argv)
    if args.auto:
        g = auto_play(seed=args.seed, max_moves=args.moves, verbose=args.verbose)
        print(f"自动演示结束：目标 {len(g.goals_reached)}/{len(GOALS)}，得分 {g.score}，步数 {g.moves}，"
              f"{'胜利' if g.won else ('阵亡' if g.dead else '步数用尽')}")
        return 0
    return play_interactive(seed=args.seed)


if __name__ == "__main__":
    sys.exit(main())
