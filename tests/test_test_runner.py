from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import test_runner


def build_full_output(
    *,
    section_6: str,
    section_7: str,
    section_9: str = "PASS / WARN / BLOCK",
    section_10: str = "建议保留主体结构，只微调 hook。",
    suffix: str = "",
) -> str:
    return "\n\n".join(
        [
            "### 1. 核心概念\n渡口、潮汐与未寄出的信。",
            "### 2. 情绪轨迹\n克制 → 推进 → 释放 → 留白。",
            "### 3. 结构建议\nIntro(4) - V1(8) - Pre(4) - C1(8) - Bridge(8) - C3(8) - Outro(8)",
            "### 4. 和声方向\nDm - Bb - Gm - A。",
            "### 5. 旋律设计建议\n弱起进入，副歌拉高音区。",
            f"### 6. 歌词意象与叙事方案\n{section_6}",
            f"### 7. 编曲推进方案\n{section_7}",
            "### 8. 副歌 Hook 构思\n音区 F4-A4，节奏有切分，歌词锚点明确。",
            f"### 9. 原创性风险检查\n{section_9}",
            f"### 10. 去相似化建议\n{section_10}",
            suffix,
        ]
    ).strip() + "\n"


class ResolveReportFilePathTests(unittest.TestCase):
    def test_accepts_new_file_when_parent_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / "nested-report.md"

            resolved = test_runner.resolve_report_file_path(str(report_path))

            self.assertEqual(resolved, report_path.resolve())

    def test_rejects_missing_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / "missing" / "nested-report.md"

            with self.assertRaises(SystemExit) as context:
                test_runner.resolve_report_file_path(str(report_path))

            self.assertEqual(
                str(context.exception),
                f"--report-file parent directory not found: {report_path.parent.resolve()}",
            )

    def test_rejects_directory_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report_dir = Path(tmp_dir)

            with self.assertRaises(SystemExit) as context:
                test_runner.resolve_report_file_path(str(report_dir))

            self.assertEqual(
                str(context.exception),
                f"--report-file must point to a file: {report_dir.resolve()}",
            )


class ResolveTestCasePathTests(unittest.TestCase):
    def test_accepts_repo_relative_test_case_path_from_repo_root(self) -> None:
        current_dir = Path.cwd()
        try:
            os.chdir(ROOT_DIR)
            resolved = test_runner.resolve_test_case_path("./test_cases/test_04.md")
        finally:
            os.chdir(current_dir)

        self.assertEqual(resolved, (ROOT_DIR / "test_cases" / "test_04.md").resolve())

    def test_accepts_repo_relative_test_case_path_outside_repo_root(self) -> None:
        current_dir = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                os.chdir(tmp_dir)
                resolved = test_runner.resolve_test_case_path("test_cases/test_04.md")
            finally:
                os.chdir(current_dir)

        self.assertEqual(resolved, (ROOT_DIR / "test_cases" / "test_04.md").resolve())


class OutputSchemaContractTests(unittest.TestCase):
    def test_similarity_guard_overall_status_matches_documented_tri_state_labels(self) -> None:
        schema_path = ROOT_DIR / "schemas" / "output_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        overall_enum = schema["properties"]["risk_check"]["properties"]["overall"]["enum"]

        self.assertEqual(overall_enum, ["PASS", "WARN", "BLOCK"])


