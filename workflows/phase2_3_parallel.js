// Phase 2 & 3: 并行执行写作交接提示词和代码编写
// ⚠️ DEMO —— 单步并行派发模板，只覆盖 Phase 2/3 的派发动作；不产出固定 JSON 产物、
// 不做契约测试与验证，不能替代 references/workflow.md 的完整流程，不得作为交付依据。
// 定位：可选宿主 Workflow 模板，依赖宿主提供 agent/parallel 全局函数。
// 调用方式：Workflow({scriptPath: "workflows/phase2_3_parallel.js", args: {final_solution: {...}, language: "python"}})

export const meta = {
  name: 'phase2-3-parallel',
  description: '并行启动写作交接Agent和代码Agent',
  phases: [{ title: '并行写作交接与代码' }]
}

async function main(args) {
  const { final_solution, language } = args
  if (!final_solution) throw new Error('args.final_solution is required')
  if (!language) throw new Error('args.language is required (python or matlab)')

  const [writerPrompt, code] = await parallel([
    () => agent(
      `你是写作交接Agent。根据以下建模方案，生成 writer_prompt.md 的交接提示词。\n\n建模方案：\n${JSON.stringify(final_solution, null, 2)}\n\n要求：\n1. 明确本 skill 不生成正式写作正文，只提供建模、代码、图表、验证和合规材料\n2. 列出 problem_brief、final_solution、validation_summary、figure_storyboard、judge_panel_review、compliance_record 和 reproducibility_manifest\n3. 给出风险提示、匿名性提示和后续写作应复核的证据清单\n\n直接输出 writer_prompt.md 内容。`,
      { label: 'writer_prompt_agent' }
    ),
    () => agent(
      `你是代码Agent。根据以下建模方案，编写完整的${language === 'python' ? 'Python' : 'MATLAB'}代码。\n\n建模方案：\n${JSON.stringify(final_solution, null, 2)}\n\n要求：\n1. 代码完整可运行\n2. 包含参数设置、数据输入、模型构建、求解计算、结果输出、可视化\n3. 生成至少1张精美图表并保存为高清PNG\n4. ${language === 'python' ? '使用if __name__ == "__main__"包裹主逻辑，使用print(f"...")输出' : '以clc;clear;close all;开头，使用fprintf输出'}\n\n直接输出完整的代码内容。`,
      { label: 'code_agent' }
    )
  ])

  return { writerPrompt, code }
}
