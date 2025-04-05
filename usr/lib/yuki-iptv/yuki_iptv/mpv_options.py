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
import shlex
import logging
import traceback
from yuki_iptv.i18n import _
from yuki_iptv.qt import show_exception
from yuki_iptv.misc import YukiData, MAIN_WINDOW_TITLE
from thirdparty import mpv

logger = logging.getLogger(__name__)

default_mpv_options = {
    "vo": "gpu-next,gpu,x11",
    "hwdec": "no",
    "force-window": True,
    "title": MAIN_WINDOW_TITLE,
    "audio-client-name": MAIN_WINDOW_TITLE,
}


def show_parse_error(options):
    show_exception(_("Custom MPV options invalid, ignoring them") + f"\n\n{options}")


def get_mpv_options():
    custom_mpv_options_text = YukiData.settings["mpv_options"]

    if YukiData.settings["lowlatency"]:
        logger.info("Trying to activate low latency mode")
        custom_mpv_options_text += " profile=low-latency"

    custom_mpv_options_text = custom_mpv_options_text.strip()

    keys = {}
    try:
        pairs = shlex.split(custom_mpv_options_text)
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
                # if value.lower().strip() == "true":
                #    value = True
                # if value.lower().strip() == "false":
                #    value = False
                keys[key] = value
    except Exception:
        logger.warning("Could not parse libmpv options!")
        logger.warning(traceback.format_exc())
        show_parse_error(custom_mpv_options_text)
    logger.info("Testing custom libmpv options...")
    logger.info(keys)
    try:
        _mpv = mpv.MPV(**keys)
        _mpv.quit()
        logger.info("libmpv options OK")
    except Exception:
        logger.warning("libmpv options test failed, ignoring them")
        logger.warning(traceback.format_exc())
        show_parse_error(f"{str(custom_mpv_options_text)}\n\n{str(keys)}")
        keys.clear()

    options = default_mpv_options.copy()
    options.update(keys)
    return options
