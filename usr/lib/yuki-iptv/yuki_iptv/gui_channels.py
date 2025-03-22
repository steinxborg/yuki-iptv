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
import time
import math
import logging
import datetime
import textwrap
import traceback
from pathlib import Path
from multiprocessing import get_context
from PyQt6 import QtCore, QtGui, QtWidgets
from yuki_iptv.i18n import _
from yuki_iptv.xdg import LOCAL_DIR
from yuki_iptv.misc import YukiData
from yuki_iptv.channel_logos import channel_logos_worker, get_custom_channel_logo


logger = logging.getLogger(__name__)

custom_logos_enabled = os.path.isdir(Path(LOCAL_DIR, "logos")) or os.path.isdir(
    Path("..", "..", "share", "yuki-iptv", "channel_logos")
)

all_channels_lang = _("All channels")
favourites_lang = _("Favourites")


def get_page_count(array_len):
    return max(1, math.ceil(array_len / 100))


logos_cache = {}


def get_pixmap_from_filename(pixmap_filename):
    if pixmap_filename in logos_cache:
        return logos_cache[pixmap_filename]
    else:
        try:
            if os.path.isfile(pixmap_filename):
                icon_pixmap = QtGui.QIcon(pixmap_filename).pixmap(QtCore.QSize(32, 32))
                if icon_pixmap.isNull():
                    raise Exception("icon_pixmap is null")
                if not icon_pixmap.height():
                    raise Exception("icon_pixmap height is 0")
                logos_cache[pixmap_filename] = icon_pixmap
                icon_pixmap = None
                return logos_cache[pixmap_filename]
            else:
                if pixmap_filename:
                    YukiData.broken_logos.add(pixmap_filename)
                return None
        except Exception:
            if pixmap_filename:
                YukiData.broken_logos.add(pixmap_filename)
            return None


def get_of_txt(of_num):
    return f"/ {of_num}"


def getArrayItem(arr_item):
    arr_item_ret = None
    if arr_item:
        if arr_item in YukiData.array:
            arr_item_ret = YukiData.array[arr_item]
        elif arr_item in YukiData.movies:
            arr_item_ret = YukiData.movies[arr_item]
        else:
            try:
                if " ::: " in arr_item:
                    arr_item_split = arr_item.split(" ::: ")
                    for season_name in YukiData.series[
                        arr_item_split[2]
                    ].seasons.keys():
                        season = YukiData.series[arr_item_split[2]].seasons[season_name]
                        if season.name == arr_item_split[1]:
                            for episode_name in season.episodes.keys():
                                episode = season.episodes[episode_name]
                                if episode.title == arr_item_split[0]:
                                    arr_item_ret = {
                                        "title": episode.title,
                                        "tvg-name": "",
                                        "tvg-ID": "",
                                        "tvg-logo": "",
                                        "tvg-group": _("All channels"),
                                        "tvg-url": "",
                                        "catchup": "default",
                                        "catchup-source": "",
                                        "catchup-days": "7",
                                        "useragent": "",
                                        "referer": "",
                                        "url": episode.url,
                                    }
                                    break
                            break
            except Exception:
                logger.warning("Exception in getArrayItem (series)")
                logger.warning(traceback.format_exc())
    return arr_item_ret


