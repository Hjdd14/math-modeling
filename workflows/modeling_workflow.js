// workflows/modeling_workflow.js
// ⚠️ DEMO ONLY —— 并行派发骨架示例，不是本 skill 的正式流程。
// 本文件只演示"如何并行派发多个建模 Agent 并做共识循环"，刻意保持精简。
// 它不实现 Phase 0-5 完整流程，缺少：problem_brief 生成、题意审计与歧义登记、
// 题型分类、资料库检索、baseline、固定 JSON 产物、契约测试、独立复现、
// 五类评委并行审查、合规复现、状态持久化。
// 不得把本文件的执行结果当作交付依据或验证证据。
// 正式流程见 references/workflow.md；产物清单见 SKILL.md「固定产物」。
// 定位：可选宿主 Workflow 模板，依赖宿主提供 bash/agent/parallel/phase/log 全局函数。
// 调用方式：通过 Workflow 工具执行；不要承诺可用 node 直接运行。

export const meta = {
  name: 'math-modeling-optimized',
  description: '【DEMO】并行派发骨架示例：Python工具 + 并行化 + 多Agent共识（非完整 Phase 0-5 流程）',
  phases: [
    { title: 'Phase 0: 数据提取' },
    { title: 'Phase 1: 建模共识' },
    { title: 'Phase 2-3: 并行写作交接与代码' },
    { title: 'Phase 4: 并行审查' },
    { title: 'Phase 5: 归档' }
  ]
}

// 工具运行辅助函数
async function runTool(workdir, tool, ...args) {
  const toolPath = `${workdir}/tools/${tool}.py`
  const result = await bash(`python "${toolPath}" ${args.join(' ')}`)
  if (result.exitCode !== 0) {
    throw new Error(`Tool ${tool} failed: ${result.stderr}`)
  }
  return JSON.parse(result.stdout)
}

// Agent 角色定义
const AGENTS = [
  {
    id: 'optimizer',
    name: '优化视角Agent',
    prompt: '你是一个专注于优化方法的建模专家。擅长线性规划、非线性规划、整数规划、动态规划。优先考虑计算效率和全局最优性。'
  },
  {
    id: 'statistician',
    name: '统计视角Agent',
    prompt: '你是一个专注于统计方法的建模专家。擅长回归分析、时间序列、贝叶斯方法、蒙特卡洛。优先考虑统计显著性和置信区间。'
  },
  {
    id: 'physicist',
    name: '物理视角Agent',
    prompt: '你是一个专注于物理机理的建模专家。擅长微分方程、动力系统、守恒定律。优先考虑物理可解释性和量纲一致性。'
  },
  {
    id: 'engineer',
    name: '工程视角Agent',
    prompt: '你是一个专注于工程实践的建模专家。擅长仿真建模、离散事件系统、排队论。优先考虑实现难度和鲁棒性。'
  },
  {
    id: 'innovator',
    name: '创新视角Agent',
    prompt: '你是一个专注于创新方法的建模专家。擅长机器学习、深度学习、混合模型。优先考虑创新性和数据驱动。'
  }
]

// 共识度评估
function evaluateConsensus(solutions) {
  const methods = Object.values(solutions).map(s => s.model_name || '')
  const unique = new Set(methods)
  const n = methods.length

  let score
  if (unique.size === 1) score = 100
  else if (unique.size === 2) score = 70
  else if (unique.size <= n / 2) score = 50
  else score = 30

  return {
    consensus_score: score,
    unique_methods: [...unique],
    convergence_trend: score > 50 ? 'improving' : 'stagnant'
  }
}

// 共识循环判断
function shouldContinue(roundNum, consensusHistory, maxRounds = 5, threshold = 80, stagnation = 2) {
  if (roundNum >= maxRounds) return false
  if (consensusHistory.length > 0 && consensusHistory[consensusHistory.length - 1] >= threshold) return false
  if (consensusHistory.length >= stagnation) {
    const recent = consensusHistory.slice(-stagnation)
    const diffs = recent.slice(1).map((v, i) => Math.abs(v - recent[i]))
    if (diffs.every(d => d < 2)) return false
  }
  return true
}

