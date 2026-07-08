"""透明调试框 —— 用红色矩形标出当前识别区域，不遮挡操作。"""

from __future__ import annotations

import logging

import win32api
import win32con
import win32gui

logger = logging.getLogger(__name__)

_hwnd: int | None = None
_class_atom: int | None = None

# 透明色键值：黑色 RGB(0,0,0) 的部分会被设为透明
_KEY_COLOR = win32api.RGB(0, 0, 0)


def _wndproc(hwnd: int, msg: int, wparam: int, lparam: int) -> int:
    """窗口过程。"""
    try:
        if msg == win32con.WM_PAINT:
            _paint(hwnd)
            return 0
        if msg == win32con.WM_ERASEBKGND:
            return 1
    except Exception:
        pass
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def _paint(hwnd: int) -> None:
    """绘制：黑色背景（透明）上画 2px 红色矩形边框，四边严格等宽。"""
    hdc, ps = win32gui.BeginPaint(hwnd)
    try:
        _, _, right, bottom = win32gui.GetClientRect(hwnd)

        # 全窗填充黑色（黑色 = 透明色键 → 不可见）
        black_brush = win32gui.GetStockObject(win32con.BLACK_BRUSH)
        win32gui.FillRect(hdc, (0, 0, right, bottom), black_brush)

        # 四条边用填充矩形绘制，避免 GDI 画笔居中导致的边缘不对称
        red_brush = win32gui.CreateSolidBrush(win32api.RGB(255, 0, 0))
        old_brush = win32gui.SelectObject(hdc, red_brush)

        # 上边 (0,0)-(w,2)    下边 (0,h-2)-(w,h)
        # 左边 (0,0)-(2,h)    右边 (w-2,0)-(w,h)
        win32gui.FillRect(hdc, (0, 0, right, 2), red_brush)
        win32gui.FillRect(hdc, (0, bottom - 2, right, bottom), red_brush)
        win32gui.FillRect(hdc, (0, 0, 2, bottom), red_brush)
        win32gui.FillRect(hdc, (right - 2, 0, right, bottom), red_brush)

        win32gui.SelectObject(hdc, old_brush)
        win32gui.DeleteObject(red_brush)
    finally:
        win32gui.EndPaint(hwnd, ps)


def create_overlay() -> int | None:
    """创建透明覆盖窗口。"""
    global _hwnd, _class_atom

    if _hwnd is not None:
        return _hwnd

    hinst = win32api.GetModuleHandle(None)

    if _class_atom is None:
        wc = win32gui.WNDCLASS()
        wc.hInstance = hinst
        wc.lpszClassName = "YachtDebugOverlay"
        wc.lpfnWndProc = _wndproc
        wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        wc.hbrBackground = win32con.COLOR_WINDOW + 1
        _class_atom = win32gui.RegisterClass(wc)

    ex_style = (
            win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_LAYERED
            | win32con.WS_EX_TOPMOST
            | win32con.WS_EX_TOOLWINDOW
    )
    hwnd = win32gui.CreateWindowEx(
        ex_style,
        _class_atom,
        "",
        win32con.WS_POPUP,
        0, 0, 0, 0,
        0, 0, hinst, None,
    )

    if not hwnd:
        logger.error("创建调试框失败")
        return None

    # 颜色键透明：黑色(RGB 0,0,0) 部分完全透明
    win32gui.SetLayeredWindowAttributes(hwnd, _KEY_COLOR, 0, win32con.LWA_COLORKEY)

    _hwnd = hwnd
    return hwnd


def show_overlay(bbox: tuple[int, int, int, int] | None) -> None:
    """移动/显示/隐藏调试框。"""
    if _hwnd is None:
        return

    if bbox is None:
        win32gui.ShowWindow(_hwnd, win32con.SW_HIDE)
        return

    left, top, right, bottom = bbox
    w, h = right - left, bottom - top

    win32gui.SetWindowPos(
        _hwnd, win32con.HWND_TOPMOST,
        left, top, w, h,
        win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE,
    )
    win32gui.InvalidateRect(_hwnd, None, True)


def destroy_overlay() -> None:
    """销毁调试框。"""
    global _hwnd
    if _hwnd is not None:
        win32gui.DestroyWindow(_hwnd)
        _hwnd = None
