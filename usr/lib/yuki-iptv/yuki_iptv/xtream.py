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
import logging
import traceback
from yuki_iptv.exception_handler import show_exception

logger = logging.getLogger(__name__)


SERIES = re.compile(
    r"(?P<series>.*?) S(?P<season>.\d{1,2}).*E(?P<episode>.\d{1,2}.*)$", re.IGNORECASE
)


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


def get_series_name(obj):
    channel_name_1 = obj["tvg-name"]
    if not channel_name_1:
        channel_name_1 = obj["title"]
    return channel_name_1


def parse_series(obj1, series):
    is_matched = False
    channel_name_1 = get_series_name(obj1)
    series_match = SERIES.fullmatch(channel_name_1)
    if series_match is not None:
        try:
            res1 = series_match.groupdict()
            series_name = res1["series"]
            if series_name in series:
                serie1 = series[series_name]
            else:
                serie1 = SerieM3U(series_name)
                serie1.logo = obj1["tvg-logo"]
                series[series_name] = serie1
            season_name1 = res1["season"]
            if season_name1 in serie1.seasons.keys():
                season1 = serie1.seasons[season_name1]
            else:
                season1 = SeasonM3U(season_name1)
                serie1.seasons[season_name1] = season1

            episode_name1 = res1["episode"]
            ep_channel = ChannelM3U()
            ep_channel.name = channel_name_1
            ep_channel.title = channel_name_1
            ep_channel.logo = obj1["tvg-logo"]
            ep_channel.url = obj1["url"]
            season1.episodes[episode_name1] = ep_channel
            serie1.episodes.append(ep_channel)
            is_matched = True
        except Exception:
            show_exception(f"M3U Series parse FAILED\n{traceback.format_exc()}")
    return series, is_matched
