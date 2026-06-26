#!/usr/bin/env python3
"""
Jay Chou Skill test runner.

This runner has two practical jobs:
1. Validate that the markdown regression test suite under test_cases/ is complete.
2. Optionally validate generated markdown outputs against the documented rules.
3. Optionally validate the bundled structured JSON examples against the repo schemas.

It does not call any remote model by itself. Instead, pass saved outputs with
--output or --output-dir after you generate them in Claude/Codex.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
TEST_CASES_DIR = ROOT_DIR / "test_cases"
DEFAULT_REPORT_PATH = ROOT_DIR / "test-report.md"
INPUT_SCHEMA_PATH = ROOT_DIR / "schemas" / "input_schema.json"
OUTPUT_SCHEMA_PATH = ROOT_DIR / "schemas" / "output_schema.json"
INPUT_EXAMPLE_PATH = ROOT_DIR / "schemas" / "input_example.json"
OUTPUT_EXAMPLE_PATH = ROOT_DIR / "schemas" / "output_example.json"
REQUIRED_TEST_SECTIONS = ("## 用途", "## 输入", "## 预期行为", "## 验收清单")
REQUIRED_OUTPUT_SECTIONS = tuple(range(1, 11))
QUESTION_PATTERN = re.compile(r"[?？]")
NUMBERED_SECTION_PATTERN = re.compile(r"^#{2,6}\s+(\d+)\.\s+.+$", re.MULTILINE)
FUSION_SOURCE_MARKER_PATTERN = re.compile(r"\[(?:JC|F|MIX)\]")
LYRIC_SAMPLE_MARKER_PATTERN = re.compile(r"(?:原创)?示例句|sample lines", re.IGNORECASE)
LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-*]|\d+\.)\s+")
OPTIONAL_NUMBERED_FUSION_SECTION_PATTERN = re.compile(
    r"^#{2,6}\s+11\.\s+.*(?:融合说明|Fusion Notes).*$",
    re.MULTILINE | re.IGNORECASE,
)


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
        help="Specific test case file(s) to validate. Accepts a filename like test_01.md, a repo-relative path like ./test_cases/test_01.md, or an absolute path.",
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
        help="Where to write the markdown report. Parent directory must already exist. Default: ./test-report.md",
    )
    parser.add_argument(
        "--no-write-report",
        action="store_true",
        help="Only print the report to stdout.",
    )
    parser.add_argument(
        "--validate-structured-examples",
        action="store_true",
        help="Also validate schemas/input_example.json and schemas/output_example.json against the bundled schema subset checks.",
    )
    parser.add_argument(
        "--structured-only",
        action="store_true",
        help="Only validate the bundled structured JSON examples. Cannot be combined with --test, --output, or --output-dir.",
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


def resolve_report_file_path(raw_value: str) -> Path:
    report_path = Path(raw_value).expanduser().resolve()

    if report_path.exists() and report_path.is_dir():
        raise SystemExit(f"--report-file must point to a file: {report_path}")

    parent_dir = report_path.parent
    if not parent_dir.exists():
        raise SystemExit(f"--report-file parent directory not found: {parent_dir}")
    if not parent_dir.is_dir():
        raise SystemExit(f"--report-file parent must be a directory: {parent_dir}")

    return report_path


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


def resolve_test_case_path(raw_value: str) -> Path:
    candidate = Path(raw_value).expanduser()
    if candidate.is_absolute():
        candidates = [candidate.resolve()]
    else:
        candidates = [candidate.resolve(), (ROOT_DIR / candidate).resolve()]
        if len(candidate.parts) == 1:
            candidates.append((TEST_CASES_DIR / candidate.name).resolve())

    seen: set[Path] = set()
    for candidate_path in candidates:
        if candidate_path in seen:
            continue
        seen.add(candidate_path)
        if not candidate_path.exists():
            continue
        if not candidate_path.is_file():
            raise SystemExit(f"--test must point to a file: {candidate_path}")
        return candidate_path

    if not any(path.exists() for path in seen):
        raise SystemExit(f"--test file not found: {raw_value}")
    raise SystemExit(f"--test file not found: {raw_value}")


def resolve_test_cases(raw_tests: list[str]) -> list[TestCaseSpec]:
    if not raw_tests:
        paths = sorted(TEST_CASES_DIR.glob("test_*.md"))
        return [load_test_case(path) for path in paths]

    specs: list[TestCaseSpec] = []
    for raw_value in raw_tests:
        specs.append(load_test_case(resolve_test_case_path(raw_value)))
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


def count_lyric_sample_lines(section_text: str) -> int:
    marker_match = LYRIC_SAMPLE_MARKER_PATTERN.search(section_text)
    if marker_match is None:
        return 0

    sample_block = section_text[marker_match.end():]
    return sum(1 for line in sample_block.splitlines() if LIST_ITEM_PATTERN.match(line.strip()))


def has_refusal_intro(text: str) -> bool:
    first_lines = "\n".join(text.splitlines()[:12])
    refusal_markers = ("不能", "无法", "不直接", "不提供", "不做字面复制", "拒绝")
    return any(marker in first_lines for marker in refusal_markers)


def contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def contains_any_casefold(text: str, needles: tuple[str, ...]) -> bool:
    normalized = text.casefold()
    return any(needle.casefold() in normalized for needle in needles)


def line_has_pass_or_block_verdict(
    section_text: str,
    label_needles: tuple[str, ...],
) -> bool:
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not contains_any_casefold(line, label_needles):
            continue
        if re.search(r"\b(?:PASS|BLOCK)\b", line, re.IGNORECASE):
            return True
    return False


def load_json_document(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def json_type_matches(value: object, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def validate_json_instance_against_schema(instance: object, schema: object, path: str = "$") -> list[str]:
    if not isinstance(schema, dict):
        return []

    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type is not None and not json_type_matches(instance, expected_type):
        return [f"{path}: expected {expected_type}"]

    enum_values = schema.get("enum")
    if enum_values is not None and instance not in enum_values:
        errors.append(f"{path}: value {instance!r} is not in enum {enum_values}")

    if isinstance(instance, dict):
        required_keys = schema.get("required", [])
        for key in required_keys:
            if key not in instance:
                errors.append(f"{path}: missing required property {key}")

        properties = schema.get("properties", {})
        for key, value in instance.items():
            property_schema = properties.get(key)
            if property_schema is not None:
                errors.extend(validate_json_instance_against_schema(value, property_schema, f"{path}.{key}"))
                continue

            additional_properties = schema.get("additionalProperties", True)
            if additional_properties is False:
                errors.append(f"{path}: unexpected property {key}")
            elif isinstance(additional_properties, dict):
                errors.extend(
                    validate_json_instance_against_schema(value, additional_properties, f"{path}.{key}")
                )

    if isinstance(instance, list):
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if min_items is not None and len(instance) < min_items:
            errors.append(f"{path}: expected at least {min_items} items, got {len(instance)}")
        if max_items is not None and len(instance) > max_items:
            errors.append(f"{path}: expected at most {max_items} items, got {len(instance)}")

        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(instance):
                errors.extend(validate_json_instance_against_schema(item, item_schema, f"{path}[{index}]"))

    if expected_type in {"integer", "number"} and isinstance(instance, (int, float)) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and instance < minimum:
            errors.append(f"{path}: expected value >= {minimum}, got {instance}")
        if maximum is not None and instance > maximum:
            errors.append(f"{path}: expected value <= {maximum}, got {instance}")

    if expected_type == "string" and isinstance(instance, str):
        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")
        if min_length is not None and len(instance) < min_length:
            errors.append(f"{path}: expected at least {min_length} characters, got {len(instance)}")
        if max_length is not None and len(instance) > max_length:
            errors.append(f"{path}: expected at most {max_length} characters, got {len(instance)}")

    one_of = schema.get("oneOf")
    if one_of is not None:
        match_count = sum(
            1
            for option in one_of
            if not validate_json_instance_against_schema(instance, option, path)
        )
        if match_count != 1:
            errors.append(f"{path}: expected exactly one oneOf match, got {match_count}")

    any_of = schema.get("anyOf")
    if any_of is not None and not any(
        not validate_json_instance_against_schema(instance, option, path)
        for option in any_of
    ):
        errors.append(f"{path}: did not satisfy anyOf requirement")

    return errors


def validate_json_artifact(schema_path: Path, example_path: Path, label: str) -> CheckResult:
    try:
        schema = load_json_document(schema_path)
    except (OSError, json.JSONDecodeError) as exc:
        return CheckResult("FAIL", label, f"无法读取 schema 文件 `{schema_path.name}`: {exc}")

    try:
        example = load_json_document(example_path)
    except (OSError, json.JSONDecodeError) as exc:
        return CheckResult("FAIL", label, f"无法读取示例文件 `{example_path.name}`: {exc}")

    errors = validate_json_instance_against_schema(example, schema)
    if not errors:
        return CheckResult("PASS", label, f"`{example_path.name}` 符合 `{schema_path.name}` 的内建 JSON Schema 子集校验。")

    preview = "；".join(errors[:3])
    if len(errors) > 3:
        preview += f"；另有 {len(errors) - 3} 条错误"
    return CheckResult("FAIL", label, preview)


def validate_structured_examples() -> tuple[CheckResult, ...]:
    return (
        validate_json_artifact(INPUT_SCHEMA_PATH, INPUT_EXAMPLE_PATH, "input_example.json × input_schema.json"),
        validate_json_artifact(OUTPUT_SCHEMA_PATH, OUTPUT_EXAMPLE_PATH, "output_example.json × output_schema.json"),
    )


def find_missing_test_02_parameter_evidence(text: str) -> list[str]:
    missing: list[str] = []

    if not contains_any_casefold(text, ("轻 r&b", "轻r&b", "r&b", "rnb")):
        missing.append("轻 R&B 律动")

    has_minor_color = contains_any_casefold(text, ("小调", "minor"))
    has_urban_color = contains_any(text, ("都市感", "都市", "城市夜", "城市", "夜景", "霓虹", "便利店", "末班车", "路灯"))
    if not (has_minor_color and has_urban_color):
        missing.append("小调都市感")

    if not contains_any_casefold(text, ("电钢", "rhodes", "rhodes ep", "electric piano")):
        missing.append("电钢铺底")

    has_chorus_context = contains_any_casefold(text, ("副歌", "chorus", "c1", "c2", "c3"))
    has_pad = contains_any_casefold(text, ("pad", "synth pad", "warm pad", "合成器 pad", "合成器铺底"))
    has_expansion = contains_any(text, ("扩张", "打开", "拉开", "铺开"))
    if not (has_chorus_context and has_pad and has_expansion):
        missing.append("副歌 Pad 扩张")

    if not contains_any(text, ("城市夜景", "夜景", "霓虹", "便利店", "末班车", "路灯", "街口", "街景", "午夜", "深夜", "出租车")):
        missing.append("城市夜景意象")

    return missing


def has_optional_numbered_fusion_section(text: str, sections: dict[int, str]) -> bool:
    return 11 in sections and OPTIONAL_NUMBERED_FUSION_SECTION_PATTERN.search(text) is not None


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
    ordered_numbers = [int(match.group(1)) for match in NUMBERED_SECTION_PATTERN.finditer(text)]
    sections = parse_numbered_sections(text)
    found_sections = tuple(sorted(sections))
    optional_numbered_fusion = has_optional_numbered_fusion_section(text, sections)
    missing = [str(number) for number in REQUIRED_OUTPUT_SECTIONS if number not in sections]
    unexpected = [str(number) for number in found_sections if number not in REQUIRED_OUTPUT_SECTIONS]
    duplicate_numbers = sorted({number for number in ordered_numbers if ordered_numbers.count(number) > 1})
    expected_order = list(REQUIRED_OUTPUT_SECTIONS)

    if optional_numbered_fusion:
        unexpected = [number for number in unexpected if number != "11"]
        expected_order.append(11)

    if not missing and not unexpected and not duplicate_numbers and ordered_numbers == expected_order:
        detail = "输出包含完整的 1–10 段编号章节。"
        if optional_numbered_fusion:
            detail = "输出包含完整的 1–10 段编号章节，并在第 11 段补充了融合说明。"
        checks.append(CheckResult("PASS", "10 段模板", detail))
    else:
        details: list[str] = []
        if missing:
            details.append(f"缺少编号章节: {', '.join(missing)}")
        if unexpected:
            details.append(f"多出未约定章节: {', '.join(unexpected)}")
        if duplicate_numbers:
            details.append(f"存在重复编号章节: {', '.join(str(number) for number in duplicate_numbers)}")
        if ordered_numbers and ordered_numbers != expected_order and not missing and not unexpected and not duplicate_numbers:
            details.append(
                "编号顺序不合法: 应按 "
                + " → ".join(str(number) for number in expected_order)
                + " 输出。"
            )
        if "11" in [str(number) for number in found_sections] and not optional_numbered_fusion:
            details.append("第 11 段若存在，标题需明确写成融合说明 / Fusion Notes。")
        checks.append(CheckResult("FAIL", "10 段模板", "；".join(details) if details else "编号章节顺序异常"))

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


def should_run_generic_output_checks(spec: TestCaseSpec, sections: dict[int, str]) -> bool:
    if spec.slug == "test_05":
        return False
    if spec.slug == "test_02":
        return bool(sections)
    return True


def validate_output_for_test(spec: TestCaseSpec, output_path: Path) -> list[CheckResult]:
    try:
        text = output_path.read_text(encoding="utf-8")
    except UnicodeError:
        return [
            CheckResult(
                "FAIL",
                "生成结果",
                f"无法按 UTF-8 读取输出文件 `{output_path.name}`。",
            )
        ]
    except OSError as exc:
        return [
            CheckResult(
                "FAIL",
                "生成结果",
                f"无法读取输出文件 `{output_path.name}`: {exc.strerror or exc}",
            )
        ]

    sections = parse_numbered_sections(text)
    checks = validate_generic_output(text) if should_run_generic_output_checks(spec, sections) else []

    if spec.slug == "test_01":
        section_6 = sections.get(6, "")
        section_8 = sections.get(8, "")
        sample_line_count = count_lyric_sample_lines(section_6)
        if sample_line_count >= 3:
            checks.append(CheckResult("PASS", "歌词示例句", f"第 6 段显式给出 {sample_line_count} 条示例句。"))
        else:
            checks.append(CheckResult("WARN", "歌词示例句", f"第 6 段仅检测到 {sample_line_count} 条显式示例句，建议人工复核。"))

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
        has_default_theme_note = contains_any(text, ("默认", "已为你默认", "如果不对请指定"))
        if sections:
            if has_default_theme_note:
                checks.append(CheckResult("PASS", "默认主题说明", "完整方案包含默认主题说明或可回退提示。"))
            else:
                checks.append(CheckResult("WARN", "默认主题说明", "输出给了完整方案，但没有明确说明默认主题选择。"))

            missing_parameter_evidence = find_missing_test_02_parameter_evidence(text)
            if missing_parameter_evidence:
                checks.append(
                    CheckResult(
                        "FAIL",
                        "参数覆盖",
                        f"完整方案缺少这些输入参数的明确证据: {', '.join(missing_parameter_evidence)}",
                    )
                )
            else:
                checks.append(
                    CheckResult(
                        "PASS",
                        "参数覆盖",
                        "完整方案覆盖了轻 R&B、小调都市感、电钢铺底、副歌 Pad 扩张和城市夜景意象这 5 项输入参数。",
                    )
                )
        elif 1 <= question_count <= 2:
            checks.append(CheckResult("PASS", "冷启动澄清", f"检测到 {question_count} 个澄清问题。"))
        elif has_default_theme_note:
            checks.append(CheckResult("WARN", "默认主题说明", "输出提到默认主题，但未给出完整 10 段方案，建议人工复核。"))
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

        section_9 = sections.get(9, "")
        missing_similarity_subchecks: list[str] = []
        if not line_has_pass_or_block_verdict(section_9, ("和声相似度", "harmony similarity")):
            missing_similarity_subchecks.append("和声相似度")
        if not line_has_pass_or_block_verdict(section_9, ("hook 相似度", "hook相似度", "hook similarity")):
            missing_similarity_subchecks.append("Hook 相似度")

        if missing_similarity_subchecks:
            checks.append(
                CheckResult(
                    "FAIL",
                    "相似度子项",
                    "第 9 段缺少这些必须显式给出 PASS/BLOCK 结论的子项: "
                    + ", ".join(missing_similarity_subchecks),
                )
            )
        else:
            checks.append(CheckResult("PASS", "相似度子项", "第 9 段显式给出了和声相似度与 Hook 相似度的 PASS/BLOCK 结论。"))

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

    elif spec.slug == "test_06":
        if contains_any(text, ("方文山", "fang-wenshan", "白描", "古典意象")):
            checks.append(CheckResult("PASS", "词人人格提示", "输出明确保留了方文山系 / 白描相关线索。"))
        else:
            checks.append(CheckResult("WARN", "词人人格提示", "未明确点名方文山系或白描线索，建议人工复核。"))

        if contains_any(text, ("50:50", "对半融合", "五五开")):
            checks.append(CheckResult("PASS", "融合比例", "输出明确交代了 50:50 融合比例。"))
        else:
            checks.append(CheckResult("FAIL", "融合比例", "未明确写出 50:50 或等价的融合比例说明。"))

        source_marker_count = len(FUSION_SOURCE_MARKER_PATTERN.findall(text))
        if source_marker_count >= 3:
            checks.append(CheckResult("PASS", "融合来源标记", f"检测到 {source_marker_count} 处 [JC]/[F]/[MIX] 来源标记。"))
        else:
            checks.append(CheckResult("FAIL", "融合来源标记", f"仅检测到 {source_marker_count} 处来源标记，少于 3 处。"))

        if contains_any(text, ("融合说明", "Fusion Notes")):
            checks.append(CheckResult("PASS", "融合说明", "输出包含额外的融合说明段。"))
        else:
            checks.append(CheckResult("FAIL", "融合说明", "未找到融合说明 / Fusion Notes 段落。"))

        electronic_markers = ("电子", "合成器", "Synth Pad", "Arpeggiator", "Sub bass", "build-up", "drop", "Vocoder")
        if contains_any(text, electronic_markers):
            checks.append(CheckResult("PASS", "融合侧音色", "输出给出了明确的电子侧音色或段落证据。"))
        else:
            checks.append(CheckResult("WARN", "融合侧音色", "未明显看到电子侧音色证据，建议人工确认融合是否够具体。"))

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
                if candidate.is_file():
                    matched_output = candidate
                else:
                    checks.append(CheckResult("WARN", "生成结果", f"匹配路径不是文件: {candidate.name}"))
            else:
                checks.append(CheckResult("WARN", "生成结果", f"未找到匹配输出文件: {candidate.name}"))

        if matched_output is not None:
            checks.extend(validate_output_for_test(spec, matched_output))

        results.append(EvaluationResult(spec=spec, checks=tuple(checks), output_path=matched_output))
    return results


def build_report(
    results: list[EvaluationResult],
    structured_example_checks: tuple[CheckResult, ...] = (),
) -> str:
    passed = sum(result.passed for result in results) + sum(1 for check in structured_example_checks if check.status == "PASS")
    failed = sum(result.failed for result in results) + sum(1 for check in structured_example_checks if check.status == "FAIL")
    warnings = sum(result.warnings for result in results) + sum(1 for check in structured_example_checks if check.status == "WARN")
    lines = [
        "# Jay Chou Skill Test Report",
        "",
        f"- Total tests: {len(results)}",
        f"- Passed checks: {passed}",
        f"- Warnings: {warnings}",
        f"- Failed checks: {failed}",
        "",
    ]
    if structured_example_checks:
        lines.insert(3, f"- Structured example checks: {len(structured_example_checks)}")

    for result in results:
        lines.append(f"## {result.spec.title}")
        lines.append(f"- Test file: `{result.spec.path.name}`")
        if result.output_path is not None:
            lines.append(f"- Output file: `{result.output_path}`")
        for check in result.checks:
            marker = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}[check.status]
            lines.append(f"- {marker} **{check.label}**: {check.detail}")
        lines.append("")

    if structured_example_checks:
        lines.append("## Structured JSON Examples")
        for check in structured_example_checks:
            marker = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}[check.status]
            lines.append(f"- {marker} **{check.label}**: {check.detail}")
        lines.append("")

    overall = "PASS" if failed == 0 else "FAIL"
    lines.append(f"## Summary")
    lines.append(f"- Overall status: **{overall}**")
    lines.append("- Interpretation: `python3 test_runner.py` validates the regression suite itself; pass `--output` / `--output-dir` for saved markdown outputs, or `--validate-structured-examples` for the bundled JSON examples.")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    if args.structured_only and (args.test or args.output or args.output_dir):
        raise SystemExit("--structured-only cannot be combined with --test, --output, or --output-dir.")

    specs = [] if args.structured_only else resolve_test_cases(args.test)
    output_path, output_dir = resolve_cli_paths(args, specs)
    results = evaluate(specs, output_path, output_dir)
    structured_example_checks = (
        validate_structured_examples()
        if args.validate_structured_examples or args.structured_only
        else ()
    )
    report = build_report(results, structured_example_checks=structured_example_checks)

    if not args.no_write_report:
        report_path = resolve_report_file_path(args.report_file)
        try:
            report_path.write_text(report, encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"Unable to write report file: {report_path} ({exc.strerror or exc})") from exc

    print(report)
    has_failures = any(result.failed for result in results) or any(
        check.status == "FAIL" for check in structured_example_checks
    )
    return 1 if has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
