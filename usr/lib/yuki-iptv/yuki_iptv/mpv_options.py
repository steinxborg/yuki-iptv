#
# Copyright (c) 2021, 2022 Astroncia
# Copyright (c) 2023-2025 liya <liyaliya@tutamail.com>
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
import json
import shlex
import logging
import traceback
from PyQt6 import QtWidgets
from yuki_iptv.i18n import _
from thirdparty import mpv

logger = logging.getLogger(__name__)


def show_parse_error(MAIN_WINDOW_TITLE, options):
    msg_wrongmpvoptions = QtWidgets.QMessageBox(
        QtWidgets.QMessageBox.Icon.Warning,
        MAIN_WINDOW_TITLE,
        _("Custom MPV options invalid, ignoring them") + f"\n\n{options}",
        QtWidgets.QMessageBox.StandardButton.Ok,
    )
    msg_wrongmpvoptions.exec()


def get_mpv_options(MAIN_WINDOW_TITLE, options, mpv_options_1):
    options_orig = options.copy()
    options_2 = {}
    try:
        pairs = shlex.split(mpv_options_1)
        keys = {}
        for pair in pairs:
            key, value = pair.split("=", 1)
            if key.startswith("--"):
                key = key.replace("--", "")
            if key.endswith("-append"):
                key = key.replace("-append", "")
                if key not in keys:
                    keys[key] = ""
                v = value.replace("=", '="', 1)
                keys[key] = f'{keys[key]},{v}"'.lstrip(",")
            else:
                keys[key] = value
        for key in keys:
            options[key] = keys[key]
            options_2[key] = keys[key]
    except Exception:
        logger.warning("Could not parse libmpv options!")
        logger.warning(traceback.format_exc())
        show_parse_error(MAIN_WINDOW_TITLE, mpv_options_1)
    logger.info("Testing custom libmpv options...")
    logger.info(options_2)
    try:
        mpv.MPV(**options_2)
        logger.info("libmpv options OK")
    except Exception:
        logger.warning("libmpv options test failed, ignoring them")
        show_parse_error(MAIN_WINDOW_TITLE, json.dumps(options_2))
        options = options_orig
    return options