def get_ua_ref_for_channel(channel_name1):
    cenc_decryption_key = ""
    useragent_ref = (
        YukiData.settings["playlist_useragent"]
        if YukiData.settings["playlist_useragent"]
        else YukiData.settings["ua"]
    )
    referer_ref = (
        YukiData.settings["playlist_referer"]
        if YukiData.settings["playlist_referer"]
        else YukiData.settings["referer"]
    )
    if channel_name1:
        channel_item = getArrayItem(channel_name1)
        if channel_item:
            if "cenc_decryption_key" in channel_item:
                cenc_decryption_key = channel_item["cenc_decryption_key"]
            useragent_ref = (
                channel_item["useragent"]
                if "useragent" in channel_item and channel_item["useragent"]
                else (
                    YukiData.settings["playlist_useragent"]
                    if YukiData.settings["playlist_useragent"]
                    else YukiData.settings["ua"]
                )
            )
            referer_ref = (
                channel_item["referer"]
                if "referer" in channel_item and channel_item["referer"]
                else (
                    YukiData.settings["playlist_referer"]
                    if YukiData.settings["playlist_referer"]
                    else YukiData.settings["referer"]
                )
            )
    if YukiData.settings["m3u"] in YukiData.channel_sets:
        channel_set = YukiData.channel_sets[YukiData.settings["m3u"]]
        if channel_name1 and channel_name1 in channel_set:
            channel_config = channel_set[channel_name1]
            if (
                "ua" in channel_config
                and channel_config["ua"]
                and channel_config["ua"]
                != (
                    YukiData.settings["playlist_useragent"]
                    if YukiData.settings["playlist_useragent"]
                    else YukiData.settings["ua"]
                )
            ):
                useragent_ref = channel_config["ua"]
            if (
                "ref" in channel_config
                and channel_config["ref"]
                and channel_config["ref"]
                != (
                    YukiData.settings["playlist_referer"]
                    if YukiData.settings["playlist_referer"]
                    else YukiData.settings["referer"]
                )
            ):
                referer_ref = channel_config["ref"]
    return useragent_ref, referer_ref, cenc_decryption_key


