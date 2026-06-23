#!/usr/bin/env python3
"""生产优化问题求解"""
import numpy as np
from scipy.optimize import linprog

# 目标函数系数（取负号因为 linprog 求最小值）
c = [-200, -300]

# 约束矩阵
A = [[2, 1], [1, 3]]
b = [80, 90]

# 变量范围
x_bounds = (0, None)
y_bounds = (0, None)

result = linprog(c, A_ub=A, b_ub=b, bounds=[x_bounds, y_bounds])

if result.success:
    x_opt, y_opt = result.x
    max_profit = -result.fun
    print(f"最优产量: A={x_opt:.2f}件, B={y_opt:.2f}件")
    print(f"最大利润: {max_profit:.2f}元")
else:
    print("求解失败")
