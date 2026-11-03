"""Windows DPI initialization and DPI-scaled window/layout dimensions."""

import ctypes
import sys
from ctypes import wintypes


def enable_windows_dpi_awareness():
    """Opt into system DPI before Tk starts, preserving any host-defined mode."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        try:
            setter = user32.SetProcessDpiAwarenessContext
        except AttributeError:
            setter = None
        if setter is not None:
            setter.argtypes = [ctypes.c_void_p]
            setter.restype = wintypes.BOOL
            # Tk 8.6 does not reliably rescale its content between unlike monitors.
            if setter(ctypes.c_void_p(-2)):  # DPI_AWARENESS_CONTEXT_SYSTEM_AWARE
                return True
            if ctypes.get_last_error() != 87:  # ERROR_INVALID_PARAMETER
                # Access denied means the host/manifest already set the mode.
                return False
        legacy_setter = user32.SetProcessDPIAware
        legacy_setter.argtypes = []
        legacy_setter.restype = wintypes.BOOL
        return bool(legacy_setter())
    except (AttributeError, OSError):
        return False


def _work_area_bounds(root):
    if sys.platform == "win32":
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            get_work_area = user32.SystemParametersInfoW
            get_work_area.argtypes = [
                wintypes.UINT, wintypes.UINT, ctypes.POINTER(wintypes.RECT), wintypes.UINT
            ]
            get_work_area.restype = wintypes.BOOL
            area = wintypes.RECT()
            if get_work_area(0x0030, 0, ctypes.byref(area), 0):  # SPI_GETWORKAREA
                width, height = area.right - area.left, area.bottom - area.top
                if width > 0 and height > 0:
                    return area.left, area.top, area.right, area.bottom
        except (AttributeError, OSError):
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


class DisplaySettings:
    def __init__(self, root):
        self.root = root
        # Fonts already use Tk's DPI-aware point sizes; only scale pixel lengths.
        # Round away small errors in Tk's millimetre-based DPI calculation.
        self.scale = (
            round(root.winfo_fpixels("1i") / 96, 2)
            if sys.platform == "win32" else 1.0
        )

    def pixels(self, value):
        return round(value * self.scale)

    def configure_window(self):
        left, top, right, bottom = _work_area_bounds(self.root)
        area_width, area_height = right - left, bottom - top
        # Leave room for window borders/title bar, including on small displays.
        max_width = max(1, area_width - self.pixels(32))
        max_height = max(1, area_height - self.pixels(64))
        width = min(self.pixels(1200), max_width)
        height = min(self.pixels(800), max_height)
        x = left + max(0, (area_width - width) // 2)
        y = top + max(0, (area_height - height - self.pixels(48)) // 2)
        self.root.geometry(f"{width}x{height}{x:+d}{y:+d}")
        self.root.minsize(
            min(self.pixels(800), max_width), min(self.pixels(600), max_height)
        )
