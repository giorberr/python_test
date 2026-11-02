"""Keep the root launcher and data paths safe after repository reorganization."""

import runpy
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from practice import app

ROOT = Path(__file__).resolve().parent.parent


class EntryPointTests(unittest.TestCase):
    def test_root_launcher_calls_main(self):
        with patch.object(app, 'main') as main:
            runpy.run_path(str(ROOT / 'app.py'), run_name='__main__')
        main.assert_called_once_with()

    def test_multiprocessing_child_import_does_not_open_another_window(self):
        with patch.object(app, 'main') as main:
            runpy.run_path(str(ROOT / 'app.py'), run_name='__mp_main__')
        main.assert_not_called()

    def test_main_builds_the_app_and_enters_event_loop(self):
        root = Mock()
        with patch.object(app.tk, 'Tk', return_value=root), patch.object(app, 'PracticeApp') as interface:
            app.main()
        interface.assert_called_once_with(root)
        root.mainloop.assert_called_once_with()

    def test_progress_path_is_in_data_not_working_directory(self):
        self.assertEqual(app.DATA_FILE, ROOT / 'data' / 'practice_progress.json')
        self.assertTrue(app.DATA_FILE.is_absolute())


if __name__ == '__main__':
    unittest.main()
