"""Keep the root launcher and data paths safe after repository reorganization."""

import runpy
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from practice import app

ROOT = Path(__file__).resolve().parent.parent


class EntryPointTests(unittest.TestCase):
    def test_root_launcher_calls_main(self):
        with patch.object(app, 'main') as main:
            runpy.run_path(str(ROOT / 'app.py'), run_name='__main__')
        main.assert_called_once_with()

    def test_multiprocessing_child_import_does_not_open_another_window(self):
        with patch.object(app, 'main') as main, patch.object(
            app, 'enable_windows_dpi_awareness'
        ) as enable_dpi:
            runpy.run_path(str(ROOT / 'app.py'), run_name='__mp_main__')
        main.assert_not_called()
        enable_dpi.assert_not_called()

    def test_main_builds_the_app_and_enters_event_loop(self):
        startup = Mock()
        root = startup.root
        startup.create_root.return_value = root
        with patch.object(
            app, 'enable_windows_dpi_awareness', startup.enable_dpi
        ), patch.object(app.tk, 'Tk', startup.create_root), patch.object(
            app, 'PracticeApp', startup.build_app
        ):
            app.main()
        self.assertEqual(startup.mock_calls, [
            call.enable_dpi(), call.create_root(), call.build_app(root),
            call.root.mainloop(),
        ])

    def test_progress_path_is_in_data_not_working_directory(self):
        self.assertEqual(app.DATA_FILE, ROOT / 'data' / 'practice_progress.json')
        self.assertTrue(app.DATA_FILE.is_absolute())


if __name__ == '__main__':
    unittest.main()
