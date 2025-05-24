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
import re
import json
import logging
import hashlib
import traceback
from pathlib import Path
from yuki_iptv.xdg import CACHE_DIR
from yuki_iptv.misc import YukiData
from yuki_iptv.exception_handler import show_exception
from thirdparty.xtream import XTream

logger = logging.getLogger(__name__)


SERIES = re.compile(
    r"(?P<series>.*?) S(?P<season>.\d{1,2}).*E(?P<episode>.\d{1,2}.*)$", re.IGNORECASE
)


class EmptyXTreamClass:
    auth_data = {}


class SerieM3U:
    def __init__(self, name):
        self.name = name
        self.logo = None
        self.logo_path = None
        self.seasons = {}
        self.episodes = []


class SeasonM3U:
    def __init__(self, name):
        self.name = name
        self.episodes = {}


class ChannelM3U:
    def __init__(self):
        self.info = None
        self.id = None
        self.name = None
        self.logo = None
        self.logo_path = None
        self.group_title = None
        self.title = None
        self.url = None


def log_xtream(*args, **kwargs):
    logger.info(" ".join(map(str, args)))


def convert_xtream_to_m3u(data, skip_init=False, append_group=""):
    output = "#EXTM3U\n" if not skip_init else ""
    for channel in data:
        if channel.name and channel.url:
            line = "#EXTINF:0"
            group = (f"{append_group} " if append_group else "") + (
                channel.group_title if channel.group_title else ""
            )
            if group:
                line += f' group-title="{group}"'
            # Add EPG channel ID in case channel name and epg_id are different.
            if channel.epg_channel_id:
                line += f' tvg-id="{channel.epg_channel_id}"'
            if channel.logo:
                line += f' tvg-logo="{channel.logo}"'
            line += f",{channel.name}"
            output += line + "\n" + channel.url + "\n"
    return output


def get_series_name(array):
    channel_name = array["tvg-name"]
    if not channel_name:
        channel_name = array["title"]
    return channel_name


def parse_series(array, series):
    is_matched = False
    channel_name = get_series_name(array)
    series_match = SERIES.fullmatch(channel_name)
    if series_match is not None:
        try:
            ret = series_match.groupdict()
            series_name = ret["series"]
            if series_name in series:
                serie = series[series_name]
            else:
                serie = SerieM3U(series_name)
                serie.logo = array["tvg-logo"]
                series[series_name] = serie
            season_name = ret["season"]
            if season_name in serie.seasons.keys():
                season = serie.seasons[season_name]
            else:
                season = SeasonM3U(season_name)
                serie.seasons[season_name] = season

            ep_channel = ChannelM3U()
            ep_channel.name = channel_name
            ep_channel.title = channel_name
            ep_channel.logo = array["tvg-logo"]
            ep_channel.url = array["url"]
            season.episodes[ret["episode"]] = ep_channel
            serie.episodes.append(ep_channel)
            is_matched = True
        except Exception:
            show_exception(f"M3U Series parse FAILED\n{traceback.format_exc()}")
    return series, is_matched


def load_xtream(m3u_url, headers=None):
    (
        _xtream_unused,
        xtream_username,
        xtream_password,
        xtream_url,
    ) = m3u_url.split("::::::::::::::")
    xtream_headers = {
        "User-Agent": (
            YukiData.settings["playlist_useragent"]
            if YukiData.settings["playlist_useragent"]
            else YukiData.settings["ua"]
        )
    }
    referer = (
        YukiData.settings["playlist_referer"]
        if YukiData.settings["playlist_referer"]
        else YukiData.settings["referer"]
    )
    if referer:
        xtream_headers["Referer"] = referer
    if headers:
        if "Referer" in headers and not headers["Referer"]:
            headers.pop("Referer")
        xtream_headers = headers
    if "Referer" in xtream_headers and xtream_headers["Referer"]:
        originURL = ""
        if xtream_headers["Referer"].endswith("/"):
            originURL = xtream_headers["Referer"][:-1]
        if originURL:
            xtream_headers["Origin"] = originURL
    logger.info(f"Loading XTream with headers {json.dumps(xtream_headers)}")
    try:
        xt = XTream(
            log_xtream,
            hashlib.sha512(m3u_url.encode("utf-8")).hexdigest(),
            xtream_username,
            xtream_password,
            xtream_url,
            headers=xtream_headers,
            hide_adult_content=False,
            cache_path=str(Path(CACHE_DIR) / "xtream"),
        )
    except Exception:
        show_exception(traceback.format_exc())
        xt = EmptyXTreamClass()
    return xt, xtream_username, xtream_password, xtream_url
