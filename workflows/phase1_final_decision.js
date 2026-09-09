// Phase 1.2.3: 主Agent综合所有方案和讨论，做出最终裁决
// ⚠️ DEMO —— 单步派发模板，只覆盖裁决动作；不产出 model_spec/solver_strategy/
// optimization_certificate 等固定产物，不能替代 references/workflow.md 的 Phase 1，不得作为交付依据。
// 定位：可选宿主 Workflow 模板，依赖宿主提供 agent 全局函数。
// 调用方式：Workflow({scriptPath: "workflows/phase1_final_decision.js", args: {all_solutions: {...}, all_criticisms: [...], consensus_history: [...]}})

export const meta = {
  name: 'phase1-final-decision',
  description: '主Agent综合所有方案和讨论，选择最优建模方案',
  phases: [{ title: '最终裁决' }]
}

async function main(args) {
  const { all_solutions, all_criticisms, consensus_history } = args
  if (!all_solutions) throw new Error('args.all_solutions is required')

  const decision = await agent(
    `你是建模方案最终裁决者。综合以下5个视角Agent的建模方案、多轮批评和修正历史，选择最优建模方案。\n\n所有方案：\n${JSON.stringify(all_solutions, null, 2)}\n\n批评历史：\n${JSON.stringify(all_criticisms, null, 2)}\n\n共识度历史：${JSON.stringify(consensus_history)}\n\n请输出：\n1. chosen_solution: 最终选择的方案（完整JSON）\n2. decision_rationale: 选择理由（详细说明为什么选这个方案，其他方案的不足）\n3. comparison_table: 各方案对比表（agent/method/score/pros/cons）\n4. key_insights: 讨论中的关键洞察\n\n输出JSON格式。`,
    { label: 'final_decision' }
  )

  return decision
}
