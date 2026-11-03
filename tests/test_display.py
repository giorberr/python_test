"""Display behavior without creating Tk windows or changing process DPI."""

import ctypes
import unittest
from ctypes import wintypes
from unittest.mock import Mock, patch

from practice import display


class DpiAwarenessTests(unittest.TestCase):
    def setUp(self):
        self.user32 = Mock(spec=[
            'SetProcessDpiAwarenessContext', 'SetProcessDPIAware',
        ])
        self.modern = self.user32.SetProcessDpiAwarenessContext
        self.modern.return_value = 1
        self.legacy = self.user32.SetProcessDPIAware
        self.legacy.return_value = 1
        platform = patch.object(display.sys, 'platform', 'win32')
        platform.start()
        self.addCleanup(platform.stop)
        loader = patch.object(
            display.ctypes, 'WinDLL', return_value=self.user32, create=True
        )
        self.load_dll = loader.start()
        self.addCleanup(loader.stop)
        last_error = patch.object(
            display.ctypes, 'get_last_error', return_value=0, create=True
        )
        self.last_error = last_error.start()
        self.addCleanup(last_error.stop)

    def test_non_windows_makes_no_native_calls(self):
        for platform in ('linux', 'darwin'):
            with self.subTest(platform=platform), patch.object(
                display.sys, 'platform', platform
            ):
                self.assertIs(display.enable_windows_dpi_awareness(), False)
        self.load_dll.assert_not_called()
        self.modern.assert_not_called()
        self.legacy.assert_not_called()
        self.last_error.assert_not_called()

    def test_context_success_uses_pointer_sized_system_awareness(self):
        self.modern.return_value = 7
        self.last_error.return_value = 5
        self.assertIs(display.enable_windows_dpi_awareness(), True)
        self.load_dll.assert_called_once_with('user32', use_last_error=True)
        self.modern.assert_called_once()
        context, = self.modern.call_args.args
        self.assertIsInstance(context, ctypes.c_void_p)
        self.assertEqual(context.value, ctypes.c_void_p(-2).value)
        self.assertEqual(self.modern.argtypes, [ctypes.c_void_p])
        self.assertIs(self.modern.restype, wintypes.BOOL)
        self.last_error.assert_not_called()
        self.legacy.assert_not_called()

    def test_missing_context_export_falls_back_to_legacy(self):
        del self.user32.SetProcessDpiAwarenessContext
        self.assertIs(display.enable_windows_dpi_awareness(), True)
        self.modern.assert_not_called()
        self.last_error.assert_not_called()
        self.legacy.assert_called_once_with()
        self.assertEqual(self.legacy.argtypes, [])
        self.assertIs(self.legacy.restype, wintypes.BOOL)
        self.load_dll.assert_called_once_with('user32', use_last_error=True)

    def test_invalid_context_parameter_falls_back_to_legacy(self):
        self.modern.return_value = 0
        self.last_error.return_value = 87
        calls = Mock()
        calls.attach_mock(self.modern, 'modern')
        calls.attach_mock(self.last_error, 'last_error')
        calls.attach_mock(self.legacy, 'legacy')
        self.assertIs(display.enable_windows_dpi_awareness(), True)
        self.assertEqual(
            [entry[0] for entry in calls.mock_calls],
            ['modern', 'last_error', 'legacy'],
        )
        self.last_error.assert_called_once_with()
        self.legacy.assert_called_once_with()

    def test_already_configured_process_does_not_fall_back(self):
        self.modern.return_value = 0
        self.last_error.return_value = 5
        self.assertIs(display.enable_windows_dpi_awareness(), False)
        self.last_error.assert_called_once_with()
        self.legacy.assert_not_called()

    def test_other_context_errors_do_not_fall_back(self):
        self.modern.return_value = 0
        for error in (0, 31, 120):
            with self.subTest(error=error):
                self.last_error.return_value = error
                self.assertIs(display.enable_windows_dpi_awareness(), False)
        self.assertEqual(self.modern.call_count, 3)
        self.assertEqual(self.last_error.call_count, 3)
        self.legacy.assert_not_called()

    def test_context_call_oserror_does_not_fall_back(self):
        self.modern.side_effect = OSError('Context call failed')
        self.assertIs(display.enable_windows_dpi_awareness(), False)
        self.last_error.assert_not_called()
        self.legacy.assert_not_called()

    def test_missing_user32_is_nonfatal(self):
        self.load_dll.side_effect = OSError('DLL unavailable')
        self.assertIs(display.enable_windows_dpi_awareness(), False)
        self.modern.assert_not_called()
        self.last_error.assert_not_called()
        self.legacy.assert_not_called()

    def test_missing_legacy_export_is_nonfatal(self):
        del self.user32.SetProcessDpiAwarenessContext
        del self.user32.SetProcessDPIAware
        self.assertIs(display.enable_windows_dpi_awareness(), False)
        self.last_error.assert_not_called()
        self.legacy.assert_not_called()

    def test_failed_legacy_call_does_not_read_last_error(self):
        del self.user32.SetProcessDpiAwarenessContext
        self.legacy.return_value = 0
        self.last_error.return_value = 87
        self.assertIs(display.enable_windows_dpi_awareness(), False)
        self.legacy.assert_called_once_with()
        self.last_error.assert_not_called()

    def test_legacy_call_oserror_is_nonfatal(self):
        del self.user32.SetProcessDpiAwarenessContext
        self.legacy.side_effect = OSError('Legacy call failed')
        self.assertIs(display.enable_windows_dpi_awareness(), False)
        self.legacy.assert_called_once_with()
        self.last_error.assert_not_called()


