from __future__ import annotations

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


class ValidateOutputForTestTests(unittest.TestCase):
    def write_output(self, body: str) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        output_path = Path(temp_dir.name) / "output.md"
        output_path.write_text(body, encoding="utf-8")
        return output_path

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


if __name__ == "__main__":
    unittest.main()
