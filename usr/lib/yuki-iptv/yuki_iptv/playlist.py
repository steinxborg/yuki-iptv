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
import chardet
import logging
import traceback
from PyQt6 import QtWidgets
from yuki_iptv.m3u import M3UParser
from yuki_iptv.xspf import parse_xspf
from yuki_iptv.exception import show_exception
from yuki_iptv.requests_timeout import requests_get
from yuki_iptv.xtreamtom3u import convert_xtream_to_m3u
from thirdparty.xtream import Serie


logger = logging.getLogger(__name__)


class PlaylistsFail:
    status_code = 0


class EmptyClass:
    pass


def load_playlist(_, settings, YukiData, load_xtream, channel_sets, channel_sort):
    m3u = ""
    array = {}
    groups = []

    xt = EmptyClass()
    xt.auth_data = {}

    logger.info("Loading playlist...")
    if settings["m3u"]:
        if settings["m3u"].startswith("XTREAM::::::::::::::"):
            # XTREAM::::::::::::::username::::::::::::::password::::::::::::::url
            YukiData.is_xtream = True
            logger.info("Using XTream API")
            xt, xtream_username, xtream_password, xtream_url = load_xtream(
                settings["m3u"]
            )
            if xt.auth_data != {}:
                try:
                    xt.load_iptv()
                    m3u = convert_xtream_to_m3u(_, xt.channels)
                    try:
                        m3u += convert_xtream_to_m3u(_, xt.movies, True, "VOD")
                    except Exception:
                        logger.warning("XTream movies parse FAILED")
                    for movie1 in xt.series:
                        if isinstance(movie1, Serie):
                            YukiData.series[movie1.name] = movie1
                    logger.info("XTream init done")
                    if not settings["epg"]:
                        logger.info("EPG not specified, using XTream xmltv.php")
                        settings["epg"] = (
                            f"{xtream_url}/xmltv.php?username="
                            f"{xtream_username}&password={xtream_password}"
                        )
                except Exception:
                    exc = traceback.format_exc()
                    logger.warning(exc)
                    message2 = "{}\n\n{}".format(
                        _("yuki-iptv error"),
                        str(
                            "XTream API: {}\n\n{}".format(
                                _("Processing error"), str(exc)
                            )
                        ),
                    )
                    msg2 = QtWidgets.QMessageBox(
                        QtWidgets.QMessageBox.Icon.Warning,
                        _("Error"),
                        message2,
                        QtWidgets.QMessageBox.StandardButton.Ok,
                    )
                    msg2.exec()
            else:
                message1 = "{}\n\n{}".format(
                    _("yuki-iptv error"),
                    str("XTream API: {}".format(_("Could not connect"))),
                )
                msg1 = QtWidgets.QMessageBox(
                    QtWidgets.QMessageBox.Icon.Warning,
                    _("Error"),
                    message1,
                    QtWidgets.QMessageBox.StandardButton.Ok,
                )
                msg1.exec()
        else:
            if os.path.isfile(settings["m3u"]):
                YukiData.is_xtream = False
                logger.info("Playlist is local file")
                try:
                    file = open(settings["m3u"], encoding="utf8")
                    m3u = file.read()
                    file.close()
                except Exception:
                    logger.warning("Playlist is not UTF-8 encoding")
                    logger.info("Trying to detect encoding...")
                    m3u_file = open(settings["m3u"], "rb")
                    try:
                        m3u_file_read = m3u_file.read()
                        m3u_encoding = chardet.detect(m3u_file_read)["encoding"]
                        logger.info(f"Detected encoding: {m3u_encoding}")
                        m3u = m3u_file_read.decode(m3u_encoding)
                    except Exception:
                        logger.warning("Encoding detection error!")
                        show_exception(
                            _(
                                "Failed to load playlist - unknown "
                                "encoding! Please use playlists "
                                "in UTF-8 encoding."
                            )
                        )
                    finally:
                        m3u_file_read = None
                        m3u_file.close()
            else:
                YukiData.is_xtream = False
                logger.info("Playlist is remote URL")
                try:
                    ua = (
                        settings["playlist_useragent"]
                        if settings["playlist_useragent"]
                        else settings["ua"]
                    )
                    ref = (
                        settings["playlist_referer"]
                        if settings["playlist_referer"]
                        else settings["referer"]
                    )
                    originURL = ""
                    if ref and ref.endswith("/"):
                        originURL = ref[:-1]
                    headers = {"User-Agent": ua}
                    if ref:
                        headers["Referer"] = ref
                    if originURL:
                        headers["Origin"] = originURL
                    logger.info(f"Loading playlist with headers {json.dumps(headers)}")
                    try:
                        m3u_req = requests_get(
                            settings["m3u"],
                            headers=headers,
                            timeout=(5, 15),  # connect, read timeout
                        )
                    except Exception:
                        logger.warning(traceback.format_exc())
                        m3u_req = PlaylistsFail()
                        m3u_req.status_code = 400

                    if m3u_req.status_code != 200:
                        logger.warning("Playlist load failed, trying empty user agent")
                        m3u_req = requests_get(
                            settings["m3u"],
                            headers={"User-Agent": ""},
                            timeout=(5, 15),  # connect, read timeout
                        )

                    logger.info(f"Status code: {m3u_req.status_code}")
                    logger.info(f"{len(m3u_req.content)} bytes")
                    m3u = m3u_req.content
                    try:
                        m3u = m3u.decode("utf-8")
                    except Exception:
                        logger.warning("Playlist is not UTF-8 encoding")
                        logger.info("Trying to detect encoding...")
                        guess_encoding = ""
                        try:
                            guess_encoding = chardet.detect(m3u)["encoding"]
                        except Exception:
                            pass
                        if guess_encoding:
                            logger.info(f"Guessed encoding: {guess_encoding}")
                            try:
                                m3u = m3u.decode(guess_encoding)
                            except Exception:
                                logger.warning("Wrong encoding guess!")
                                show_exception(
                                    _(
                                        "Failed to load playlist - unknown "
                                        "encoding! Please use playlists "
                                        "in UTF-8 encoding."
                                    )
                                )
                        else:
                            logger.warning("Unknown encoding!")
                            show_exception(
                                _(
                                    "Failed to load playlist - unknown "
                                    "encoding! Please use playlists "
                                    "in UTF-8 encoding."
                                )
                            )
                except Exception:
                    m3u = ""
                    exp3 = traceback.format_exc()
                    logger.warning("Playlist URL loading error!" + "\n" + exp3)
                    show_exception(traceback.format_exc(), _("Playlist loading error!"))

    m3u_parser = M3UParser(
        settings["playlist_udp_proxy"]
        if settings["playlist_udp_proxy"]
        else settings["udp_proxy"],
        _,
    )
    epg_url = ""
    if m3u:
        try:
            is_xspf = '<?xml version="' in m3u and (
                "http://xspf.org/" in m3u or "https://xspf.org/" in m3u
            )
            if not is_xspf:
                m3u_data0 = m3u_parser.parse_m3u(m3u)
            else:
                m3u_data0 = parse_xspf(m3u)
            m3u_data_got = m3u_data0[0]
            m3u_data = []

            for m3u_datai in m3u_data_got:
                if "tvg-group" in m3u_datai:
                    if (
                        m3u_datai["tvg-group"].lower() == "vod"
                        or m3u_datai["tvg-group"].lower().startswith("vod ")
                        or m3u_datai["tvg-group"].lower().endswith(" vod")
                    ):
                        YukiData.movies[m3u_datai["title"]] = m3u_datai
                    else:
                        m3u_data.append(m3u_datai)

            epg_url = m3u_data0[1]
            if epg_url and not settings["epg"]:
                settings["epg"] = epg_url
            for m3u_line in m3u_data:
                array[m3u_line["title"]] = m3u_line
                if m3u_line["tvg-group"] not in groups:
                    groups.append(m3u_line["tvg-group"])
        except Exception:
            logger.warning("Playlist parsing error!" + "\n" + traceback.format_exc())
            show_exception(traceback.format_exc(), _("Playlist loading error!"))
            m3u = ""
            array = {}
            groups = []

    m3u_exists = not not m3u
    m3u = ""

    logger.info(
        "{} channels, {} groups, {} movies, {} series".format(
            len(array),
            len([group2 for group2 in groups if group2 != _("All channels")]),
            len(YukiData.movies),
            len(YukiData.series),
        )
    )

    for ch3 in array.copy():
        if settings["m3u"] in channel_sets:
            if ch3 in channel_sets[settings["m3u"]]:
                if "group" in channel_sets[settings["m3u"]][ch3]:
                    if channel_sets[settings["m3u"]][ch3]["group"]:
                        array[ch3]["tvg-group"] = channel_sets[settings["m3u"]][ch3][
                            "group"
                        ]
                        if channel_sets[settings["m3u"]][ch3]["group"] not in groups:
                            groups.append(channel_sets[settings["m3u"]][ch3]["group"])
                if "hidden" in channel_sets[settings["m3u"]][ch3]:
                    if channel_sets[settings["m3u"]][ch3]["hidden"]:
                        array.pop(ch3)

    if _("All channels") in groups:
        groups.remove(_("All channels"))
    groups = [_("All channels"), _("Favourites")] + groups

    logger.info("Sorting playlist...")

    def sort_custom(sub):
        try:
            return channel_sort.index(sub)
        except Exception:
            return len(array) + 10

    def doSort(arr0):
        if settings["sort"] == 0:
            return arr0
        if settings["sort"] == 1:
            return sorted(arr0)
        if settings["sort"] == 2:
            return sorted(arr0, reverse=True)
        if settings["sort"] == 3:
            try:
                return sorted(arr0, key=sort_custom)
            except Exception:
                return arr0
        return arr0

    array_sorted = doSort(array)

    logger.info("Playling loading done!")

    return array, array_sorted, groups, m3u_exists, xt, YukiData
