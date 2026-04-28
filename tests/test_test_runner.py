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


if __name__ == "__main__":
    unittest.main()
