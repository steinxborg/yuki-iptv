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
import logging

logger = logging.getLogger(__name__)


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
