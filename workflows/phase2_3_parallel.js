// Phase 2 & 3: 并行执行文档撰写和代码编写
// 定位：可选宿主 Workflow 模板，依赖宿主提供 agent/parallel 全局函数。
// 调用方式：Workflow({scriptPath: "workflows/phase2_3_parallel.js", args: {final_solution: {...}, language: "python"}})

export const meta = {
  name: 'phase2-3-parallel',
  description: '并行启动文档Agent和代码Agent',
  phases: [{ title: '并行文档与代码' }]
}

async function main(args) {
  const { final_solution, language } = args
  if (!final_solution) throw new Error('args.final_solution is required')
  if (!language) throw new Error('args.language is required (python or matlab)')

  const [document, code] = await parallel([
    () => agent(
      `你是文档Agent。根据以下建模方案，撰写完整的LaTeX建模报告（modeling_report.md）。\n\n建模方案：\n${JSON.stringify(final_solution, null, 2)}\n\n要求：\n1. 包含问题描述、模型假设、符号说明、模型建立（含LaTeX公式）、模型验证、模型评价\n2. 所有公式使用严谨的LaTeX语法\n3. 数据引用需标注来源\n\n直接输出完整的Markdown文档内容。`,
      { label: 'document_agent' }
    ),
    () => agent(
      `你是代码Agent。根据以下建模方案，编写完整的${language === 'python' ? 'Python' : 'MATLAB'}代码。\n\n建模方案：\n${JSON.stringify(final_solution, null, 2)}\n\n要求：\n1. 代码完整可运行\n2. 包含参数设置、数据输入、模型构建、求解计算、结果输出、可视化\n3. 生成至少1张精美图表并保存为高清PNG\n4. ${language === 'python' ? '使用if __name__ == "__main__"包裹主逻辑，使用print(f"...")输出' : '以clc;clear;close all;开头，使用fprintf输出'}\n\n直接输出完整的代码内容。`,
      { label: 'code_agent' }
    )
  ])

  return { document, code }
}
