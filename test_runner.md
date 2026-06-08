# Test Runner —— 回归套件与输出校验

> `test_runner.py` 的主职责是校验 `test_cases/` 回归套件本身，以及校验你已经保存到本地的生成结果；现在还可以额外用 `--validate-structured-examples` 检查仓库内置的 JSON 示例是否仍然符合 schema 合同。

## 它实际会做什么

### 模式 1：校验测试用例文档

默认运行 `python3 test_runner.py` 时，脚本会检查 `test_cases/test_*.md` 是否具备最基本的回归结构：

- 是否包含 `## 用途` / `## 输入` / `## 预期行为` / `## 验收清单`
- 是否存在可复用的 fenced code 输入块
- checklist 数量是否足够支撑回归

如果你要只检查某个用例，可以传 `--test`。它接受 `test_04.md` 这种文件名、`./test_cases/test_04.md` 这种 repo 相对路径，或一个绝对路径；路径必须存在且指向文件。

### 模式 2：校验已保存的生成结果

如果你已经在 Claude/Codex 里手动生成并保存了 markdown 输出，可以额外传给脚本：

- `--output`：校验单个 test case 对应的一份输出。必须配合单个 `--test`，并且文件必须已存在
- `--output-dir`：批量校验一个目录里的输出文件。目录必须已存在
- `--report-file`：自定义 markdown 报告输出位置。父目录必须已存在，目标不能是目录
- `--validate-structured-examples`：额外检查 `schemas/input_example.json` 和 `schemas/output_example.json` 是否通过仓库内建的 JSON Schema 子集校验

内建 JSON Schema 子集现在会检查 `type`、`enum`、`required`、`minItems` / `maxItems`、`minimum` / `maximum`、`oneOf`、`anyOf` 和 `additionalProperties`。两份结构化 schema 的顶层和主要嵌套对象已设置为不接受未声明字段，避免示例里出现拼写错误或旧字段时仍被判通过。输出 schema 还要求第 4–8 段和第 10 段包含各自的最低可用字段，不再接受 `chord_direction: {}`、`hook_concept: {}` 或 `de_similarization: {}` 这类只有段落名、没有实际内容的对象；`emotional_arc.anchors` 和 `lyric_direction.sample_lines` 也都严格限制为 3–5 项，与 `system_prompt.md` 的输出模板一致。

通用检查包括（仅适用于**预期应输出完整 10 段方案**的场景）：

- 10 段编号章节是否完整、按顺序且不重复；标题层级可用 `## 1.` 到 `###### 1.`，便于校验嵌套在示例文档里的输出
- 第 9 段是否包含 `PASS` / `WARN` / `BLOCK`
- 第 10 段是否给出明确的去相似化建议

融合模式下，`Fusion Notes` / `融合说明` 仍然属于默认 10 段之后的附加说明；如果你习惯继续编号，写成 `### 11. 融合说明`、`#### 11. Fusion Notes` 这类二级到六级 markdown 标题也会被视为合法输出。

`test_02` 的“先问 1–2 个澄清问题”分支，以及 `test_05` 的首轮冷启动提问，不会再被误判成“缺少 10 段”；这两类输出会直接走各自的场景化检查。

针对 `test_01` 到 `test_06`，脚本还会做少量场景化检查，例如：

- `test_01`：歌词示例句数量（只统计 `示例句` / `原创示例句` 标记后的列表项）、Hook 描述粒度、是否显式出现 `C3`
- `test_02`：是走澄清问题分支，还是走“默认主题说明 + 完整 10 段”分支；如果是完整方案分支，还会检查 5 个输入参数是否都落到输出里：`轻 R&B`、`小调都市感`、`电钢铺底`、`副歌 Pad 扩张`、`城市夜景`
- `test_03`：东方万能词黑名单
- `test_04`：复制请求是否被拒绝、是否出现高风险原句，以及第 9 段是否显式给出 `和声相似度` / `Hook 相似度` 的 `PASS` 或 `BLOCK`
- `test_05`：第一次响应是否保持冷启动提问而不是直接出 10 段
- `test_06`：词人人格提示、`50:50` 融合比例、`[JC]/[F]/[MIX]` 来源标记、`融合说明`

## 它不会做什么

为避免误解，当前脚本 **不会**：

- 自动调用 Claude / Codex 生成内容
- 对 markdown 输出执行通用 JSON Schema 校验
- 自动计算 LUFS、BPM、和弦次数等音乐统计指标

`schemas/input_schema.json` 和 `schemas/output_schema.json` 主要还是给结构化集成和人工对照使用；`test_runner.py` 不会拿它们去校验任意 markdown 输出，但现在可以在 `--validate-structured-examples` 模式下验证仓库自带的 JSON example 文件是否仍然满足这两份 schema 的核心合同。