// 主工作流
async function main(args) {
  const { problem_files, language, workdir } = args
  if (!workdir) throw new Error('workdir is required')
  if (!language) throw new Error('language is required (python or matlab)')
  if (!problem_files || !problem_files.data) throw new Error('problem_files.data is required')

  // Phase 0: 数据提取
  phase('Phase 0: 数据提取')
  const dataStructure = await runTool(workdir, 'data_analyzer', 'read', '--file', problem_files.data)
  log(`数据结构: ${dataStructure.sheets[0].rows} 行, ${dataStructure.sheets[0].columns} 列`)

  const stats = await runTool(workdir, 'data_analyzer', 'stats', '--file', problem_files.data)
  log(`统计摘要: ${stats.columns.length} 列`)

  const quality = await runTool(workdir, 'data_analyzer', 'quality', '--file', problem_files.data)
  log(`数据质量评分: ${quality.quality_score}/100`)

  // Phase 1: 建模共识
  phase('Phase 1: 建模共识')

  // Round 0: 并行生成初始方案
  const initialSolutions = await parallel(
    AGENTS.map(a => () => agent(
      `${a.prompt}\n\n为以下问题生成建模方案：\n${JSON.stringify(dataStructure.sheets[0].column_names)}`,
      { label: `initial_${a.id}` }
    ))
  )

  let solutions = {}
  AGENTS.forEach((a, i) => { solutions[a.id] = initialSolutions[i] })
  let consensusHistory = []
  let round = 0

  // 共识循环
  while (shouldContinue(round, consensusHistory)) {
    round++
    phase(`共识循环 Round ${round}`)

    // 并行批评
    const criticisms = await parallel(
      AGENTS.map(a => () => agent(
        `作为${a.name}，批评以下方案并评分：\n${JSON.stringify(solutions)}`,
        { label: `critic_${a.id}` }
      ))
    )

    // 并行修正
    const updatedSolutions = await parallel(
      AGENTS.map((a, i) => () => agent(
        `作为${a.name}，回应以下批评并修正方案：\n批评：${JSON.stringify(criticisms[i])}\n原方案：${JSON.stringify(solutions[a.id])}`,
        { label: `update_${a.id}` }
      ))
    )

    AGENTS.forEach((a, i) => { solutions[a.id] = updatedSolutions[i] })
    const consensus = evaluateConsensus(solutions)
    consensusHistory.push(consensus.consensus_score)
    log(`Round ${round} 共识度: ${consensus.consensus_score}%`)
  }

  // 最终裁决
  const finalSolution = await agent(
    `综合以下方案和讨论，选择最优建模方案：\n${JSON.stringify({ solutions, consensusHistory })}`,
    { label: 'final_decision' }
  )

  // Phase 2-3: 并行
  phase('Phase 2-3: 并行写作交接与代码')
  // 本 skill 不生成正式写作正文（见 SKILL.md 核心约束 5）：
  // 文档 Agent 只产出 writer_prompt.md 交接材料，正文交给后续独立写作 skill。
  const [writerPrompt, code] = await parallel([
    () => agent(
      `根据建模方案生成 writer_prompt.md 写作交接提示词（不要生成正式论文正文、不要生成 LaTeX 文档）：\n${JSON.stringify(finalSolution)}`,
      { label: 'writer_prompt_agent' }
    ),
    () => agent(
      `根据建模方案编写 ${language} 代码：\n${JSON.stringify(finalSolution)}`,
      { label: 'code_agent' }
    )
  ])

  // Phase 4: 并行审查
  phase('Phase 4: 并行审查')
  const [syntaxCheck, logicCheck, outputCheck] = await parallel([
    () => agent(`语法审查以下代码：\n${code}`, { label: 'syntax_check' }),
    () => agent(`逻辑审查：代码与建模方案一致性\n代码：${code}\n方案：${JSON.stringify(finalSolution)}`, { label: 'logic_check' }),
    () => agent(`输出审查：检查结果完整性\n代码：${code}`, { label: 'output_check' })
  ])

  // Phase 5: 归档
  phase('Phase 5: 归档')
  const finalCheck = await runTool(workdir, 'brief_validator', 'validate',
    '--brief', 'problem_brief.md', '--stage', 'output', '--target', 'results/')

  log(`最终核查评分: ${finalCheck.score}/100`)

  return {
    demo_only: true,
    demo_note: '本工作流仅演示并行派发骨架，未执行完整 Phase 0-5 流程，不得作为交付依据。',
    final_solution: finalSolution,
    writer_prompt: writerPrompt,
    code: code,
    consensus_rounds: round,
    consensus_history: consensusHistory,
    final_check_score: finalCheck.score
  }
}
