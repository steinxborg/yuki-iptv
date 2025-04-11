#
# Copyright (c) 2021, 2022 Astroncia
# Copyright (c) 2023-2025 liya <liyaastrova@proton.me>
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
import os
import signal
import logging
import traceback
import threading
from PyQt6 import QtCore
from functools import partial
from multiprocessing import active_children
from yuki_iptv.kill_process_childs import kill_process_childs

logger = logging.getLogger(__name__)


class Communicate(QtCore.QObject):
    executeInMainThread = QtCore.pyqtSignal(partial)


# avoid circular import
def _show_exception(*args, **kwargs):
    from yuki_iptv.exception_handler import show_exception

    show_exception(*args, **kwargs)


def execute_function(fn):
    try:
        fn()
    except KeyboardInterrupt:
        pass
    except Exception:
        _show_exception(traceback.format_exc())


comm_instance = Communicate()
comm_instance.executeInMainThread.connect(execute_function)


def executeInMainThread(fn):
    try:
        comm_instance.executeInMainThread.emit(fn)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        if not isinstance(exc, RuntimeError):
            logger.warning("executeInMainThread failed")
            logger.warning(traceback.format_exc())


# Used as a decorator to run things in the main loop, from another thread
def idle_function(func):
    def wrapper(*args, **kwargs):
        executeInMainThread(partial(func, *args, **kwargs))

    return wrapper


# Used as a decorator to run things in the background (GUI blocking)
class ExceptionCatchThread(threading.Thread):
    def run(self):
        try:
            self.ret = self._target(*self._args, **self._kwargs)
        except KeyboardInterrupt:
            pass
        except BaseException:
            _show_exception(traceback.format_exc())


def async_gui_blocking_function(func):
    def wrapper(*args, **kwargs):
        thread = ExceptionCatchThread(
            target=func, daemon=True, args=args, kwargs=kwargs
        )
        thread.start()
        return thread

    return wrapper


def kill_active_childs():
    for process in active_children():
        try:
            process.kill()
        except Exception:
            try:
                process.terminate()
            except Exception:
                pass


def force_kill_childs():
    kill_active_childs()
    kill_process_childs(os.getpid(), signal.SIGKILL)