class StructuredExampleFilesTests(unittest.TestCase):
    def test_input_example_documents_json_mode_fusion_request(self) -> None:
        example_path = ROOT_DIR / "schemas" / "input_example.json"
        payload = json.loads(example_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["output_format"], "json")
        self.assertEqual(payload["lyricist_persona"], "fang-wenshan")
        self.assertEqual(payload["fusion"]["style"], "electronic")
        self.assertEqual(payload["fusion"]["ratio"], "50:50")

    def test_output_example_covers_required_schema_top_level_fields(self) -> None:
        schema_path = ROOT_DIR / "schemas" / "output_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        example_path = ROOT_DIR / "schemas" / "output_example.json"
        payload = json.loads(example_path.read_text(encoding="utf-8"))

        self.assertTrue(set(schema["required"]).issubset(payload.keys()))
        self.assertEqual(payload["lyric_direction"]["lyricist_persona"], "fang-wenshan")
        self.assertGreaterEqual(len(payload["lyric_direction"]["sample_lines"]), 3)
        self.assertIn(payload["risk_check"]["overall"], {"PASS", "WARN", "BLOCK"})
        self.assertEqual(payload["fusion_notes"]["fusion_style"], "electronic")
        self.assertEqual(payload["fusion_notes"]["ratio"], "50:50")

    def test_bundled_structured_examples_pass_builtin_schema_contract_checks(self) -> None:
        checks = test_runner.validate_structured_examples()
        statuses = {check.label: check.status for check in checks}

        self.assertEqual(statuses["input_example.json × input_schema.json"], "PASS")
        self.assertEqual(statuses["output_example.json × output_schema.json"], "PASS")

    def test_builtin_schema_contract_check_reports_missing_required_field_and_bad_enum(self) -> None:
        schema_path = ROOT_DIR / "schemas" / "output_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        example_path = ROOT_DIR / "schemas" / "output_example.json"
        payload = json.loads(example_path.read_text(encoding="utf-8"))

        broken_payload = {
            **payload,
            "risk_check": {
                **payload["risk_check"],
                "overall": "WARN_WITH_REWRITES",
            },
        }
        broken_payload.pop("de_similarization")

        errors = test_runner.validate_json_instance_against_schema(broken_payload, schema)

        self.assertTrue(any("$.risk_check.overall" in error for error in errors))
        self.assertTrue(any("missing required property de_similarization" in error for error in errors))

    def test_output_schema_rejects_unknown_top_level_properties(self) -> None:
        schema_path = ROOT_DIR / "schemas" / "output_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        example_path = ROOT_DIR / "schemas" / "output_example.json"
        payload = json.loads(example_path.read_text(encoding="utf-8"))

        errors = test_runner.validate_json_instance_against_schema(
            {**payload, "legacy_similarity_status": "WARN_WITH_REWRITES"},
            schema,
        )

        self.assertTrue(any("$: unexpected property legacy_similarity_status" in error for error in errors))

    def test_additional_properties_schema_can_validate_unknown_property_values(self) -> None:
        errors = test_runner.validate_json_instance_against_schema(
            {"known": "ok", "extra": 3},
            {
                "type": "object",
                "properties": {"known": {"type": "string"}},
                "additionalProperties": {"type": "string"},
            },
        )

        self.assertEqual(errors, ["$.extra: expected string"])

    def test_input_schema_rejects_empty_emotion_object(self) -> None:
        schema_path = ROOT_DIR / "schemas" / "input_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        errors = test_runner.validate_json_instance_against_schema({"emotion": {}}, schema)

        self.assertTrue(errors)
        self.assertTrue(any("$" in error for error in errors))

    def test_input_schema_requires_theme_or_emotion_or_reference_mood(self) -> None:
        schema_path = ROOT_DIR / "schemas" / "input_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        errors = test_runner.validate_json_instance_against_schema({}, schema)

        self.assertTrue(errors)
        self.assertTrue(any("anyOf" in error for error in errors))

    def test_output_schema_requires_section_and_text_for_each_sample_line(self) -> None:
        schema_path = ROOT_DIR / "schemas" / "output_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        example_path = ROOT_DIR / "schemas" / "output_example.json"
        payload = json.loads(example_path.read_text(encoding="utf-8"))

        broken_payload = {
            **payload,
            "lyric_direction": {
                **payload["lyric_direction"],
                "sample_lines": [
                    {"section": "Verse"},
                    {"text": "我把潮声折成一页。"},
                    {"section": "Bridge", "text": "木船没开口，只把绳结晃给夜色看。"},
                ],
            },
        }

        errors = test_runner.validate_json_instance_against_schema(broken_payload, schema)

        self.assertTrue(any("$.lyric_direction.sample_lines[0]" in error for error in errors))
        self.assertTrue(any("$.lyric_direction.sample_lines[1]" in error for error in errors))

    def test_output_schema_requires_complete_de_similarization_actions(self) -> None:
        schema_path = ROOT_DIR / "schemas" / "output_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        example_path = ROOT_DIR / "schemas" / "output_example.json"
        payload = json.loads(example_path.read_text(encoding="utf-8"))

        broken_payload = {
            **payload,
            "de_similarization": {
                **payload["de_similarization"],
                "actions": [
                    {"target_section": "hook_concept"},
                    {"issue": "副歌切分组合过于常见。"},
                    {"rewrite": "把第二小节从 16-16-8 改成 8-16-16-8。"},
                ],
            },
        }

        errors = test_runner.validate_json_instance_against_schema(broken_payload, schema)

        self.assertTrue(any("$.de_similarization.actions[0]" in error for error in errors))
        self.assertTrue(any("$.de_similarization.actions[1]" in error for error in errors))
        self.assertTrue(any("$.de_similarization.actions[2]" in error for error in errors))


