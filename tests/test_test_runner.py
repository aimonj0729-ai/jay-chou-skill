from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import test_runner


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


if __name__ == "__main__":
    unittest.main()
