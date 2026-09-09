// Phase 1.2.1: 5个视角Agent并行生成初始建模方案
// ⚠️ DEMO —— 单步并行派发模板，只覆盖五视角初始方案派发；不含题型分类、资料库检索、
// baseline 与动态专家，不能替代 references/workflow.md 的 Phase 1，不得作为交付依据。
// 定位：可选宿主 Workflow 模板，依赖宿主提供 agent/parallel 全局函数。
// 调用方式：Workflow({scriptPath: "workflows/phase1_initial_solutions.js", args: {problem_description: "..."}})

export const meta = {
  name: 'phase1-initial-solutions',
  description: '并行启动5个视角Agent生成初始建模方案',
  phases: [{ title: '生成初始方案' }]
}

const AGENTS = [
  {
    id: 'optimizer',
    name: '优化视角Agent',
    prompt: '你是优化视角的建模专家。擅长线性规划、非线性规划、整数规划、动态规划。优先考虑计算效率、收敛性、全局最优性。'
  },
  {
    id: 'statistician',
    name: '统计视角Agent',
    prompt: '你是统计视角的建模专家。擅长回归分析、时间序列、贝叶斯方法、蒙特卡洛。优先考虑统计显著性、置信区间、模型假设检验。'
  },
  {
    id: 'physicist',
    name: '物理视角Agent',
    prompt: '你是物理视角的建模专家。擅长微分方程、偏微分方程、动力系统、守恒定律。优先考虑物理可解释性、量纲一致性、边界条件。'
  },
  {
    id: 'engineer',
    name: '工程视角Agent',
    prompt: '你是工程视角的建模专家。擅长仿真建模、离散事件系统、排队论、可靠性分析。优先考虑实现难度、计算资源、实时性、鲁棒性。'
  },
  {
    id: 'innovator',
    name: '创新视角Agent',
    prompt: '你是创新视角的建模专家。擅长机器学习、深度学习、强化学习、图神经网络、混合模型。优先考虑创新性、数据驱动、自适应能力。'
  }
]

async function main(args) {
  const { problem_description } = args
  if (!problem_description) throw new Error('args.problem_description is required')

  const solutions = await parallel(
    AGENTS.map(a => () => agent(
      `${a.prompt}\n\n为以下数学建模问题生成建模方案。要求输出JSON格式。\n\n问题描述：\n${problem_description}\n\n输出格式要求：\n{"model_name":"模型名称","variables":[{"name":"x","meaning":"含义","range":"范围"}],"objective_function":"目标函数","constraints":["约束1"],"solution_method":"求解方法","assumptions":["假设1"],"pros":["优点1"],"cons":["缺点1"],"complexity":"复杂度"}`,
      { label: `initial_${a.id}` }
    ))
  )

  const result = {}
  AGENTS.forEach((a, i) => { result[a.id] = solutions[i] })
  return result
}