def generate_channels():
    channel_logos_request = {}

    try:
        idx = (YukiData.YukiGUI.page_box.value() - 1) * 100
    except Exception:
        idx = 0

    # Group and favourites filter
    array_filtered = []
    for j1 in YukiData.array_sorted:
        group1 = YukiData.array[j1]["tvg-group"]
        if YukiData.current_group != all_channels_lang:
            if YukiData.current_group == favourites_lang:
                if j1 not in YukiData.favourite_sets:
                    continue
            else:
                if group1 != YukiData.current_group:
                    continue
        array_filtered.append(j1)

    ch_array = [
        x13
        for x13 in array_filtered
        if YukiData.search.lower().strip() in x13.lower().strip()
    ]
    ch_array = ch_array[idx : idx + 100]
    try:
        if YukiData.search:
            YukiData.YukiGUI.page_box.setMaximum(get_page_count(len(ch_array)))
            YukiData.YukiGUI.of_lbl.setText(get_of_txt(get_page_count(len(ch_array))))
        else:
            YukiData.YukiGUI.page_box.setMaximum(get_page_count(len(array_filtered)))
            YukiData.YukiGUI.of_lbl.setText(
                get_of_txt(get_page_count(len(array_filtered)))
            )
    except Exception:
        pass
    res = {}
    k0 = -1
    k = 0
    for i in ch_array:
        k0 += 1
        k += 1
        prog = ""
        orig_category = ""
        orig_desc = ""
        prog_desc = ""

        epg_id = YukiData.get_epg_id(YukiData.array[i])
        epg_found = False

        if epg_id:
            current_prog = YukiData.get_current_programme(epg_id)
            if current_prog and current_prog["start"] != 0:
                epg_found = True
                start_time = datetime.datetime.fromtimestamp(
                    current_prog["start"]
                ).strftime("%H:%M")
                stop_time = datetime.datetime.fromtimestamp(
                    current_prog["stop"]
                ).strftime("%H:%M")
                t_t = time.time()
                percentage = round(
                    (t_t - current_prog["start"])
                    / (current_prog["stop"] - current_prog["start"])
                    * 100,
                    2,
                )
                if YukiData.settings["hideepgpercentage"]:
                    prog = current_prog["title"]
                else:
                    prog = str(percentage) + "% " + current_prog["title"]
                try:
                    if current_prog["desc"]:
                        orig_desc = current_prog["desc"]
                        prog_desc = "\n\n" + textwrap.fill(current_prog["desc"], 100)
                    else:
                        orig_desc = ""
                        prog_desc = ""
                except Exception:
                    orig_desc = ""
                    prog_desc = ""
                try:
                    if current_prog["category"]:
                        orig_category = current_prog["category"]
                except Exception:
                    orig_category = ""
            else:
                start_time = ""
                stop_time = ""
                t_t = time.time()
                percentage = 0
                prog = ""
                orig_desc = ""
                prog_desc = ""
                orig_category = ""
        MyPlaylistWidget = YukiData.YukiGUI.PlaylistWidget(
            YukiData.YukiGUI, YukiData.settings["hidechannellogos"]
        )
        channel_name = i

        original_channel_name = channel_name

        if YukiData.settings["channellogos"] != 3:
            try:
                channel_logo1 = ""
                if "tvg-logo" in YukiData.array[i]:
                    channel_logo1 = YukiData.array[i]["tvg-logo"]

                if (
                    custom_logos_enabled
                    and not channel_logo1
                    and "channel-logo-file-checked" not in YukiData.array[i]
                ):
                    YukiData.array[i]["channel-logo-file-checked"] = True
                    custom_channel_logo = get_custom_channel_logo(i)
                    if custom_channel_logo:
                        channel_logo1 = custom_channel_logo
                        YukiData.array[i]["tvg-logo"] = custom_channel_logo

                epg_logo1 = ""
                if epg_id:
                    epg_icon = YukiData.get_epg_icon(epg_id)
                    if epg_icon:
                        epg_logo1 = epg_icon

                (
                    req_data_ua,
                    req_data_ref,
                    _cenc_decryption_key,
                ) = get_ua_ref_for_channel(original_channel_name)
                channel_logos_request[YukiData.array[i]["title"]] = [
                    channel_logo1,
                    epg_logo1,
                    req_data_ua,
                    req_data_ref,
                ]
            except Exception:
                logger.warning(f"Exception in channel logos (channel '{i}')")
                logger.warning(traceback.format_exc())

        unicode_play_symbol = chr(9654) + " "
        append_symbol = ""
        if YukiData.playing_channel == channel_name:
            append_symbol = unicode_play_symbol
        MyPlaylistWidget.name_label.setText(
            append_symbol + str(k) + ". " + channel_name
        )
        orig_prog = prog
        try:
            tooltip_group = "{}: {}".format(_("Group"), YukiData.array[i]["tvg-group"])
        except Exception:
            tooltip_group = "{}: {}".format(_("Group"), _("All channels"))
        if epg_found and orig_prog and not YukiData.settings["hideepgfromplaylist"]:
            desc1 = ""
            wrap_desc = 40
            if orig_desc:
                if YukiData.settings["description_view"] == 0:
                    desc_wrapped = textwrap.fill(
                        (f"({orig_category}) " if orig_category else "") + orig_desc,
                        wrap_desc,
                    ).split("\n")
                    if len(desc_wrapped) > 2:
                        desc_wrapped = desc_wrapped[:2]
                        desc_wrapped[1] = desc_wrapped[1][:-3] + "..."
                    desc_wrapped = "<br>".join(desc_wrapped)
                    desc1 = "<br>" + desc_wrapped
                elif YukiData.settings["description_view"] == 1:
                    desc1 = "<br>" + "<br>".join(
                        textwrap.fill(
                            (
                                (f"({orig_category}) " if orig_category else "")
                                + orig_desc
                            ),
                            wrap_desc,
                        ).split("\n")
                    )
            MyPlaylistWidget.setDescription(
                "<i>" + prog + "</i>" + desc1,
                (
                    f"<b>{i}</b>" + f"<br>{tooltip_group}<br><br>"
                    "<i>" + orig_prog + "</i>" + prog_desc
                ).replace("\n", "<br>"),
            )
            MyPlaylistWidget.showDescription()
            try:
                if start_time:
                    MyPlaylistWidget.progress_label.setText(start_time)
                    MyPlaylistWidget.end_label.setText(stop_time)
                    MyPlaylistWidget.progress_bar.setValue(int(percentage))
                else:
                    MyPlaylistWidget.progress_bar.hide()
            except Exception:
                logger.warning("Async EPG load problem, ignoring")
        else:
            MyPlaylistWidget.setDescription("", f"<b>{i}</b><br>{tooltip_group}")
            MyPlaylistWidget.progress_bar.hide()
            MyPlaylistWidget.hideDescription()

        MyPlaylistWidget.setPixmap(YukiData.YukiGUI.tv_icon)

        if YukiData.settings["channellogos"] != 3:  # Do not load any logos
            try:
                if f"LOGO:::{original_channel_name}" in YukiData.mp_manager_dict:
                    if YukiData.settings["channellogos"] == 0:  # Prefer M3U
                        first_loaded = False
                        if YukiData.mp_manager_dict[f"LOGO:::{original_channel_name}"][
                            0
                        ]:
                            channel_logo = get_pixmap_from_filename(
                                YukiData.mp_manager_dict[
                                    f"LOGO:::{original_channel_name}"
                                ][0]
                            )
                            if channel_logo:
                                first_loaded = True
                                MyPlaylistWidget.setPixmap(channel_logo)
                        if not first_loaded:
                            channel_logo = get_pixmap_from_filename(
                                YukiData.mp_manager_dict[
                                    f"LOGO:::{original_channel_name}"
                                ][1]
                            )
                            if channel_logo:
                                MyPlaylistWidget.setPixmap(channel_logo)
                    elif YukiData.settings["channellogos"] == 1:  # Prefer EPG
                        first_loaded = False
                        if YukiData.mp_manager_dict[f"LOGO:::{original_channel_name}"][
                            1
                        ]:
                            channel_logo = get_pixmap_from_filename(
                                YukiData.mp_manager_dict[
                                    f"LOGO:::{original_channel_name}"
                                ][1]
                            )
                            if channel_logo:
                                first_loaded = True
                                MyPlaylistWidget.setPixmap(channel_logo)
                        if not first_loaded:
                            channel_logo = get_pixmap_from_filename(
                                YukiData.mp_manager_dict[
                                    f"LOGO:::{original_channel_name}"
                                ][0]
                            )
                            if channel_logo:
                                MyPlaylistWidget.setPixmap(channel_logo)
                    elif (
                        YukiData.settings["channellogos"] == 2
                    ):  # Do not load from EPG (only M3U)
                        if YukiData.mp_manager_dict[f"LOGO:::{original_channel_name}"][
                            0
                        ]:
                            channel_logo = get_pixmap_from_filename(
                                YukiData.mp_manager_dict[
                                    f"LOGO:::{original_channel_name}"
                                ][0]
                            )
                            if channel_logo:
                                MyPlaylistWidget.setPixmap(channel_logo)
            except Exception:
                logger.warning("Set channel logos failed with exception")
                logger.warning(traceback.format_exc())

        myQListWidgetItem = QtWidgets.QListWidgetItem()
        myQListWidgetItem.setData(QtCore.Qt.ItemDataRole.UserRole, i)
        myQListWidgetItem.setSizeHint(
            QtCore.QSize(
                YukiData.win.listWidget.sizeHint().width(),
                MyPlaylistWidget.sizeHint().height(),
            )
        )
        res[k0] = [myQListWidgetItem, MyPlaylistWidget, k0, i]
    j1 = YukiData.playing_channel
    if j1:
        current_programme = None
        epg_id = YukiData.get_epg_id(j1)
        if epg_id:
            programme = YukiData.get_current_programme(epg_id)
            if programme:
                current_programme = programme
        YukiData.show_progress(current_programme)

    # Fetch channel logos
    try:
        if YukiData.settings["channellogos"] != 3:
            if channel_logos_request != YukiData.channel_logos_request_old:
                YukiData.channel_logos_request_old = channel_logos_request
                logger.debug("Channel logos request")
                if (
                    YukiData.channel_logos_process
                    and YukiData.channel_logos_process.is_alive()
                ):
                    # logger.debug(
                    #     "Old channel logos request found, stopping it"
                    # )
                    YukiData.channel_logos_process.kill()
                YukiData.channel_logos_process = get_context("spawn").Process(
                    name="[yuki-iptv] channel_logos_worker",
                    target=channel_logos_worker,
                    daemon=True,
                    args=(
                        channel_logos_request,
                        YukiData.mp_manager_dict,
                    ),
                )
                YukiData.channel_logos_process.start()
    except Exception:
        logger.warning("Fetch channel logos failed with exception:")
        logger.warning(traceback.format_exc())

    return res
