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
import os
import json
from pathlib import Path
from yuki_iptv.misc import YukiData
from yuki_iptv.xdg import LOCAL_DIR, SAVE_FOLDER_DEFAULT


def parse_settings():
    settings_default = {
        "m3u": "",
        "epg": "",
        "deinterlace": False,
        "udp_proxy": "",
        "save_folder": SAVE_FOLDER_DEFAULT,
        "epgoffset": 0,
        "sort": 0,
        "sort_categories": 0,
        "description_view": 0,
        "cache_secs": 0,
        "ua": "Mozilla/5.0",
        "mpv_options": "",
        "donotupdateepg": False,
        "openprevchannel": False,
        "hideepgfromplaylist": False,
        "hideplaylistbyleftmouseclick": False,
        "hideepgpercentage": False,
        "hidebitrateinfo": False,
        "volumechangestep": 1,
        "autoreconnection": False,
        "channellogos": 0,
        "nocacheepg": False,
        "scrrecnosubfolders": False,
        "hidetvprogram": False,
        "rewindenable": False,
        "hidechannellogos": False,
        "enabletransparency": True,
        "panelposition": 0,
        "videoaspect": 0,
        "zoom": 0,
        "panscan": 0.0,
        "referer": "",
        "gui": 0,
        "playlist_useragent": "",
        "playlist_referer": "",
        "playlist_udp_proxy": "",
    }

    settings = settings_default
    settings_loaded = False

    if os.path.isfile(str(Path(LOCAL_DIR, "settings.json"))):
        with open(
            str(Path(LOCAL_DIR, "settings.json")), encoding="utf8"
        ) as settings_file:
            settings = json.loads(settings_file.read())

        for option in settings_default:
            if option not in settings:
                settings[option] = settings_default[option]

        settings_loaded = True

    return settings, settings_loaded


def get_epg_url():
    return (
        YukiData.settings["epg"]
        if YukiData.settings["epg"]
        else (
            YukiData.settings["epg_temporary"]
            if "epg_temporary" in YukiData.settings
            and YukiData.settings["epg_temporary"]
            else ""
        )
    )
