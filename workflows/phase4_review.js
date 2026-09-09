// Phase 4: 并行启动3个审查Agent（语法/逻辑/输出）
// ⚠️ DEMO —— 单步并行派发模板，只覆盖技术审查三人组；不含独立复现 Agent、
// 五类评委并行审查与 chair judge 汇总，不能替代 references/workflow.md 的 Phase 4，不得作为交付依据。
// 定位：可选宿主 Workflow 模板，依赖宿主提供 agent/parallel 全局函数。
// 调用方式：Workflow({scriptPath: "workflows/phase4_review.js", args: {code: "...", document: "...", problem_brief: "..."}})

export const meta = {
  name: 'phase4-review',
  description: '并行启动语法、逻辑、输出3个审查Agent',
  phases: [{ title: '并行审查' }]
}

async function main(args) {
  const { code, document, problem_brief } = args
  if (!code) throw new Error('args.code is required')

  const [syntaxCheck, logicCheck, outputCheck] = await parallel([
    () => agent(
      `你是语法审查Agent。检查以下代码的语法错误、类型错误、缩进问题、括号匹配、变量命名等。\n\n代码：\n${code}\n\n输出JSON格式：\n{"issues":[{"severity":"high/medium/low","location":"行号","description":"问题描述","fix":"修复建议"}],"passed":true/false,"summary":"总结"}`,
      { label: 'syntax_review' }
    ),
    () => agent(
      `你是逻辑审查Agent。检查以下代码的公式是否与建模文档一致，数据是否与problem_brief一致，算法逻辑是否正确。\n\n代码：\n${code}\n\n建模文档：\n${document || '未提供'}\n\n问题简报：\n${problem_brief || '未提供'}\n\n输出JSON格式：\n{"issues":[{"severity":"high/medium/low","location":"描述","description":"问题描述","fix":"修复建议"}],"passed":true/false,"summary":"总结"}`,
      { label: 'logic_review' }
    ),
    () => agent(
      `你是输出审查Agent。检查以下代码的输出是否覆盖所有求解目标，格式是否符合要求，结果是否合理。\n\n代码：\n${code}\n\n问题简报：\n${problem_brief || '未提供'}\n\n输出JSON格式：\n{"issues":[{"severity":"high/medium/low","location":"描述","description":"问题描述","fix":"修复建议"}],"passed":true/false,"summary":"总结"}`,
      { label: 'output_review' }
    )
  ])

  return { syntaxCheck, logicCheck, outputCheck }
}