class WorkAreaTests(unittest.TestCase):
    def setUp(self):
        self.root = Mock(spec=['winfo_screenwidth', 'winfo_screenheight'])
        self.root.winfo_screenwidth.return_value = 1920
        self.root.winfo_screenheight.return_value = 1080
        self.bounds = (120, 80, 1720, 980)
        self.native_result = 1
        self.user32 = Mock(spec=['SystemParametersInfoW'])
        self.get_work_area = self.user32.SystemParametersInfoW
        self.get_work_area.side_effect = self.fill_work_area
        platform = patch.object(display.sys, 'platform', 'win32')
        platform.start()
        self.addCleanup(platform.stop)
        loader = patch.object(
            display.ctypes, 'WinDLL', return_value=self.user32, create=True
        )
        self.load_dll = loader.start()
        self.addCleanup(loader.stop)

    def fill_work_area(self, action, parameter, output, flags):
        area = ctypes.cast(output, ctypes.POINTER(wintypes.RECT)).contents
        area.left, area.top, area.right, area.bottom = self.bounds
        return self.native_result

    def assert_screen_fallback(self):
        self.assertEqual(display._work_area_bounds(self.root), (0, 0, 1920, 1080))
        self.root.winfo_screenwidth.assert_called_once_with()
        self.root.winfo_screenheight.assert_called_once_with()

    def test_native_work_area_preserves_rectangle_bounds_and_signature(self):
        self.assertEqual(
            display._work_area_bounds(self.root), (120, 80, 1720, 980)
        )
        self.load_dll.assert_called_once_with('user32', use_last_error=True)
        self.get_work_area.assert_called_once()
        action, parameter, output, flags = self.get_work_area.call_args.args
        self.assertEqual((action, parameter, flags), (0x0030, 0, 0))
        self.assertEqual(self.get_work_area.argtypes, [
            wintypes.UINT, wintypes.UINT, ctypes.POINTER(wintypes.RECT),
            wintypes.UINT,
        ])
        self.assertIs(self.get_work_area.restype, wintypes.BOOL)
        self.root.winfo_screenwidth.assert_not_called()
        self.root.winfo_screenheight.assert_not_called()

    def test_native_work_area_accepts_negative_origin(self):
        self.bounds = (-1600, -100, 0, 800)
        self.assertEqual(
            display._work_area_bounds(self.root), (-1600, -100, 0, 800)
        )
        self.root.winfo_screenwidth.assert_not_called()
        self.root.winfo_screenheight.assert_not_called()

    def test_failed_native_call_ignores_even_a_valid_rectangle(self):
        self.native_result = 0
        self.assert_screen_fallback()
        self.get_work_area.assert_called_once()

    def test_invalid_native_rectangles_fall_back_to_screen(self):
        for bounds in (
            (100, 20, 100, 920),
            (100, 20, 99, 920),
            (100, 20, 1700, 20),
            (100, 20, 1700, 19),
            (0, 0, 0, 0),
        ):
            with self.subTest(bounds=bounds):
                self.bounds = bounds
                self.root.reset_mock()
                self.assert_screen_fallback()

    def test_missing_native_export_falls_back_to_screen(self):
        del self.user32.SystemParametersInfoW
        self.assert_screen_fallback()
        self.get_work_area.assert_not_called()

    def test_missing_dll_falls_back_to_screen(self):
        self.load_dll.side_effect = OSError('DLL unavailable')
        self.assert_screen_fallback()
        self.get_work_area.assert_not_called()

    def test_native_call_oserror_falls_back_to_screen(self):
        self.get_work_area.side_effect = OSError('Work-area call failed')
        self.assert_screen_fallback()

    def test_non_windows_uses_screen_without_native_calls(self):
        for platform in ('linux', 'darwin'):
            with self.subTest(platform=platform), patch.object(
                display.sys, 'platform', platform
            ):
                self.root.reset_mock()
                self.assert_screen_fallback()
        self.load_dll.assert_not_called()
        self.get_work_area.assert_not_called()


