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
import time
import logging
import datetime
import traceback
from yuki_iptv.misc import YukiData
from yuki_iptv.exception_handler import show_exception

logger = logging.getLogger(__name__)


# https://github.com/kodi-pvr/pvr.iptvsimple/blob/-/src/iptvsimple/data/Channel.cpp
# bool Channel::GenerateAppendCatchupSource(


def format_catchup_array(array):
    if "catchup" not in array:
        array["catchup"] = "default"
    if "catchup-source" not in array:
        array["catchup-source"] = ""
    if "catchup-days" not in array:
        array["catchup-days"] = "7"

    if not array["catchup-source"] and array["catchup"] not in (
        "flussonic",
        "flussonic-hls",
        "flussonic-ts",
        "fs",
        "xc",
    ):
        array["catchup"] = "shift"

    if array["catchup-source"]:
        if not (
            array["catchup-source"].startswith("http://")
            or array["catchup-source"].startswith("https://")
        ):
            array["catchup"] = "append"
    return array


def format_placeholders(start_time, end_time, catchup_id, orig_url):
    logger.info(f"Placeholder: {orig_url}")

    start_timestamp = int(time.mktime(time.strptime(start_time, "%d.%m.%Y %H:%M:%S")))
    end_timestamp = int(time.mktime(time.strptime(end_time, "%d.%m.%Y %H:%M:%S")))
    duration = int(end_timestamp - start_timestamp)

    current_utc = int(time.time())
    utcend = start_timestamp + duration
    offset2 = int(current_utc - start_timestamp)

    start_timestamp_split = list(
        reversed(start_time.split(" ")[0].split("."))
    ) + start_time.split(" ")[1].split(":")

    # offset
    orig_url = orig_url.replace("${offset}", "${offset:1}")
    orig_url = orig_url.replace("{offset}", "{offset:1}")

    orig_url = orig_url.replace("${utc}", str(start_timestamp))
    orig_url = orig_url.replace("{utc}", str(start_timestamp))

    orig_url = orig_url.replace("${start}", str(start_timestamp))
    orig_url = orig_url.replace("{start}", str(start_timestamp))

    orig_url = orig_url.replace("${s}", str(start_timestamp))
    orig_url = orig_url.replace("{s}", str(start_timestamp))

    orig_url = orig_url.replace("${lutc}", str(current_utc))
    orig_url = orig_url.replace("{lutc}", str(current_utc))

    orig_url = orig_url.replace("${now}", str(current_utc))
    orig_url = orig_url.replace("{now}", str(current_utc))

    orig_url = orig_url.replace("${timestamp}", str(current_utc))
    orig_url = orig_url.replace("{timestamp}", str(current_utc))

    orig_url = orig_url.replace("${utcend}", str(utcend))
    orig_url = orig_url.replace("{utcend}", str(utcend))

    orig_url = orig_url.replace("${end}", str(utcend))
    orig_url = orig_url.replace("{end}", str(utcend))

    orig_url = orig_url.replace("${Y}", str(start_timestamp_split[0]))
    orig_url = orig_url.replace("{Y}", str(start_timestamp_split[0]))

    orig_url = orig_url.replace("${m}", str(start_timestamp_split[1]))
    orig_url = orig_url.replace("{m}", str(start_timestamp_split[1]))

    orig_url = orig_url.replace("${d}", str(start_timestamp_split[2]))
    orig_url = orig_url.replace("{d}", str(start_timestamp_split[2]))

    orig_url = orig_url.replace("${H}", str(start_timestamp_split[3]))
    orig_url = orig_url.replace("{H}", str(start_timestamp_split[3]))

    orig_url = orig_url.replace("${M}", str(start_timestamp_split[4]))
    orig_url = orig_url.replace("{M}", str(start_timestamp_split[4]))

    orig_url = orig_url.replace("${S}", str(start_timestamp_split[5]))
    orig_url = orig_url.replace("{S}", str(start_timestamp_split[5]))

    orig_url = orig_url.replace("${duration}", str(duration))
    orig_url = orig_url.replace("{duration}", str(duration))

    orig_url = orig_url.replace("${catchup-id}", str(catchup_id))
    orig_url = orig_url.replace("{catchup-id}", str(catchup_id))

    try:
        duration_re = sorted(re.findall(r"\$?{duration:\d+}", orig_url))
        if duration_re:
            for duration_re_i in duration_re:
                duration_re_i_parse = int(duration_re_i.split(":")[1].split("}")[0])
                orig_url = orig_url.replace(
                    duration_re_i, str(int(duration / duration_re_i_parse))
                )
    except Exception:
        show_exception(
            "format_placeholders / "
            f"duration_re parsing failed\n{traceback.format_exc()}"
        )

    try:
        offset_re = sorted(re.findall(r"\$?{offset:\d+}", orig_url))
        if offset_re:
            for offset_re_i in offset_re:
                offset_re_i_parse = int(offset_re_i.split(":")[1].split("}")[0])
                orig_url = orig_url.replace(
                    offset_re_i, str(int(offset2 / offset_re_i_parse))
                )
    except Exception:
        show_exception(
            f"format_placeholders / offset_re parsing failed\n{traceback.format_exc()}"
        )

    utc_time = (
        datetime.datetime.fromtimestamp(start_timestamp)
        .strftime("%Y-%m-%d-%H-%M-%S")
        .split("-")
    )
    lutc_time = (
        datetime.datetime.fromtimestamp(current_utc)
        .strftime("%Y-%m-%d-%H-%M-%S")
        .split("-")
    )
    utcend_time = (
        datetime.datetime.fromtimestamp(utcend).strftime("%Y-%m-%d-%H-%M-%S").split("-")
    )

    try:
        specifiers_re = re.findall(
            re.compile(
                "((\\$?){(utc|start|lutc|now|timestamp|utcend|end):"
                "([YmdHMS])(-?)([YmdHMS]?)(-?)([YmdHMS]?)(-?)"
                "([YmdHMS]?)(-?)([YmdHMS]?)(-?)([YmdHMS]?)})"
            ),
            orig_url,
        )
        if specifiers_re:
            for specifiers_re_i in specifiers_re:
                specifiers_re_i_o = specifiers_re_i[0]
                spec_name = str(specifiers_re_i_o.split("{")[1].split(":")[0])
                spec_val = str(specifiers_re_i_o.split(":")[1].split("}")[0])
                if spec_name in ("utc", "start"):
                    spec_val = spec_val.replace("Y", str(utc_time[0]))
                    spec_val = spec_val.replace("m", str(utc_time[1]))
                    spec_val = spec_val.replace("d", str(utc_time[2]))
                    spec_val = spec_val.replace("H", str(utc_time[3]))
                    spec_val = spec_val.replace("M", str(utc_time[4]))
                    spec_val = spec_val.replace("S", str(utc_time[5]))
                elif spec_name in ("lutc", "now", "timestamp"):
                    spec_val = spec_val.replace("Y", str(lutc_time[0]))
                    spec_val = spec_val.replace("m", str(lutc_time[1]))
                    spec_val = spec_val.replace("d", str(lutc_time[2]))
                    spec_val = spec_val.replace("H", str(lutc_time[3]))
                    spec_val = spec_val.replace("M", str(lutc_time[4]))
                    spec_val = spec_val.replace("S", str(lutc_time[5]))
                elif spec_name in ("utcend", "end"):
                    spec_val = spec_val.replace("Y", str(utcend_time[0]))
                    spec_val = spec_val.replace("m", str(utcend_time[1]))
                    spec_val = spec_val.replace("d", str(utcend_time[2]))
                    spec_val = spec_val.replace("H", str(utcend_time[3]))
                    spec_val = spec_val.replace("M", str(utcend_time[4]))
                    spec_val = spec_val.replace("S", str(utcend_time[5]))
                orig_url = orig_url.replace(specifiers_re_i_o, str(spec_val))
    except Exception:
        show_exception(
            "format_placeholders / "
            f"specifiers_re parsing failed\n{traceback.format_exc()}"
        )

    return orig_url