class ValidateOutputForTestTests(unittest.TestCase):
    def write_output(self, body: str) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        output_path = Path(temp_dir.name) / "output.md"
        output_path.write_text(body, encoding="utf-8")
        return output_path

    def test_test_01_metadata_bullets_do_not_count_as_lyric_sample_lines(self) -> None:
        spec = test_runner.load_test_case(ROOT_DIR / "test_cases" / "test_01.md")
        output_path = self.write_output(
            build_full_output(
                section_6=(
                    "- 主题定位：毕业前夜的告别。\n"
                    "- 叙事视角：第一人称。\n"
                    "- 意象库：风扇、抽屉、门牌。\n"
                    "- 押韵策略：副歌开口韵。"
                ),
                section_7="Piano 为主，副歌加入 Strings 和鼓组。",
            )
        )

        checks = test_runner.validate_output_for_test(spec, output_path)
        statuses = {check.label: check.status for check in checks}

        self.assertEqual(statuses["歌词示例句"], "WARN")

    def test_test_01_explicit_lyric_sample_block_passes(self) -> None:
        spec = test_runner.load_test_case(ROOT_DIR / "test_cases" / "test_01.md")
        output_path = self.write_output(
            build_full_output(
                section_6=(
                    "- 主题定位：毕业前夜的告别。\n"
                    "- **原创示例句**（3 条）：\n"
                    "1. 风扇在头顶慢慢数完最后一圈。\n"
                    "2. 抽屉里那张票根把晚自习折成两半。\n"
                    "3. 门牌旁的白灯亮到走廊都安静。"
                ),
                section_7="Piano 为主，副歌加入 Strings 和鼓组。",
            )
        )

        checks = test_runner.validate_output_for_test(spec, output_path)
        statuses = {check.label: check.status for check in checks}

        self.assertEqual(statuses["歌词示例句"], "PASS")

    def test_generic_output_accepts_nested_markdown_heading_levels(self) -> None:
        spec = test_runner.load_test_case(ROOT_DIR / "test_cases" / "test_01.md")
        output_path = self.write_output(
            build_full_output(
                section_6=(
                    "- **原创示例句**（3 条）：\n"
                    "1. 渡口的旧灯照着潮痕。\n"
                    "2. 宣纸把晚风折成一页。\n"
                    "3. 木船没说话，只晃了晃绳结。"
                ),
                section_7="Piano 为主，副歌加入 Strings 和鼓组。",
            ).replace("### ", "#### ")
        )

        checks = test_runner.validate_output_for_test(spec, output_path)
        statuses = {check.label: check.status for check in checks}

        self.assertEqual(statuses["10 段模板"], "PASS")

    def test_generic_output_fails_when_numbered_sections_are_out_of_order(self) -> None:
        spec = test_runner.load_test_case(ROOT_DIR / "test_cases" / "test_01.md")
        output_path = self.write_output(
            "\n\n".join(
                [
                    "### 1. 核心概念\n渡口、潮汐与未寄出的信。",
                    "### 2. 情绪轨迹\n克制 → 推进 → 释放 → 留白。",
                    "### 4. 和声方向\nDm - Bb - Gm - A。",
                    "### 3. 结构建议\nIntro(4) - V1(8) - Pre(4) - C1(8) - Bridge(8) - C3(8) - Outro(8)",
                    "### 5. 旋律设计建议\n弱起进入，副歌拉高音区。",
                    "### 6. 歌词意象与叙事方案\n- **原创示例句**（3 条）：\n1. 渡口的旧灯照着潮痕。\n2. 宣纸把晚风折成一页。\n3. 木船没说话，只晃了晃绳结。",
                    "### 7. 编曲推进方案\nPiano 为主，副歌加入 Strings 和鼓组。",
                    "### 8. 副歌 Hook 构思\n音区 F4-A4，节奏有切分，歌词锚点明确。",
                    "### 9. 原创性风险检查\nPASS / WARN / BLOCK",
                    "### 10. 去相似化建议\n建议保留主体结构，只微调 hook。",
                ]
            )
            + "\n"
        )

        checks = test_runner.validate_output_for_test(spec, output_path)
        status_by_label = {check.label: check.status for check in checks}
        detail_by_label = {check.label: check.detail for check in checks}

        self.assertEqual(status_by_label["10 段模板"], "FAIL")
        self.assertIn("编号顺序不合法", detail_by_label["10 段模板"])

    def test_generic_output_fails_when_numbered_sections_are_duplicated(self) -> None:
        spec = test_runner.load_test_case(ROOT_DIR / "test_cases" / "test_01.md")
        output_path = self.write_output(
            build_full_output(
                section_6=(
                    "- **原创示例句**（3 条）：\n"
                    "1. 渡口的旧灯照着潮痕。\n"
                    "2. 宣纸把晚风折成一页。\n"
                    "3. 木船没说话，只晃了晃绳结。"
                ),
                section_7="Piano 为主，副歌加入 Strings 和鼓组。",
                suffix="### 9. 原创性风险检查（补写）\nPASS",
            )
        )

        checks = test_runner.validate_output_for_test(spec, output_path)
        status_by_label = {check.label: check.status for check in checks}
        detail_by_label = {check.label: check.detail for check in checks}

        self.assertEqual(status_by_label["10 段模板"], "FAIL")
        self.assertIn("存在重复编号章节: 9", detail_by_label["10 段模板"])

    def test_test_02_clarification_only_output_skips_generic_10_section_checks(self) -> None:
        spec = test_runner.load_test_case(ROOT_DIR / "test_cases" / "test_02.md")
        output_path = self.write_output(
            "你更想写的是独处、等待，还是告别？\n"
            "这首歌希望最后停在压抑、释怀，还是平静？\n"
        )

        checks = test_runner.validate_output_for_test(spec, output_path)
        labels = {check.label for check in checks}

        self.assertIn("冷启动澄清", labels)
        self.assertNotIn("10 段模板", labels)
        self.assertNotIn("Similarity Guard", labels)
        self.assertNotIn("去相似化建议", labels)

    def test_test_02_full_plan_passes_when_all_five_requested_parameters_have_evidence(self) -> None:
        spec = test_runner.load_test_case(ROOT_DIR / "test_cases" / "test_02.md")
        output_path = self.write_output(
            (
                "我先为你默认一个主题：便利店打烊前的城市独处，如果不对请指定。\n\n"
                + build_full_output(
                    section_6=(
                        "主题围绕便利店白灯、末班车站牌和霓虹倒影展开，保持小调都市感。"
                    ),
                    section_7=(
                        "Verse 用 Rhodes 电钢铺底，保留轻 R&B 反拍律动；"
                        "副歌让 Warm Pad 扩张打开空间，城市夜景意象继续留在路灯与街口。"
                    ),
                )
            )
        )

        checks = test_runner.validate_output_for_test(spec, output_path)
        statuses = {check.label: check.status for check in checks}

        self.assertEqual(statuses["默认主题说明"], "PASS")
        self.assertEqual(statuses["参数覆盖"], "PASS")

    def test_test_02_full_plan_fails_when_requested_parameters_are_missing_from_output(self) -> None:
        spec = test_runner.load_test_case(ROOT_DIR / "test_cases" / "test_02.md")
        output_path = self.write_output(
            (
                "我先为你默认一个主题：深夜独处，如果不对请指定。\n\n"
                + build_full_output(
                    section_6="主题只停留在抽象独处，没有城市夜景物件。",
                    section_7="编曲以钢琴和弦乐为主，节奏克制但没有额外的风格说明。",
                )
            )
        )

        checks = test_runner.validate_output_for_test(spec, output_path)
        status_by_label = {check.label: check.status for check in checks}
        detail_by_label = {check.label: check.detail for check in checks}

        self.assertEqual(status_by_label["默认主题说明"], "PASS")
        self.assertEqual(status_by_label["参数覆盖"], "FAIL")
        self.assertIn("轻 R&B", detail_by_label["参数覆盖"])
        self.assertIn("电钢铺底", detail_by_label["参数覆盖"])

    def test_test_04_requires_explicit_harmony_and_hook_similarity_verdicts(self) -> None:
        spec = test_runner.load_test_case(ROOT_DIR / "test_cases" / "test_04.md")
        output_path = self.write_output(
            (
                "不能直接照着《晴天》逐字逐句复制，这会碰到版权边界；我改为保留你想要的少年感和钢琴底色，给你一份原创替代方案。\n\n"
                + build_full_output(
                    section_6=(
                        "- **原创示例句**（3 条）：\n"
                        "1. 操场边的长椅把影子拉得很慢。\n"
                        "2. 铅笔屑停在课本折角，像没说完的话。\n"
                        "3. 风从旧楼梯口经过，却没带走那句再见。"
                    ),
                    section_7="Piano 主导，Pre 末尾进 Strings，C3 再开鼓组。",
                    section_9=(
                        "- 和声相似度：PASS —— 避开原作标志性走向，只保留温暖大调的气质。\n"
                        "- Hook 相似度：BLOCK —— 首句不要沿用原作句法，改用新的节奏锚点。\n"
                        "- 总体：PASS"
                    ),
                )
            )
        )

        checks = test_runner.validate_output_for_test(spec, output_path)
        status_by_label = {check.label: check.status for check in checks}

        self.assertEqual(status_by_label["复制请求拒绝"], "PASS")
        self.assertEqual(status_by_label["原句复用"], "PASS")
        self.assertEqual(status_by_label["相似度子项"], "PASS")

    def test_test_04_fails_when_similarity_subchecks_are_missing(self) -> None:
        spec = test_runner.load_test_case(ROOT_DIR / "test_cases" / "test_04.md")
        output_path = self.write_output(
            (
                "不能直接复制《晴天》，因为这会涉及版权问题；我改用相近气质但不复用具体歌词或和弦的原创方案。\n\n"
                + build_full_output(
                    section_6=(
                        "- **原创示例句**（3 条）：\n"
                        "1. 午后的栏杆还留着太阳退场后的温度。\n"
                        "2. 旧校车把街角的风吹成一层白雾。\n"
                        "3. 你没回头，我也把名字收进外套口袋。"
                    ),
                    section_7="Piano 主导，副歌前加一层 Pad，Bridge 退鼓。",
                    section_9="总体：PASS —— 没有直接复用原句，保留少年回忆气质。",
                )
            )
        )

        checks = test_runner.validate_output_for_test(spec, output_path)
        status_by_label = {check.label: check.status for check in checks}
        detail_by_label = {check.label: check.detail for check in checks}

        self.assertEqual(status_by_label["相似度子项"], "FAIL")
        self.assertIn("和声相似度", detail_by_label["相似度子项"])
        self.assertIn("Hook 相似度", detail_by_label["相似度子项"])

    def test_test_05_clarification_only_output_skips_generic_10_section_checks(self) -> None:
        spec = test_runner.load_test_case(ROOT_DIR / "test_cases" / "test_05.md")
        output_path = self.write_output(
            "这首歌想讲一段经历、一个场景，还是一种情绪？\n"
            "开始是什么情绪，结束又想停在哪种感觉？\n"
            "你更想让它偏钢琴抒情，还是轻 R&B / 城市夜景？\n"
        )

        checks = test_runner.validate_output_for_test(spec, output_path)
        labels = {check.label for check in checks}

        self.assertIn("冷启动行为", labels)
        self.assertNotIn("10 段模板", labels)
        self.assertNotIn("Similarity Guard", labels)
        self.assertNotIn("去相似化建议", labels)

    def test_test_06_fusion_output_checks_ratio_markers_and_notes(self) -> None:
        spec = test_runner.load_test_case(ROOT_DIR / "test_cases" / "test_06.md")
        output_path = self.write_output(
            build_full_output(
                section_6="方文山系白描：渡口、檐角、宣纸与潮汐，不直说想念。",
                section_7=(
                    "- Intro: 古筝采样 [JC] + Synth Pad [F]\n"
                    "- Verse: Piano 分解和弦 [JC] + Arpeggiator [F]\n"
                    "- Chorus: 情绪弧线 [JC] + Sub bass [F] + 和声点缀 [MIX]\n"
                    "- 比例：50:50"
                ),
                suffix=(
                    "### 融合说明 Fusion Notes\n"
                    "- 融合方案：周杰伦 × electronic（50:50）\n"
                    "- 保留维度：结构与情绪弧线 [JC]\n"
                    "- 融合维度：编曲、节奏、音色 [MIX]\n"
                ),
            )
        )

        checks = test_runner.validate_output_for_test(spec, output_path)
        statuses = {check.label: check.status for check in checks}

        self.assertEqual(statuses["融合比例"], "PASS")
        self.assertEqual(statuses["融合来源标记"], "PASS")
        self.assertEqual(statuses["融合说明"], "PASS")
        self.assertEqual(statuses["融合侧音色"], "PASS")

    def test_test_06_accepts_numbered_fusion_notes_as_section_11(self) -> None:
        spec = test_runner.load_test_case(ROOT_DIR / "test_cases" / "test_06.md")
        output_path = self.write_output(
            build_full_output(
                section_6="方文山系白描：木牌、檐角、宣纸与潮痕，不直说离别。",
                section_7=(
                    "- Intro: 古筝采样 [JC] + Synth Pad [F]\n"
                    "- Verse: Piano 分解和弦 [JC] + Arpeggiator [F]\n"
                    "- Chorus: 情绪弧线 [JC] + Sub bass [F] + 和声点缀 [MIX]\n"
                    "- 比例：50:50"
                ),
                suffix=(
                    "#### 11. 融合说明 Fusion Notes\n"
                    "- 融合方案：周杰伦 × electronic（50:50）\n"
                    "- 保留维度：结构与情绪弧线 [JC]\n"
                    "- 融合维度：编曲、节奏、音色 [MIX]\n"
                ),
            )
        )

        checks = test_runner.validate_output_for_test(spec, output_path)
        statuses = {check.label: check.status for check in checks}

        self.assertEqual(statuses["10 段模板"], "PASS")
        self.assertEqual(statuses["融合说明"], "PASS")
        self.assertEqual(statuses["融合来源标记"], "PASS")

    def test_test_06_missing_fusion_notes_fails(self) -> None:
        spec = test_runner.load_test_case(ROOT_DIR / "test_cases" / "test_06.md")
        output_path = self.write_output(
            build_full_output(
                section_6="白描句法写渡口和宣纸，保留方文山系留白。",
                section_7=(
                    "- Intro: Piano [JC] + Synth Pad [F]\n"
                    "- Chorus: Sub bass [F] + 和声框架 [MIX]\n"
                    "- Outro: 50:50 对半融合"
                ),
            )
        )

        checks = test_runner.validate_output_for_test(spec, output_path)
        statuses = {check.label: check.status for check in checks}

        self.assertEqual(statuses["融合比例"], "PASS")
        self.assertEqual(statuses["融合来源标记"], "PASS")
        self.assertEqual(statuses["融合说明"], "FAIL")


class EvaluateTests(unittest.TestCase):
    def test_output_dir_directory_entry_becomes_warning_instead_of_traceback(self) -> None:
        spec = test_runner.load_test_case(ROOT_DIR / "test_cases" / "test_01.md")

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            (output_dir / "test_01.md").mkdir()

            results = test_runner.evaluate([spec], output_path=None, output_dir=output_dir)

        self.assertEqual(len(results), 1)
        result = results[0]
        warning_map = {check.label: check.detail for check in result.checks if check.status == "WARN"}

        self.assertIsNone(result.output_path)
        self.assertIn("生成结果", warning_map)
        self.assertEqual(warning_map["生成结果"], "匹配路径不是文件: test_01.md")


if __name__ == "__main__":
    unittest.main()
