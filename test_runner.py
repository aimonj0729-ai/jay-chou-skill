#!/usr/bin/env python3
"""
Jay Chou Skill test runner.

This runner has two practical jobs:
1. Validate that the markdown regression test suite under test_cases/ is complete.
2. Optionally validate generated markdown outputs against the documented rules.

It does not call any remote model by itself. Instead, pass saved outputs with
--output or --output-dir after you generate them in Claude/Codex.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
TEST_CASES_DIR = ROOT_DIR / "test_cases"
DEFAULT_REPORT_PATH = ROOT_DIR / "test-report.md"
REQUIRED_TEST_SECTIONS = ("## 用途", "## 输入", "## 预期行为", "## 验收清单")
REQUIRED_OUTPUT_SECTIONS = tuple(range(1, 11))
QUESTION_PATTERN = re.compile(r"[?？]")
NUMBERED_SECTION_PATTERN = re.compile(r"^###\s+(\d+)\.\s+.+$", re.MULTILINE)


@dataclass(frozen=True)
class CheckResult:
    status: str
    label: str
    detail: str


@dataclass(frozen=True)
class TestCaseSpec:
    path: Path
    title: str
    body: str
    input_block: str
    checklist_count: int

    @property
    def slug(self) -> str:
        return self.path.stem


@dataclass(frozen=True)
class EvaluationResult:
    spec: TestCaseSpec
    checks: tuple[CheckResult, ...]
    output_path: Path | None = None

    @property
    def passed(self) -> int:
        return sum(1 for check in self.checks if check.status == "PASS")

    @property
    def warnings(self) -> int:
        return sum(1 for check in self.checks if check.status == "WARN")

    @property
    def failed(self) -> int:
        return sum(1 for check in self.checks if check.status == "FAIL")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Jay Chou skill test cases and optional outputs.")
    parser.add_argument(
        "--test",
        action="append",
        default=[],
        help="Specific test case file(s) to validate. Accepts a filename like test_01.md or an absolute path.",
    )
    parser.add_argument(
        "--output",
        help="Single generated markdown output to validate. Requires exactly one selected test case and an existing file.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory containing generated outputs named after test case stems, e.g. test_01.md. Must already exist.",
    )
    parser.add_argument(
        "--report-file",
        default=str(DEFAULT_REPORT_PATH),
        help="Where to write the markdown report. Default: ./test-report.md",
    )
    parser.add_argument(
        "--no-write-report",
        action="store_true",
        help="Only print the report to stdout.",
    )
    return parser.parse_args()


def resolve_cli_paths(args: argparse.Namespace, specs: list[TestCaseSpec]) -> tuple[Path | None, Path | None]:
    if args.output and args.output_dir:
        raise SystemExit("Use either --output or --output-dir, not both.")
    if args.output and len(specs) != 1:
        raise SystemExit("--output requires exactly one selected test case.")

    output_path = Path(args.output).expanduser().resolve() if args.output else None
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else None

    if output_path is not None:
        if not output_path.exists():
            raise SystemExit(f"--output file not found: {output_path}")
        if not output_path.is_file():
            raise SystemExit(f"--output must point to a file: {output_path}")

    if output_dir is not None:
        if not output_dir.exists():
            raise SystemExit(f"--output-dir directory not found: {output_dir}")
        if not output_dir.is_dir():
            raise SystemExit(f"--output-dir must point to a directory: {output_dir}")

    return output_path, output_dir


def load_test_case(path: Path) -> TestCaseSpec:
    body = path.read_text(encoding="utf-8")
    title = next((line.lstrip("# ").strip() for line in body.splitlines() if line.startswith("# ")), path.stem)
    input_match = re.search(r"## 输入\s+```(?:\w+)?\n(.*?)```", body, re.DOTALL)
    input_block = input_match.group(1).strip() if input_match else ""
    checklist_count = len(re.findall(r"^- \[ \]", body, re.MULTILINE))
    return TestCaseSpec(
        path=path,
        title=title,
        body=body,
        input_block=input_block,
        checklist_count=checklist_count,
    )


def resolve_test_cases(raw_tests: list[str]) -> list[TestCaseSpec]:
    if not raw_tests:
        paths = sorted(TEST_CASES_DIR.glob("test_*.md"))
        return [load_test_case(path) for path in paths]

    specs: list[TestCaseSpec] = []
    for raw_value in raw_tests:
        candidate = Path(raw_value)
        if not candidate.is_absolute():
            candidate = (TEST_CASES_DIR / raw_value).resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"Test case not found: {raw_value}")
        specs.append(load_test_case(candidate))
    return specs


def parse_numbered_sections(text: str) -> dict[int, str]:
    matches = list(NUMBERED_SECTION_PATTERN.finditer(text))
    sections: dict[int, str] = {}
    for index, match in enumerate(matches):
        section_number = int(match.group(1))
        section_start = match.end()
        section_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[section_number] = text[section_start:section_end].strip()
    return sections


def count_questions(text: str) -> int:
    return len(QUESTION_PATTERN.findall(text))


def has_refusal_intro(text: str) -> bool:
    first_lines = "\n".join(text.splitlines()[:12])
    refusal_markers = ("不能", "无法", "不直接", "不提供", "不做字面复制", "拒绝")
    return any(marker in first_lines for marker in refusal_markers)


def contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def validate_test_case_spec(spec: TestCaseSpec) -> list[CheckResult]:
    checks: list[CheckResult] = []
    missing_sections = [section for section in REQUIRED_TEST_SECTIONS if section not in spec.body]
    if missing_sections:
        checks.append(CheckResult("FAIL", "测试说明结构", f"缺少章节: {', '.join(missing_sections)}"))
    else:
        checks.append(CheckResult("PASS", "测试说明结构", "包含用途、输入、预期行为和验收清单四个核心章节。"))

    if spec.input_block:
        checks.append(CheckResult("PASS", "输入样例", "找到可直接复用的 fenced code 输入块。"))
    else:
        checks.append(CheckResult("FAIL", "输入样例", "未找到 ## 输入 下的代码块。"))

    if spec.checklist_count >= 6:
        checks.append(CheckResult("PASS", "验收清单密度", f"共发现 {spec.checklist_count} 条 checklist 项，足够支撑回归。"))
    else:
        checks.append(CheckResult("WARN", "验收清单密度", f"仅发现 {spec.checklist_count} 条 checklist 项，建议补充更多可操作检查点。"))

    return checks


def validate_generic_output(text: str) -> list[CheckResult]:
    checks: list[CheckResult] = []
    sections = parse_numbered_sections(text)
    found_sections = tuple(sorted(sections))
    if found_sections == REQUIRED_OUTPUT_SECTIONS:
        checks.append(CheckResult("PASS", "10 段模板", "输出包含完整的 1–10 段编号章节。"))
    else:
        missing = [str(number) for number in REQUIRED_OUTPUT_SECTIONS if number not in sections]
        checks.append(CheckResult("FAIL", "10 段模板", f"缺少编号章节: {', '.join(missing) if missing else '顺序异常'}"))

    section_9 = sections.get(9, "")
    if contains_any(section_9, ("PASS", "WARN", "BLOCK")):
        checks.append(CheckResult("PASS", "Similarity Guard", "第 9 段包含 PASS/WARN/BLOCK 标签。"))
    else:
        checks.append(CheckResult("FAIL", "Similarity Guard", "第 9 段缺少 PASS/WARN/BLOCK 显式标签。"))

    section_10 = sections.get(10, "")
    if not section_10:
        checks.append(CheckResult("FAIL", "去相似化建议", "第 10 段为空。"))
    elif contains_any(section_10, ("无需改写", "建议", "改写", "避免", "替换", "调整")):
        checks.append(CheckResult("PASS", "去相似化建议", "第 10 段给出了明确处理方向。"))
    else:
        checks.append(CheckResult("WARN", "去相似化建议", "第 10 段存在内容，但建议再明确一些。"))

    return checks


def validate_output_for_test(spec: TestCaseSpec, output_path: Path) -> list[CheckResult]:
    text = output_path.read_text(encoding="utf-8")
    checks = validate_generic_output(text)
    sections = parse_numbered_sections(text)

    if spec.slug == "test_01":
        section_6 = sections.get(6, "")
        section_8 = sections.get(8, "")
        if len(re.findall(r"^- ", section_6, re.MULTILINE)) >= 3:
            checks.append(CheckResult("PASS", "歌词示例句", "第 6 段至少包含 3 条示例句。"))
        else:
            checks.append(CheckResult("WARN", "歌词示例句", "第 6 段未明显给出 3 条示例句，建议人工复核。"))

        if "音区" in section_8 and contains_any(section_8, ("节奏", "切分", "锚点")):
            checks.append(CheckResult("PASS", "Hook 描述粒度", "第 8 段同时覆盖音区与节奏/锚点。"))
        else:
            checks.append(CheckResult("WARN", "Hook 描述粒度", "第 8 段建议再明确音区、节奏或歌词锚点。"))

        if "C3" in text:
            checks.append(CheckResult("PASS", "情绪顶点", "输出显式把最大释放点落在 C3。"))
        else:
            checks.append(CheckResult("WARN", "情绪顶点", "未找到 C3 显式标记，建议人工确认高潮位置。"))

    elif spec.slug == "test_02":
        question_count = count_questions(text)
        if 1 <= question_count <= 2:
            checks.append(CheckResult("PASS", "冷启动澄清", f"检测到 {question_count} 个澄清问题。"))
        elif contains_any(text, ("默认", "已为你默认", "如果不对请指定")):
            checks.append(CheckResult("PASS", "默认主题说明", "输出说明了默认主题选择或可回退方式。"))
        else:
            checks.append(CheckResult("WARN", "冷启动澄清", "没有明显澄清问题或默认主题说明，建议人工复核。"))

    elif spec.slug == "test_03":
        banned_terms = ("红尘", "江湖", "苍茫", "刹那", "轮回", "缘分", "宿命", "千年", "万载", "一梦", "流年")
        hits = [term for term in banned_terms if term in text]
        if hits:
            checks.append(CheckResult("FAIL", "东方陈词黑名单", f"命中黑名单词: {', '.join(hits)}"))
        else:
            checks.append(CheckResult("PASS", "东方陈词黑名单", "未命中东方万能词黑名单。"))

    elif spec.slug == "test_04":
        if has_refusal_intro(text) and "版权" in text:
            checks.append(CheckResult("PASS", "复制请求拒绝", "开头明确拒绝字面复制并解释版权边界。"))
        else:
            checks.append(CheckResult("FAIL", "复制请求拒绝", "未在开头明确拒绝字面复制请求。"))

        banned_quotes = ("刮风这天", "起风那天", "吹风的天")
        hits = [term for term in banned_quotes if term in text]
        if hits:
            checks.append(CheckResult("FAIL", "原句复用", f"输出仍包含高风险原句或换皮表达: {', '.join(hits)}"))
        else:
            checks.append(CheckResult("PASS", "原句复用", "未发现《晴天》高风险原句或换皮表达。"))

    elif spec.slug == "test_05":
        question_count = count_questions(text)
        if parse_numbered_sections(text):
            checks.append(CheckResult("FAIL", "冷启动行为", "第一次响应已经给出 10 段方案，不符合冷启动预期。"))
        elif 2 <= question_count <= 3:
            checks.append(CheckResult("PASS", "冷启动行为", f"第一次响应提出 {question_count} 个澄清问题。"))
        else:
            checks.append(CheckResult("FAIL", "冷启动行为", f"问题数量为 {question_count}，不在 2–3 范围内。"))

        technical_terms = ("C大调", "D小调", "BPM", "和弦进行", "乐器列表")
        if contains_any(text, technical_terms):
            checks.append(CheckResult("WARN", "提问层级", "第一次追问里出现偏技术的词，建议人工确认是否过早下钻。"))
        else:
            checks.append(CheckResult("PASS", "提问层级", "问题聚焦主题/情绪，不是纯技术细节。"))

    return checks


def evaluate(specs: list[TestCaseSpec], output_path: Path | None, output_dir: Path | None) -> list[EvaluationResult]:
    results: list[EvaluationResult] = []
    for spec in specs:
        checks = validate_test_case_spec(spec)
        matched_output: Path | None = None

        if output_path is not None:
            matched_output = output_path
        elif output_dir is not None:
            candidate = output_dir / f"{spec.slug}.md"
            if candidate.exists():
                matched_output = candidate
            else:
                checks.append(CheckResult("WARN", "生成结果", f"未找到匹配输出文件: {candidate.name}"))

        if matched_output is not None:
            checks.extend(validate_output_for_test(spec, matched_output))

        results.append(EvaluationResult(spec=spec, checks=tuple(checks), output_path=matched_output))
    return results


def build_report(results: list[EvaluationResult]) -> str:
    passed = sum(result.passed for result in results)
    failed = sum(result.failed for result in results)
    warnings = sum(result.warnings for result in results)
    lines = [
        "# Jay Chou Skill Test Report",
        "",
        f"- Total tests: {len(results)}",
        f"- Passed checks: {passed}",
        f"- Warnings: {warnings}",
        f"- Failed checks: {failed}",
        "",
    ]

    for result in results:
        lines.append(f"## {result.spec.title}")
        lines.append(f"- Test file: `{result.spec.path.name}`")
        if result.output_path is not None:
            lines.append(f"- Output file: `{result.output_path}`")
        for check in result.checks:
            marker = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}[check.status]
            lines.append(f"- {marker} **{check.label}**: {check.detail}")
        lines.append("")

    overall = "PASS" if failed == 0 else "FAIL"
    lines.append(f"## Summary")
    lines.append(f"- Overall status: **{overall}**")
    lines.append("- Interpretation: `python3 test_runner.py` validates the regression suite itself; pass `--output` or `--output-dir` to validate generated outputs.")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    specs = resolve_test_cases(args.test)
    output_path, output_dir = resolve_cli_paths(args, specs)
    results = evaluate(specs, output_path, output_dir)
    report = build_report(results)

    if not args.no_write_report:
        report_path = Path(args.report_file).expanduser().resolve()
        report_path.write_text(report, encoding="utf-8")

    print(report)
    return 1 if any(result.failed for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