def get_catchup_url(channel_url, array, start_time, end_time, catchup_id):
    logger.info(f"Start time: {start_time}")
    logger.info(f"End time: {end_time}")
    if catchup_id:
        logger.info(f"Catchup id: {catchup_id}")
    logger.info(f"Original URL: {channel_url}")
    logger.info("Catchup type: " + array["catchup"])
    play_url = channel_url
    if array["catchup"] == "default":
        play_url = format_placeholders(
            start_time, end_time, catchup_id, array["catchup-source"]
        )
    elif array["catchup"] == "append":
        play_url = channel_url + format_placeholders(
            start_time, end_time, catchup_id, array["catchup-source"]
        )
    elif array["catchup"] == "shift":
        if "?" in channel_url:
            play_url = channel_url + format_placeholders(
                start_time, end_time, catchup_id, "&utc={utc}&lutc={lutc}"
            )
        else:
            play_url = channel_url + format_placeholders(
                start_time, end_time, catchup_id, "?utc={utc}&lutc={lutc}"
            )
    elif array["catchup"] in ("flussonic", "flussonic-hls", "flussonic-ts", "fs"):
        fs_url = channel_url
        flussonic_re = re.findall(
            r"^(http[s]?://[^/]+)/(.*)/([^/]*)(mpegts|\.m3u8)(\?.+=.+)?$", channel_url
        )
        if flussonic_re:
            if len(flussonic_re[0]) == 5:
                fs_host = flussonic_re[0][0]
                fs_channelid = flussonic_re[0][1]
                fs_listtype = flussonic_re[0][2]
                fs_streamtype = flussonic_re[0][3]
                fs_urlappend = flussonic_re[0][4]
                if fs_streamtype == "mpegts":
                    fs_url = "{}/{}/timeshift_abs-{}.ts{}".format(
                        fs_host, fs_channelid, "${start}", fs_urlappend
                    )
                else:
                    if fs_listtype == "index":
                        fs_url = "{}/{}/timeshift_rel-{}.m3u8{}".format(
                            fs_host, fs_channelid, "{offset:1}", fs_urlappend
                        )
                    else:
                        fs_url = "{}/{}/{}-timeshift_rel-{}.m3u8{}".format(
                            fs_host,
                            fs_channelid,
                            fs_listtype,
                            "{offset:1}",
                            fs_urlappend,
                        )
        else:
            flussonic_re_2 = re.findall(
                r"^(http[s]?://[^/]+)/(.*)/([^\\?]*)(\\?.+=.+)?$", channel_url
            )
            if flussonic_re_2:
                if len(flussonic_re_2[0]) == 4:
                    fs_host = flussonic_re_2[0][0]
                    fs_channelid = flussonic_re_2[0][1]
                    fs_urlappend = flussonic_re_2[0][3]
                    if array["catchup"] in ("flussonic-ts", "fs"):
                        fs_url = "{}/{}/timeshift_abs-{}.ts{}".format(
                            fs_host, fs_channelid, "${start}", fs_urlappend
                        )
                    elif array["catchup"] in ("flussonic", "flussonic-hls"):
                        fs_url = "{}/{}/timeshift_rel-{}.m3u8{}".format(
                            fs_host, fs_channelid, "{offset:1}", fs_urlappend
                        )
        play_url = format_placeholders(start_time, end_time, catchup_id, fs_url)
    elif array["catchup"] == "xc":
        xc_url = channel_url
        xc_re = re.findall(
            r"^(http[s]?://[^/]+)/(?:live/)?([^/]+)/([^/]+)/([^/\.]+)(\.m3u[8]?|\.ts?)?$",  # noqa: E501
            channel_url,
        )
        if xc_re:
            if len(xc_re[0]) == 5:
                xc_host = xc_re[0][0]
                xc_username = xc_re[0][1]
                xc_password = xc_re[0][2]
                xc_channelid = xc_re[0][3]
                xc_extension = xc_re[0][4]
                if not xc_extension:
                    xc_extension = ".ts"
                xc_url = "{}/timeshift/{}/{}/{}/{}/{}{}".format(
                    xc_host,
                    xc_username,
                    xc_password,
                    "{duration:60}",
                    "{Y}-{m}-{d}:{H}-{M}",
                    xc_channelid,
                    xc_extension,
                )
        play_url = format_placeholders(start_time, end_time, catchup_id, xc_url)
    logger.info(f"Final URL: {play_url}")
    return play_url


