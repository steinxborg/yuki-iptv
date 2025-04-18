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
from yuki_iptv.i18n import _
from yuki_iptv.record import is_youtube_url
from yuki_iptv.drm import (
    extract_cenc_decryption_key_from_kodiprop,
    extract_cenc_decryption_key_from_url,
)

logger = logging.getLogger(__name__)


class M3UParser:
    def __init__(self, udp_proxy):
        self.udp_proxy = udp_proxy
        self.all_channels = _("All channels")
        self.epg_urls = []
        self.m3u_epg = ""
        self.catchup_data = ["default", "7", ""]
        self.epg_url_final = ""
        self.regexp_cache = {}

    def parse_regexp(self, name, line_info, default="", custom_regex=False):
        regexp = name
        if not custom_regex:
            regexp += '="(.*?)"'
        if regexp not in self.regexp_cache:
            self.regexp_cache[regexp] = re.compile(regexp)
        re_match = self.regexp_cache[regexp].search(line_info)
        try:
            res = re_match.group(1)
        except AttributeError:
            res = default
        # catchup-days check start
        if name == "catchup-days":
            try:
                res = str(int(res))
            except Exception:
                logger.warning(
                    f"M3U STANDARDS VIOLATION: catchup-days is not int (got '{res}')"
                )
                res = default
        # catchup-days check end
        res = res.strip()
        return res

    def parse_url_kodi_arguments(self, url):
        useragent = ""
        referrer = ""
        if "|" in url:
            logger.debug("Found Kodi-style arguments, parsing")
            split_kodi = url.split("|")[1]
            if "&" in split_kodi:
                logger.debug("Multiple")
                split_kodi = split_kodi.split("&")
            else:
                logger.debug("Single")
                split_kodi = [split_kodi]
            for kodi_str in split_kodi:
                if kodi_str.startswith("User-Agent="):
                    kodi_user_agent = kodi_str.replace("User-Agent=", "", 1)
                    logger.debug(f"Kodi-style User-Agent found: {kodi_user_agent}")
                    useragent = kodi_user_agent
                if kodi_str.startswith("user-agent="):
                    kodi_user_agent = kodi_str.replace("user-agent=", "", 1)
                    logger.debug(f"Kodi-style User-Agent found: {kodi_user_agent}")
                    useragent = kodi_user_agent
                if kodi_str.startswith("Referer="):
                    kodi_referer = kodi_str.replace("Referer=", "", 1)
                    logger.debug(f"Kodi-style Referer found: {kodi_referer}")
                    referrer = kodi_referer
                if kodi_str.startswith("referer="):
                    kodi_referer = kodi_str.replace("referer=", "", 1)
                    logger.debug(f"Kodi-style Referer found: {kodi_referer}")
                    referrer = kodi_referer
            url = url.split("|")[0]
        return url, useragent, referrer

    def get_title(self, line_info):
        title_regex = re.sub('\\="(.*?)"', "", line_info).split(",", 1)
        if len(title_regex) < 2:
            title = ""
        else:
            title = title_regex[1].strip()
        return title

    def parse_channel(self, line_info, ch_url, overrides):
        title = self.get_title(line_info)

        if self.udp_proxy and (
            ch_url.startswith("udp://") or ch_url.startswith("rtp://")
        ):
            ch_url = (
                self.udp_proxy
                + "/"
                + ch_url.replace("udp://", "udp/").replace("rtp://", "rtp/")
            )
            ch_url = ch_url.replace("//udp/", "/udp/").replace("//rtp/", "/rtp/")
            ch_url = ch_url.replace("@", "")

        tvg_url = self.parse_regexp("tvg-url", line_info)
        if not tvg_url:
            url_tvg = self.parse_regexp("url-tvg", line_info)
            if url_tvg:
                tvg_url = url_tvg

        group = self.parse_regexp("group-title", line_info, "")
        if not group:
            group = self.parse_regexp("tvg-group", line_info, self.all_channels)
            if not group:
                group = self.all_channels

        catchup_tag = self.parse_regexp("catchup", line_info, "")
        if not catchup_tag:
            catchup_tag = self.parse_regexp(
                "catchup-type", line_info, self.catchup_data[0]
            )

        tvg_id = self.parse_regexp("tvg-id", line_info)
        if not tvg_id:
            tvg_ID = self.parse_regexp("tvg-ID", line_info)
            if tvg_ID:
                tvg_id = tvg_ID

        ch_array = {
            "title": title,
            "orig_title": title,
            "tvg-name": self.parse_regexp("tvg-name", line_info),
            "tvg-id": tvg_id,
            "tvg-logo": self.parse_regexp("tvg-logo", line_info),
            "tvg-group": group,
            "tvg-url": tvg_url,
            "catchup": catchup_tag,
            "catchup-source": self.parse_regexp(
                "catchup-source", line_info, self.catchup_data[2]
            ),
            "catchup-days": self.parse_regexp(
                "catchup-days", line_info, self.catchup_data[1]
            ),
            "useragent": self.parse_regexp("user-agent", line_info),
            "referer": "",
            "cenc_decryption_key": "",
            "url": ch_url,
        }

        # Parse Kodi-style URL arguments
        channel_url, kodi_useragent, kodi_referrer = self.parse_url_kodi_arguments(
            ch_array["url"]
        )
        if kodi_useragent:
            ch_array["useragent"] = kodi_useragent
        if kodi_referrer:
            ch_array["referer"] = kodi_referrer
        ch_array["url"] = channel_url

        # EXTGRP and EXTVLCOPT always have priority over EXTINF options
        for override in overrides:
            ch_array[override] = overrides[override]

        return ch_array

    def parse_m3u(self, m3u_str):
        self.epg_urls = []
        self.m3u_epg = ""
        self.catchup_data = ["default", "7", ""]
        self.epg_url_final = ""
        if not ("#EXTM3U" in m3u_str and "#EXTINF" in m3u_str):
            raise Exception("Malformed M3U: no #EXTM3U and #EXTINF tags found")
        channels = []
        titles = set()
        buffer = []
        for line in m3u_str.split("\n"):
            line = line.rstrip("\n").rstrip().strip()
            if line.startswith("#EXTM3U"):
                epg_m3u_url = ""
                if 'x-tvg-url="' in line:
                    try:
                        epg_m3u_url = re.findall('x-tvg-url="(.*?)"', line)[0]
                    except Exception:
                        pass
                else:
                    if 'tvg-url="' in line:
                        try:
                            epg_m3u_url = re.findall('tvg-url="(.*?)"', line)[0]
                        except Exception:
                            pass
                    else:
                        try:
                            epg_m3u_url = re.findall('url-tvg="(.*?)"', line)[0]
                        except Exception:
                            pass
                if 'catchup="' in line:
                    try:
                        self.catchup_data[0] = re.findall('catchup="(.*?)"', line)[0]
                    except Exception:
                        pass
                if 'catchup-days="' in line:
                    try:
                        self.catchup_data[1] = re.findall('catchup-days="(.*?)"', line)[
                            0
                        ]
                    except Exception:
                        pass
                if 'catchup-source="' in line:
                    try:
                        self.catchup_data[2] = re.findall(
                            'catchup-source="(.*?)"', line
                        )[0]
                    except Exception:
                        pass
                if epg_m3u_url:
                    self.m3u_epg = epg_m3u_url
            else:
                if line:
                    if line.startswith("#"):
                        buffer.append(line)
                    else:
                        channel = False
                        overrides = {}
                        is_clearkey = False
                        # work around commented channels
                        metadata_found = False
                        buffer.reverse()
                        buffer_new = []
                        for buffer_line in buffer:
                            check_line = buffer_line.replace("#", "").lower().strip()
                            if metadata_found and (
                                check_line.startswith("http")
                                or check_line.startswith("rtp")
                                or check_line.startswith("udp")
                                or check_line.startswith("file")
                                or check_line.startswith("/")
                            ):
                                break
                            if (
                                buffer_line.startswith("#EXTINF:")
                                or buffer_line.startswith("#EXTGRP:")
                                or buffer_line.startswith("#EXTLOGO:")
                                or buffer_line.startswith("#EXTVLCOPT:")
                                or buffer_line.startswith("#KODIPROP:")
                            ):
                                metadata_found = True
                                buffer_new.insert(0, buffer_line)
                        for buffer_line in buffer_new:
                            if buffer_line.startswith("#EXTINF:"):
                                channel = buffer_line
                            if buffer_line.startswith("#EXTGRP:"):
                                group1 = buffer_line.replace("#EXTGRP:", "").strip()
                                if group1:
                                    overrides["tvg-group"] = group1
                            if buffer_line.startswith("#EXTLOGO:"):
                                logo1 = buffer_line.replace("#EXTLOGO:", "").strip()
                                if logo1:
                                    overrides["tvg-logo"] = logo1
                            if buffer_line.startswith("#EXTVLCOPT:"):
                                extvlcopt = buffer_line.replace(
                                    "#EXTVLCOPT:", ""
                                ).strip()
                                if extvlcopt.startswith("http-user-agent="):
                                    http_user_agent = extvlcopt.replace(
                                        "http-user-agent=", ""
                                    ).strip()
                                    if http_user_agent:
                                        overrides["useragent"] = http_user_agent
                                if extvlcopt.startswith("http-referrer="):
                                    http_referer = extvlcopt.replace(
                                        "http-referrer=", ""
                                    ).strip()
                                    if http_referer:
                                        overrides["referer"] = http_referer
                            if buffer_line.startswith("#KODIPROP:"):
                                for headers_name in (
                                    "common_headers",
                                    "manifest_headers",
                                    "stream_headers",
                                ):
                                    if buffer_line.startswith(
                                        "#KODIPROP:"
                                        f"inputstream.adaptive.{headers_name}="
                                    ):
                                        kodiprop_headers = buffer_line.replace(
                                            (
                                                "#KODIPROP:"
                                                f"inputstream.adaptive.{headers_name}="
                                            ),
                                            "",
                                            1,
                                        ).split("&")
                                        for kodiprop_header in kodiprop_headers:
                                            kodiprop_header_split = (
                                                kodiprop_header.split("=")
                                            )
                                            if len(kodiprop_header_split) == 2:
                                                kodiprop_header_name = (
                                                    kodiprop_header_split[0]
                                                    .lower()
                                                    .strip()
                                                )
                                                kodiprop_header_value = (
                                                    kodiprop_header_split[1].strip()
                                                )
                                                if kodiprop_header_value:
                                                    if (
                                                        kodiprop_header_name
                                                        == "user-agent"
                                                    ):
                                                        overrides[
                                                            "useragent"
                                                        ] = kodiprop_header_value
                                                    elif (
                                                        kodiprop_header_name
                                                        == "referer"
                                                        or kodiprop_header_name
                                                        == "referrer"
                                                    ):
                                                        overrides[
                                                            "referer"
                                                        ] = kodiprop_header_value
                                if "clearkey" in buffer_line:
                                    is_clearkey = True
                                cenc_decryption_key = (
                                    extract_cenc_decryption_key_from_kodiprop(
                                        buffer_line
                                    )
                                )
                                if cenc_decryption_key:
                                    overrides[
                                        "cenc_decryption_key"
                                    ] = cenc_decryption_key
                        if (
                            "cenc_decryption_key" in overrides
                            and overrides["cenc_decryption_key"]
                            and not is_clearkey
                        ):
                            overrides["cenc_decryption_key"] = ""
                        buffer_new.clear()
                        if channel:
                            parsed_channel = self.parse_channel(
                                channel, line, overrides
                            )
                            # For multiple channels with same name
                            if parsed_channel["title"] in titles:
                                i = 0
                                while True:
                                    i += 1
                                    parsed_channel["title"] = (
                                        parsed_channel["orig_title"] + f" ({i})"
                                    )
                                    if parsed_channel["title"] not in titles:
                                        break
                            titles.add(parsed_channel["title"])
                            if parsed_channel["tvg-url"]:
                                if parsed_channel["tvg-url"] not in self.epg_urls:
                                    self.epg_urls.append(parsed_channel["tvg-url"])
                            # DRM
                            (
                                parsed_channel["url"],
                                _cenc_key,
                            ) = extract_cenc_decryption_key_from_url(
                                parsed_channel["url"]
                            )
                            if _cenc_key:
                                parsed_channel["cenc_decryption_key"] = _cenc_key
                            if parsed_channel["cenc_decryption_key"]:
                                parsed_channel[
                                    "title"
                                ] = f"[DRM] {parsed_channel['title']}"
                            # YouTube
                            if is_youtube_url(parsed_channel["url"]):
                                parsed_channel[
                                    "title"
                                ] = f"[YT] {parsed_channel['title']}"
                            channels.append(parsed_channel)
                        buffer.clear()
        buffer.clear()
        self.epg_url_final = self.m3u_epg
        if self.epg_urls and not self.m3u_epg:
            self.epg_url_final = ",".join(self.epg_urls)
        if not channels:
            raise Exception("No channels found")
        return [channels, self.epg_url_final]
