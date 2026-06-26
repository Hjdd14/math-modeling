#!/usr/bin/env python3
"""生产优化问题求解"""

from scipy.optimize import linprog


def solve():
    # 目标函数系数（取负号因为 linprog 求最小值）
    c = [-200, -300]
    # 约束矩阵
    a_ub = [[2, 1], [1, 3]]
    b_ub = [80, 90]
    x_bounds = (0, None)
    y_bounds = (0, None)
    return linprog(c, A_ub=a_ub, b_ub=b_ub, bounds=[x_bounds, y_bounds])


def main():
    result = solve()
    if result.success:
        x, y = result.x
        max_profit = -result.fun
        print(f"最优产量: A={x:.2f}件, B={y:.2f}件")
        print(f"最大利润: {max_profit:.2f}元")
    else:
        print("求解失败")


if __name__ == "__main__":
    main()
