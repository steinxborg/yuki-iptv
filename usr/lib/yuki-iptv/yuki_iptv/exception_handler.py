#
# Copyright (c) 2025 liya <liyaastrova@proton.me>
#
# This file is part of yuki-iptv.
#
# yuki-iptv is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# yuki-iptv is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with yuki-iptv. If not, see <https://www.gnu.org/licenses/>.
#
# The Font Awesome pictograms are licensed under the CC BY 4.0 License.
# Font Awesome Free 5.15.4 by @fontawesome - https://fontawesome.com
# https://creativecommons.org/licenses/by/4.0/
#
import sys
from yuki_iptv.qt import show_exception
from yuki_iptv.threads import force_kill_childs


def format_tb_data(tb):
    try:
        filename = tb.tb_frame.f_code.co_filename
    except Exception:
        filename = "?"
    try:
        name = tb.tb_frame.f_code.co_name
    except Exception:
        name = "?"
    try:
        line_no = tb.tb_lineno
    except Exception:
        line_no = "?"
    return filename, name, line_no


def yuki_excepthook(exctype, value, tb):
    # Ignore KeyboardInterrupt
    if issubclass(exctype, KeyboardInterrupt):
        return
    filename, name, line_no = format_tb_data(tb)
    show_exception(
        f"CRITICAL: {filename}\n{name}\n{line_no}\n{exctype.__name__}\n{value}"
    )
    force_kill_childs()
    sys.__excepthook__(exctype, value, tb)


def yuki_unraisablehook(unraisable, **kwargs):
    try:
        filename, name, line_no = format_tb_data(unraisable.exc_traceback)
    except Exception:
        filename, name, line_no = "?", "?", "?"
    show_exception(f"{filename}\n{name}\n{line_no}\n{str(unraisable)}\n{str(kwargs)}")
    sys.__unraisablehook__(unraisable, **kwargs)
    del filename, name, line_no, unraisable, kwargs


sys.excepthook = yuki_excepthook
sys.unraisablehook = yuki_unraisablehook
