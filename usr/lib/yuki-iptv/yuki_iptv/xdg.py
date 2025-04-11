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
import os.path
import logging
from pathlib import Path

home_folder = str(Path.home())
logger = logging.getLogger(__name__)


def get_cache_dir():
    if "XDG_CACHE_HOME" in os.environ and os.environ["XDG_CACHE_HOME"]:
        cache_dir = str(Path(os.environ["XDG_CACHE_HOME"]) / "yuki-iptv")
    else:
        cache_dir = str((Path(os.environ["HOME"]) / ".cache" / "yuki-iptv"))
    return cache_dir


def get_config_dir():
    if "XDG_CONFIG_HOME" in os.environ and os.environ["XDG_CONFIG_HOME"]:
        config_dir = str(Path(os.environ["XDG_CONFIG_HOME"] / "yuki-iptv"))
    else:
        config_dir = str((Path(os.environ["HOME"]) / ".config" / "yuki-iptv"))
    return config_dir


LOCAL_DIR = str(get_config_dir())
CACHE_DIR = str(get_cache_dir())
SAVE_FOLDER_DEFAULT = str((Path(CACHE_DIR) / "saves"))

for dir_create in (
    LOCAL_DIR,
    CACHE_DIR,
    SAVE_FOLDER_DEFAULT,
):
    Path(dir_create).mkdir(parents=True, exist_ok=True)

for dir_create2 in ("xtream", "epg", "logo"):
    (Path(CACHE_DIR) / dir_create2).mkdir(parents=True, exist_ok=True)