def parse_specifiers_now_url(url):
    if url.endswith("/icons/main.png") or url.endswith("/icons_dark/main.png"):
        return url
    orig_spec_url = url
    current_utc_str = int(time.time())
    url = url.replace("${lutc}", str(current_utc_str))
    url = url.replace("{lutc}", str(current_utc_str))

    url = url.replace("${now}", str(current_utc_str))
    url = url.replace("{now}", str(current_utc_str))

    url = url.replace("${timestamp}", str(current_utc_str))
    url = url.replace("{timestamp}", str(current_utc_str))

    cur_utc_time = (
        datetime.datetime.fromtimestamp(current_utc_str)
        .strftime("%Y-%m-%d-%H-%M-%S")
        .split("-")
    )

    try:
        specifiers_re_url = re.findall(
            re.compile(
                "((\\$?){(lutc|now|timestamp):([YmdHMS])(-?)([YmdHMS]?)"
                "(-?)([YmdHMS]?)(-?)([YmdHMS]?)(-?)([YmdHMS]?)(-?)([YmdHMS]?)})"
            ),
            url,
        )
        if specifiers_re_url:
            for specifiers_re_url_i in specifiers_re_url:
                spec_val = str(specifiers_re_url_i[0].split(":")[1].split("}")[0])
                spec_val = spec_val.replace("Y", str(cur_utc_time[0]))
                spec_val = spec_val.replace("m", str(cur_utc_time[1]))
                spec_val = spec_val.replace("d", str(cur_utc_time[2]))
                spec_val = spec_val.replace("H", str(cur_utc_time[3]))
                spec_val = spec_val.replace("M", str(cur_utc_time[4]))
                spec_val = spec_val.replace("S", str(cur_utc_time[5]))
                url = url.replace(specifiers_re_url_i[0], str(spec_val))
    except Exception:
        show_exception(
            "parse_specifiers_now_url / "
            f"specifiers_re_url parsing failed\n{traceback.format_exc()}"
        )

    if url != orig_spec_url:
        logger.info(f"Original URL: {orig_spec_url}")
        logger.info(f"URL with parsed specifiers: {url}")

    return url


def get_catchup_days(is_seconds=False):
    try:
        catchup_days = min(
            max(
                1,
                max(
                    int(YukiData.array[channel]["catchup-days"])
                    for channel in YukiData.array
                    if "catchup-days" in YukiData.array[channel]
                ),
            ),
            7,
        )
    except Exception:
        catchup_days = 7
    if is_seconds:
        catchup_days = 86400 * (catchup_days + 1)
    return catchup_days