## 常用命令

```bash
cd ~/.claude/skills/jay-chou

# 1) 只检查 test_cases/ 套件结构，并生成 test-report.md
python3 test_runner.py

# 2) 只检查一个 test case 文档
python3 test_runner.py --test test_04.md
# --test 接受文件名、repo 相对路径或绝对路径；路径写错时脚本会直接报错退出

python3 test_runner.py --test ./test_cases/test_04.md
# 如果你更习惯直接从仓库路径复制，也可以这样写

# 3) 检查一个 test case + 它对应的一份已保存输出
python3 test_runner.py --test test_04.md --output ./generated_outputs/test_04.md
# --output 需要单个 --test，且文件必须已经存在

# 4) 批量检查目录下所有已保存输出
python3 test_runner.py --output-dir ./generated_outputs
# --output-dir 必须是已存在目录
# 如果目录里的 `test_02.md` 是澄清问题响应，或 `test_05.md` 是首轮冷启动提问，脚本会按对应规则校验，不强制要求 10 段
# 如果 `test_02.md` 走的是完整方案分支，脚本还会检查 5 个输入参数是否都在输出里有明确证据
# 如果某个同名路径存在但它其实是目录而不是文件，报告会给 `生成结果` 的 `WARN`，不会抛 traceback

# 5) 自定义报告文件位置
python3 test_runner.py --report-file ./reports/jay-chou-test-report.md
# --report-file 的父目录必须已存在；路径指向目录时也会直接报错退出

# 6) 显式检查仓库内置的 JSON example 是否还符合 schema
python3 test_runner.py --validate-structured-examples
# 结果会在报告里追加一个 Structured JSON Examples 小节
# 适合在修改 schemas/*.json 或 *_example.json 后做快速回归

# 7) 只打印报告，不写 test-report.md
python3 test_runner.py --no-write-report
```

## 输出文件命名约定

使用 `--output-dir` 时，脚本按 `test_cases` 的 stem 找文件，因此目录里的文件名需要和测试用例一一对应：

```text
generated_outputs/
  test_01.md
  test_02.md
  test_03.md
  test_04.md
  test_05.md
  test_06.md
```

如果目录存在但某个文件不存在，或同名路径其实是目录而不是文件，报告里会给出 `生成结果` 的 `WARN`，但不会中断其他用例。  
如果 `--test`、`--output`、`--output-dir` 或 `--report-file` 的路径本身不合法，脚本会直接报错退出，避免 traceback 或误导性的通过报告。

## 报告格式

实际输出是 markdown 报告，格式类似：

```markdown
# Jay Chou Skill Test Report

- Total tests: 6
- Passed checks: 17
- Warnings: 2
- Failed checks: 0

## Test 04 — 相似度警报触发：用户要求直接复制
- Test file: `test_04.md`
- Output file: `/abs/path/generated_outputs/test_04.md`
- ✓ **测试说明结构**: 包含用途、输入、预期行为和验收清单四个核心章节。
- ✓ **复制请求拒绝**: 开头明确拒绝字面复制并解释版权边界。
- ✓ **原句复用**: 未发现《晴天》高风险原句或换皮表达。

## Summary
- Overall status: **PASS**
- Interpretation: `python3 test_runner.py` validates the regression suite itself; pass `--output` or `--output-dir` to validate generated outputs.
```

## 推荐工作流

1. 先运行 `python3 test_runner.py`，确认 `test_cases/` 本身没有退化。
2. 在 Claude/Codex 里按 `test_cases/*.md` 逐条生成输出，并保存成 `test_01.md` 这类文件名。
3. 再运行 `python3 test_runner.py --output-dir ./generated_outputs`，检查 10 段结构、Similarity Guard、冷启动/拒绝行为，以及 v1.1 的词人人格 + 融合标记规则。
4. 如果你刚改过 `schemas/*.json` 或 `*_example.json`，再跑 `python3 test_runner.py --validate-structured-examples`，确认结构化样例没有漂移。
5. 如需聚焦单个问题，用 `--test` + `--output` 缩小范围。

## CI 示例

```yaml
name: Jay-Chou Skill Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.x"
      - name: Validate regression suite
        run: python3 test_runner.py
```

如果你的 CI 流水线里还保存了模型生成结果，也可以在后续步骤里继续跑 `--output-dir`；如果你也维护结构化 JSON 示例，再补一条 `python3 test_runner.py --validate-structured-examples` 会更稳。

---

**交付标准**：`test_runner.md` 描述的命令、输出和限制应与 `test_runner.py` 的真实行为保持一致，包括 `--validate-structured-examples` 的能力边界。
