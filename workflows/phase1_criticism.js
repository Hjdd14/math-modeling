// Phase 1.2.2 Round N: 5个视角Agent并行批评所有方案
// ⚠️ DEMO —— 单步并行派发模板，只覆盖并行批评；不能替代 references/workflow.md 的
// Phase 1 完整共识流程，不得作为交付依据。
// 定位：可选宿主 Workflow 模板，依赖宿主提供 agent/parallel 全局函数。
// 调用方式：Workflow({scriptPath: "workflows/phase1_criticism.js", args: {all_solutions: {...}}})

export const meta = {
  name: 'phase1-criticism',
  description: '并行启动5个视角Agent批评所有建模方案',
  phases: [{ title: '批评阶段' }]
}

const AGENTS = [
  { id: 'optimizer', name: '优化视角Agent', prompt: '你是优化视角的建模专家，擅长线性/非线性/整数规划、动态规划。' },
  { id: 'statistician', name: '统计视角Agent', prompt: '你是统计视角的建模专家，擅长回归、时间序列、贝叶斯、蒙特卡洛。' },
  { id: 'physicist', name: '物理视角Agent', prompt: '你是物理视角的建模专家，擅长微分方程、动力系统、守恒定律。' },
  { id: 'engineer', name: '工程视角Agent', prompt: '你是工程视角的建模专家，擅长仿真、离散事件、排队论。' },
  { id: 'innovator', name: '创新视角Agent', prompt: '你是创新视角的建模专家，擅长机器学习、深度学习、混合模型。' }
]

async function main(args) {
  const { all_solutions } = args
  if (!all_solutions) throw new Error('args.all_solutions is required')

  const criticisms = await parallel(
    AGENTS.map(a => () => agent(
      `${a.prompt}\n\n作为${a.name}，对以下所有建模方案进行批评。对每个方案：指出问题、给出改进建议、评分(0-100)、严重程度(high/medium/low)。\n\n所有方案：\n${JSON.stringify(all_solutions, null, 2)}\n\n输出JSON格式：\n{"target_agent_id":{"criticisms":["问题1"],"suggestions":["建议1"],"score":75,"severity":"medium"}}`,
      { label: `critic_${a.id}` }
    ))
  )

  const result = {}
  AGENTS.forEach((a, i) => { result[a.id] = criticisms[i] })
  return result
}
