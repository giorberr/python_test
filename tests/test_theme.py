"""Native title-bar styling, with portable mocks and a real Windows check."""

import ctypes
import sys
import tkinter as tk
import unittest
from ctypes import wintypes
from unittest.mock import Mock, patch

from practice import theme


class WindowsTitleBarTests(unittest.TestCase):
    def setUp(self):
        self.root = Mock()
        self.root.winfo_id.return_value = 0x12345678
        self.user32 = Mock(spec=["GetAncestor"])
        self.user32.GetAncestor.return_value = 0x123456789
        self.dwmapi = Mock(spec=["DwmSetWindowAttribute"])
        self.setter = self.dwmapi.DwmSetWindowAttribute
        self.setter.return_value = 0
        platform = patch.object(theme.sys, "platform", "win32")
        platform.start()
        self.addCleanup(platform.stop)
        loader = patch.object(
            theme.ctypes, "WinDLL", create=True,
            side_effect=lambda name, **kwargs: {
                "user32": self.user32, "dwmapi": self.dwmapi,
            }[name],
        )
        self.load_dll = loader.start()
        self.addCleanup(loader.stop)

    def test_modern_attribute_targets_pointer_sized_outer_window(self):
        def check_attribute(hwnd, attribute, value, size):
            self.assertEqual(hwnd, 0x123456789)
            self.assertEqual(attribute, 20)
            self.assertEqual(size, ctypes.sizeof(wintypes.BOOL))
            self.assertEqual(
                ctypes.cast(value, ctypes.POINTER(wintypes.BOOL)).contents.value, 1
            )
            return 0

        self.setter.side_effect = check_attribute
        self.assertIs(theme._apply_windows_dark_title_bar(self.root), True)
        self.user32.GetAncestor.assert_called_once_with(0x12345678, 2)
        self.assertEqual(
            self.user32.GetAncestor.argtypes, [wintypes.HWND, wintypes.UINT]
        )
        self.assertIs(self.user32.GetAncestor.restype, wintypes.HWND)
        self.assertEqual(self.setter.argtypes, [
            wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ])
        self.assertIs(self.setter.restype, ctypes.c_long)
        self.setter.assert_called_once()

    def test_older_windows_attribute_is_used_as_fallback(self):
        self.setter.side_effect = [-2147024809, 0]
        self.assertIs(theme._apply_windows_dark_title_bar(self.root), True)
        self.assertEqual(
            [call.args[1] for call in self.setter.call_args_list], [20, 19]
        )

    def test_unsupported_attributes_are_nonfatal(self):
        self.setter.return_value = -2147024809
        self.assertIs(theme._apply_windows_dark_title_bar(self.root), False)
        self.assertEqual(self.setter.call_count, 2)

    def test_missing_native_support_is_nonfatal(self):
        for error in (OSError("DLL unavailable"), AttributeError("No export")):
            with self.subTest(error=error):
                self.load_dll.side_effect = error
                self.assertIs(theme._apply_windows_dark_title_bar(self.root), False)
        self.setter.assert_not_called()

    def test_missing_outer_window_does_not_set_attributes(self):
        self.user32.GetAncestor.return_value = None
        self.assertIs(theme._apply_windows_dark_title_bar(self.root), False)
        self.setter.assert_not_called()

    def test_destroyed_tk_window_is_nonfatal(self):
        self.root.winfo_id.side_effect = tk.TclError("Window destroyed")
        self.assertIs(theme._apply_windows_dark_title_bar(self.root), False)
        self.setter.assert_not_called()

    def test_other_platforms_do_not_call_windows_apis(self):
        for platform in ("linux", "darwin"):
            with self.subTest(platform=platform), patch.object(
                theme.sys, "platform", platform
            ):
                self.assertIs(theme._apply_windows_dark_title_bar(self.root), False)
        self.load_dll.assert_not_called()
        self.root.winfo_id.assert_not_called()


class ThemeMappingTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display is unavailable: {error}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def test_title_bar_is_styled_on_mapping_and_remapping_only(self):
        mapped = Mock()
        self.root.bind("<Map>", mapped)
        with patch.object(theme.sys, "platform", "win32"), patch.object(
            theme, "_apply_windows_dark_title_bar"
        ) as darken:
            theme.apply_dark_theme(self.root)
            darken.assert_not_called()
            self.root.deiconify()
            self.root.update()
            darken.assert_called_once_with(self.root)
            mapped.assert_called_once()
            child = theme.ttk.Frame(self.root)
            child.pack()
            self.root.update()
            darken.assert_called_once_with(self.root)
            self.root.withdraw()
            self.root.update()
            self.root.deiconify()
            self.root.update()
            self.assertEqual(darken.call_count, 2)

    @unittest.skipUnless(sys.platform == "win32", "Windows DWM integration")
    def test_native_title_bar_dark_mode_survives_remapping(self):
        theme.apply_dark_theme(self.root)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_ancestor = user32.GetAncestor
        get_ancestor.argtypes = [wintypes.HWND, wintypes.UINT]
        get_ancestor.restype = wintypes.HWND
        get_attribute = ctypes.WinDLL("dwmapi").DwmGetWindowAttribute
        get_attribute.argtypes = [
            wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
        ]
        get_attribute.restype = ctypes.c_long
        for mapping in ("first display", "restored window"):
            with self.subTest(mapping=mapping):
                self.root.deiconify()
                self.root.update()
                hwnd = get_ancestor(self.root.winfo_id(), 2)
                enabled = wintypes.BOOL()
                for attribute in (20, 19):
                    result = get_attribute(
                        hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)
                    )
                    if result == 0:
                        break
                else:
                    self.skipTest("Windows does not expose dark title-bar attributes")
                self.assertEqual(enabled.value, 1)
                self.root.withdraw()
                self.root.update()


if __name__ == "__main__":
    unittest.main()