class DisplaySettingsTests(unittest.TestCase):
    def setUp(self):
        self.root = Mock(spec=['winfo_fpixels', 'geometry', 'minsize'])
        self.root.winfo_fpixels.return_value = 96
        platform = patch.object(display.sys, 'platform', 'win32')
        platform.start()
        self.addCleanup(platform.stop)
        work_area = patch.object(
            display, '_work_area_bounds', return_value=(0, 0, 4096, 2160)
        )
        self.work_area = work_area.start()
        self.addCleanup(work_area.stop)
        loader = patch.object(
            display.ctypes, 'WinDLL', create=True,
            side_effect=AssertionError('Layout tests must not call native APIs'),
        )
        self.load_dll = loader.start()
        self.addCleanup(loader.stop)
        self.addCleanup(self.load_dll.assert_not_called)

    def test_windows_pixel_scaling_at_common_display_percentages(self):
        for dpi, scale, padding, width in (
            (96, 1.0, 32, 1200),
            (120, 1.25, 40, 1500),
            (144, 1.5, 48, 1800),
            (192, 2.0, 64, 2400),
        ):
            with self.subTest(dpi=dpi):
                self.root.reset_mock()
                self.root.winfo_fpixels.return_value = dpi
                settings = display.DisplaySettings(self.root)
                self.assertIs(settings.root, self.root)
                self.assertEqual(settings.scale, scale)
                self.assertEqual(settings.pixels(0), 0)
                self.assertEqual(settings.pixels(32), padding)
                self.assertEqual(settings.pixels(1200), width)
                self.assertIsInstance(settings.pixels(32), int)
                self.root.winfo_fpixels.assert_called_once_with('1i')

    def test_fractional_pixel_lengths_round_to_nearest_integer(self):
        self.root.winfo_fpixels.return_value = 120
        settings = display.DisplaySettings(self.root)
        for value, expected in ((1, 1), (2, 2), (3, 4), (5, 6)):
            with self.subTest(value=value):
                self.assertEqual(settings.pixels(value), expected)

    def test_tk_dpi_noise_does_not_change_layout_dimensions(self):
        for dpi, scale, width in (
            (95.9, 1.0, 1200),
            (96.1, 1.0, 1200),
            (119.9, 1.25, 1500),
            (120.1, 1.25, 1500),
            (143.8, 1.5, 1800),
            (144.2, 1.5, 1800),
            (191.7, 2.0, 2400),
            (192.3, 2.0, 2400),
        ):
            with self.subTest(dpi=dpi):
                self.root.winfo_fpixels.return_value = dpi
                settings = display.DisplaySettings(self.root)
                self.assertEqual(settings.scale, scale)
                self.assertEqual(settings.pixels(1200), width)

    def test_large_work_area_preserves_scaled_window_and_minimum_sizes(self):
        for dpi, geometry, minimum in (
            (96, '1200x800+1448+656', (800, 600)),
            (120, '1500x1000+1298+550', (1000, 750)),
            (144, '1800x1200+1148+444', (1200, 900)),
            (192, '2400x1600+848+232', (1600, 1200)),
        ):
            with self.subTest(dpi=dpi):
                self.root.reset_mock()
                self.work_area.reset_mock()
                self.root.winfo_fpixels.return_value = dpi
                display.DisplaySettings(self.root).configure_window()
                self.work_area.assert_called_once_with(self.root)
                self.root.geometry.assert_called_once_with(geometry)
                self.root.minsize.assert_called_once_with(*minimum)

    def test_window_and_minimum_sizes_are_clamped_to_scaled_work_area(self):
        for dpi, work_area, geometry, minimum in (
            (96, (0, 0, 1024, 768), '992x704+16+8', (800, 600)),
            (120, (0, 0, 1366, 768), '1326x688+20+10', (1000, 688)),
            (144, (0, 0, 1600, 900), '1552x804+24+12', (1200, 804)),
            (192, (0, 0, 1920, 1080), '1856x952+32+16', (1600, 952)),
        ):
            with self.subTest(dpi=dpi, work_area=work_area):
                self.root.reset_mock()
                self.root.winfo_fpixels.return_value = dpi
                self.work_area.return_value = work_area
                display.DisplaySettings(self.root).configure_window()
                self.root.geometry.assert_called_once_with(geometry)
                self.root.minsize.assert_called_once_with(*minimum)

    def test_work_area_axes_are_clamped_independently(self):
        for work_area, geometry, minimum in (
            ((0, 0, 3000, 700), '1200x636+900+8', (800, 600)),
            ((0, 0, 700, 2000), '668x800+16+576', (668, 600)),
        ):
            with self.subTest(work_area=work_area):
                self.root.reset_mock()
                self.work_area.return_value = work_area
                display.DisplaySettings(self.root).configure_window()
                self.root.geometry.assert_called_once_with(geometry)
                self.root.minsize.assert_called_once_with(*minimum)

    def test_window_position_respects_left_and_top_work_area_offsets(self):
        self.root.winfo_fpixels.return_value = 144
        for bounds, geometry in (
            ((120, 0, 1720, 900), '1552x804+144+12'),
            ((0, 80, 1600, 980), '1552x804+24+92'),
            ((120, 80, 1720, 980), '1552x804+144+92'),
        ):
            with self.subTest(bounds=bounds):
                self.root.reset_mock()
                self.work_area.return_value = bounds
                display.DisplaySettings(self.root).configure_window()
                self.root.geometry.assert_called_once_with(geometry)
                self.root.minsize.assert_called_once_with(1200, 804)

    def test_tiny_displays_keep_geometry_and_minimum_sizes_positive(self):
        for dpi, work_area, geometry, minimum in (
            (96, (0, 0, 640, 480), '608x416+16+8', (608, 416)),
            (192, (0, 0, 100, 100), '36x1+32+1', (36, 1)),
            (192, (0, 0, 64, 128), '1x1+31+15', (1, 1)),
            (96, (0, 0, 1, 100), '1x36+0+8', (1, 36)),
            (96, (0, 0, 1, 1), '1x1+0+0', (1, 1)),
        ):
            with self.subTest(dpi=dpi, work_area=work_area):
                self.root.reset_mock()
                self.root.winfo_fpixels.return_value = dpi
                self.work_area.return_value = work_area
                display.DisplaySettings(self.root).configure_window()
                self.root.geometry.assert_called_once_with(geometry)
                self.root.minsize.assert_called_once_with(*minimum)

    def test_non_windows_preserves_unscaled_layout_even_at_high_dpi(self):
        for platform in ('linux', 'darwin'):
            with self.subTest(platform=platform), patch.object(
                display.sys, 'platform', platform
            ):
                self.root.reset_mock()
                self.root.winfo_fpixels.return_value = 192
                self.work_area.return_value = (0, 0, 1024, 768)
                settings = display.DisplaySettings(self.root)
                self.assertEqual(settings.scale, 1.0)
                self.assertEqual(settings.pixels(32), 32)
                self.assertEqual(settings.pixels(1200), 1200)
                settings.configure_window()
                self.root.geometry.assert_called_once_with('992x704+16+8')
                self.root.minsize.assert_called_once_with(800, 600)
                self.root.winfo_fpixels.assert_not_called()


if __name__ == '__main__':
    unittest.main()
