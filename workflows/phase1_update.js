// Phase 1.2.2 Round N: 5个视角Agent并行回应批评并修正方案
// ⚠️ DEMO —— 单步并行派发模板，只覆盖并行修正；不能替代 references/workflow.md 的
// Phase 1 完整共识流程，不得作为交付依据。
// 定位：可选宿主 Workflow 模板，依赖宿主提供 agent/parallel 全局函数。
// 调用方式：Workflow({scriptPath: "workflows/phase1_update.js", args: {my_solution: {...}, all_criticisms: {...}, all_solutions: {...}}})

export const meta = {
  name: 'phase1-update',
  description: '并行启动5个视角Agent回应批评并修正方案',
  phases: [{ title: '修正阶段' }]
}

const AGENTS = [
  { id: 'optimizer', name: '优化视角Agent', prompt: '你是优化视角的建模专家。' },
  { id: 'statistician', name: '统计视角Agent', prompt: '你是统计视角的建模专家。' },
  { id: 'physicist', name: '物理视角Agent', prompt: '你是物理视角的建模专家。' },
  { id: 'engineer', name: '工程视角Agent', prompt: '你是工程视角的建模专家。' },
  { id: 'innovator', name: '创新视角Agent', prompt: '你是创新视角的建模专家。' }
]

async function main(args) {
  const { all_criticisms, all_solutions } = args
  if (!all_criticisms) throw new Error('args.all_criticisms is required')
  if (!all_solutions) throw new Error('args.all_solutions is required')

  const updated = await parallel(
    AGENTS.map(a => () => agent(
      `${a.prompt}\n\n作为${a.name}，你收到了其他专家对你方案的批评。请回应每条批评（接受或拒绝，说明理由），并修正你的建模方案。\n\n你的原方案：\n${JSON.stringify(all_solutions[a.id], null, 2)}\n\n收到的批评：\n${JSON.stringify(all_criticisms, null, 2)}\n\n输出修正后的方案（JSON格式，同初始方案格式）：\n{"model_name":"...","variables":[...],"objective_function":"...","constraints":[...],"solution_method":"...","assumptions":[...],"pros":[...],"cons":[...],"complexity":"...","responses":[{"criticism":"...","response":"...","accepted":true/false,"modification":"..."}]}`,
      { label: `update_${a.id}` }
    ))
  )

  const result = {}
  AGENTS.forEach((a, i) => { result[a.id] = updated[i] })
  return result
}
