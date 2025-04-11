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
import re
import sys
import json
import time
import atexit
import locale
import pprint
import signal
import urllib
import hashlib
import logging
import os.path
import datetime
import traceback
import subprocess
import urllib.parse
from yuki_iptv import environ, exception_handler  # noqa: F401
from pathlib import Path
from functools import partial
from gi.repository import Gio, GLib
from PyQt6 import QtGui, QtCore, QtWidgets
from multiprocessing import Manager, get_context
from yuki_iptv.i18n import _, load_qt_translations
from yuki_iptv.drm import convert_key
from yuki_iptv.exception_handler import show_exception
from yuki_iptv.xtream import log_xtream
from yuki_iptv.args import args1
from yuki_iptv.kill_process_childs import kill_process_childs
from yuki_iptv.epg import (
    epg_worker,
    epg_is_in_date,
    worker_get_epg_id,
    worker_get_epg_icon,
    worker_get_all_epg_names,
    worker_get_epg_programmes,
    worker_get_current_programme,
    worker_check_programmes_actual,
)
from yuki_iptv.gui import (
    SizeGrip,
    centerwidget,
    YukiGUIClass,
    tvguide_hide,
    TVguideCloseLabel,
    moveWindowToCenter,
    PlaylistDockWidget,
    ControlPanelDockWidget,
    set_record_icon,
    set_record_stop_icon,
    destroy_listwidget_items,
    thread_tvguide_update_start,
    thread_tvguide_update_error,
    thread_tvguide_update_outdated,
    thread_tvguide_update_end,
)
from yuki_iptv.xdg import CACHE_DIR, LOCAL_DIR, SAVE_FOLDER_DEFAULT
from yuki_iptv.gui_channels import (
    getArrayItem,
    get_page_count,
    generate_channels,
    get_ua_ref_for_channel,
    get_pixmap_from_filename,
)
from yuki_iptv.misc import (
    BCOLOR,
    YTDL_NAME,
    WINDOW_SIZE,
    TVGUIDE_WIDTH,
    QT_TIME_FORMAT,
    FORBIDDEN_FILENAME_CHARS,
    MAIN_WINDOW_TITLE,
    AUDIO_SAMPLE_FORMATS,
    DOCKWIDGET_PLAYLIST_WIDTH,
    DOCKWIDGET_CONTROLPANEL_HEIGHT_LOW,
    DOCKWIDGET_CONTROLPANEL_HEIGHT_HIGH,
    YukiData,
    decode,
    stream_info,
    convert_size,
    format_bytes,
    format_seconds,
    get_current_time,
)
from yuki_iptv.mpris import start_mpris, mpris_seeked, emit_mpris_change
from yuki_iptv.record import (
    record,
    stop_record,
    record_return,
    is_youtube_url,
    is_ffmpeg_recording,
    terminate_record_process,
)
from yuki_iptv.archive_catchup import (
    get_catchup_url,
    get_catchup_days,
    format_catchup_array,
    parse_specifiers_now_url,
)
from yuki_iptv.inhibit import inhibit, uninhibit, screensaver_register
from yuki_iptv.menubar import (
    get_seq,
    get_first_run,
    update_menubar,
    populate_menubar,
    init_menubar_player,
    get_active_vf_filters,
    init_yuki_iptv_menubar,
    reload_menubar_shortcuts,
)
from yuki_iptv.options import read_option, write_option
from yuki_iptv.threads import (
    kill_active_childs,
    idle_function,
    executeInMainThread,
    async_gui_blocking_function,
)
from yuki_iptv.shortcuts import (
    fixup_shortcuts,
    main_shortcuts_default,
    main_shortcuts_internal,
    main_shortcuts_translations,
)
from yuki_iptv.playlist import load_playlist, EmptyXTreamClass
from yuki_iptv.settings import parse_settings
from yuki_iptv.mpv_options import get_mpv_options
from yuki_iptv.channel_logos import channel_logos_worker
from yuki_iptv.gui_playlists import Data as gui_playlists_data
from yuki_iptv.gui_playlists import (
    show_playlists,
    playlist_selected,
)
from thirdparty.xtream import XTream

os.chdir(os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger("yuki-iptv")
mpv_logger = logging.getLogger("libmpv")

APP_VERSION = "__DEB_VERSION__"

if os.path.isfile("/.flatpak-info"):
    APP_VERSION += " (Flatpak)"
elif "SNAP" in os.environ:
    APP_VERSION += " (Snap)"
elif "container" in os.environ:
    APP_VERSION += " (container)"

if args1.version:
    print(f"{MAIN_WINDOW_TITLE} {APP_VERSION}")
    sys.exit(0)


if __name__ == "__main__":
    try:

        def exit_handler(*args):
            if not YukiData.exiting:
                YukiData.exiting = True
                logger.info("Exiting")
                try:
                    if YukiData.player:
                        YukiData.player.quit()
                except Exception:
                    pass
            try:
                try:
                    if YukiData.epg_pool:
                        try:
                            YukiData.epg_pool.close()
                            YukiData.epg_pool = None
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    if multiprocessing_manager:
                        multiprocessing_manager.shutdown()
                except Exception:
                    pass
                kill_active_childs()
                try:
                    uninhibit()
                except Exception:
                    pass
                kill_active_childs()
                try:
                    stop_record()
                except Exception:
                    pass
                try:
                    for rec_1 in sch_recordings:
                        do_stop_record(rec_1)
                except Exception:
                    pass
                try:
                    if YukiData.mpris_loop:
                        YukiData.mpris_running = False
                        YukiData.mpris_loop.quit()
                except Exception:
                    pass
                try:
                    if multiprocessing_manager:
                        multiprocessing_manager.shutdown()
                except Exception:
                    pass
                kill_active_childs()
                if not YukiData.do_save_settings:
                    kill_process_childs(os.getpid(), signal.SIGKILL)
            except BaseException:
                pass

        atexit.register(exit_handler)
        signal.signal(signal.SIGTERM, exit_handler)
        signal.signal(signal.SIGINT, exit_handler)

        if not QtWidgets.QApplication.instance():
            app = QtWidgets.QApplication(sys.argv)
        else:
            app = QtWidgets.QApplication.instance()

        def sigint_handler(*args, **kwargs):
            try:
                if YukiData.mpris_loop:
                    YukiData.mpris_running = False
                    YukiData.mpris_loop.quit()
            except Exception:
                pass
            app.quit()

        signal.signal(signal.SIGINT, sigint_handler)
        signal.signal(signal.SIGTERM, sigint_handler)

        app.setDesktopFileName("yuki-iptv")
        load_qt_translations(app)

        # https://www.qt.io/blog/dark-mode-on-windows-11-with-qt-6.5#before-qt-65
        current_palette = QtGui.QPalette()
        YukiData.use_dark_icon_theme = (
            current_palette.color(QtGui.QPalette.ColorRole.WindowText).lightness()
            > current_palette.color(QtGui.QPalette.ColorRole.Window).lightness()
        )
        YukiData.icons_folder = (
            Path(os.path.dirname(os.path.abspath(__file__))).parent.parent
            / "share"
            / "yuki-iptv"
            / ("icons_dark" if YukiData.use_dark_icon_theme else "icons")
        )

        # This is necessary since PyQT stomps over the locale settings needed by libmpv.
        # This needs to happen after importing PyQT before
        # creating the first mpv.MPV instance.
        locale.setlocale(locale.LC_NUMERIC, "C")

        logger.info(f"Version: {APP_VERSION}")
        logger.info("Python " + sys.version.strip())
        logger.info(f"Qt {QtCore.qVersion()} ({app.platformName()})")
        logger.info(
            f"{'Dark' if YukiData.use_dark_icon_theme else 'Light'} window theme"
        )

        from thirdparty import mpv

        multiprocessing_manager = Manager()
        YukiData.mp_manager_dict = multiprocessing_manager.dict()
        YukiData.mp_manager_dict["logos_inprogress"] = False
        YukiData.mp_manager_dict["logos_completed"] = False
        YukiData.mp_manager_dict["logosmovie_inprogress"] = False
        YukiData.mp_manager_dict["logosmovie_completed"] = False

        YukiData.mpv_api_version = (
            " (API v" + ".".join(map(str, mpv._mpv_client_api_version())) + ")"
        )

        if not os.path.isfile(Path(LOCAL_DIR) / "favplaylist.m3u"):
            with open(
                Path(LOCAL_DIR) / "favplaylist.m3u", "w", encoding="utf8"
            ) as favplaylist_file:
                favplaylist_file.write(
                    "#EXTM3U\n#EXTINF:-1,-\nhttp://255.255.255.255\n"
                )

        def save_channel_sets():
            with open(
                Path(LOCAL_DIR) / "channelsettings.json", "w", encoding="utf8"
            ) as channel_sets_file:
                channel_sets_file.write(json.dumps(YukiData.channel_sets))

        if not os.path.isfile(Path(LOCAL_DIR) / "channelsettings.json"):
            save_channel_sets()
        else:
            with open(
                Path(LOCAL_DIR) / "channelsettings.json", encoding="utf8"
            ) as channel_sets_file1:
                YukiData.channel_sets = json.loads(channel_sets_file1.read())

        YukiData.settings, settings_loaded = parse_settings()

        def save_favourite_sets():
            favourite_sets_2 = {}
            if os.path.isfile(Path(LOCAL_DIR) / "favouritechannels.json"):
                with open(
                    Path(LOCAL_DIR) / "favouritechannels.json", encoding="utf8"
                ) as favouritechannels_file:
                    favourite_sets_2 = json.loads(favouritechannels_file.read())
            if YukiData.settings["m3u"]:
                favourite_sets_2[YukiData.settings["m3u"]] = YukiData.favourite_sets
            with open(
                Path(LOCAL_DIR) / "favouritechannels.json", "w", encoding="utf8"
            ) as favouritechannels_file2:
                favouritechannels_file2.write(json.dumps(favourite_sets_2))

        if not os.path.isfile(Path(LOCAL_DIR) / "favouritechannels.json"):
            save_favourite_sets()
        else:
            favourite_sets1 = {}
            with open(
                Path(LOCAL_DIR) / "favouritechannels.json", encoding="utf8"
            ) as favouritechannels_file3:
                favourite_sets1 = json.loads(favouritechannels_file3.read())
            if YukiData.settings["m3u"] in favourite_sets1:
                YukiData.favourite_sets = favourite_sets1[YukiData.settings["m3u"]]

        def save_player_tracks():
            player_tracks_2 = {}
            if os.path.isfile(Path(LOCAL_DIR) / "tracks.json"):
                with open(
                    Path(LOCAL_DIR) / "tracks.json", encoding="utf8"
                ) as tracks_file0:
                    player_tracks_2 = json.loads(tracks_file0.read())
            if YukiData.settings["m3u"]:
                player_tracks_2[YukiData.settings["m3u"]] = YukiData.player_tracks
            with open(
                Path(LOCAL_DIR) / "tracks.json", "w", encoding="utf8"
            ) as tracks_file1:
                tracks_file1.write(json.dumps(player_tracks_2))

        if os.path.isfile(Path(LOCAL_DIR) / "tracks.json"):
            with open(Path(LOCAL_DIR) / "tracks.json", encoding="utf8") as tracks_file:
                player_tracks1 = json.loads(tracks_file.read())
            if YukiData.settings["m3u"] in player_tracks1:
                YukiData.player_tracks = player_tracks1[YukiData.settings["m3u"]]

        # Get EPG name from settings
        def get_epg_name(channel_name):
            epg_name = ""
            if (
                YukiData.settings["m3u"] in YukiData.channel_sets
                and channel_name in YukiData.channel_sets[YukiData.settings["m3u"]]
            ):
                if (
                    "epgname"
                    in YukiData.channel_sets[YukiData.settings["m3u"]][channel_name]
                ):
                    if YukiData.channel_sets[YukiData.settings["m3u"]][channel_name][
                        "epgname"
                    ]:
                        epg_name = YukiData.channel_sets[YukiData.settings["m3u"]][
                            channel_name
                        ]["epgname"]
            return epg_name

        def _get_epg_id(tvg_id, tvg_name, channel_name):
            ret = None
            if not YukiData.epg_pool_running:
                try:
                    ret = worker_get_epg_id(
                        tvg_id,
                        tvg_name,
                        channel_name,
                        get_epg_name(channel_name),
                        YukiData.epg_array,
                    )
                except Exception:
                    logger.warning("get_epg_id failed")
                    logger.warning(traceback.format_exc())
            return ret

        def get_epg_id(_data):
            if isinstance(_data, dict):
                _epg_title = (
                    _data["orig_title"] if "orig_title" in _data else _data["title"]
                )
                return _get_epg_id(_data["tvg-ID"], _data["tvg-name"], _epg_title)
            elif isinstance(_data, str):
                if _data in YukiData.array:
                    _epg_title = (
                        YukiData.array[_data]["orig_title"]
                        if "orig_title" in YukiData.array[_data]
                        else YukiData.array[_data]["title"]
                    )
                    return _get_epg_id(
                        YukiData.array[_data]["tvg-ID"],
                        YukiData.array[_data]["tvg-name"],
                        _epg_title,
                    )
                else:
                    return _get_epg_id("", "", _data)
            else:
                # logger.warning("get_epg_id failed - unknown type passed")
                return None

        YukiData.get_epg_id = get_epg_id

        def get_epg_programmes(epg_id):
            ret = None
            if not YukiData.epg_pool_running:
                try:
                    ret = worker_get_epg_programmes(epg_id, YukiData.epg_array)
                except Exception:
                    logger.warning("get_epg_programmes failed")
                    logger.warning(traceback.format_exc())
            return ret

        def get_epg_icon(epg_id):
            ret = None
            if not YukiData.epg_pool_running:
                try:
                    ret = worker_get_epg_icon(epg_id, YukiData.epg_array)
                except Exception:
                    logger.warning("get_epg_programmes failed")
                    logger.warning(traceback.format_exc())
            return ret

        YukiData.get_epg_icon = get_epg_icon

        def check_programmes_actual():
            ret = None
            if not YukiData.epg_pool_running:
                try:
                    ret = worker_check_programmes_actual(YukiData.epg_array)
                except Exception:
                    logger.warning("check_programmes_actual failed")
                    logger.warning(traceback.format_exc())
            return ret

        def get_all_epg_names():
            ret = None
            if not YukiData.epg_pool_running:
                try:
                    ret = worker_get_all_epg_names(YukiData.epg_array)
                except Exception:
                    logger.warning("get_all_epg_names failed")
                    logger.warning(traceback.format_exc())
            return ret

        def get_current_programme(epg_id):
            ret = None
            if not YukiData.epg_pool_running:
                try:
                    ret = worker_get_current_programme(epg_id, YukiData.epg_array)
                except Exception:
                    logger.warning("get_current_programme failed")
                    logger.warning(traceback.format_exc())
            return ret

        YukiData.get_current_programme = get_current_programme

        def purge_epg_cache():
            if not YukiData.epg_pool_running:
                logger.info("Purging EPG cache")
                for epg_cache_filename in os.listdir(Path(CACHE_DIR) / "epg"):
                    epg_cache_file = Path(CACHE_DIR) / "epg" / epg_cache_filename
                    if os.path.isfile(epg_cache_file):
                        os.remove(epg_cache_file)

        def force_update_epg_act():
            logger.info("Force update EPG triggered")
            purge_epg_cache()
            epg_update()

        YukiGUI = YukiGUIClass()
        YukiData.YukiGUI = YukiGUI

        channels = {}

        save_folder = YukiData.settings["save_folder"]

        if not os.path.isdir(str(Path(save_folder))):
            try:
                Path(save_folder).mkdir(parents=True, exist_ok=True)
            except Exception:
                show_exception("Failed to create save folder!")
                save_folder = SAVE_FOLDER_DEFAULT
                if not os.path.isdir(str(Path(save_folder))):
                    Path(save_folder).mkdir(parents=True, exist_ok=True)

        if not os.access(save_folder, os.W_OK | os.X_OK):
            save_folder = SAVE_FOLDER_DEFAULT
            show_exception(
                "Save folder is not writable (os.access), using default save folder"
            )

        if not YukiData.settings["scrrecnosubfolders"]:
            try:
                (Path(save_folder) / "screenshots").mkdir(parents=True, exist_ok=True)
                (Path(save_folder) / "recordings").mkdir(parents=True, exist_ok=True)
            except Exception:
                save_folder = SAVE_FOLDER_DEFAULT
                show_exception(
                    "Save folder is not writable (subfolders), "
                    "using default save folder"
                )
        else:
            if os.path.isdir(Path(save_folder) / "screenshots"):
                try:
                    os.rmdir(Path(save_folder) / "screenshots")
                except Exception:
                    pass
            if os.path.isdir(Path(save_folder) / "recordings"):
                try:
                    os.rmdir(Path(save_folder) / "recordings")
                except Exception:
                    pass

        YukiData.save_folder = save_folder

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
            logger.info(f"Loading XTream with headers {json.dumps(xtream_headers)}")
            try:
                xt = XTream(
                    log_xtream,
                    hashlib.sha512(
                        YukiData.settings["m3u"].encode("utf-8")
                    ).hexdigest(),
                    xtream_username,
                    xtream_password,
                    xtream_url,
                    headers=xtream_headers,
                    hide_adult_content=False,
                    cache_path="",
                )
            except Exception:
                show_exception(traceback.format_exc())
                xt = EmptyXTreamClass()
            return xt, xtream_username, xtream_password, xtream_url

        YukiData.load_xtream = load_xtream

        if os.path.isfile(Path(LOCAL_DIR) / "sortchannels.json"):
            with open(
                Path(LOCAL_DIR) / "sortchannels.json", encoding="utf8"
            ) as channel_sort_file1:
                channel_sort3 = json.loads(channel_sort_file1.read())
                if YukiData.settings["m3u"] in channel_sort3:
                    YukiData.channel_sort = channel_sort3[YukiData.settings["m3u"]]

        (
            groups,
            m3u_exists,
            xt,
        ) = load_playlist()

        YukiGUI.create_windows()

        if os.path.isfile(Path(LOCAL_DIR) / "hotkeys.json"):
            os.rename(
                (Path(LOCAL_DIR) / "hotkeys.json"), (Path(LOCAL_DIR) / "shortcuts.json")
            )

        def resettodefaults_btn_clicked():
            resettodefaults_btn_clicked_msg = QtWidgets.QMessageBox.question(
                None,
                MAIN_WINDOW_TITLE,
                _("Are you sure?"),
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.Yes,
            )
            if (
                resettodefaults_btn_clicked_msg
                == QtWidgets.QMessageBox.StandardButton.Yes
            ):
                logger.info("Restoring default shortcuts")
                YukiData.main_shortcuts = main_shortcuts_default.copy()
                YukiGUI.shortcuts_table.setRowCount(len(YukiData.main_shortcuts))
                shortcut_i = -1
                for shortcut in YukiData.main_shortcuts:
                    shortcut_i += 1
                    YukiGUI.shortcuts_table.setItem(
                        shortcut_i,
                        0,
                        get_widget_item(main_shortcuts_translations[shortcut]),
                    )
                    if isinstance(YukiData.main_shortcuts[shortcut], str):
                        shortcut_str = YukiData.main_shortcuts[shortcut]
                    else:
                        shortcut_str = QtGui.QKeySequence(
                            YukiData.main_shortcuts[shortcut]
                        ).toString()
                    kbd_widget = get_widget_item(shortcut_str)
                    kbd_widget.setToolTip(_("Double click to change"))
                    YukiGUI.shortcuts_table.setItem(shortcut_i, 1, kbd_widget)
                YukiGUI.shortcuts_table.resizeColumnsToContents()
                with open(
                    Path(LOCAL_DIR) / "shortcuts.json", "w", encoding="utf8"
                ) as shortcuts_file_1:
                    shortcuts_file_1.write(
                        json.dumps(
                            {
                                "current_profile": {
                                    "keys": fixup_shortcuts(YukiData.main_shortcuts)
                                }
                            }
                        )
                    )
                reload_shortcuts()

        YukiGUI.resettodefaults_btn.clicked.connect(resettodefaults_btn_clicked)

        class KeySequenceEdit(QtWidgets.QKeySequenceEdit):
            def keyPressEvent(self, event):
                super().keyPressEvent(event)
                self.setKeySequence(QtGui.QKeySequence(self.keySequence()))

        keyseq = KeySequenceEdit()

        def keyseq_ok_clicked():
            if YukiData.selected_shortcut_row != -1:
                sel_keyseq = keyseq.keySequence().toString()
                search_value = YukiGUI.shortcuts_table.item(
                    YukiData.selected_shortcut_row, 0
                ).text()
                shortcut_taken = False
                for sci1 in range(YukiGUI.shortcuts_table.rowCount()):
                    if sci1 != YukiData.selected_shortcut_row:
                        if YukiGUI.shortcuts_table.item(sci1, 1).text() == sel_keyseq:
                            shortcut_taken = True
                forbidden_shortcuts = [
                    "Return",
                    "Key.Key_MediaNext",
                    "Key.Key_MediaPause",
                    "Key.Key_MediaPlay",
                    "Key.Key_MediaPrevious",
                    "Key.Key_MediaRecord",
                    "Key.Key_MediaStop",
                    "Key.Key_MediaTogglePlayPause",
                    "Key.Key_Play",
                    "Key.Key_Stop",
                    "Key.Key_VolumeDown",
                    "Key.Key_VolumeMute",
                    "Key.Key_VolumeUp",
                ]
                if sel_keyseq in forbidden_shortcuts:
                    shortcut_taken = True
                if not shortcut_taken:
                    YukiGUI.shortcuts_table.item(
                        YukiData.selected_shortcut_row, 1
                    ).setText(sel_keyseq)
                    for (
                        shortcut_name,
                        shortcut_value,
                    ) in main_shortcuts_translations.items():
                        if shortcut_value == search_value:
                            YukiData.main_shortcuts[shortcut_name] = sel_keyseq
                            with open(
                                Path(LOCAL_DIR) / "shortcuts.json",
                                "w",
                                encoding="utf8",
                            ) as shortcuts_file:
                                shortcuts_file.write(
                                    json.dumps(
                                        {
                                            "current_profile": {
                                                "keys": fixup_shortcuts(
                                                    YukiData.main_shortcuts
                                                )
                                            }
                                        }
                                    )
                                )
                            reload_shortcuts()
                    YukiGUI.shortcuts_win_2.hide()
                else:
                    msg_shortcut_taken = QtWidgets.QMessageBox(
                        QtWidgets.QMessageBox.Icon.Warning,
                        MAIN_WINDOW_TITLE,
                        _("Shortcut already used"),
                        QtWidgets.QMessageBox.StandardButton.Ok,
                    )
                    msg_shortcut_taken.exec()

        def epg_win_checkbox_changed():
            YukiGUI.tvguide_lbl_2.verticalScrollBar().setSliderPosition(
                YukiGUI.tvguide_lbl_2.verticalScrollBar().minimum()
            )
            YukiGUI.tvguide_lbl_2.setText(_("No TV guide for channel"))
            try:
                ch_3 = YukiGUI.epg_win_checkbox.currentText()
                ch_3_guide = update_tvguide(
                    ch_3, True, date_selected=YukiData.epg_selected_date
                ).replace("!@#$%^^&*(", "\n")
                ch_3_guide = ch_3_guide.replace("\n", "<br>").replace("<br>", "", 1)
                if ch_3_guide.strip():
                    YukiGUI.tvguide_lbl_2.setText(ch_3_guide)
                else:
                    YukiGUI.tvguide_lbl_2.setText(_("No TV guide for channel"))
            except Exception:
                show_exception(
                    f"Exception in epg_win_checkbox_changed\n\n{traceback.format_exc()}"
                )

        def tvguide_channelfilter_do():
            try:
                if YukiGUI.tvguidechannelfilter:
                    filter_txt3 = YukiGUI.tvguidechannelfilter.text()
                else:
                    filter_txt3 = ""
            except Exception:
                filter_txt3 = ""
            for tvguide_item in range(YukiGUI.epg_win_checkbox.count()):
                if (
                    filter_txt3.lower().strip()
                    in YukiGUI.epg_win_checkbox.itemText(tvguide_item).lower().strip()
                ):
                    YukiGUI.epg_win_checkbox.view().setRowHidden(tvguide_item, False)
                else:
                    YukiGUI.epg_win_checkbox.view().setRowHidden(tvguide_item, True)

        def epg_date_changed(epg_date):
            YukiData.epg_selected_date = datetime.datetime.fromordinal(
                epg_date.toPyDate().toordinal()
            )
            epg_win_checkbox_changed()

        def do_open_archive(link):
            if "#__archive__" in link:
                archive_json = json.loads(
                    urllib.parse.unquote_plus(link.split("#__archive__")[1])
                )
                arr1 = getArrayItem(archive_json[0])
                arr1 = format_catchup_array(arr1)

                channel_url = getArrayItem(archive_json[0])["url"]
                start_time = archive_json[1]
                end_time = archive_json[2]
                prog_index = archive_json[3]

                if "#__rewind__" not in link:
                    YukiData.archive_epg = archive_json

                catchup_id = ""
                try:
                    current_programmes = None
                    epg_id = get_epg_id(archive_json[0])
                    if epg_id:
                        programmes = get_epg_programmes(epg_id)
                        if programmes:
                            current_programmes = programmes

                    if current_programmes:
                        if "catchup-id" in current_programmes[int(prog_index)]:
                            catchup_id = current_programmes[int(prog_index)][
                                "catchup-id"
                            ]
                except Exception:
                    show_exception(
                        "do_open_archive / catchup_id parsing"
                        f" failed\n\n{traceback.format_exc()}"
                    )

                arr2 = arr1

                if YukiData.is_xtream:
                    arr2["catchup"] = "xc"

                play_url = get_catchup_url(
                    channel_url, arr2, start_time, end_time, catchup_id
                )

                itemClicked_event(
                    archive_json[0], play_url, True, is_rewind=(len(archive_json) == 5)
                )
                setChannelText("({}) {}".format(_("Archive"), archive_json[0]), True)
                YukiGUI.progress.hide()
                YukiGUI.start_label.setText("")
                YukiGUI.start_label.hide()
                YukiGUI.stop_label.setText("")
                YukiGUI.stop_label.hide()
                YukiGUI.epg_win.hide()

                return False

        def ext_open_btn_clicked():
            write_option("extplayer", YukiGUI.ext_player_txt.text().strip())
            YukiGUI.ext_win.close()
            try:
                subprocess.Popen(
                    YukiGUI.ext_player_txt.text().strip().split(" ")
                    + [getArrayItem(YukiData.item_selected)["url"]]
                )
            except Exception:
                show_exception(
                    traceback.format_exc(), _("Failed to open external player!")
                )

        YukiGUI.create4(keyseq)

        YukiGUI.keyseq_cancel.clicked.connect(YukiGUI.shortcuts_win_2.hide)
        YukiGUI.keyseq_ok.clicked.connect(keyseq_ok_clicked)
        YukiGUI.tvguidechannelfiltersearch.clicked.connect(tvguide_channelfilter_do)
        YukiGUI.tvguidechannelfilter.returnPressed.connect(tvguide_channelfilter_do)
        YukiGUI.showonlychplaylist_chk.clicked.connect(lambda: update_tvguide_2())
        YukiGUI.epg_win_checkbox.currentIndexChanged.connect(epg_win_checkbox_changed)
        YukiGUI.epg_select_date.activated.connect(epg_date_changed)
        YukiGUI.epg_select_date.clicked.connect(epg_date_changed)
        YukiGUI.tvguide_lbl_2.label.linkActivated.connect(do_open_archive)
        YukiGUI.epg_custom_name_button.clicked.connect(
            YukiGUI.epg_custom_name_input_edit
        )
        YukiGUI.epg_custom_name_select.itemDoubleClicked.connect(
            YukiGUI.epg_custom_name_select_clicked
        )
        YukiGUI.ext_open_btn.clicked.connect(ext_open_btn_clicked)

        extplayer = read_option("extplayer")
        if not extplayer:
            extplayer = "mpv"
        YukiGUI.ext_player_txt.setText(extplayer)

        if os.path.isfile(Path(LOCAL_DIR) / "playlists.json"):
            with open(
                Path(LOCAL_DIR) / "playlists.json", encoding="utf8"
            ) as playlists_json:
                YukiData.playlists_saved = json.loads(playlists_json.read())

        def programme_clicked(item):
            times = item.text().split("\n")[0]
            start_time = QtCore.QDateTime.fromString(
                times.split(" - ")[0], QT_TIME_FORMAT
            )
            end_time = QtCore.QDateTime.fromString(
                times.split(" - ")[1], QT_TIME_FORMAT
            )
            if not start_time or not end_time:
                show_exception(f"Cannot parse date format - {times}!")
                return
            YukiGUI.starttime_w.setDateTime(start_time)
            YukiGUI.endtime_w.setDateTime(end_time)

        def addrecord_clicked():
            selected_channel = YukiGUI.choosechannel_ch.currentText()
            start_time_r = (
                YukiGUI.starttime_w.dateTime()
                .toPyDateTime()
                .strftime("%d.%m.%Y %H:%M:%S")
            )
            end_time_r = (
                YukiGUI.endtime_w.dateTime()
                .toPyDateTime()
                .strftime("%d.%m.%Y %H:%M:%S")
            )
            YukiGUI.schedulers.addItem(
                _("Channel") + ": " + selected_channel + "\n"
                "{}: ".format(_("Start record time")) + start_time_r + "\n"
                "{}: ".format(_("End record time")) + end_time_r + "\n"
            )

        sch_recordings = {}

        def do_start_record(name1):
            ch_name = name1.split("_")[0]
            ch = ch_name.replace(" ", "_")
            for char in FORBIDDEN_FILENAME_CHARS:
                ch = ch.replace(char, "")
            cur_time = datetime.datetime.now().strftime("%d%m%Y_%H%M%S")
            record_url = getArrayItem(ch_name)["url"]
            record_format = ".ts"
            if is_youtube_url(record_url):
                record_format = ".mkv"
            if not YukiData.settings["scrrecnosubfolders"]:
                out_file = str(
                    Path(
                        save_folder,
                        "recordings",
                        "recording_-_" + cur_time + "_-_" + ch + record_format,
                    )
                )
            else:
                out_file = str(
                    Path(
                        save_folder,
                        "recording_-_" + cur_time + "_-_" + ch + record_format,
                    )
                )
            return [
                record_return(
                    record_url,
                    out_file,
                    ch_name,
                    f"Referer: {YukiData.settings['referer']}",
                    get_ua_ref_for_channel,
                ),
                time.time(),
                out_file,
                ch_name,
            ]

        def do_stop_record(sch_recordings_name):
            if sch_recordings_name in sch_recordings:
                ffmpeg_process = sch_recordings[sch_recordings_name][0]
                if ffmpeg_process:
                    terminate_record_process(ffmpeg_process)

        @idle_function
        def record_post_action_after(*args, **kwargs):
            logger.info("Record via scheduler ended, executing post-action...")
            # 0 - nothing to do
            if YukiGUI.praction_choose.currentIndex() == 1:  # 1 - Press Stop
                mpv_stop()

        @async_gui_blocking_function
        def record_post_action(*args, **kwargs):
            while True:
                if is_recording_func() is True:
                    break
                time.sleep(1)
            record_post_action_after()

        def delrecord_clicked():
            schCurrentRow = YukiGUI.schedulers.currentRow()
            if schCurrentRow != -1:
                sch_index = "_".join(
                    [
                        xs.split(": ")[1]
                        for xs in YukiGUI.schedulers.item(schCurrentRow)
                        .text()
                        .split("\n")
                        if xs
                    ]
                )
                YukiGUI.schedulers.takeItem(schCurrentRow)
                if sch_index in sch_recordings:
                    do_stop_record(sch_index)
                    sch_recordings.pop(sch_index)

        def scheduler_channelfilter_do():
            try:
                filter_txt2 = YukiGUI.schedulerchannelfilter.text()
            except Exception:
                filter_txt2 = ""
            for item5 in range(YukiGUI.choosechannel_ch.count()):
                if (
                    filter_txt2.lower().strip()
                    in YukiGUI.choosechannel_ch.itemText(item5).lower().strip()
                ):
                    YukiGUI.choosechannel_ch.view().setRowHidden(item5, False)
                else:
                    YukiGUI.choosechannel_ch.view().setRowHidden(item5, True)

        YukiGUI.create_scheduler_widgets()

        def save_sort():
            YukiData.channel_sort = [
                YukiGUI.sort_list.item(channel_sort_i).text()
                for channel_sort_i in range(YukiGUI.sort_list.count())
            ]
            channel_sort2 = {}
            if os.path.isfile(Path(LOCAL_DIR) / "sortchannels.json"):
                with open(
                    Path(LOCAL_DIR) / "sortchannels.json", encoding="utf8"
                ) as sortchannels_file:
                    channel_sort2 = json.loads(sortchannels_file.read())
            channel_sort2[YukiData.settings["m3u"]] = YukiData.channel_sort
            with open(
                Path(LOCAL_DIR) / "sortchannels.json", "w", encoding="utf8"
            ) as channel_sort_file:
                channel_sort_file.write(json.dumps(channel_sort2))
            YukiGUI.sort_win.hide()

        YukiGUI.create_sort_widgets()
        YukiGUI.save_sort_btn.clicked.connect(save_sort)

        YukiGUI.tvguide_sch.itemClicked.connect(programme_clicked)
        YukiGUI.addrecord_btn.clicked.connect(addrecord_clicked)
        YukiGUI.delrecord_btn.clicked.connect(delrecord_clicked)
        YukiGUI.schedulerchannelfiltersearch.clicked.connect(scheduler_channelfilter_do)
        YukiGUI.schedulerchannelfilter.returnPressed.connect(scheduler_channelfilter_do)

        # Channel settings window
        def epgname_btn_action():
            prog_ids_0 = get_all_epg_names()
            if not prog_ids_0:
                prog_ids_0 = set()
            YukiGUI.epg_custom_name_select.clear()
            YukiGUI.epg_custom_name_select.addItem("")
            for prog_ids_0_dat in prog_ids_0:
                YukiGUI.epg_custom_name_select.addItem(prog_ids_0_dat)
            YukiGUI.epg_custom_name_input_edit()
            moveWindowToCenter(YukiGUI.epg_select_win)
            YukiGUI.epg_select_win.show()

        YukiGUI.epgname_btn.clicked.connect(epgname_btn_action)

        def_user_agent = (
            YukiData.settings["playlist_useragent"]
            if YukiData.settings["playlist_useragent"]
            else YukiData.settings["ua"]
        )
        logger.info(f"Default user agent: {def_user_agent}")
        def_referer = (
            YukiData.settings["playlist_referer"]
            if YukiData.settings["playlist_referer"]
            else YukiData.settings["referer"]
        )
        if def_referer:
            logger.info(f"Default HTTP referer: {def_referer}")
        else:
            logger.info("Default HTTP referer: (empty)")

        def on_bitrate(prop, bitrate):
            try:
                if not bitrate or prop not in ["video-bitrate", "audio-bitrate"]:
                    return

                if _("Average Bitrate") in stream_info.video_properties:
                    if _("Average Bitrate") in stream_info.audio_properties:
                        if not YukiData.streaminfo_win_visible:
                            return

                rates = {
                    "video": stream_info.video_bitrates,
                    "audio": stream_info.audio_bitrates,
                }
                rate = "video"
                if prop == "audio-bitrate":
                    rate = "audio"

                rates[rate].append(int(bitrate) / 1000.0)
                rates[rate] = rates[rate][-30:]
                br = sum(rates[rate]) / float(len(rates[rate]))

                if rate == "video":
                    stream_info.video_properties[_("General")][_("Average Bitrate")] = (
                        "%.f " + _("kbps")
                    ) % br
                else:
                    stream_info.audio_properties[_("General")][_("Average Bitrate")] = (
                        "%.f " + _("kbps")
                    ) % br
            except Exception:
                if not YukiData.bitrate_failed:
                    YukiData.bitrate_failed = True
                    logger.warning("on_bitrate FAILED with exception!")
                    logger.warning(traceback.format_exc())

        def on_video_params(property1, params):
            try:
                if not params or not isinstance(params, dict):
                    return
                if "w" in params and "h" in params:
                    stream_info.video_properties[_("General")][
                        _("Dimensions")
                    ] = "{}x{}".format(params["w"], params["h"])
                if "aspect" in params:
                    aspect = round(float(params["aspect"]), 2)
                    stream_info.video_properties[_("General")][_("Aspect")] = (
                        "%s" % aspect
                    )
                if "pixelformat" in params:
                    stream_info.video_properties[_("Color")][
                        _("Pixel Format")
                    ] = params["pixelformat"]
                if "gamma" in params:
                    stream_info.video_properties[_("Color")][_("Gamma")] = params[
                        "gamma"
                    ]
                if "average-bpp" in params:
                    stream_info.video_properties[_("Color")][
                        _("Bits Per Pixel")
                    ] = params["average-bpp"]
            except Exception:
                logger.warning(traceback.format_exc())

        def on_video_format(property1, vformat):
            try:
                if not vformat:
                    return
                stream_info.video_properties[_("General")][_("Codec")] = vformat
            except Exception:
                logger.warning(traceback.format_exc())

        def on_audio_params(property1, params):
            try:
                if not params or not isinstance(params, dict):
                    return
                if "channels" in params:
                    layout_channels = params["channels"]
                    if "5.1" in layout_channels or "7.1" in layout_channels:
                        layout_channels += " " + _("surround sound")
                    stream_info.audio_properties[_("Layout")][
                        _("Channels")
                    ] = layout_channels
                if "samplerate" in params:
                    sr = float(params["samplerate"]) / 1000.0
                    stream_info.audio_properties[_("General")][_("Sample Rate")] = (
                        "%.1f KHz" % sr
                    )
                if "format" in params:
                    fmt = params["format"]
                    fmt = AUDIO_SAMPLE_FORMATS.get(fmt, fmt)
                    stream_info.audio_properties[_("General")][_("Format")] = fmt
                if "channel-count" in params:
                    stream_info.audio_properties[_("Layout")][
                        _("Channel Count")
                    ] = params["channel-count"]
            except Exception:
                logger.warning(traceback.format_exc())

        def on_audio_codec(property1, codec):
            try:
                if not codec:
                    return
                stream_info.audio_properties[_("General")][_("Codec")] = codec.split()[
                    0
                ]
            except Exception:
                logger.warning(traceback.format_exc())

        @async_gui_blocking_function
        def monitor_playback(*args, **kwargs):
            try:
                YukiData.player.wait_until_playing()
                YukiData.player.observe_property("video-params", on_video_params)
                YukiData.player.observe_property("video-format", on_video_format)
                YukiData.player.observe_property("audio-params", on_audio_params)
                YukiData.player.observe_property("audio-codec", on_audio_codec)
                YukiData.player.observe_property("video-bitrate", on_bitrate)
                YukiData.player.observe_property("audio-bitrate", on_bitrate)
            except Exception:
                logger.warning(traceback.format_exc())

        def clear_stream_info():
            stream_info.video_properties.clear()
            stream_info.video_properties[_("General")] = {}
            stream_info.video_properties[_("Color")] = {}

            stream_info.audio_properties.clear()
            stream_info.audio_properties[_("General")] = {}
            stream_info.audio_properties[_("Layout")] = {}

            stream_info.video_bitrates.clear()
            stream_info.audio_bitrates.clear()

        @idle_function
        def idle_on_metadata():
            try:
                if YukiData.event_handler:
                    YukiData.event_handler.on_metadata()
            except Exception:
                logger.warning(traceback.format_exc())

        def hideLoading():
            YukiData.is_loading = False
            loading.hide()
            YukiGUI.loading_movie.stop()
            YukiGUI.loading1.hide()
            idle_on_metadata()

        def showLoading():
            YukiData.is_loading = True
            centerwidget(YukiGUI.loading1)
            loading.show()
            YukiGUI.loading_movie.start()
            YukiGUI.loading1.show()
            idle_on_metadata()

        @idle_function
        def on_before_play(*args, **kwargs):
            YukiGUI.streaminfo_win.hide()
            clear_stream_info()

        def _mpv_override_play(
            arg_override_play,
            channel_name1,
            useragent_ref,
            referer_ref,
            cenc_decryption_key,
        ):
            try:
                YukiData.player.demuxer_lavf_o = (
                    f"cenc_decryption_key={cenc_decryption_key}"
                )
                if cenc_decryption_key:
                    logger.info("DRM is enabled")
                    logger.debug(f"DRM encryption key: {cenc_decryption_key}")
            except Exception:
                logger.warning("Failed to enable DRM")
                logger.warning(traceback.format_exc())
                try:
                    YukiData.player.demuxer_lavf_o = "cenc_decryption_key="
                except Exception:
                    logger.warning(traceback.format_exc())
            YukiData.player.user_agent = useragent_ref
            if referer_ref:
                originURL = ""
                if referer_ref.endswith("/"):
                    originURL = referer_ref[:-1]
                if originURL:
                    YukiData.player.http_header_fields = (
                        f"Referer: {referer_ref},Origin: {originURL}"
                    )
                else:
                    YukiData.player.http_header_fields = f"Referer: {referer_ref}"
            else:
                YukiData.player.http_header_fields = ""

            if not (
                arg_override_play.endswith("/icons/main.png")
                or arg_override_play.endswith("/icons_dark/main.png")
            ):
                logger.info(f"Using User-Agent: {YukiData.player.user_agent}")
                cur_ref = ""
                try:
                    for ref1 in YukiData.player.http_header_fields:
                        if ref1.startswith("Referer: "):
                            ref1 = ref1.replace("Referer: ", "", 1)
                            cur_ref = ref1
                except Exception:
                    logger.warning(traceback.format_exc())
                if cur_ref:
                    logger.info(f"Using HTTP Referer: {cur_ref}")
                else:
                    logger.info("Using HTTP Referer: (empty)")

            YukiData.player.pause = False
            mpv_play_url = parse_specifiers_now_url(arg_override_play)
            if is_youtube_url(mpv_play_url) and not is_ytdl_enabled_in_options():
                executeInMainThread(partial(end_file_error_callback))
                show_exception(f"{YTDL_NAME} not found or disabled in options")
            else:
                YukiData.player.play(mpv_play_url)
            if YukiData.event_handler:
                try:
                    YukiData.event_handler.on_metadata()
                except Exception:
                    logger.warning(traceback.format_exc())

        def mpv_override_play(arg_override_play, channel_name1=""):
            on_before_play()
            useragent_ref, referer_ref, cenc_decryption_key = get_ua_ref_for_channel(
                channel_name1
            )
            try:
                cenc_decryption_key = convert_key(
                    cenc_decryption_key, arg_override_play, useragent_ref, referer_ref
                )
                try:
                    if channel_name1:
                        _arr_item = getArrayItem(channel_name1)
                        if _arr_item:
                            _arr_item["cenc_decryption_key"] = cenc_decryption_key
                except Exception:
                    logger.warning(traceback.format_exc())
                executeInMainThread(
                    partial(
                        _mpv_override_play,
                        arg_override_play,
                        channel_name1,
                        useragent_ref,
                        referer_ref,
                        cenc_decryption_key,
                    )
                )
            except Exception:
                show_exception(traceback.format_exc())
                executeInMainThread(partial(end_file_error_callback))

        def mpv_override_stop(ignore=False):
            YukiData.player.command("stop")
            if not ignore:
                logger.info("Disabling deinterlace for main.png")
                YukiData.player.deinterlace = False
            YukiData.player.play(str(YukiData.icons_folder / "main.png"))
            YukiData.player.pause = True
            if YukiData.event_handler:
                try:
                    YukiData.event_handler.on_metadata()
                except Exception:
                    logger.warning(traceback.format_exc())

        def mpv_override_volume(volume_val):
            YukiData.player.volume = volume_val
            YukiData.volume = volume_val
            if YukiData.event_handler:
                try:
                    YukiData.event_handler.on_volume()
                except Exception:
                    logger.warning(traceback.format_exc())

        def mpv_override_mute(mute_val):
            YukiData.player.mute = mute_val
            if YukiData.event_handler:
                try:
                    YukiData.event_handler.on_volume()
                except Exception:
                    logger.warning(traceback.format_exc())

        def stopPlayer(ignore=False):
            try:
                mpv_override_stop(ignore)
            except Exception:
                YukiData.player.loop = True
                mpv_override_play(str(YukiData.icons_folder / "main.png"))
                YukiData.player.pause = True

        def setVideoAspect(va):
            if va == 0:
                va = -1
            try:
                YukiData.player.video_aspect_override = va
            except Exception:
                YukiData.player.video_aspect = va

        def getVideoAspect():
            try:
                va1 = YukiData.player.video_aspect_override
            except Exception:
                va1 = YukiData.player.video_aspect
            return va1

        @async_gui_blocking_function
        def async_mpv_override_play(*args, **kwargs):
            mpv_override_play(*args, **kwargs)

        def doPlay(play_url1, ua_ch=def_user_agent, channel_name_0=""):
            YukiData.do_play_args = (play_url1, ua_ch, channel_name_0)
            logger.info(f"Playing '{channel_name_0}' ('{play_url1}')")
            loading.setText(_("Loading..."))
            loading.setFont(YukiGUI.font_italic_medium)
            showLoading()
            YukiData.player.loop = False
            # Playing
            async_mpv_override_play(play_url1, channel_name_0)
            # Set channel (video) settings
            setPlayerSettings(channel_name_0)
            # Monitor playback (for stream information)
            monitor_playback()

        def channel_settings_save():
            channel_3 = YukiGUI.title.text()
            if YukiData.settings["m3u"] not in YukiData.channel_sets:
                YukiData.channel_sets[YukiData.settings["m3u"]] = {}
            YukiData.channel_sets[YukiData.settings["m3u"]][channel_3] = {
                "deinterlace": YukiGUI.deinterlace_chk.isChecked(),
                "ua": YukiGUI.useragent_choose.text(),
                "ref": YukiGUI.referer_choose_custom.text(),
                "group": YukiGUI.group_text.text(),
                "hidden": YukiGUI.hidden_chk.isChecked(),
                "contrast": YukiGUI.contrast_choose.value(),
                "brightness": YukiGUI.brightness_choose.value(),
                "hue": YukiGUI.hue_choose.value(),
                "saturation": YukiGUI.saturation_choose.value(),
                "gamma": YukiGUI.gamma_choose.value(),
                "videoaspect": YukiGUI.videoaspect_choose.currentIndex(),
                "zoom": YukiGUI.zoom_choose.currentIndex(),
                "panscan": YukiGUI.panscan_choose.value(),
                "epgname": (
                    YukiGUI.epgname_lbl.text()
                    if YukiGUI.epgname_lbl.text() != _("Default")
                    else ""
                ),
            }
            save_channel_sets()
            if YukiData.playing_channel == channel_3:
                YukiData.player.deinterlace = YukiGUI.deinterlace_chk.isChecked()
                YukiData.player.contrast = YukiGUI.contrast_choose.value()
                YukiData.player.brightness = YukiGUI.brightness_choose.value()
                YukiData.player.hue = YukiGUI.hue_choose.value()
                YukiData.player.saturation = YukiGUI.saturation_choose.value()
                YukiData.player.gamma = YukiGUI.gamma_choose.value()
                YukiData.player.video_zoom = YukiGUI.zoom_vars[
                    list(YukiGUI.zoom_vars)[YukiGUI.zoom_choose.currentIndex()]
                ]
                YukiData.player.panscan = YukiGUI.panscan_choose.value()
                setVideoAspect(
                    YukiGUI.videoaspect_vars[
                        list(YukiGUI.videoaspect_vars)[
                            YukiGUI.videoaspect_choose.currentIndex()
                        ]
                    ]
                )
            redraw_channels()
            YukiGUI.channels_win.close()

        YukiGUI.save_btn.clicked.connect(channel_settings_save)

        YukiGUI.channels_win.setCentralWidget(YukiGUI.wid)

        # Settings window
        def save_settings():
            settings_arr = YukiGUI.get_settings()
            with open(
                Path(LOCAL_DIR) / "settings.json", "w", encoding="utf8"
            ) as settings_file:
                settings_file.write(json.dumps(settings_arr))
            YukiGUI.settings_win.hide()
            YukiData.do_save_settings = True
            app.quit()

        YukiData.save_settings = save_settings

        def reset_channel_settings():
            if os.path.isfile(Path(LOCAL_DIR) / "channelsettings.json"):
                os.remove(Path(LOCAL_DIR) / "channelsettings.json")
            if os.path.isfile(Path(LOCAL_DIR) / "favouritechannels.json"):
                os.remove(Path(LOCAL_DIR) / "favouritechannels.json")
            if os.path.isfile(Path(LOCAL_DIR) / "sortchannels.json"):
                os.remove(Path(LOCAL_DIR) / "sortchannels.json")
            save_settings()

        def do_clear_logo_cache():
            logger.info("Clearing channel logos cache...")
            if os.path.isdir(Path(CACHE_DIR) / "logo"):
                channel_logos = os.listdir(Path(CACHE_DIR) / "logo")
                for channel_logo in channel_logos:
                    if os.path.isfile(Path(CACHE_DIR) / "logo" / channel_logo):
                        os.remove(Path(CACHE_DIR) / "logo" / channel_logo)
            logger.info("Channel logos cache cleared!")

        def close_settings():
            YukiGUI.settings_win.hide()
            if not win.isVisible():
                if not gui_playlists_data.playlists_win.isVisible():
                    myExitHandler_before()
                    sys.exit(0)

        YukiGUI.ssave.clicked.connect(save_settings)
        YukiGUI.sreset.clicked.connect(reset_channel_settings)
        YukiGUI.clear_logo_cache.clicked.connect(do_clear_logo_cache)
        YukiGUI.sclose.clicked.connect(close_settings)

        YukiGUI.set_from_settings()

        @idle_function
        def setUrlText(*args, **kwargs):
            YukiGUI.url_text.setText(YukiData.playing_url)
            YukiGUI.url_text.setCursorPosition(0)
            if YukiGUI.streaminfo_win.isVisible():
                YukiGUI.streaminfo_win.hide()

        def shortcuts_table_clicked(row1, column1):
            if column1 == 1:  # shortcut
                sc1_text = YukiGUI.shortcuts_table.item(row1, column1).text()
                keyseq.setKeySequence(sc1_text)
                YukiData.selected_shortcut_row = row1
                keyseq.setFocus()
                moveWindowToCenter(YukiGUI.shortcuts_win_2)
                YukiGUI.shortcuts_win_2.show()

        YukiGUI.shortcuts_table.cellDoubleClicked.connect(shortcuts_table_clicked)

        def get_widget_item(widget_str):
            widget_item = QtWidgets.QTableWidgetItem(widget_str)
            widget_item.setFlags(
                widget_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable
            )
            return widget_item

        def show_shortcuts():
            if not YukiGUI.shortcuts_win.isVisible():
                YukiGUI.shortcuts_table.setRowCount(len(YukiData.main_shortcuts))
                shortcut_i = -1
                for shortcut in YukiData.main_shortcuts:
                    shortcut_i += 1
                    YukiGUI.shortcuts_table.setItem(
                        shortcut_i,
                        0,
                        get_widget_item(main_shortcuts_translations[shortcut]),
                    )
                    if isinstance(YukiData.main_shortcuts[shortcut], str):
                        shortcut_str = YukiData.main_shortcuts[shortcut]
                    else:
                        shortcut_str = QtGui.QKeySequence(
                            YukiData.main_shortcuts[shortcut]
                        ).toString()
                    kbd_widget = get_widget_item(shortcut_str)
                    kbd_widget.setToolTip(_("Double click to change"))
                    YukiGUI.shortcuts_table.setItem(shortcut_i, 1, kbd_widget)
                YukiGUI.shortcuts_table.resizeColumnsToContents()

                moveWindowToCenter(YukiGUI.shortcuts_win)
                YukiGUI.shortcuts_win.show()
            else:
                YukiGUI.shortcuts_win.hide()

        def show_help():
            if not YukiGUI.help_win.isVisible():
                moveWindowToCenter(YukiGUI.help_win)
                YukiGUI.help_win.show()
            else:
                YukiGUI.help_win.hide()

        def show_sort():
            if not YukiGUI.sort_win.isVisible():
                YukiGUI.sort_list.clear()
                for sort_label_ch in (
                    YukiData.array_sorted
                    if not YukiData.channel_sort
                    else YukiData.channel_sort
                ):
                    YukiGUI.sort_list.addItem(sort_label_ch)

                moveWindowToCenter(YukiGUI.sort_win)
                YukiGUI.sort_win.show()
            else:
                YukiGUI.sort_win.hide()

        @idle_function
        def reload_playlist(*args, **kwargs):
            logger.info("Reloading playlist...")
            save_settings()

        def set_mpv_osc(osc_value):
            if osc_value != YukiData.osc:
                YukiData.osc = osc_value
                YukiData.player.osc = osc_value

        def init_mpv_player():
            YukiData.player = mpv.MPV(
                **options,
                wid=str(int(win.container.winId())),
                log_handler=mpv_log_handler,
            )

            mpv_version = YukiData.player.mpv_version.replace("mpv ", "", 1).strip()
            logger.info(f"Using libmpv {mpv_version}{YukiData.mpv_api_version}")

            YukiGUI.textbox.setText(get_about_text())

            if YukiData.settings["cache_secs"] != 0:
                try:
                    YukiData.player["demuxer-readahead-secs"] = YukiData.settings[
                        "cache_secs"
                    ]
                    logger.info(
                        f'Demuxer cache set to {YukiData.settings["cache_secs"]}s'
                    )
                except Exception:
                    logger.warning(traceback.format_exc())
                try:
                    YukiData.player["cache-secs"] = YukiData.settings["cache_secs"]
                    logger.info(f'Cache set to {YukiData.settings["cache_secs"]}s')
                except Exception:
                    logger.warning(traceback.format_exc())
            else:
                logger.info("Using default cache settings")
            YukiData.player.user_agent = def_user_agent
            _referer = (
                YukiData.settings["playlist_referer"]
                if YukiData.settings["playlist_referer"]
                else YukiData.settings["referer"]
            )
            if _referer:
                referer = _referer
                originURL = ""
                if referer.endswith("/"):
                    originURL = referer[:-1]
                if originURL:
                    YukiData.player.http_header_fields = (
                        f"Referer: {referer},Origin: {originURL}"
                    )
                else:
                    YukiData.player.http_header_fields = f"Referer: {referer}"
                logger.info(f"HTTP referer: '{referer}'")
            else:
                logger.info("No HTTP referer set up")
            mpv_override_volume(100)
            YukiData.player.loop = True

            try:
                populate_menubar(
                    0,
                    win.menu_bar_qt,
                    win,
                    YukiData.player.track_list,
                    YukiData.playing_channel,
                )
                populate_menubar(
                    1,
                    YukiData.right_click_menu,
                    win,
                    YukiData.player.track_list,
                    YukiData.playing_channel,
                )
            except Exception:
                logger.warning("populate_menubar failed")
                show_exception(traceback.format_exc(), "populate_menubar failed")
            redraw_menubar()

            @YukiData.player.property_observer("duration")
            def duration_observer(_name, value):
                try:
                    if YukiData.old_playing_url != YukiData.playing_url:
                        YukiData.old_playing_url = YukiData.playing_url
                        if YukiData.event_handler:
                            YukiData.event_handler.on_metadata()
                except Exception:
                    logger.warning(traceback.format_exc())

            @idle_function
            def seek_event_callback(*args, **kwargs):
                if YukiData.player and YukiData.mpris_ready and YukiData.mpris_running:
                    (
                        playback_status,
                        mpris_trackid,
                        artUrl,
                        player_position,
                    ) = get_mpris_metadata()
                    mpris_seeked(player_position)

            @YukiData.player.event_callback("seek")
            def seek_event(event):
                seek_event_callback()

            @YukiData.player.event_callback("file-loaded")
            def my_file_loaded(event):
                file_loaded_callback()

            @YukiData.player.event_callback("end_file")
            def ready_handler_2(event):
                _event = event.as_dict()
                if "reason" in _event and "error" in decode(_event["reason"]):
                    end_file_error_callback()
                else:
                    end_file_callback()

            @YukiData.player.on_key_press("MBTN_RIGHT")
            def my_mouse_right():
                my_mouse_right_callback()

            @YukiData.player.on_key_press("MBTN_LEFT")
            def my_mouse_left():
                my_mouse_left_callback()

            @YukiData.player.on_key_press("MBTN_LEFT_DBL")
            def my_leftdbl_binding():
                mpv_fullscreen()

            @YukiData.player.on_key_press("MBTN_FORWARD")
            def my_forward_binding():
                next_channel()

            @YukiData.player.on_key_press("MBTN_BACK")
            def my_back_binding():
                prev_channel()

            @YukiData.player.on_key_press("WHEEL_UP")
            def my_up_binding():
                my_up_binding_execute()

            @YukiData.player.on_key_press("WHEEL_DOWN")
            def my_down_binding():
                my_down_binding_execute()

            @idle_function
            def pause_handler(*args, **kwargs):
                try:
                    if not YukiData.player.pause:
                        YukiGUI.btn_playpause.setIcon(
                            QtGui.QIcon(str(YukiData.icons_folder / "pause.png"))
                        )
                        YukiGUI.btn_playpause.setToolTip(_("Pause"))
                    else:
                        YukiGUI.btn_playpause.setIcon(
                            QtGui.QIcon(str(YukiData.icons_folder / "play.png"))
                        )
                        YukiGUI.btn_playpause.setToolTip(_("Play"))
                    if YukiData.event_handler:
                        try:
                            YukiData.event_handler.on_playpause()
                        except Exception:
                            logger.warning(traceback.format_exc())
                except Exception:
                    logger.warning(traceback.format_exc())

            YukiData.player.observe_property("pause", pause_handler)

            def yuki_track_set(track, type1):
                logger.info(f"Set {type1} track to {track}")
                if YukiData.playing_channel not in YukiData.player_tracks:
                    YukiData.player_tracks[YukiData.playing_channel] = {}
                if type1 == "vid":
                    YukiData.player.vid = track
                    YukiData.player_tracks[YukiData.playing_channel]["vid"] = track
                elif type1 == "aid":
                    YukiData.player.aid = track
                    YukiData.player_tracks[YukiData.playing_channel]["aid"] = track
                elif type1 == "sid":
                    YukiData.player.sid = track
                    YukiData.player_tracks[YukiData.playing_channel]["sid"] = track

            init_menubar_player(
                YukiData.player,
                mpv_play_pause,
                mpv_stop,
                prev_channel,
                next_channel,
                mpv_fullscreen,
                showhideeverything,
                main_channel_settings,
                show_help,
                do_screenshot,
                mpv_mute,
                showhideplaylist,
                lowpanel_ch_1,
                open_stream_info,
                app.quit,
                redraw_menubar,
                QtGui.QIcon(
                    QtGui.QIcon(str(YukiData.icons_folder / "circle.png")).pixmap(8, 8)
                ),
                my_up_binding_execute,
                my_down_binding_execute,
                show_playlists,
                show_sort,
                force_update_epg_act,
                show_tvguide_2,
                show_multi_epg,
                reload_playlist,
                show_shortcuts,
                yuki_track_set,
                mpv_frame_step,
                mpv_frame_back_step,
            )

            volume_option1 = read_option("volume")
            if volume_option1 is not None:
                logger.info(f"Set volume to {vol_remembered}")
                YukiGUI.volume_slider.setValue(vol_remembered)
                mpv_volume_set()
            else:
                YukiGUI.volume_slider.setValue(100)
                mpv_volume_set()

        def set_label_width(label, width):
            if width > 0:
                label.setFixedWidth(width)

        class MainWindow(QtWidgets.QMainWindow):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.windowWidth = self.width()
                self.windowHeight = self.height()
                self.container = None
                self.listWidget = None
                self.moviesWidget = None
                self.seriesWidget = None

                self.menu_bar_qt = self.menuBar()
                init_yuki_iptv_menubar(self, app, self.menu_bar_qt)

                class Container(QtWidgets.QWidget):
                    def mousePressEvent(self, event):
                        if event.button() == QtCore.Qt.MouseButton.LeftButton:
                            my_mouse_left_callback()
                        elif event.button() == QtCore.Qt.MouseButton.RightButton:
                            my_mouse_right_callback()
                        elif event.button() in [
                            QtCore.Qt.MouseButton.BackButton,
                            QtCore.Qt.MouseButton.XButton1,
                            QtCore.Qt.MouseButton.ExtraButton1,
                        ]:
                            prev_channel()
                        elif event.button() in [
                            QtCore.Qt.MouseButton.ForwardButton,
                            QtCore.Qt.MouseButton.XButton2,
                            QtCore.Qt.MouseButton.ExtraButton2,
                        ]:
                            next_channel()
                        else:
                            super().mousePressEvent(event)

                    def mouseDoubleClickEvent(self, event):
                        if event.button() == QtCore.Qt.MouseButton.LeftButton:
                            mpv_fullscreen()
                        else:
                            super().mouseDoubleClickEvent(event)

                    def wheelEvent(self, event):
                        if event.angleDelta().y() > 0:
                            my_up_binding_execute()
                        else:
                            my_down_binding_execute()
                        event.accept()

                self.container = QtWidgets.QWidget(self)
                self.setCentralWidget(self.container)
                self.container.setAttribute(
                    QtCore.Qt.WidgetAttribute.WA_DontCreateNativeAncestors
                )
                self.container.setAttribute(QtCore.Qt.WidgetAttribute.WA_NativeWindow)
                self.container.setFocus()
                self.container.setStyleSheet("background-color: #C0C6CA;")

            def resize_rewind(self):
                rewind_normal_offset = 150
                rewind_fullscreen_offset = 180
                if YukiData.settings["panelposition"] == 2:
                    dockWidget_playlist_cur_width = 0
                else:
                    dockWidget_playlist_cur_width = dockWidget_playlist.width()

                if not YukiData.fullscreen:
                    if not dockWidget_controlPanel.isVisible():
                        set_label_width(
                            YukiGUI.rewind,
                            self.windowWidth - dockWidget_playlist_cur_width + 58,
                        )
                        YukiGUI.rewind.move(
                            int(
                                ((self.windowWidth - YukiGUI.rewind.width()) / 2)
                                - (dockWidget_playlist_cur_width / 1.7)
                            ),
                            int(
                                (self.windowHeight - YukiGUI.rewind.height())
                                - rewind_fullscreen_offset
                            ),
                        )
                    else:
                        set_label_width(
                            YukiGUI.rewind,
                            self.windowWidth - dockWidget_playlist_cur_width + 58,
                        )
                        YukiGUI.rewind.move(
                            int(
                                ((self.windowWidth - YukiGUI.rewind.width()) / 2)
                                - (dockWidget_playlist_cur_width / 1.7)
                            ),
                            int(
                                (self.windowHeight - YukiGUI.rewind.height())
                                - dockWidget_controlPanel.height()
                                - rewind_normal_offset
                            ),
                        )
                else:
                    set_label_width(YukiGUI.rewind, YukiGUI.controlpanel_widget.width())
                    rewind_position_x = (
                        YukiGUI.controlpanel_widget.pos().x() - win.pos().x()
                    )
                    if rewind_position_x < 0:
                        rewind_position_x = 0
                    YukiGUI.rewind.move(
                        rewind_position_x,
                        int(
                            (self.windowHeight - YukiGUI.rewind.height())
                            - rewind_fullscreen_offset
                        ),
                    )

            def update(self):
                if YukiData.settings["panelposition"] == 2:
                    dockWidget_playlist_cur_width2 = 0
                else:
                    dockWidget_playlist_cur_width2 = dockWidget_playlist.width()

                if YukiData.settings["panelposition"] in (0, 2):
                    YukiData.tvguide_lbl.move(2, YukiGUI.tvguide_lbl_offset)
                else:
                    YukiData.tvguide_lbl.move(
                        win.width() - YukiData.tvguide_lbl.width(),
                        YukiGUI.tvguide_lbl_offset,
                    )
                self.resize_rewind()
                if not YukiData.fullscreen:
                    if not dockWidget_controlPanel.isVisible():
                        set_label_width(
                            YukiData.state,
                            self.windowWidth - dockWidget_playlist_cur_width2 + 58,
                        )
                        YukiData.state.move(
                            int(
                                ((self.windowWidth - YukiData.state.width()) / 2)
                                - (dockWidget_playlist_cur_width2 / 1.7)
                            ),
                            int((self.windowHeight - YukiData.state.height()) - 20),
                        )
                        h = 0
                        h2 = 10
                    else:
                        set_label_width(
                            YukiData.state,
                            self.windowWidth - dockWidget_playlist_cur_width2 + 58,
                        )
                        YukiData.state.move(
                            int(
                                ((self.windowWidth - YukiData.state.width()) / 2)
                                - (dockWidget_playlist_cur_width2 / 1.7)
                            ),
                            int(
                                (self.windowHeight - YukiData.state.height())
                                - dockWidget_controlPanel.height()
                                - 10
                            ),
                        )
                        h = dockWidget_controlPanel.height()
                        h2 = 20
                else:
                    set_label_width(YukiData.state, self.windowWidth)
                    YukiData.state.move(
                        int((self.windowWidth - YukiData.state.width()) / 2),
                        int((self.windowHeight - YukiData.state.height()) - 20),
                    )
                    h = 0
                    h2 = 10
                if dockWidget_playlist.isVisible():
                    if YukiData.settings["panelposition"] in (0, 2):
                        YukiGUI.lbl2.move(0, YukiGUI.lbl2_offset)
                    else:
                        YukiGUI.lbl2.move(
                            YukiData.tvguide_lbl.width() + YukiGUI.lbl2.width(),
                            YukiGUI.lbl2_offset,
                        )
                else:
                    YukiGUI.lbl2.move(0, YukiGUI.lbl2_offset)
                if YukiData.state.isVisible():
                    state_h = YukiData.state.height()
                else:
                    state_h = 15
                YukiData.tvguide_lbl.setFixedHeight(
                    (self.windowHeight - state_h - h) - 40 - state_h + h2
                )

            def resizeEvent(self, event):
                super().resizeEvent(event)
                self.windowWidth = self.width()
                self.windowHeight = self.height()
                try:
                    self.update()
                except Exception:
                    logger.warning(traceback.format_exc())

            def closeEvent(self, event):
                try:
                    if YukiData.player:
                        YukiData.player.vo = "null"
                except Exception:
                    pass
                if YukiGUI.streaminfo_win.isVisible():
                    YukiGUI.streaminfo_win.hide()
                if YukiData.settings["panelposition"] == 2:
                    dockWidget_playlist.hide()
                super().closeEvent(event)

        win = MainWindow()
        win.setMinimumSize(1, 1)
        win.setWindowTitle(MAIN_WINDOW_TITLE)
        win.setWindowIcon(YukiGUI.main_icon)
        YukiData.win = win

        YukiGUI.create3()

        window_data = read_option("window")
        if window_data:
            win.setGeometry(
                window_data["x"], window_data["y"], window_data["w"], window_data["h"]
            )
        else:
            YukiData.needs_resize = True
            win.resize(WINDOW_SIZE[0], WINDOW_SIZE[1])
            qr = win.frameGeometry()
            qr.moveCenter(
                QtGui.QScreen.availableGeometry(
                    QtWidgets.QApplication.primaryScreen()
                ).center()
            )
            win.move(qr.topLeft())

        def get_curwindow_pos():
            try:
                win_geometry = win.screen().availableGeometry()
            except Exception:
                win_geometry = QtWidgets.QDesktopWidget().screenGeometry(win)
            win_width = win_geometry.width()
            win_height = win_geometry.height()
            logger.debug(f"Screen size: {win_width}x{win_height}")
            return (
                win_width,
                win_height,
            )

        @idle_function
        def set_mpv_title(*args, **kwargs):
            try:
                YukiData.player.title = win.windowTitle()
            except Exception:
                logger.warning(traceback.format_exc())

        def setChannelText(channelText, do_channel_set=False):
            chTextStrip = channelText.strip()
            if chTextStrip:
                win.setWindowTitle(chTextStrip + " - " + MAIN_WINDOW_TITLE)
            else:
                win.setWindowTitle(MAIN_WINDOW_TITLE)
            set_mpv_title()
            if not do_channel_set:
                YukiGUI.channel.setText(f"{chr(9654)} {channelText}")
                YukiGUI.channel.show()
            if (
                YukiData.fullscreen
                and chTextStrip
                and not YukiData.dockWidget_playlistVisible
            ):
                YukiData.state.show()
                YukiData.state.setTextYuki(chTextStrip)
                YukiData.time_stop = time.time() + 1

        @async_gui_blocking_function
        def setPlayerSettings(j):
            try:
                logger.info("setPlayerSettings waiting for channel load...")
                try:
                    YukiData.player.wait_until_playing()
                except Exception:
                    logger.warning(traceback.format_exc())
                if j == YukiData.playing_channel:
                    logger.info(f"setPlayerSettings '{j}'")
                    idle_on_metadata()
                    if (
                        YukiData.settings["m3u"] in YukiData.channel_sets
                        and j in YukiData.channel_sets[YukiData.settings["m3u"]]
                    ):
                        d = YukiData.channel_sets[YukiData.settings["m3u"]][j]
                        YukiData.player.deinterlace = d["deinterlace"]
                        if "ua" not in d:
                            d["ua"] = ""
                        if "ref" not in d:
                            d["ref"] = ""
                        if "contrast" in d:
                            YukiData.player.contrast = d["contrast"]
                        else:
                            YukiData.player.contrast = 0
                        if "brightness" in d:
                            YukiData.player.brightness = d["brightness"]
                        else:
                            YukiData.player.brightness = 0
                        if "hue" in d:
                            YukiData.player.hue = d["hue"]
                        else:
                            YukiData.player.hue = 0
                        if "saturation" in d:
                            YukiData.player.saturation = d["saturation"]
                        else:
                            YukiData.player.saturation = 0
                        if "gamma" in d:
                            YukiData.player.gamma = d["gamma"]
                        else:
                            YukiData.player.gamma = 0
                        if "videoaspect" in d:
                            setVideoAspect(
                                YukiGUI.videoaspect_vars[
                                    list(YukiGUI.videoaspect_vars)[d["videoaspect"]]
                                ]
                            )
                        else:
                            setVideoAspect(
                                YukiGUI.videoaspect_vars[
                                    YukiGUI.videoaspect_def_choose.itemText(
                                        YukiData.settings["videoaspect"]
                                    )
                                ]
                            )
                        if "zoom" in d:
                            YukiData.player.video_zoom = YukiGUI.zoom_vars[
                                list(YukiGUI.zoom_vars)[d["zoom"]]
                            ]
                        else:
                            YukiData.player.video_zoom = YukiGUI.zoom_vars[
                                YukiGUI.zoom_def_choose.itemText(
                                    YukiData.settings["zoom"]
                                )
                            ]
                        if "panscan" in d:
                            YukiData.player.panscan = d["panscan"]
                        else:
                            YukiData.player.panscan = YukiData.settings["panscan"]
                    else:
                        YukiData.player.deinterlace = YukiData.settings["deinterlace"]
                        setVideoAspect(
                            YukiGUI.videoaspect_vars[
                                YukiGUI.videoaspect_def_choose.itemText(
                                    YukiData.settings["videoaspect"]
                                )
                            ]
                        )
                        YukiData.player.video_zoom = YukiGUI.zoom_vars[
                            YukiGUI.zoom_def_choose.itemText(YukiData.settings["zoom"])
                        ]
                        YukiData.player.panscan = YukiData.settings["panscan"]
                        YukiData.player.gamma = 0
                        YukiData.player.saturation = 0
                        YukiData.player.hue = 0
                        YukiData.player.brightness = 0
                        YukiData.player.contrast = 0
                    # Print settings
                    if YukiData.player.deinterlace:
                        logger.info("Deinterlace: enabled")
                    else:
                        logger.info("Deinterlace: disabled")
                    logger.info(f"Contrast: {YukiData.player.contrast}")
                    logger.info(f"Brightness: {YukiData.player.brightness}")
                    logger.info(f"Hue: {YukiData.player.hue}")
                    logger.info(f"Saturation: {YukiData.player.saturation}")
                    logger.info(f"Gamma: {YukiData.player.gamma}")
                    logger.info(f"Video aspect: {getVideoAspect()}")
                    logger.info(f"Zoom: {YukiData.player.video_zoom}")
                    logger.info(f"Panscan: {YukiData.player.panscan}")
                    # Restore video / audio / subtitle tracks for channel
                    if YukiData.playing_channel in YukiData.player_tracks:
                        last_track = YukiData.player_tracks[YukiData.playing_channel]
                        if "vid" in last_track:
                            logger.info(
                                f"Restoring last video track: '{last_track['vid']}'"
                            )
                            YukiData.player.vid = last_track["vid"]
                        else:
                            YukiData.player.vid = "auto"
                        if "aid" in last_track:
                            logger.info(
                                f"Restoring last audio track: '{last_track['aid']}'"
                            )
                            YukiData.player.aid = last_track["aid"]
                        else:
                            YukiData.player.aid = "auto"
                        if "sid" in last_track:
                            logger.info(
                                f"Restoring last subtitle track: '{last_track['sid']}'"
                            )
                            YukiData.player.sid = last_track["sid"]
                        else:
                            YukiData.player.sid = "auto"
                    else:
                        YukiData.player.vid = "auto"
                        YukiData.player.aid = "auto"
                        YukiData.player.sid = "auto"
                    file_loaded_callback()
            except Exception:
                logger.warning(traceback.format_exc())

        def itemClicked_event(item, custom_url="", archived=False, is_rewind=False):
            is_ic_ok = True
            try:
                is_ic_ok = item.text() != _("Nothing found")
            except Exception:
                pass
            if is_ic_ok:
                YukiData.playing_archive = archived
                if not archived:
                    YukiData.archive_epg = None
                    YukiGUI.rewind_slider.setValue(100)
                    YukiData.rewind_value = YukiGUI.rewind_slider.value()
                else:
                    if not is_rewind:
                        YukiGUI.rewind_slider.setValue(0)
                        YukiData.rewind_value = YukiGUI.rewind_slider.value()
                try:
                    j = item.data(QtCore.Qt.ItemDataRole.UserRole)
                except Exception:
                    j = item
                if not j:
                    return
                YukiData.playing_channel = j
                YukiData.playing_group = playmode_selector.currentIndex()
                YukiData.item_selected = j
                array_item = None
                try:
                    array_item = getArrayItem(j)
                    play_url = array_item["url"]
                except Exception:
                    play_url = custom_url
                if archived:
                    play_url = custom_url
                MAX_CHAN_SIZE = 35
                channel_name = j
                if len(channel_name) > MAX_CHAN_SIZE:
                    channel_name = channel_name[: MAX_CHAN_SIZE - 3] + "..."
                setChannelText("  " + channel_name)
                current_prog = None
                if YukiData.settings["epg"] and array_item:
                    epg_id = get_epg_id(array_item)
                    if epg_id:
                        programme = get_current_programme(epg_id)
                        if programme:
                            current_prog = programme
                YukiData.current_prog1 = current_prog
                YukiGUI.show_progress(current_prog)
                if YukiGUI.start_label.isVisible():
                    dockWidget_controlPanel.setFixedHeight(
                        DOCKWIDGET_CONTROLPANEL_HEIGHT_HIGH
                    )
                else:
                    dockWidget_controlPanel.setFixedHeight(
                        DOCKWIDGET_CONTROLPANEL_HEIGHT_LOW
                    )
                inhibit()
                YukiData.playing = True
                win.update()
                YukiData.playing_url = play_url
                setUrlText()
                ua_choose = def_user_agent
                if (
                    YukiData.settings["m3u"] in YukiData.channel_sets
                    and j in YukiData.channel_sets[YukiData.settings["m3u"]]
                ):
                    ua_choose = YukiData.channel_sets[YukiData.settings["m3u"]][j]["ua"]
                if not custom_url:
                    doPlay(play_url, ua_choose, j)
                else:
                    doPlay(custom_url, ua_choose, j)
                redraw_channels()

        def itemSelected_event(item):
            try:
                if item:
                    n_1 = item.data(QtCore.Qt.ItemDataRole.UserRole)
                    if n_1:
                        YukiData.item_selected = n_1
                        update_tvguide(n_1)
            except Exception:
                logger.warning(traceback.format_exc())

        def mpv_play_pause():
            YukiData.player.pause = not YukiData.player.pause

        def mpv_stop():
            YukiData.playing_channel = ""
            YukiData.playing_group = -1
            YukiData.playing_url = ""
            setUrlText()
            hideLoading()
            setChannelText("")
            uninhibit()
            YukiData.playing = False
            stopPlayer()
            YukiData.player.loop = True
            YukiData.player.deinterlace = False
            mpv_override_play(str(YukiData.icons_folder / "main.png"))
            YukiData.player.pause = True
            YukiGUI.channel.setText("")
            YukiGUI.channel.hide()
            YukiGUI.progress.hide()
            YukiGUI.start_label.hide()
            YukiGUI.stop_label.hide()
            YukiGUI.start_label.setText("")
            YukiGUI.stop_label.setText("")
            dockWidget_controlPanel.setFixedHeight(DOCKWIDGET_CONTROLPANEL_HEIGHT_LOW)
            win.update()
            redraw_channels()
            redraw_menubar()

        def esc_handler():
            if YukiData.fullscreen:
                mpv_fullscreen()

        YukiData.currentWidthHeight = [
            win.geometry().x(),
            win.geometry().y(),
            win.width(),
            win.height(),
        ]
        YukiData.currentMaximized = win.isMaximized()

        @idle_function
        def mpv_fullscreen(*args, **kwargs):
            if not YukiData.fullscreen:
                # Entering fullscreen
                if not YukiData.fullscreen_locked:
                    YukiData.fullscreen_locked = True
                    rewind_layout_offset = 10
                    YukiGUI.rewind_layout.setContentsMargins(
                        rewind_layout_offset, 0, rewind_layout_offset - 50, 0
                    )
                    YukiData.isControlPanelVisible = dockWidget_controlPanel.isVisible()
                    YukiData.isPlaylistVisible = dockWidget_playlist.isVisible()
                    setShortcutState(True)
                    YukiData.currentWidthHeight = [
                        win.geometry().x(),
                        win.geometry().y(),
                        win.width(),
                        win.height(),
                    ]
                    YukiData.currentMaximized = win.isMaximized()
                    YukiGUI.channelfilter.usePopup = False
                    win.menu_bar_qt.hide()
                    YukiData.fullscreen = True
                    dockWidget_playlist.hide()
                    YukiGUI.label_video_data.hide()
                    YukiGUI.label_avsync.hide()
                    for lbl3 in YukiGUI.controlpanel_btns:
                        if lbl3 not in YukiGUI.show_lbls_fullscreen:
                            lbl3.hide()
                    YukiGUI.progress.hide()
                    YukiGUI.start_label.hide()
                    YukiGUI.stop_label.hide()
                    dockWidget_controlPanel.hide()
                    dockWidget_controlPanel.setFixedHeight(
                        DOCKWIDGET_CONTROLPANEL_HEIGHT_LOW
                    )
                    win.update()
                    win.raise_()
                    win.setFocus(QtCore.Qt.FocusReason.PopupFocusReason)
                    win.activateWindow()
                    win.showFullScreen()
                    if YukiData.settings["panelposition"] == 1:
                        YukiData.tvguide_close_lbl.move(
                            get_curwindow_pos()[0] - YukiData.tvguide_lbl.width() - 40,
                            YukiGUI.tvguide_lbl_offset,
                        )
                    centerwidget(YukiGUI.loading1)
                    centerwidget(YukiGUI.loading2, 50)
                    YukiData.fullscreen_locked = False
            else:
                # Leaving fullscreen
                if not YukiData.fullscreen_locked:
                    YukiData.fullscreen_locked = True
                    YukiGUI.rewind_layout.setContentsMargins(100, 0, 50, 0)
                    setShortcutState(False)
                    if YukiData.state.isVisible() and YukiData.state.text().startswith(
                        _("Volume")
                    ):
                        YukiData.state.hide()
                    win.menu_bar_qt.show()
                    hide_playlist_fullscreen()
                    hide_controlpanel_fullscreen()
                    dockWidget_playlist.setWindowOpacity(1)
                    dockWidget_playlist.hide()
                    dockWidget_controlPanel.setWindowOpacity(1)
                    dockWidget_controlPanel.hide()
                    YukiData.fullscreen = False
                    if YukiData.state.text().endswith(
                        "{} F".format(_("To exit fullscreen mode press"))
                    ):
                        YukiData.state.setTextYuki("")
                        if not YukiData.gl_is_static:
                            YukiData.state.hide()
                            win.update()
                    if (
                        not YukiData.player.pause
                        and YukiData.playing
                        and YukiGUI.start_label.text()
                    ):
                        YukiGUI.progress.show()
                        YukiGUI.start_label.show()
                        YukiGUI.stop_label.show()
                        dockWidget_controlPanel.setFixedHeight(
                            DOCKWIDGET_CONTROLPANEL_HEIGHT_HIGH
                        )
                    YukiGUI.label_video_data.show()
                    YukiGUI.label_avsync.show()
                    for lbl3 in YukiGUI.controlpanel_btns:
                        if lbl3 not in YukiGUI.show_lbls_fullscreen:
                            lbl3.show()
                    dockWidget_controlPanel.show()
                    dockWidget_playlist.show()
                    win.update()
                    if not YukiData.currentMaximized:
                        win.showNormal()
                    else:
                        win.showMaximized()
                    win.setGeometry(
                        YukiData.currentWidthHeight[0],
                        YukiData.currentWidthHeight[1],
                        YukiData.currentWidthHeight[2],
                        YukiData.currentWidthHeight[3],
                    )
                    if not YukiData.isPlaylistVisible:
                        show_hide_playlist()
                    if YukiData.settings["panelposition"] == 1:
                        YukiData.tvguide_close_lbl.move(
                            win.width() - YukiData.tvguide_lbl.width() - 40,
                            YukiGUI.tvguide_lbl_offset,
                        )
                    centerwidget(YukiGUI.loading1)
                    centerwidget(YukiGUI.loading2, 50)
                    if YukiData.isControlPanelVisible:
                        dockWidget_controlPanel.show()
                    else:
                        dockWidget_controlPanel.hide()
                    if YukiData.compact_mode:
                        win.menu_bar_qt.hide()
                        setShortcutState(True)
                    dockWidget_playlist.lower()
                    YukiData.fullscreen_locked = False
            try:
                if YukiData.event_handler:
                    YukiData.event_handler.on_fullscreen()
            except Exception:
                logger.warning(traceback.format_exc())

        def is_show_volume():
            showdata = YukiData.fullscreen
            if not YukiData.fullscreen and win.isVisible():
                showdata = not dockWidget_controlPanel.isVisible()
            return showdata and not YukiGUI.controlpanel_widget.isVisible()

        def show_volume(volume1):
            if is_show_volume():
                YukiData.state.show()
                if isinstance(volume1, str):
                    YukiData.state.setTextYuki(volume1)
                else:
                    YukiData.state.setTextYuki(
                        "{}: {}%".format(_("Volume"), int(volume1))
                    )

        def mpv_mute():
            YukiData.time_stop = time.time() + 3
            if YukiData.player.mute:
                if YukiData.old_value > 50:
                    YukiGUI.btn_volume.setIcon(
                        QtGui.QIcon(str(YukiData.icons_folder / "volume.png"))
                    )
                else:
                    YukiGUI.btn_volume.setIcon(
                        QtGui.QIcon(str(YukiData.icons_folder / "volume-low.png"))
                    )
                mpv_override_mute(False)
                YukiGUI.volume_slider.setValue(YukiData.old_value)
                show_volume(YukiData.old_value)
            else:
                YukiGUI.btn_volume.setIcon(
                    QtGui.QIcon(str(YukiData.icons_folder / "mute.png"))
                )
                mpv_override_mute(True)
                YukiData.old_value = YukiGUI.volume_slider.value()
                YukiGUI.volume_slider.setValue(0)
                show_volume(_("Volume off"))

        def mpv_volume_set(*args, **kwargs):
            YukiData.time_stop = time.time() + 3
            vol = int(YukiGUI.volume_slider.value())
            try:
                if vol == 0:
                    show_volume(_("Volume off"))
                else:
                    show_volume(vol)
            except NameError:
                pass
            mpv_override_volume(vol)
            if vol == 0:
                mpv_override_mute(True)
                YukiGUI.btn_volume.setIcon(
                    QtGui.QIcon(str(YukiData.icons_folder / "mute.png"))
                )
            else:
                mpv_override_mute(False)
                if vol > 50:
                    YukiGUI.btn_volume.setIcon(
                        QtGui.QIcon(str(YukiData.icons_folder / "volume.png"))
                    )
                else:
                    YukiGUI.btn_volume.setIcon(
                        QtGui.QIcon(str(YukiData.icons_folder / "volume-low.png"))
                    )

        dockWidget_playlist = PlaylistDockWidget(win)
        dockWidget_playlist.installEventFilter(win)

        win.listWidget = QtWidgets.QListWidget()
        win.moviesWidget = QtWidgets.QListWidget()
        win.seriesWidget = QtWidgets.QListWidget()

        YukiData.tvguide_lbl = YukiGUI.ScrollableLabel(win)
        YukiData.tvguide_lbl.move(0, YukiGUI.tvguide_lbl_offset)
        YukiData.tvguide_lbl.setFixedWidth(TVGUIDE_WIDTH)
        YukiData.tvguide_lbl.hide()

        YukiGUI.set_widget_opacity(YukiData.tvguide_lbl, YukiGUI.DEFAULT_OPACITY)

        YukiData.tvguide_close_lbl = TVguideCloseLabel(win)
        YukiData.tvguide_close_lbl.setPixmap(
            QtGui.QIcon(str(YukiData.icons_folder / "close.png")).pixmap(32, 32)
        )
        YukiData.tvguide_close_lbl.setStyleSheet(
            "background-color: {};".format(
                "black" if YukiData.use_dark_icon_theme else "white"
            )
        )
        YukiData.tvguide_close_lbl.resize(32, 32)
        if YukiData.settings["panelposition"] in (0, 2):
            YukiData.tvguide_close_lbl.move(
                YukiData.tvguide_lbl.width() + 5, YukiGUI.tvguide_lbl_offset
            )
        else:
            YukiData.tvguide_close_lbl.move(
                win.width() - YukiData.tvguide_lbl.width() - 40,
                YukiGUI.tvguide_lbl_offset,
            )
            YukiGUI.lbl2.move(
                YukiData.tvguide_lbl.width() + YukiGUI.lbl2.width(), YukiGUI.lbl2_offset
            )
        YukiData.tvguide_close_lbl.hide()

        YukiGUI.set_widget_opacity(YukiData.tvguide_close_lbl, YukiGUI.DEFAULT_OPACITY)

        @idle_function
        def redraw_channels(*args, **kwargs):
            channels_1 = generate_channels()
            update_tvguide()
            YukiData.row0 = win.listWidget.currentRow()
            val0 = win.listWidget.verticalScrollBar().value()
            destroy_listwidget_items(win.listWidget)
            win.listWidget.clear()
            if channels_1:
                for channel_1 in channels_1.values():
                    channel_3 = channel_1
                    win.listWidget.addItem(channel_3[0])
                    win.listWidget.setItemWidget(channel_3[0], channel_3[1])
            else:
                win.listWidget.addItem(_("Nothing found"))
            win.listWidget.setCurrentRow(YukiData.row0)
            win.listWidget.verticalScrollBar().setValue(val0)

        def group_change(self):
            YukiData.comboboxIndex = YukiData.combobox.currentIndex()
            YukiData.current_group = groups[self]
            if not YukiData.first_change:
                YukiData.first_change = True
            else:
                redraw_channels()

        def playmode_change(self=False):
            YukiData.playmodeIndex = playmode_selector.currentIndex()
            if not YukiData.first_playmode_change:
                YukiData.first_playmode_change = True
            else:
                tv_widgets = [YukiData.combobox, win.listWidget, YukiGUI.widget4]
                movies_widgets = [movies_combobox, win.moviesWidget]
                series_widgets = [win.seriesWidget]
                # Clear search text when play mode is changed
                # (TV channels, movies, series)
                try:
                    YukiGUI.channelfilter.setText("")
                    YukiGUI.channelfiltersearch.click()
                except Exception:
                    show_exception(traceback.format_exc())
                if playmode_selector.currentIndex() == 0:
                    # TV channels
                    for movie_label in movies_widgets:
                        movie_label.hide()
                    for serie_label in series_widgets:
                        serie_label.hide()
                    for tv_label in tv_widgets:
                        tv_label.show()
                    try:
                        YukiGUI.channelfilter.setPlaceholderText(_("Search channel"))
                    except Exception:
                        show_exception(traceback.format_exc())
                if playmode_selector.currentIndex() == 1:
                    # Movies
                    for tv_label in tv_widgets:
                        tv_label.hide()
                    for serie_label in series_widgets:
                        serie_label.hide()
                    for movie_label in movies_widgets:
                        movie_label.show()
                    try:
                        YukiGUI.channelfilter.setPlaceholderText(_("Search movie"))
                    except Exception:
                        show_exception(traceback.format_exc())
                if playmode_selector.currentIndex() == 2:
                    # Series
                    for tv_label in tv_widgets:
                        tv_label.hide()
                    for movie_label in movies_widgets:
                        movie_label.hide()
                    for serie_label in series_widgets:
                        serie_label.show()
                    try:
                        YukiGUI.channelfilter.setPlaceholderText(_("Search series"))
                    except Exception:
                        show_exception(traceback.format_exc())

        channels = generate_channels()
        for channel in channels:
            win.listWidget.addItem(channels[channel][0])
            win.listWidget.setItemWidget(channels[channel][0], channels[channel][1])

        YukiGUI.create_sort_widgets2()

        def tvguide_context_menu():
            update_tvguide()
            YukiData.tvguide_lbl.show()
            YukiData.tvguide_close_lbl.show()

        def settings_context_menu():
            if YukiGUI.channels_win.isVisible():
                YukiGUI.channels_win.close()
            YukiGUI.title.setText(str(YukiData.item_selected))
            if (
                YukiData.settings["m3u"] in YukiData.channel_sets
                and YukiData.item_selected
                in YukiData.channel_sets[YukiData.settings["m3u"]]
            ):
                YukiGUI.deinterlace_chk.setChecked(
                    YukiData.channel_sets[YukiData.settings["m3u"]][
                        YukiData.item_selected
                    ]["deinterlace"]
                )
                try:
                    YukiGUI.useragent_choose.setText(
                        YukiData.channel_sets[YukiData.settings["m3u"]][
                            YukiData.item_selected
                        ]["ua"]
                    )
                except Exception:
                    YukiGUI.useragent_choose.setText("")
                try:
                    YukiGUI.referer_choose_custom.setText(
                        YukiData.channel_sets[YukiData.settings["m3u"]][
                            YukiData.item_selected
                        ]["ref"]
                    )
                except Exception:
                    YukiGUI.referer_choose_custom.setText("")
                try:
                    YukiGUI.group_text.setText(
                        YukiData.channel_sets[YukiData.settings["m3u"]][
                            YukiData.item_selected
                        ]["group"]
                    )
                except Exception:
                    YukiGUI.group_text.setText("")
                try:
                    YukiGUI.hidden_chk.setChecked(
                        YukiData.channel_sets[YukiData.settings["m3u"]][
                            YukiData.item_selected
                        ]["hidden"]
                    )
                except Exception:
                    YukiGUI.hidden_chk.setChecked(False)
                try:
                    YukiGUI.contrast_choose.setValue(
                        YukiData.channel_sets[YukiData.settings["m3u"]][
                            YukiData.item_selected
                        ]["contrast"]
                    )
                except Exception:
                    YukiGUI.contrast_choose.setValue(0)
                try:
                    YukiGUI.brightness_choose.setValue(
                        YukiData.channel_sets[YukiData.settings["m3u"]][
                            YukiData.item_selected
                        ]["brightness"]
                    )
                except Exception:
                    YukiGUI.brightness_choose.setValue(0)
                try:
                    YukiGUI.hue_choose.setValue(
                        YukiData.channel_sets[YukiData.settings["m3u"]][
                            YukiData.item_selected
                        ]["hue"]
                    )
                except Exception:
                    YukiGUI.hue_choose.setValue(0)
                try:
                    YukiGUI.saturation_choose.setValue(
                        YukiData.channel_sets[YukiData.settings["m3u"]][
                            YukiData.item_selected
                        ]["saturation"]
                    )
                except Exception:
                    YukiGUI.saturation_choose.setValue(0)
                try:
                    YukiGUI.gamma_choose.setValue(
                        YukiData.channel_sets[YukiData.settings["m3u"]][
                            YukiData.item_selected
                        ]["gamma"]
                    )
                except Exception:
                    YukiGUI.gamma_choose.setValue(0)
                try:
                    YukiGUI.videoaspect_choose.setCurrentIndex(
                        YukiData.channel_sets[YukiData.settings["m3u"]][
                            YukiData.item_selected
                        ]["videoaspect"]
                    )
                except Exception:
                    YukiGUI.videoaspect_choose.setCurrentIndex(0)
                try:
                    YukiGUI.zoom_choose.setCurrentIndex(
                        YukiData.channel_sets[YukiData.settings["m3u"]][
                            YukiData.item_selected
                        ]["zoom"]
                    )
                except Exception:
                    YukiGUI.zoom_choose.setCurrentIndex(0)
                try:
                    YukiGUI.panscan_choose.setValue(
                        YukiData.channel_sets[YukiData.settings["m3u"]][
                            YukiData.item_selected
                        ]["panscan"]
                    )
                except Exception:
                    YukiGUI.panscan_choose.setValue(0)
                try:
                    epgname_saved = YukiData.channel_sets[YukiData.settings["m3u"]][
                        YukiData.item_selected
                    ]["epgname"]
                    if not epgname_saved:
                        epgname_saved = _("Default")
                    YukiGUI.epgname_lbl.setText(epgname_saved)
                except Exception:
                    YukiGUI.epgname_lbl.setText(_("Default"))
            else:
                YukiGUI.deinterlace_chk.setChecked(YukiData.settings["deinterlace"])
                YukiGUI.hidden_chk.setChecked(False)
                YukiGUI.contrast_choose.setValue(0)
                YukiGUI.brightness_choose.setValue(0)
                YukiGUI.hue_choose.setValue(0)
                YukiGUI.saturation_choose.setValue(0)
                YukiGUI.gamma_choose.setValue(0)
                YukiGUI.videoaspect_choose.setCurrentIndex(0)
                YukiGUI.zoom_choose.setCurrentIndex(0)
                YukiGUI.panscan_choose.setValue(0)
                YukiGUI.useragent_choose.setText("")
                YukiGUI.referer_choose_custom.setText("")
                YukiGUI.group_text.setText("")
                YukiGUI.epgname_lbl.setText(_("Default"))
            moveWindowToCenter(YukiGUI.channels_win)
            YukiGUI.channels_win.show()

        def tvguide_favourites_add():
            if YukiData.item_selected in YukiData.favourite_sets:
                isdelete_fav_msg = QtWidgets.QMessageBox.question(
                    None,
                    MAIN_WINDOW_TITLE,
                    str(_("Delete from favourites")) + "?",
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.Yes,
                )
                if isdelete_fav_msg == QtWidgets.QMessageBox.StandardButton.Yes:
                    YukiData.favourite_sets.remove(YukiData.item_selected)
            else:
                YukiData.favourite_sets.append(YukiData.item_selected)
            save_favourite_sets()
            redraw_channels()

        def favoritesplaylistsep_add():
            ps_data = getArrayItem(YukiData.item_selected)
            str1 = "#EXTINF:-1"
            if ps_data["tvg-name"]:
                str1 += f" tvg-name=\"{ps_data['tvg-name']}\""
            if ps_data["tvg-ID"]:
                str1 += f" tvg-id=\"{ps_data['tvg-ID']}\""
            if ps_data["tvg-logo"]:
                str1 += f" tvg-logo=\"{ps_data['tvg-logo']}\""
            if ps_data["tvg-group"]:
                str1 += f" tvg-group=\"{ps_data['tvg-group']}\""
            if ps_data["tvg-url"]:
                str1 += f" tvg-url=\"{ps_data['tvg-url']}\""
            else:
                str1 += f" tvg-url=\"{YukiData.settings['epg']}\""
            if ps_data["catchup"]:
                str1 += f" catchup=\"{ps_data['catchup']}\""
            if ps_data["catchup-source"]:
                str1 += f" catchup-source=\"{ps_data['catchup-source']}\""
            if ps_data["catchup-days"]:
                str1 += f" catchup-days=\"{ps_data['catchup-days']}\""

            str_append = ""
            if ps_data["useragent"]:
                str_append += f"#EXTVLCOPT:http-user-agent={ps_data['useragent']}\n"
            if ps_data["referer"]:
                str_append += f"#EXTVLCOPT:http-referrer={ps_data['referer']}\n"

            str1 += f",{YukiData.item_selected}\n{str_append}{ps_data['url']}\n"
            with open(
                Path(LOCAL_DIR) / "favplaylist.m3u", encoding="utf8"
            ) as favplaylist_file1:
                favplaylist_file_contents = favplaylist_file1.read()
            if (
                favplaylist_file_contents
                == "#EXTM3U\n#EXTINF:-1,-\nhttp://255.255.255.255\n"
            ):
                with open(
                    Path(LOCAL_DIR) / "favplaylist.m3u", "w", encoding="utf8"
                ) as favplaylist_file2:
                    favplaylist_file2.write("#EXTM3U\n" + str1)
            else:
                if str1 in favplaylist_file_contents:
                    playlistsep_del_msg = QtWidgets.QMessageBox.question(
                        None,
                        MAIN_WINDOW_TITLE,
                        _("Remove channel from Favourites+?"),
                        QtWidgets.QMessageBox.StandardButton.Yes
                        | QtWidgets.QMessageBox.StandardButton.No,
                        QtWidgets.QMessageBox.StandardButton.Yes,
                    )
                    if playlistsep_del_msg == QtWidgets.QMessageBox.StandardButton.Yes:
                        new_data = favplaylist_file_contents.replace(str1, "")
                        if new_data == "#EXTM3U\n":
                            new_data = "#EXTM3U\n#EXTINF:-1,-\nhttp://255.255.255.255\n"
                        with open(
                            Path(LOCAL_DIR) / "favplaylist.m3u",
                            "w",
                            encoding="utf8",
                        ) as favplaylist_file3:
                            favplaylist_file3.write(new_data)
                else:
                    with open(
                        Path(LOCAL_DIR) / "favplaylist.m3u", "w", encoding="utf8"
                    ) as favplaylist_file4:
                        favplaylist_file4.write(favplaylist_file_contents + str1)

        def show_context_menu(pos):
            is_continue = True
            try:
                is_continue = win.listWidget.selectedItems()[0].text() != _(
                    "Nothing found"
                )
            except Exception:
                pass
            try:
                if is_continue:
                    self = win.listWidget
                    itemSelected_event(self.selectedItems()[0])
                    menu = QtWidgets.QMenu(self)
                    menu.addAction(_("TV guide"), tvguide_context_menu)
                    menu.addAction(_("Hide TV guide"), tvguide_hide)
                    menu.addAction(_("Favourites"), tvguide_favourites_add)
                    menu.addAction(
                        _("Favourites+ (separate playlist)"), favoritesplaylistsep_add
                    )
                    menu.addAction(
                        _("Open in external player"), YukiGUI.open_external_player
                    )
                    menu.addAction(_("Video settings"), settings_context_menu)
                    menu.exec(self.mapToGlobal(pos))
            except Exception:
                logger.warning(traceback.format_exc())

        win.listWidget.setContextMenuPolicy(
            QtCore.Qt.ContextMenuPolicy.CustomContextMenu
        )
        win.listWidget.customContextMenuRequested.connect(show_context_menu)
        win.listWidget.currentItemChanged.connect(itemSelected_event)
        win.listWidget.itemClicked.connect(itemSelected_event)
        win.listWidget.itemDoubleClicked.connect(itemClicked_event)

        def enterPressed():
            currentItem = win.listWidget.currentItem()
            if currentItem:
                itemClicked_event(currentItem)

        shortcuts = {}
        shortcuts_return = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Return),
            win.listWidget,
            activated=enterPressed,
        )

        def get_movie_text(movie_1):
            movie_1_txt = ""
            try:
                movie_1_txt = movie_1.text()
            except Exception:
                pass
            try:
                movie_1_txt = movie_1.data(QtCore.Qt.ItemDataRole.UserRole)
            except Exception:
                pass
            if not movie_1_txt:
                movie_1_txt = ""
            return movie_1_txt

        def channelfilter_do():
            try:
                filter_txt1 = YukiGUI.channelfilter.text()
            except Exception:
                filter_txt1 = ""
            YukiData.search = filter_txt1
            if YukiData.playmodeIndex == 0:  # TV channels
                redraw_channels()
            elif YukiData.playmodeIndex == 1:  # Movies
                for item3 in range(win.moviesWidget.count()):
                    if (
                        filter_txt1.lower().strip()
                        in get_movie_text(win.moviesWidget.item(item3)).lower().strip()
                    ):
                        win.moviesWidget.item(item3).setHidden(False)
                    else:
                        win.moviesWidget.item(item3).setHidden(True)
            elif YukiData.playmodeIndex == 2:  # Series
                try:
                    redraw_series()
                except Exception:
                    show_exception(f"redraw_series FAILED\n{traceback.format_exc()}")
                for item4 in range(win.seriesWidget.count()):
                    if (
                        filter_txt1.lower().strip()
                        in win.seriesWidget.item(item4).text().lower().strip()
                    ):
                        win.seriesWidget.item(item4).setHidden(False)
                    else:
                        win.seriesWidget.item(item4).setHidden(True)

        loading = QtWidgets.QLabel(_("Loading..."))
        loading.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        loading.setFont(YukiGUI.font_12_bold)
        hideLoading()

        YukiData.combobox = QtWidgets.QComboBox()
        YukiData.combobox.currentIndexChanged.connect(group_change)

        if YukiData.settings["sort_categories"] == 1:
            groups_sorted = sorted(groups)
        elif YukiData.settings["sort_categories"] == 2:
            groups_sorted = sorted(groups, reverse=True)
        else:
            groups_sorted = groups

        if YukiData.settings["sort_categories"] in (1, 2):
            groups_sorted.remove(_("All channels"))
            YukiData.combobox.addItem(_("All channels"))

            groups_sorted.remove(_("Favourites"))
            YukiData.combobox.addItem(_("Favourites"))

        YukiData.groups_sorted = groups_sorted

        for group in groups_sorted:
            YukiData.combobox.addItem(group)

        def update_movie_icons():
            if YukiData.settings["channellogos"] != 3:  # Do not load any logos
                try:
                    for item4 in range(win.moviesWidget.count()):
                        movie_name = get_movie_text(win.moviesWidget.item(item4))
                        if movie_name:
                            if f"LOGOmovie:::{movie_name}" in YukiData.mp_manager_dict:
                                if YukiData.mp_manager_dict[
                                    f"LOGOmovie:::{movie_name}"
                                ][0]:
                                    movie_logo = get_pixmap_from_filename(
                                        YukiData.mp_manager_dict[
                                            f"LOGOmovie:::{movie_name}"
                                        ][0]
                                    )
                                    if movie_logo:
                                        win.moviesWidget.itemWidget(
                                            win.moviesWidget.item(item4)
                                        ).setPixmap(movie_logo)
                except Exception:
                    show_exception(
                        "Set movie logos failed with exception"
                        f"\n{traceback.format_exc()}"
                    )

        def movies_group_change():
            if YukiData.movies:
                current_movies_group = movies_combobox.currentText()
                if current_movies_group:
                    destroy_listwidget_items(win.moviesWidget)
                    win.moviesWidget.clear()
                    YukiData.currentMoviesGroup = {}
                    movie_logos_request = {}
                    for movies1 in YukiData.movies:
                        if "tvg-group" in YukiData.movies[movies1]:
                            if (
                                YukiData.movies[movies1]["tvg-group"]
                                == current_movies_group
                            ):
                                MovieWidget = YukiGUI.PlaylistWidget()
                                MovieWidget.name_label.setText(
                                    YukiData.movies[movies1]["title"]
                                )
                                MovieWidget.progress_bar.hide()
                                MovieWidget.hideDescription()
                                MovieWidget.setPixmap(YukiGUI.movie_icon)
                                # Create QListWidgetItem
                                myMovieQListWidgetItem = QtWidgets.QListWidgetItem()
                                myMovieQListWidgetItem.setData(
                                    QtCore.Qt.ItemDataRole.UserRole,
                                    YukiData.movies[movies1]["title"],
                                )
                                # Set size hint
                                myMovieQListWidgetItem.setSizeHint(
                                    MovieWidget.sizeHint()
                                )
                                win.moviesWidget.addItem(myMovieQListWidgetItem)
                                win.moviesWidget.setItemWidget(
                                    myMovieQListWidgetItem, MovieWidget
                                )
                                YukiData.currentMoviesGroup[
                                    YukiData.movies[movies1]["title"]
                                ] = YukiData.movies[movies1]
                                (
                                    req_data_ua1,
                                    req_data_ref1,
                                    _cenc_decryption_key,
                                ) = get_ua_ref_for_channel(
                                    YukiData.movies[movies1]["title"]
                                )
                                movie_logo1 = ""
                                if "tvg-logo" in YukiData.movies[movies1]:
                                    movie_logo1 = YukiData.movies[movies1]["tvg-logo"]
                                movie_logos_request[
                                    YukiData.movies[movies1]["title"]
                                ] = [
                                    movie_logo1,
                                    "",
                                    req_data_ua1,
                                    req_data_ref1,
                                ]
                    # Fetch movie logos
                    try:
                        if YukiData.settings["channellogos"] != 3:
                            if movie_logos_request != YukiData.movie_logos_request_old:
                                YukiData.movie_logos_request_old = movie_logos_request
                                logger.debug("Movie logos request")
                                if (
                                    YukiData.movie_logos_process
                                    and YukiData.movie_logos_process.is_alive()
                                ):
                                    # logger.debug(
                                    #     "Old movie logos request found, stopping it"
                                    # )
                                    YukiData.movie_logos_process.kill()
                                YukiData.movie_logos_process = get_context(
                                    "spawn"
                                ).Process(
                                    name="[yuki-iptv] channel_logos_worker_for_movie",
                                    target=channel_logos_worker,
                                    daemon=True,
                                    args=(
                                        movie_logos_request,
                                        YukiData.mp_manager_dict,
                                        "movie",
                                    ),
                                )
                                YukiData.movie_logos_process.start()
                    except Exception:
                        show_exception(
                            "Fetch movie logos failed with exception:"
                            f"\n{traceback.format_exc()}"
                        )
                    update_movie_icons()
            else:
                destroy_listwidget_items(win.moviesWidget)
                win.moviesWidget.clear()
                win.moviesWidget.addItem(_("Nothing found"))

        def movies_play(mov_item):
            if get_movie_text(mov_item) in YukiData.currentMoviesGroup:
                itemClicked_event(
                    get_movie_text(mov_item),
                    YukiData.currentMoviesGroup[get_movie_text(mov_item)]["url"],
                )

        win.moviesWidget.itemDoubleClicked.connect(movies_play)

        movies_groups = []
        movies_combobox = QtWidgets.QComboBox()
        for movie_combobox in YukiData.movies:
            if "tvg-group" in YukiData.movies[movie_combobox]:
                if YukiData.movies[movie_combobox]["tvg-group"] not in movies_groups:
                    movies_groups.append(YukiData.movies[movie_combobox]["tvg-group"])
        for movie_group in movies_groups:
            movies_combobox.addItem(movie_group)
        movies_combobox.currentIndexChanged.connect(movies_group_change)
        movies_group_change()

        def redraw_series():
            YukiData.serie_selected = False
            win.seriesWidget.clear()
            if YukiData.series:
                for serie2 in YukiData.series:
                    win.seriesWidget.addItem(serie2)
            else:
                win.seriesWidget.addItem(_("Nothing found"))

        @idle_function
        def series_change_pt2(sel_serie):
            YukiGUI.channelfilter.setDisabled(False)
            YukiGUI.channelfiltersearch.setDisabled(False)
            win.seriesWidget.clear()
            win.seriesWidget.addItem("< " + _("Back"))
            win.seriesWidget.item(0).setForeground(QtCore.Qt.GlobalColor.blue)
            for season_name in YukiData.series[sel_serie].seasons.keys():
                season = YukiData.series[sel_serie].seasons[season_name]
                season_item = QtWidgets.QListWidgetItem()
                season_item.setText(season.name)
                season_item.setFont(YukiGUI.font_bold)
                win.seriesWidget.addItem(season_item)
                for episode_name in season.episodes.keys():
                    episode = season.episodes[episode_name]
                    episode_item = QtWidgets.QListWidgetItem()
                    episode_item.setText(episode.title)
                    episode_item.setData(
                        QtCore.Qt.ItemDataRole.UserRole,
                        episode.url
                        + ":::::::::::::::::::"
                        + season.name
                        + ":::::::::::::::::::"
                        + sel_serie,
                    )
                    win.seriesWidget.addItem(episode_item)
            YukiData.serie_selected = True

        @idle_function
        def series_loading(*args, **kwargs):
            YukiGUI.channelfilter.setDisabled(True)
            YukiGUI.channelfiltersearch.setDisabled(True)
            win.seriesWidget.clear()
            win.seriesWidget.addItem(_("Loading..."))

        @async_gui_blocking_function
        def series_load(sel_serie):
            if sel_serie != _("Nothing found"):
                if not YukiData.series[sel_serie].seasons:
                    logger.info(f"Fetching data for serie '{sel_serie}'")
                    series_loading()
                    try:
                        xt.get_series_info_by_id(YukiData.series[sel_serie])
                        logger.info(
                            f"Fetching data for serie '{sel_serie}' completed"
                            f", seasons: {len(YukiData.series[sel_serie].seasons)}"
                        )
                    except Exception:
                        show_exception(
                            f"Fetching data for serie '{sel_serie}' FAILED"
                            f"\n{traceback.format_exc()}"
                        )
                series_change_pt2(sel_serie)

        def series_change(series_item):
            sel_serie = series_item.text()
            if sel_serie == "< " + _("Back"):
                redraw_series()
            elif sel_serie != _("Loading..."):
                if YukiData.serie_selected:
                    try:
                        serie_data = series_item.data(QtCore.Qt.ItemDataRole.UserRole)
                        if serie_data:
                            series_name = serie_data.split(":::::::::::::::::::")[2]
                            season_name = serie_data.split(":::::::::::::::::::")[1]
                            serie_url = serie_data.split(":::::::::::::::::::")[0]
                            itemClicked_event(
                                sel_serie
                                + " ::: "
                                + season_name
                                + " ::: "
                                + series_name,
                                serie_url,
                            )
                    except Exception:
                        show_exception(traceback.format_exc())
                else:
                    series_load(sel_serie)

        win.seriesWidget.itemDoubleClicked.connect(series_change)

        redraw_series()

        playmode_selector = QtWidgets.QComboBox()
        playmode_selector.currentIndexChanged.connect(playmode_change)
        for playmode in [_("TV channels"), _("Movies"), _("Series")]:
            playmode_selector.addItem(playmode)

        def focusOutEvent_after(
            playlist_widget_visible,
            controlpanel_widget_visible,
            channelfiltersearch_has_focus,
        ):
            YukiGUI.channelfilter.usePopup = False
            YukiGUI.playlist_widget.setWindowFlags(
                QtCore.Qt.WindowType.CustomizeWindowHint
                | QtCore.Qt.WindowType.FramelessWindowHint
                | QtCore.Qt.WindowType.X11BypassWindowManagerHint
            )
            YukiGUI.controlpanel_widget.setWindowFlags(
                QtCore.Qt.WindowType.CustomizeWindowHint
                | QtCore.Qt.WindowType.FramelessWindowHint
                | QtCore.Qt.WindowType.X11BypassWindowManagerHint
            )
            if playlist_widget_visible:
                YukiGUI.playlist_widget.show()
            if controlpanel_widget_visible:
                YukiGUI.controlpanel_widget.show()
            if channelfiltersearch_has_focus:
                YukiGUI.channelfiltersearch.click()

        @async_gui_blocking_function
        def mainthread_timer(execute):
            time.sleep(0.05)
            executeInMainThread(execute)

        class MyLineEdit(QtWidgets.QLineEdit):
            usePopup = False
            click_event = QtCore.pyqtSignal()

            def mousePressEvent(self, event1):
                if event1.button() == QtCore.Qt.MouseButton.LeftButton:
                    self.click_event.emit()
                else:
                    super().mousePressEvent(event1)

            def focusOutEvent(self, event):
                super().focusOutEvent(event)
                if YukiData.fullscreen:
                    playlist_widget_visible1 = YukiGUI.playlist_widget.isVisible()
                    controlpanel_widget_visible1 = (
                        YukiGUI.controlpanel_widget.isVisible()
                    )
                    channelfiltersearch_has_focus1 = (
                        YukiGUI.channelfiltersearch.hasFocus()
                    )
                    focusOutEvent_after_partial = partial(
                        focusOutEvent_after,
                        playlist_widget_visible1,
                        controlpanel_widget_visible1,
                        channelfiltersearch_has_focus1,
                    )
                    mainthread_timer_1 = partial(
                        mainthread_timer, focusOutEvent_after_partial
                    )
                    executeInMainThread(mainthread_timer_1)

        def channelfilter_clicked():
            if YukiData.fullscreen:
                playlist_widget_visible1 = YukiGUI.playlist_widget.isVisible()
                controlpanel_widget_visible1 = YukiGUI.controlpanel_widget.isVisible()
                YukiGUI.channelfilter.usePopup = True
                YukiGUI.playlist_widget.setWindowFlags(
                    QtCore.Qt.WindowType.CustomizeWindowHint
                    | QtCore.Qt.WindowType.FramelessWindowHint
                    | QtCore.Qt.WindowType.X11BypassWindowManagerHint
                    | QtCore.Qt.WindowType.Popup
                )
                YukiGUI.controlpanel_widget.setWindowFlags(
                    QtCore.Qt.WindowType.CustomizeWindowHint
                    | QtCore.Qt.WindowType.FramelessWindowHint
                    | QtCore.Qt.WindowType.X11BypassWindowManagerHint
                    | QtCore.Qt.WindowType.Popup
                )
                if playlist_widget_visible1:
                    YukiGUI.playlist_widget.show()
                if controlpanel_widget_visible1:
                    YukiGUI.controlpanel_widget.show()

        def page_change():
            win.listWidget.verticalScrollBar().setValue(0)
            redraw_channels()
            try:
                YukiGUI.page_box.clearFocus()
            except Exception:
                logger.warning(traceback.format_exc())

        YukiGUI.create2(
            get_page_count(len(YukiData.array)),
            channelfilter_clicked,
            channelfilter_do,
            page_change,
            MyLineEdit,
            playmode_selector,
            movies_combobox,
            loading,
        )

        if YukiData.settings["panelposition"] == 2:
            dockWidget_playlist.resize(
                DOCKWIDGET_PLAYLIST_WIDTH, dockWidget_playlist.height()
            )
            playlist_label = QtWidgets.QLabel(_("Playlist"))
            playlist_label.setFont(YukiGUI.font_12_bold)
            dockWidget_playlist.setTitleBarWidget(playlist_label)
        else:
            dockWidget_playlist.setFixedWidth(DOCKWIDGET_PLAYLIST_WIDTH)
            dockWidget_playlist.setTitleBarWidget(QtWidgets.QWidget())
        if YukiData.settings["panelposition"] == 2:
            gripWidget = QtWidgets.QWidget()
            gripLayout = QtWidgets.QVBoxLayout()
            gripLayout.setContentsMargins(0, 0, 0, 0)
            gripLayout.setSpacing(0)
            gripLayout.addWidget(YukiGUI.widget)
            gripLayout.addWidget(
                QtWidgets.QSizeGrip(YukiGUI.widget),
                0,
                QtCore.Qt.AlignmentFlag.AlignBottom
                | QtCore.Qt.AlignmentFlag.AlignRight,
            )
            gripWidget.setLayout(gripLayout)
            dockWidget_playlist.setWidget(gripWidget)
        else:
            dockWidget_playlist.setWidget(YukiGUI.widget)
        dockWidget_playlist.setFloating(YukiData.settings["panelposition"] == 2)
        dockWidget_playlist.setFeatures(
            QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
        )
        if YukiData.settings["panelposition"] == 0:
            win.addDockWidget(
                QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dockWidget_playlist
            )
        elif YukiData.settings["panelposition"] == 1:
            win.addDockWidget(
                QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dockWidget_playlist
            )
        elif YukiData.settings["panelposition"] == 2:
            separate_playlist_data = read_option("separate_playlist")
            if separate_playlist_data:
                dockWidget_playlist.setGeometry(
                    separate_playlist_data["x"],
                    separate_playlist_data["y"],
                    separate_playlist_data["w"],
                    separate_playlist_data["h"],
                )
            else:
                dockWidget_playlist.resize(dockWidget_playlist.width(), win.height())
                dockWidget_playlist.move(
                    win.pos().x() + win.width() - dockWidget_playlist.width() + 25,
                    win.pos().y(),
                )

        def do_screenshot():
            if YukiData.playing_channel:
                YukiData.state.show()
                YukiData.state.setTextYuki(_("Doing screenshot..."))
                ch = YukiData.playing_channel.replace(" ", "_")
                for char in FORBIDDEN_FILENAME_CHARS:
                    ch = ch.replace(char, "")
                cur_time = datetime.datetime.now().strftime("%d%m%Y_%H%M%S")
                screenshot_filename = "screenshot_-_" + cur_time + "_-_" + ch + ".png"
                if not YukiData.settings["scrrecnosubfolders"]:
                    screenshot_path = str(
                        Path(save_folder) / "screenshots" / screenshot_filename
                    )
                else:
                    screenshot_path = str(Path(save_folder) / screenshot_filename)
                try:
                    YukiData.player.screenshot_to_file(
                        screenshot_path, includes="subtitles"
                    )
                    YukiData.state.show()
                    YukiData.state.setTextYuki(_("Screenshot saved!"))
                except Exception:
                    logger.warning(traceback.format_exc())
                    YukiData.state.show()
                    YukiData.state.setTextYuki(_("Screenshot saving error!"))
                YukiData.time_stop = time.time() + 1
            else:
                YukiData.state.show()
                YukiData.state.setTextYuki("{}!".format(_("No channel selected")))
                YukiData.time_stop = time.time() + 1

        def update_tvguide(
            channel_1="",
            do_return=False,
            show_all_guides=False,
            mark_integers=False,
            date_selected=None,
        ):
            if YukiData.array:
                if not channel_1:
                    if YukiData.item_selected:
                        channel_2 = YukiData.item_selected
                    else:
                        channel_2 = sorted(YukiData.array.items())[0][0]
                else:
                    channel_2 = channel_1
                try:
                    channel_1_item = getArrayItem(channel_1)
                except Exception:
                    channel_1_item = None
                txt = _("No TV guide for channel")
                newline_symbol = "\n"
                if do_return:
                    newline_symbol = "!@#$%^^&*("

                current_programmes = None
                epg_id = get_epg_id(channel_2)
                if epg_id:
                    programmes = get_epg_programmes(epg_id)
                    if programmes:
                        current_programmes = programmes

                if current_programmes:
                    txt = newline_symbol
                    for pr in current_programmes:
                        override_this = False
                        if show_all_guides:
                            override_this = pr["start"] < time.time() + 1
                        else:
                            override_this = pr["stop"] > time.time() - 1
                        archive_btn = ""
                        if date_selected is not None:
                            override_this = epg_is_in_date(pr, date_selected)
                        if override_this:
                            def_placeholder = "%d.%m.%Y %H:%M"
                            if mark_integers:
                                def_placeholder = "%d.%m.%Y %H:%M:%S"
                            start_2 = (
                                datetime.datetime.fromtimestamp(pr["start"]).strftime(
                                    def_placeholder
                                )
                                + " - "
                            )
                            stop_2 = (
                                datetime.datetime.fromtimestamp(pr["stop"]).strftime(
                                    def_placeholder
                                )
                                + "\n"
                            )
                            try:
                                title_2 = pr["title"] if "title" in pr else ""
                            except Exception:
                                title_2 = ""
                            try:
                                desc_2 = (
                                    ("\n" + pr["desc"] + "\n") if "desc" in pr else ""
                                )
                            except Exception:
                                desc_2 = ""
                            attach_1 = ""
                            if mark_integers:
                                try:
                                    marked_integer = current_programmes.index(pr)
                                except Exception:
                                    marked_integer = -1
                                attach_1 = f" ({marked_integer})"
                            if (
                                date_selected is not None
                                and YukiGUI.showonlychplaylist_chk.isChecked()
                            ):
                                try:
                                    catchup_days2 = int(channel_1_item["catchup-days"])
                                except Exception:
                                    catchup_days2 = 7
                                # support for seconds
                                if catchup_days2 < 1000:
                                    catchup_days2 = catchup_days2 * 86400
                                if (
                                    pr["start"] < time.time() + 1
                                    and not (
                                        time.time() > pr["start"]
                                        and time.time() < pr["stop"]
                                    )
                                    and pr["stop"] > time.time() - catchup_days2
                                ):
                                    archive_link = urllib.parse.quote_plus(
                                        json.dumps(
                                            [
                                                channel_1,
                                                datetime.datetime.fromtimestamp(
                                                    pr["start"]
                                                ).strftime("%d.%m.%Y %H:%M:%S"),
                                                datetime.datetime.fromtimestamp(
                                                    pr["stop"]
                                                ).strftime("%d.%m.%Y %H:%M:%S"),
                                                current_programmes.index(pr),
                                            ]
                                        )
                                    )
                                    archive_btn = (
                                        '\n<a href="#__archive__'
                                        + archive_link
                                        + '">'
                                        + _("Open archive")
                                        + "</a>"
                                    )
                            start_symbl = ""
                            stop_symbl = ""
                            if YukiData.use_dark_icon_theme:
                                start_symbl = '<span style="color: white;">'
                                stop_symbl = "</span>"
                            use_epg_color = "green"
                            if time.time() > pr["start"] and time.time() < pr["stop"]:
                                use_epg_color = "red"
                            txt += (
                                f'<span style="color: {use_epg_color};">'
                                + start_2
                                + stop_2
                                + "</span>"
                                + start_symbl
                                + "<b>"
                                + title_2
                                + "</b>"
                                + archive_btn
                                + desc_2
                                + attach_1
                                + stop_symbl
                                + newline_symbol
                            )
                if txt == newline_symbol or not txt:
                    txt = _("No TV guide for channel")
                if do_return:
                    return txt
                txt = txt.replace("\n", "<br>").replace("<br>", "", 1)
                YukiData.tvguide_lbl.setText(txt)
            return ""

        def show_tvguide():
            if YukiData.tvguide_lbl.isVisible():
                YukiData.tvguide_lbl.setText("")
                YukiData.tvguide_lbl.hide()
                YukiData.tvguide_close_lbl.hide()
            else:
                update_tvguide()
                YukiData.tvguide_lbl.show()
                YukiData.tvguide_close_lbl.show()

        def update_tvguide_2():
            YukiGUI.epg_win_checkbox.clear()
            if YukiGUI.showonlychplaylist_chk.isChecked():
                YukiGUI.epg_win_count.setText(
                    "({}: {})".format(_("channels"), len(YukiData.array_sorted))
                )
                for channel_0 in YukiData.array_sorted:
                    YukiGUI.epg_win_checkbox.addItem(channel_0)
            else:
                epg_names = get_all_epg_names()
                if not epg_names:
                    epg_names = set()
                YukiGUI.epg_win_count.setText(
                    "({}: {})".format(_("channels"), len(epg_names))
                )
                for channel_0 in epg_names:
                    YukiGUI.epg_win_checkbox.addItem(channel_0)

        def show_tvguide_2():
            if YukiGUI.epg_win.isVisible():
                YukiGUI.epg_win.hide()
            else:
                epg_index = YukiGUI.epg_win_checkbox.currentIndex()
                update_tvguide_2()
                if epg_index != -1:
                    YukiGUI.epg_win_checkbox.setCurrentIndex(epg_index)
                moveWindowToCenter(YukiGUI.epg_win)
                YukiGUI.epg_win.show()

        def show_multi_epg():
            if YukiGUI.multi_epg_win.isVisible():
                YukiGUI.multi_epg_win.hide()
            else:
                YukiGUI.multi_epg_win._set(
                    getArrayItem=getArrayItem,
                    get_epg_id=get_epg_id,
                    get_epg_programmes=get_epg_programmes,
                    epg_is_in_date=epg_is_in_date,
                )
                YukiGUI.multi_epg_win.first()
                moveWindowToCenter(YukiGUI.multi_epg_win)
                YukiGUI.multi_epg_win.show()

        def show_archive():
            if not YukiGUI.epg_win.isVisible():
                show_tvguide_2()
                find_channel = YukiData.item_selected
                if not find_channel:
                    find_channel = YukiData.playing_channel
                if find_channel:
                    try:
                        find_channel_index = YukiGUI.epg_win_checkbox.findText(
                            find_channel, QtCore.Qt.MatchFlag.MatchExactly
                        )
                    except Exception:
                        find_channel_index = -1
                    if find_channel_index != -1:
                        YukiGUI.epg_win_checkbox.setCurrentIndex(find_channel_index)
                epg_date_changed(YukiGUI.epg_select_date.selectedDate())
            else:
                YukiGUI.epg_win.hide()

        def start_record(ch1, url3):
            orig_channel_name = ch1
            if not YukiData.is_recording:
                YukiData.is_recording = True
                YukiGUI.lbl2.show()
                YukiGUI.lbl2.setText(_("Preparing record"))
                ch = ch1.replace(" ", "_")
                for char in FORBIDDEN_FILENAME_CHARS:
                    ch = ch.replace(char, "")
                cur_time = datetime.datetime.now().strftime("%d%m%Y_%H%M%S")
                record_format = ".ts"
                if is_youtube_url(url3):
                    record_format = ".mkv"
                if not YukiData.settings["scrrecnosubfolders"]:
                    out_file = str(
                        Path(
                            save_folder,
                            "recordings",
                            "recording_-_" + cur_time + "_-_" + ch + record_format,
                        )
                    )
                else:
                    out_file = str(
                        Path(
                            save_folder,
                            "recording_-_" + cur_time + "_-_" + ch + record_format,
                        )
                    )
                YukiData.record_file = out_file
                record(
                    url3,
                    out_file,
                    orig_channel_name,
                    f"Referer: {YukiData.settings['referer']}",
                    get_ua_ref_for_channel,
                )
            else:
                YukiData.is_recording = False
                YukiData.recording_time = 0
                stop_record()
                YukiGUI.lbl2.setText("")
                YukiGUI.lbl2.hide()

        def do_record():
            if YukiData.playing_channel:
                start_record(YukiData.playing_channel, YukiData.playing_url)
            else:
                YukiData.time_stop = time.time() + 1
                YukiData.state.show()
                YukiData.state.setTextYuki(_("No channel selected for record"))

        def mpv_log_handler(mpv_loglevel, component, message):
            mpv_loglevel_ = str(mpv_loglevel).lower().strip()
            mpv_log_str = f"{component}: {message}".strip()

            if "Invalid video timestamp: " not in mpv_log_str:
                if "debug" in mpv_loglevel_ or "trace" in mpv_loglevel_:
                    mpv_logger.debug(mpv_log_str)
                elif "warn" in mpv_loglevel_:
                    mpv_logger.warning(mpv_log_str)
                elif "error" in mpv_loglevel_:
                    mpv_logger.error(mpv_log_str)
                elif "fatal" in mpv_loglevel_:
                    mpv_logger.critical(mpv_log_str)
                    show_exception(f"libmpv [CRITICAL] {mpv_log_str}")
                else:
                    mpv_logger.info(mpv_log_str)

            if "stream: failed to open" in mpv_log_str.lower():
                end_file_error_callback(True)

            if (
                "software renderer" in mpv_log_str.lower()
                or "indirect context" in mpv_log_str.lower()
            ):
                logger.warning(
                    "libmpv detected software renderer, "
                    "switching profile to fast to avoid lagging"
                )
                try:
                    YukiData.player.profile = "fast"
                except Exception:
                    logger.warning(
                        f"Failed setting profile to fast!\n{traceback.format_exc()}"
                    )

        def playLastChannel():
            isPlayingLast = False
            if (
                os.path.isfile(Path(LOCAL_DIR) / "lastchannels.json")
                and YukiData.settings["openprevchannel"]
            ):
                try:
                    with open(
                        Path(LOCAL_DIR) / "lastchannels.json", encoding="utf8"
                    ) as lastchannels_file:
                        lastfile_file_data = json.loads(lastchannels_file.read())
                    if lastfile_file_data[0] in YukiData.array_sorted:
                        isPlayingLast = True
                        YukiData.player.user_agent = lastfile_file_data[2]
                        setChannelText(f"  {lastfile_file_data[0]}")
                        itemClicked_event(lastfile_file_data[0])
                        setChannelText(f"  {lastfile_file_data[0]}")
                        try:
                            if lastfile_file_data[3] < YukiData.combobox.count():
                                YukiData.combobox.setCurrentIndex(lastfile_file_data[3])
                        except Exception:
                            pass
                        try:
                            win.listWidget.setCurrentRow(lastfile_file_data[4])
                        except Exception:
                            pass
                except Exception:
                    if os.path.isfile(Path(LOCAL_DIR) / "lastchannels.json"):
                        os.remove(Path(LOCAL_DIR) / "lastchannels.json")
            return isPlayingLast

        options = get_mpv_options()

        def is_ytdl_enabled_in_options():
            return not (
                "ytdl" not in options
                or "no" in str(options["ytdl"]).lower().strip()
                or "false" in str(options["ytdl"]).lower().strip()
                or not options["ytdl"]
            )

        logger.info(f"Using libmpv options:\n{pprint.pformat(options)}")

        def get_about_text():
            about_txt = f"<b>yuki-iptv {APP_VERSION}</b>"
            about_txt += "<br><br>" + _("IPTV player with EPG support") + "<br><br>"
            about_txt += (
                _("Using Qt {}").replace("Qt", "Python").format(sys.version.strip())
            )
            about_txt += (
                "<br>"
                + _("Using Qt {}").format(QtCore.qVersion())
                + f" ({app.platformName()})"
            )
            mpv_version = YukiData.player.mpv_version
            if " " in mpv_version:
                mpv_version = mpv_version.split(" ", 1)[1]
            if not mpv_version:
                mpv_version = "UNKNOWN"
            about_txt += "<br>" + _("Using libmpv {}").format(mpv_version)
            about_txt += YukiData.mpv_api_version
            about_txt += (
                "<br><br>"
                + _("mpv options")
                + ":<br>"
                + pprint.pformat(options).replace("\n", "<br>")
            )
            return about_txt

        def main_channel_settings():
            if YukiData.playing_channel:
                YukiData.item_selected = YukiData.playing_channel
                settings_context_menu()
            else:
                msg = QtWidgets.QMessageBox(
                    QtWidgets.QMessageBox.Icon.Warning,
                    MAIN_WINDOW_TITLE,
                    _("No channel selected"),
                    QtWidgets.QMessageBox.StandardButton.Ok,
                )
                msg.exec()

        @idle_function
        def showhideplaylist(*args, **kwargs):
            if not YukiData.fullscreen:
                try:
                    show_hide_playlist()
                except Exception:
                    show_exception(traceback.format_exc())

        @idle_function
        def lowpanel_ch_1(*args, **kwargs):
            if not YukiData.fullscreen:
                try:
                    lowpanel_ch()
                except Exception:
                    show_exception(traceback.format_exc())

        def showhideeverything():
            if not YukiData.fullscreen:
                if dockWidget_playlist.isVisible():
                    YukiData.compact_mode = True
                    dockWidget_playlist.hide()
                    dockWidget_controlPanel.hide()
                    win.menu_bar_qt.hide()
                else:
                    YukiData.compact_mode = False
                    dockWidget_playlist.show()
                    dockWidget_controlPanel.show()
                    win.menu_bar_qt.show()

        def process_stream_info(
            stream_info_count,
            stream_info_name,
            stream_properties,
            stream_information_name,
        ):
            if stream_information_name:
                stream_information_label1 = QtWidgets.QLabel()
                stream_information_label1.setStyleSheet("color:green")
                stream_information_label1.setFont(YukiGUI.font_bold)
                stream_information_label1.setText("\n" + stream_information_name + "\n")
                YukiGUI.stream_information_layout.addWidget(
                    stream_information_label1, stream_info_count, 0
                )
                stream_info_count += 1

            stream_information_label2 = QtWidgets.QLabel()
            stream_information_label2.setFont(YukiGUI.font_bold)
            stream_information_label2.setText(stream_info_name)
            YukiGUI.stream_information_layout.addWidget(
                stream_information_label2, stream_info_count, 0
            )

            for stream_information_data in stream_properties:
                stream_info_count += 1
                stream_info_widget1 = QtWidgets.QLabel()
                stream_info_widget2 = QtWidgets.QLabel()
                stream_info_widget1.setText(str(stream_information_data))
                stream_info_widget2.setText(
                    str(stream_properties[stream_information_data])
                )

                if (
                    str(stream_information_data) == _("Average Bitrate")
                    and stream_properties == stream_info.video_properties[_("General")]
                ):
                    stream_info.data["video"] = [stream_info_widget2, stream_properties]

                if (
                    str(stream_information_data) == _("Average Bitrate")
                    and stream_properties == stream_info.audio_properties[_("General")]
                ):
                    stream_info.data["audio"] = [stream_info_widget2, stream_properties]

                YukiGUI.stream_information_layout.addWidget(
                    stream_info_widget1, stream_info_count, 0
                )
                YukiGUI.stream_information_layout.addWidget(
                    stream_info_widget2, stream_info_count, 1
                )
            return stream_info_count + 1

        def open_stream_info():
            if YukiData.playing_channel:
                for stream_info_i in reversed(
                    range(YukiGUI.stream_information_layout.count())
                ):
                    YukiGUI.stream_information_layout.itemAt(
                        stream_info_i
                    ).widget().setParent(None)

                stream_props = [
                    stream_info.video_properties[_("General")],
                    stream_info.video_properties[_("Color")],
                    stream_info.audio_properties[_("General")],
                    stream_info.audio_properties[_("Layout")],
                ]

                stream_info_count = 1
                stream_info_video_lbl = QtWidgets.QLabel(_("Video") + "\n")
                stream_info_video_lbl.setStyleSheet("color:green")
                stream_info_video_lbl.setFont(YukiGUI.font_bold)
                YukiGUI.stream_information_layout.addWidget(stream_info_video_lbl, 0, 0)
                stream_info_count = process_stream_info(
                    stream_info_count, _("General"), stream_props[0], ""
                )
                stream_info_count = process_stream_info(
                    stream_info_count, _("Color"), stream_props[1], ""
                )
                stream_info_count = process_stream_info(
                    stream_info_count, _("General"), stream_props[2], _("Audio")
                )
                stream_info_count = process_stream_info(
                    stream_info_count, _("Layout"), stream_props[3], ""
                )

                if not YukiGUI.streaminfo_win.isVisible():
                    moveWindowToCenter(YukiGUI.streaminfo_win)
                    YukiGUI.streaminfo_win.show()
                else:
                    YukiGUI.streaminfo_win.hide()
            else:
                YukiData.state.show()
                YukiData.state.setTextYuki("{}!".format(_("No channel selected")))
                YukiData.time_stop = time.time() + 1

        def is_recording_func():
            ret_code_rec = False
            if YukiData.ffmpeg_processes:
                ret_code_array = []
                for ffmpeg_process_1 in YukiData.ffmpeg_processes:
                    if ffmpeg_process_1[0].processId() == 0:
                        ret_code_array.append(True)
                        YukiData.ffmpeg_processes.remove(ffmpeg_process_1)
                    else:
                        ret_code_array.append(False)
                ret_code_rec = False not in ret_code_array
            else:
                ret_code_rec = True
            return ret_code_rec

        def redraw_menubar():
            try:
                update_menubar(
                    YukiData.player.track_list,
                    YukiData.playing_channel,
                    YukiData.settings["m3u"],
                )
            except Exception:
                logger.warning("redraw_menubar failed")
                show_exception(traceback.format_exc(), "redraw_menubar failed")

        YukiData.right_click_menu = QtWidgets.QMenu()

        @idle_function
        def do_reconnect1(*args, **kwargs):
            if YukiData.playing_channel:
                logger.info("Reconnecting to stream")
                try:
                    doPlay(*YukiData.do_play_args)
                except Exception:
                    logger.warning("Failed reconnecting to stream - no known URL")

        @async_gui_blocking_function
        def do_reconnect1_async(*args, **kwargs):
            time.sleep(1)
            do_reconnect1()

        @idle_function
        def end_file_error_callback(no_reconnect=False):
            logger.warning("Playing error!")
            logger.warning("Hint: check User-Agent and Referer headers.")
            logger.warning(
                "You can try browser user-agents "
                "or (if stream works in mpv) use User-Agent 'libmpv'."
            )
            if (
                not no_reconnect
                and YukiData.settings["autoreconnection"]
                and YukiData.playing_group == 0
            ):
                logger.warning("Connection to stream lost, waiting 1 sec...")
                do_reconnect1_async()
            elif not YukiData.is_loading:
                mpv_stop()
            else:
                YukiData.resume_playback = not YukiData.player.pause
                mpv_stop()

            YukiGUI.channel.setText("")
            YukiGUI.channel.hide()
            loading.setText(_("Playing error"))
            loading.setFont(YukiGUI.font_bold_medium)
            showLoading()
            YukiGUI.loading1.hide()
            YukiGUI.loading_movie.stop()

        @idle_function
        def end_file_callback(*args, **kwargs):
            if win.isVisible():
                if YukiData.playing_channel and YukiData.player.path is None:
                    if (
                        YukiData.settings["autoreconnection"]
                        and YukiData.playing_group == 0
                    ):
                        logger.warning("Connection to stream lost, waiting 1 sec...")
                        do_reconnect1_async()
                    elif not YukiData.is_loading:
                        mpv_stop()

        @idle_function
        def file_loaded_callback(*args, **kwargs):
            if YukiData.playing_channel:
                redraw_menubar()

        @idle_function
        def my_mouse_right_callback(*args, **kwargs):
            YukiData.right_click_menu.exec(QtGui.QCursor.pos())

        @idle_function
        def my_mouse_left_callback(*args, **kwargs):
            if YukiData.right_click_menu.isVisible():
                YukiData.right_click_menu.hide()
            elif YukiData.settings["hideplaylistbyleftmouseclick"]:
                show_hide_playlist()

        @idle_function
        def my_up_binding_execute(*args, **kwargs):
            if YukiData.settings["mouseswitchchannels"]:
                next_channel()
            else:
                volume = int(
                    YukiData.player.volume + YukiData.settings["volumechangestep"]
                )
                volume = min(volume, 200)
                YukiGUI.volume_slider.setValue(volume)
                mpv_volume_set()

        @idle_function
        def my_down_binding_execute(*args, **kwargs):
            if YukiData.settings["mouseswitchchannels"]:
                prev_channel()
            else:
                volume = int(
                    YukiData.player.volume - YukiData.settings["volumechangestep"]
                )
                volume = max(volume, 0)
                YukiData.time_stop = time.time() + 3
                show_volume(volume)
                YukiGUI.volume_slider.setValue(volume)
                mpv_volume_set()

        dockWidget_controlPanel = ControlPanelDockWidget(win)

        def go_channel(i1):
            pause_state = YukiData.player.pause
            if YukiData.resume_playback:
                YukiData.resume_playback = False
                pause_state = False
            row = win.listWidget.currentRow()
            if row == -1:
                row = YukiData.row0
            next_row = row + i1
            if next_row < 0:
                # Previous page
                if YukiGUI.page_box.value() - 1 == 0:
                    next_row = 0
                else:
                    YukiGUI.page_box.setValue(YukiGUI.page_box.value() - 1)
                    next_row = win.listWidget.count()
            elif next_row > win.listWidget.count() - 1:
                # Next page
                if YukiGUI.page_box.value() + 1 > YukiGUI.page_box.maximum():
                    next_row = row
                else:
                    YukiGUI.page_box.setValue(YukiGUI.page_box.value() + 1)
                    next_row = 0
            next_row = max(next_row, 0)
            next_row = min(next_row, win.listWidget.count() - 1)
            chk_pass = True
            try:
                chk_pass = win.listWidget.item(next_row).text() != _("Nothing found")
            except Exception:
                pass
            if chk_pass:
                win.listWidget.setCurrentRow(next_row)
                itemClicked_event(win.listWidget.currentItem())
            YukiData.player.pause = pause_state

        @idle_function
        def prev_channel(*args, **kwargs):
            go_channel(-1)

        @idle_function
        def next_channel(*args, **kwargs):
            go_channel(1)

        def win_show_raise():
            win.show()
            win.raise_()
            win.setFocus(QtCore.Qt.FocusReason.PopupFocusReason)
            win.activateWindow()

        # MPRIS
        def mpris_set_volume(val):
            YukiGUI.volume_slider.setValue(int(val * 100))
            mpv_volume_set()

        def mpris_seek(val):
            if YukiData.playing_channel:
                YukiData.player.command("seek", val)

        def mpris_set_position(track_id, val):
            if YukiData.mpris_ready and YukiData.mpris_running:
                (
                    playback_status,
                    mpris_trackid,
                    artUrl,
                    player_position,
                ) = get_mpris_metadata()
                if track_id == mpris_trackid:
                    YukiData.player.time_pos = val

        def get_playlist_hash(playlist):
            return hashlib.sha512(playlist["m3u"].encode("utf-8")).hexdigest()

        def get_playlists():
            prefix = "/page/codeberg/liya/yuki_iptv/Playlist/"
            current_playlist = (f"{prefix}Unknown", _("Unknown"), "")
            current_playlist_name = _("Unknown")
            for playlist in YukiData.playlists_saved:
                if (
                    YukiData.playlists_saved[playlist]["m3u"]
                    == YukiData.settings["m3u"]
                ):
                    current_playlist_name = playlist
                    current_playlist = (
                        f"{prefix}"
                        f"{get_playlist_hash(YukiData.playlists_saved[playlist])}",
                        playlist,
                        "",
                    )
                    break
            return (
                current_playlist_name,
                current_playlist,
                [
                    (
                        f"{prefix}{get_playlist_hash(YukiData.playlists_saved[x])}",
                        x,
                        "",
                    )
                    for x in YukiData.playlists_saved
                ],
            )

        @idle_function
        def mpris_select_playlist(*args, **kwargs):
            (
                _current_playlist_name,
                _current_playlist,
                playlists,
            ) = get_playlists()
            for playlist in playlists:
                if playlist[0] == YukiData.mpris_select_playlist:
                    playlist_selected(f"playlist:{playlist[1]}")
                    break

        try:

            def mpris_callback(mpris_data):
                if (
                    mpris_data[0] == "org.mpris.MediaPlayer2"
                    and mpris_data[1] == "Raise"
                ):
                    executeInMainThread(partial(win_show_raise))
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2"
                    and mpris_data[1] == "Quit"
                ):
                    QtCore.QTimer.singleShot(
                        100, lambda: executeInMainThread(partial(app.quit))
                    )
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "Next"
                ):
                    executeInMainThread(partial(next_channel))
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "Previous"
                ):
                    executeInMainThread(partial(prev_channel))
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "Pause"
                ):
                    if not YukiData.player.pause:
                        executeInMainThread(partial(mpv_play_pause))
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "PlayPause"
                ):
                    executeInMainThread(partial(mpv_play_pause))
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "Stop"
                ):
                    executeInMainThread(partial(mpv_stop))
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "Play"
                ):
                    if YukiData.player.pause:
                        executeInMainThread(partial(mpv_play_pause))
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "Seek"
                ):
                    # microseconds to seconds
                    executeInMainThread(partial(mpris_seek, mpris_data[2][0] / 1000000))
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "SetPosition"
                ):
                    track_id = mpris_data[2][0]
                    position = mpris_data[2][1] / 1000000  # microseconds to seconds
                    if track_id != "/page/codeberg/liya/yuki_iptv/Track/NoTrack":
                        executeInMainThread(
                            partial(mpris_set_position, track_id, position)
                        )
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Player"
                    and mpris_data[1] == "OpenUri"
                ):
                    mpris_play_url = mpris_data[2].unpack()[0]
                    executeInMainThread(
                        partial(itemClicked_event, mpris_play_url, mpris_play_url)
                    )
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Playlists"
                    and mpris_data[1] == "ActivatePlaylist"
                ):
                    YukiData.mpris_select_playlist = mpris_data[2].unpack()[0]
                    mpris_select_playlist()
                elif (
                    mpris_data[0] == "org.mpris.MediaPlayer2.Playlists"
                    and mpris_data[1] == "GetPlaylists"
                ):
                    (
                        _current_playlist_name,
                        _current_playlist,
                        playlists,
                    ) = get_playlists()
                    return GLib.Variant.new_tuple(GLib.Variant("a(oss)", playlists))
                elif (
                    mpris_data[0] == "org.freedesktop.DBus.Properties"
                    and mpris_data[1] == "Set"
                ):
                    mpris_data_params = mpris_data[2].unpack()
                    if (
                        mpris_data_params[0] == "org.mpris.MediaPlayer2"
                        and mpris_data_params[1] == "Fullscreen"
                    ):
                        if mpris_data_params[2]:
                            # Enable fullscreen
                            if not YukiData.fullscreen:
                                executeInMainThread(partial(mpv_fullscreen))
                        else:
                            # Disable fullscreen
                            if YukiData.fullscreen:
                                executeInMainThread(partial(mpv_fullscreen))
                    elif (
                        mpris_data_params[0] == "org.mpris.MediaPlayer2.Player"
                        and mpris_data_params[1] == "LoopStatus"
                    ):
                        # Not implemented
                        pass
                    elif (
                        mpris_data_params[0] == "org.mpris.MediaPlayer2.Player"
                        and mpris_data_params[1] == "Rate"
                    ):
                        executeInMainThread(
                            partial(set_playback_speed, mpris_data_params[2])
                        )
                    elif (
                        mpris_data_params[0] == "org.mpris.MediaPlayer2.Player"
                        and mpris_data_params[1] == "Shuffle"
                    ):
                        # Not implemented
                        pass
                    elif (
                        mpris_data_params[0] == "org.mpris.MediaPlayer2.Player"
                        and mpris_data_params[1] == "Volume"
                    ):
                        executeInMainThread(
                            partial(mpris_set_volume, mpris_data_params[2])
                        )
                # Always responding None, even if unknown command called
                # to prevent freezing
                return None

            def get_mpris_metadata():
                # Playback status
                if YukiData.playing_channel:
                    if YukiData.player.pause or YukiData.is_loading:
                        playback_status = "Paused"
                    else:
                        playback_status = "Playing"
                else:
                    playback_status = "Stopped"
                # Metadata
                playing_url_hash = hashlib.sha512(
                    YukiData.playing_url.encode("utf-8")
                ).hexdigest()
                mpris_trackid = (
                    f"/page/codeberg/liya/yuki_iptv/Track/{playing_url_hash}"
                    if YukiData.playing_url
                    else "/page/codeberg/liya/yuki_iptv/Track/NoTrack"
                )
                # Logo
                artUrl = ""
                if YukiData.playing_channel in YukiData.array:
                    if "tvg-logo" in YukiData.array[YukiData.playing_channel]:
                        if YukiData.array[YukiData.playing_channel]["tvg-logo"]:
                            artUrl = YukiData.array[YukiData.playing_channel][
                                "tvg-logo"
                            ]
                # Position in microseconds
                player_position = (
                    YukiData.player.duration * 1000000
                    if YukiData.player.duration
                    else 0
                )
                return playback_status, mpris_trackid, artUrl, player_position

            def get_mpris_options():
                if not YukiData.player:
                    return {
                        "org.mpris.MediaPlayer2": {},
                        "org.mpris.MediaPlayer2.Player": {},
                        "org.mpris.MediaPlayer2.Playlists": {},
                    }
                if YukiData.mpris_ready and YukiData.mpris_running:
                    (
                        playback_status,
                        mpris_trackid,
                        artUrl,
                        player_position,
                    ) = get_mpris_metadata()
                    current_playlist_name, current_playlist, playlists = get_playlists()
                    return {
                        "org.mpris.MediaPlayer2": {
                            "CanQuit": GLib.Variant("b", True),
                            "Fullscreen": GLib.Variant("b", YukiData.fullscreen),
                            "CanSetFullscreen": GLib.Variant("b", True),
                            "CanRaise": GLib.Variant("b", True),
                            "HasTrackList": GLib.Variant("b", False),
                            "Identity": GLib.Variant("s", "yuki-iptv"),
                            "DesktopEntry": GLib.Variant("s", "yuki-iptv"),
                            "SupportedUriSchemes": GLib.Variant(
                                "as",
                                ("file", "http", "https", "rtp", "udp"),
                            ),
                            "SupportedMimeTypes": GLib.Variant(
                                "as",
                                (
                                    "audio/mpeg",
                                    "audio/x-mpeg",
                                    "video/mpeg",
                                    "video/x-mpeg",
                                    "video/x-mpeg-system",
                                    "video/mp4",
                                    "audio/mp4",
                                    "video/x-msvideo",
                                    "video/quicktime",
                                    "application/ogg",
                                    "application/x-ogg",
                                    "video/x-ms-asf",
                                    "video/x-ms-asf-plugin",
                                    "application/x-mplayer2",
                                    "video/x-ms-wmv",
                                    "video/x-google-vlc-plugin",
                                    "audio/x-wav",
                                    "audio/3gpp",
                                    "video/3gpp",
                                    "audio/3gpp2",
                                    "video/3gpp2",
                                    "video/x-flv",
                                    "video/x-matroska",
                                    "audio/x-matroska",
                                    "application/xspf+xml",
                                ),
                            ),
                        },
                        "org.mpris.MediaPlayer2.Player": {
                            "PlaybackStatus": GLib.Variant("s", playback_status),
                            "LoopStatus": GLib.Variant("s", "None"),
                            "Rate": GLib.Variant("d", YukiData.player.speed),
                            "Shuffle": GLib.Variant("b", False),
                            "Metadata": GLib.Variant(
                                "a{sv}",
                                {
                                    "mpris:trackid": GLib.Variant("o", mpris_trackid),
                                    "mpris:artUrl": GLib.Variant("s", artUrl),
                                    "mpris:length": GLib.Variant("x", player_position),
                                    "xesam:url": GLib.Variant(
                                        "s", YukiData.playing_url
                                    ),
                                    "xesam:title": GLib.Variant(
                                        "s", YukiData.playing_channel
                                    ),
                                },
                            ),
                            "Volume": GLib.Variant(
                                "d", float(YukiData.player.volume / 100)
                            ),
                            "Position": GLib.Variant(
                                "x",
                                YukiData.player.time_pos * 1000000
                                if YukiData.player.time_pos
                                else 0,
                            ),
                            "MinimumRate": GLib.Variant("d", 0.01),
                            "MaximumRate": GLib.Variant("d", 5.0),
                            "CanGoNext": GLib.Variant("b", True),
                            "CanGoPrevious": GLib.Variant("b", True),
                            "CanPlay": GLib.Variant("b", True),
                            "CanPause": GLib.Variant("b", True),
                            "CanSeek": GLib.Variant("b", True),
                            "CanControl": GLib.Variant("b", True),
                        },
                        "org.mpris.MediaPlayer2.Playlists": {
                            "PlaylistCount": GLib.Variant("u", len(playlists)),
                            "Orderings": GLib.Variant("as", ("UserDefined",)),
                            "ActivePlaylist": GLib.Variant(
                                "(b(oss))",
                                (
                                    True,
                                    GLib.Variant(
                                        "(oss)",
                                        current_playlist,
                                    ),
                                ),
                            ),
                        },
                    }

            def wait_until():
                while True:
                    if (win.isVisible() and YukiData.player) or YukiData.stopped:
                        return True
                    else:
                        time.sleep(0.1)
                return False

            @async_gui_blocking_function
            def mpris_loop_start(*args, **kwargs):
                wait_until()
                if not YukiData.stopped:
                    try:
                        mpris_owner_bus_id = start_mpris(
                            os.getpid(), mpris_callback, get_mpris_options
                        )
                        YukiData.mpris_ready = True
                        YukiData.mpris_running = True
                        YukiData.mpris_loop.run()
                        Gio.bus_unown_name(mpris_owner_bus_id)
                    except Exception:
                        logger.warning("MPRIS loop error!")
                        logger.warning(traceback.format_exc())

            class MPRISEventHandler:
                def on_metadata(self):
                    if YukiData.mpris_ready and YukiData.mpris_running:
                        (
                            playback_status,
                            mpris_trackid,
                            artUrl,
                            player_position,
                        ) = get_mpris_metadata()
                        executeInMainThread(
                            partial(
                                emit_mpris_change,
                                "org.mpris.MediaPlayer2.Player",
                                {
                                    "PlaybackStatus": GLib.Variant(
                                        "s", playback_status
                                    ),
                                    "Rate": GLib.Variant("d", YukiData.player.speed),
                                    "Metadata": GLib.Variant(
                                        "a{sv}",
                                        {
                                            "mpris:trackid": GLib.Variant(
                                                "o", mpris_trackid
                                            ),
                                            "mpris:artUrl": GLib.Variant("s", artUrl),
                                            "mpris:length": GLib.Variant(
                                                "x", player_position
                                            ),
                                            "xesam:url": GLib.Variant(
                                                "s", YukiData.playing_url
                                            ),
                                            "xesam:title": GLib.Variant(
                                                "s", YukiData.playing_channel
                                            ),
                                        },
                                    ),
                                },
                            )
                        )

                def on_playpause(self):
                    if YukiData.mpris_ready and YukiData.mpris_running:
                        (
                            playback_status,
                            mpris_trackid,
                            artUrl,
                            player_position,
                        ) = get_mpris_metadata()
                        executeInMainThread(
                            partial(
                                emit_mpris_change,
                                "org.mpris.MediaPlayer2.Player",
                                {"PlaybackStatus": GLib.Variant("s", playback_status)},
                            )
                        )

                def on_volume(self):
                    if YukiData.mpris_ready and YukiData.mpris_running:
                        executeInMainThread(
                            partial(
                                emit_mpris_change,
                                "org.mpris.MediaPlayer2.Player",
                                {
                                    "Volume": GLib.Variant(
                                        "d", float(YukiData.player.volume / 100)
                                    )
                                },
                            )
                        )

                def on_fullscreen(self):
                    if YukiData.mpris_ready and YukiData.mpris_running:
                        executeInMainThread(
                            partial(
                                emit_mpris_change,
                                "org.mpris.MediaPlayer2",
                                {"Fullscreen": GLib.Variant("b", YukiData.fullscreen)},
                            )
                        )

            YukiData.event_handler = MPRISEventHandler()
            YukiData.mpris_loop = GLib.MainLoop()
            mpris_loop_start()
        except Exception:
            logger.warning(traceback.format_exc())
            logger.warning("Failed to set up MPRIS!")
        # MPRIS end

        def update_scheduler_programme():
            channel_list_2 = [channel_name for channel_name in YukiData.array_sorted]
            ch_choosed = YukiGUI.choosechannel_ch.currentText()
            YukiGUI.tvguide_sch.clear()
            if ch_choosed in channel_list_2:
                tvguide_got = re.sub(
                    "<[^<]+?>", "", update_tvguide(ch_choosed, True)
                ).split("!@#$%^^&*(")[2:]
                for tvguide_el in tvguide_got:
                    if tvguide_el:
                        YukiGUI.tvguide_sch.addItem(tvguide_el)

        def show_scheduler():
            if YukiGUI.scheduler_win.isVisible():
                YukiGUI.scheduler_win.hide()
            else:
                YukiGUI.choosechannel_ch.clear()
                channel_list = [channel_name for channel_name in YukiData.array_sorted]
                for channel1 in channel_list:
                    YukiGUI.choosechannel_ch.addItem(channel1)
                if YukiData.item_selected in channel_list:
                    YukiGUI.choosechannel_ch.setCurrentIndex(
                        channel_list.index(YukiData.item_selected)
                    )
                YukiGUI.choosechannel_ch.currentIndexChanged.connect(
                    update_scheduler_programme
                )
                update_scheduler_programme()
                moveWindowToCenter(YukiGUI.scheduler_win)
                YukiGUI.scheduler_win.show()

        YukiGUI.btn_playpause.clicked.connect(mpv_play_pause)
        YukiGUI.btn_stop.clicked.connect(mpv_stop)
        YukiGUI.btn_fullscreen.clicked.connect(mpv_fullscreen)
        YukiGUI.btn_record.clicked.connect(do_record)
        YukiGUI.btn_show_scheduler.clicked.connect(show_scheduler)
        YukiGUI.btn_volume.clicked.connect(mpv_mute)
        YukiGUI.volume_slider.valueChanged.connect(mpv_volume_set)
        YukiGUI.btn_screenshot.clicked.connect(do_screenshot)
        YukiGUI.btn_show_archive.clicked.connect(show_archive)
        YukiGUI.btn_multi_epg.clicked.connect(show_multi_epg)
        YukiGUI.btn_tv_guide.clicked.connect(show_tvguide)
        YukiGUI.btn_prev_channel.clicked.connect(prev_channel)
        YukiGUI.btn_next_channel.clicked.connect(next_channel)

        dockWidget_controlPanel.setTitleBarWidget(QtWidgets.QWidget())
        dockWidget_controlPanel.setWidget(YukiGUI.controlpanel_dock_widget)
        dockWidget_controlPanel.setFloating(False)
        dockWidget_controlPanel.setFixedHeight(DOCKWIDGET_CONTROLPANEL_HEIGHT_HIGH)
        dockWidget_controlPanel.setFeatures(
            QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
        )
        win.addDockWidget(
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dockWidget_controlPanel
        )
        dockWidget_controlPanel.setFixedHeight(DOCKWIDGET_CONTROLPANEL_HEIGHT_LOW)

        YukiData.state = QtWidgets.QLabel(win)
        YukiData.state.setStyleSheet("background-color: " + BCOLOR)
        YukiData.state.setFont(YukiGUI.font_12_bold)
        YukiData.state.setWordWrap(True)
        YukiData.state.move(50, 50)
        YukiData.state.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        YukiGUI.set_widget_opacity(YukiData.state, YukiGUI.DEFAULT_OPACITY)

        class Slider(QtWidgets.QSlider):
            def getRewindTime(self):
                s_start = None
                s_stop = None
                s_index = None
                if YukiData.archive_epg:
                    s_start = datetime.datetime.strptime(
                        YukiData.archive_epg[1], "%d.%m.%Y %H:%M:%S"
                    ).timestamp()
                    s_stop = datetime.datetime.strptime(
                        YukiData.archive_epg[2], "%d.%m.%Y %H:%M:%S"
                    ).timestamp()
                    s_index = YukiData.archive_epg[3]
                else:
                    if YukiData.settings["epg"] and YukiData.playing_channel:
                        prog1 = None
                        epg_id = get_epg_id(YukiData.playing_channel)
                        if epg_id:
                            programmes = get_epg_programmes(epg_id)
                            if programmes:
                                prog1 = programmes
                        if prog1:
                            for pr in prog1:
                                if (
                                    time.time() > pr["start"]
                                    and time.time() < pr["stop"]
                                ):
                                    s_start = pr["start"]
                                    # s_stop = pr["stop"]
                                    s_stop = datetime.datetime.now().timestamp()
                                    s_index = prog1.index(pr)
                if not s_start:
                    return None
                return (
                    s_start + (self.value() / 100) * (s_stop - s_start),
                    s_stop,
                    s_index,
                )

            def mouseMoveEvent(self, event1):
                if YukiData.playing_channel:
                    rewind_time = self.getRewindTime()
                    if rewind_time:
                        QtWidgets.QToolTip.showText(
                            self.mapToGlobal(event1.pos()),
                            datetime.datetime.fromtimestamp(rewind_time[0]).strftime(
                                "%H:%M:%S"
                            ),
                        )
                super().mouseMoveEvent(event1)

            def doMouseReleaseEvent(self):
                if YukiData.playing_channel:
                    QtWidgets.QToolTip.hideText()
                    rewind_time = self.getRewindTime()
                    if rewind_time:
                        YukiData.rewind_value = self.value()
                        do_open_archive(
                            "#__rewind__#__archive__"
                            + urllib.parse.quote_plus(
                                json.dumps(
                                    [
                                        YukiData.playing_channel,
                                        datetime.datetime.fromtimestamp(
                                            rewind_time[0]
                                        ).strftime("%d.%m.%Y %H:%M:%S"),
                                        datetime.datetime.fromtimestamp(
                                            rewind_time[1]
                                        ).strftime("%d.%m.%Y %H:%M:%S"),
                                        rewind_time[2],
                                        True,
                                    ]
                                )
                            )
                        )

            def mouseReleaseEvent(self, event1):
                self.doMouseReleaseEvent()
                super().mouseReleaseEvent(event1)

        YukiGUI.create_rewind(Slider)

        def set_text_state(text="", is_previous=False):
            if is_previous:
                text = YukiData.previous_text
            else:
                YukiData.previous_text = text
            if YukiData.gl_is_static:
                br = "    "
                if not text or not YukiData.static_text:
                    br = ""
                text = YukiData.static_text + br + text
            win.update()
            YukiData.state.setText(text)

        def set_text_static(is_static):
            YukiData.static_text = ""
            YukiData.gl_is_static = is_static

        YukiData.state.setTextYuki = set_text_state
        YukiData.state.setStaticYuki = set_text_static
        YukiData.state.hide()

        def getUserAgent():
            try:
                userAgent2 = YukiData.player.user_agent
            except Exception:
                userAgent2 = def_user_agent
            return userAgent2

        def saveLastChannel():
            if YukiData.playing_url and playmode_selector.currentIndex() == 0:
                current_group_0 = 0
                if YukiData.combobox.currentIndex() != 0:
                    try:
                        current_group_0 = groups.index(
                            YukiData.array[YukiData.playing_channel]["tvg-group"]
                        )
                    except Exception:
                        pass
                current_channel_0 = 0
                try:
                    current_channel_0 = win.listWidget.currentRow()
                except Exception:
                    pass
                with open(
                    Path(LOCAL_DIR) / "lastchannels.json", "w", encoding="utf8"
                ) as lastchannels_file1:
                    lastchannels_file1.write(
                        json.dumps(
                            [
                                YukiData.playing_channel,
                                YukiData.playing_url,
                                getUserAgent(),
                                current_group_0,
                                current_channel_0,
                            ]
                        )
                    )
            else:
                if os.path.isfile(Path(LOCAL_DIR) / "lastchannels.json"):
                    os.remove(Path(LOCAL_DIR) / "lastchannels.json")

        def myExitHandler_before():
            try:
                for broken_logo in YukiData.broken_logos:
                    if os.path.isfile(broken_logo):
                        os.remove(broken_logo)
                channel_logos = os.listdir(Path(CACHE_DIR) / "logo")
                for channel_logo in channel_logos:
                    if os.path.isfile(
                        Path(CACHE_DIR) / "logo" / channel_logo
                    ) and channel_logo.endswith(".png"):
                        os.remove(Path(CACHE_DIR) / "logo" / channel_logo)
                if YukiData.epg_pool:
                    try:
                        YukiData.epg_pool.close()
                        YukiData.epg_pool = None
                    except Exception:
                        pass
                uninhibit()
                if YukiData.comboboxIndex != -1:
                    write_option(
                        "comboboxindex",
                        {
                            "m3u": YukiData.settings["m3u"],
                            "index": YukiData.comboboxIndex,
                        },
                    )
                try:
                    if get_first_run():
                        write_option("vf_filters", get_active_vf_filters())
                except Exception:
                    logger.warning(traceback.format_exc())
                try:
                    if not YukiData.first_start:
                        write_option(
                            "window",
                            {
                                "x": win.geometry().x(),
                                "y": win.geometry().y(),
                                "w": win.width(),
                                "h": win.height(),
                            },
                        )
                        if YukiData.settings["panelposition"] == 2:
                            write_option(
                                "separate_playlist",
                                {
                                    "x": dockWidget_playlist.geometry().x(),
                                    "y": dockWidget_playlist.geometry().y(),
                                    "w": dockWidget_playlist.width(),
                                    "h": dockWidget_playlist.height(),
                                },
                            )
                except Exception:
                    logger.warning(traceback.format_exc())
                try:
                    write_option(
                        "compactstate",
                        {
                            "compact_mode": YukiData.compact_mode,
                            "playlist_hidden": YukiData.playlist_hidden,
                            "controlpanel_hidden": YukiData.controlpanel_hidden,
                        },
                    )
                except Exception:
                    logger.warning(traceback.format_exc())
                try:
                    if YukiGUI.save_fullscreenPlaylistWidth:
                        write_option(
                            "fullscreen_playlist_width",
                            YukiGUI.save_fullscreenPlaylistWidth,
                        )
                    if YukiGUI.save_fullscreenPlaylistHeight:
                        write_option(
                            "fullscreen_playlist_height",
                            YukiGUI.save_fullscreenPlaylistHeight,
                        )
                except Exception:
                    logger.warning(traceback.format_exc())
                try:
                    write_option("volume", int(YukiData.volume))
                except Exception:
                    logger.warning(traceback.format_exc())
                save_player_tracks()
                saveLastChannel()
                stop_record()
                for rec_1 in sch_recordings:
                    do_stop_record(rec_1)
                if YukiData.mpris_loop:
                    YukiData.mpris_running = False
                    YukiData.mpris_loop.quit()
                YukiData.stopped = True
                if multiprocessing_manager:
                    multiprocessing_manager.shutdown()
                kill_active_childs()
            except Exception:
                logger.warning(traceback.format_exc())
            exit_handler()

        def myExitHandler():
            myExitHandler_before()
            if not YukiData.do_save_settings:
                sys.exit(0)

        logger.info(f"catchup-days = {get_catchup_days()}")

        sizeGrip = SizeGrip()

        def show_playlist_fullscreen():
            if not YukiGUI.fullscreenPlaylistHeight:
                YukiGUI.fullscreenPlaylistHeight = win.height() - 50

            if YukiData.settings["panelposition"] in (0, 2):
                YukiGUI.playlist_widget.move(
                    win.mapToGlobal(
                        QtCore.QPoint(win.width() - YukiGUI.fullscreenPlaylistWidth, 0)
                    )
                )
            else:
                YukiGUI.playlist_widget.move(win.mapToGlobal(QtCore.QPoint(0, 0)))

            YukiGUI.playlist_widget.resize(
                YukiGUI.fullscreenPlaylistWidth, YukiGUI.fullscreenPlaylistHeight
            )

            if YukiData.settings["enabletransparency"]:
                YukiGUI.playlist_widget.setWindowOpacity(0.75)
            YukiGUI.playlist_widget.setWindowFlags(
                QtCore.Qt.WindowType.CustomizeWindowHint
                | QtCore.Qt.WindowType.FramelessWindowHint
                | QtCore.Qt.WindowType.X11BypassWindowManagerHint
            )
            YukiGUI.pl_layout.addWidget(YukiGUI.widget)
            YukiGUI.pl_layout.addWidget(
                sizeGrip,
                0,
                QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignLeft,
            )
            YukiGUI.playlist_widget.show()

        def hide_playlist_fullscreen():
            YukiGUI.pl_layout.removeWidget(YukiGUI.widget)
            YukiGUI.pl_layout.removeWidget(sizeGrip)
            dockWidget_playlist.setWidget(YukiGUI.widget)
            YukiGUI.playlist_widget.hide()

        def resizeandmove_controlpanel():
            lb2_width = 0
            cur_screen = win.screen() if win else QtWidgets.QApplication.primaryScreen()
            cur_width = cur_screen.availableGeometry().width()
            YukiGUI.controlpanel_widget.setFixedWidth(cur_width)
            for lb2_wdg in YukiGUI.show_lbls_fullscreen:
                if (
                    YukiGUI.controlpanel_layout.indexOf(lb2_wdg) != -1
                    and lb2_wdg.isVisible()
                ):
                    lb2_width += lb2_wdg.width() + 10
            YukiGUI.controlpanel_widget.setFixedWidth(lb2_width + 30)
            p_3 = (
                win.container.frameGeometry().center()
                - QtCore.QRect(
                    QtCore.QPoint(), YukiGUI.controlpanel_widget.sizeHint()
                ).center()
            )
            YukiGUI.controlpanel_widget.move(
                win.mapToGlobal(QtCore.QPoint(p_3.x() - 100, win.height() - 100))
            )

        def show_controlpanel_fullscreen():
            if not YukiData.VOLUME_SLIDER_WIDTH:
                YukiData.VOLUME_SLIDER_WIDTH = YukiGUI.volume_slider.width()
            YukiGUI.volume_slider.setFixedWidth(YukiData.VOLUME_SLIDER_WIDTH)
            if YukiData.settings["enabletransparency"]:
                YukiGUI.controlpanel_widget.setWindowOpacity(0.75)
            if YukiGUI.channelfilter.usePopup:
                YukiGUI.controlpanel_widget.setWindowFlags(
                    QtCore.Qt.WindowType.CustomizeWindowHint
                    | QtCore.Qt.WindowType.FramelessWindowHint
                    | QtCore.Qt.WindowType.X11BypassWindowManagerHint
                    | QtCore.Qt.WindowType.Popup
                )
            else:
                YukiGUI.controlpanel_widget.setWindowFlags(
                    QtCore.Qt.WindowType.CustomizeWindowHint
                    | QtCore.Qt.WindowType.FramelessWindowHint
                    | QtCore.Qt.WindowType.X11BypassWindowManagerHint
                )
            YukiGUI.cp_layout.addWidget(YukiGUI.controlpanel_dock_widget)
            resizeandmove_controlpanel()
            YukiGUI.controlpanel_widget.show()
            resizeandmove_controlpanel()

        def hide_controlpanel_fullscreen():
            if YukiData.VOLUME_SLIDER_WIDTH:
                YukiGUI.volume_slider.setFixedWidth(YukiData.VOLUME_SLIDER_WIDTH)
            YukiGUI.cp_layout.removeWidget(YukiGUI.controlpanel_dock_widget)
            dockWidget_controlPanel.setWidget(YukiGUI.controlpanel_dock_widget)
            YukiGUI.controlpanel_widget.hide()
            YukiGUI.rewind.hide()

        def do_reconnect():
            if (YukiData.playing_channel and not YukiData.is_loading) and (
                YukiData.player.cache_buffering_state == 0
            ):
                logger.info("Reconnecting to stream")
                try:
                    doPlay(*YukiData.do_play_args)
                except Exception:
                    logger.warning("Failed reconnecting to stream - no known URL")
            YukiData.x_conn = None

        def check_connection():
            if YukiData.settings["autoreconnection"]:
                if YukiData.playing_group == 0:
                    if not YukiData.connprinted:
                        YukiData.connprinted = True
                        logger.info("Connection loss detector enabled")
                    try:
                        if (
                            YukiData.playing_channel and not YukiData.is_loading
                        ) and YukiData.player.cache_buffering_state == 0:
                            if not YukiData.x_conn:
                                logger.warning(
                                    "Connection to stream lost, waiting 5 secs..."
                                )
                                YukiData.x_conn = QtCore.QTimer()
                                YukiData.x_conn.timeout.connect(do_reconnect)
                                YukiData.x_conn.start(5000)
                    except Exception:
                        show_exception(
                            "Failed to set connection loss detector!"
                            f"\n{traceback.format_exc()}"
                        )
            else:
                if not YukiData.connprinted:
                    YukiData.connprinted = True
                    logger.info("Connection loss detector disabled")

        # Timers
        def timer_logos_update():
            try:
                if not YukiData.timer_logos_update_lock:
                    YukiData.timer_logos_update_lock = True
                    if YukiData.mp_manager_dict["logos_completed"]:
                        YukiData.mp_manager_dict["logos_completed"] = False
                        redraw_channels()
                    if YukiData.mp_manager_dict["logosmovie_completed"]:
                        YukiData.mp_manager_dict["logosmovie_completed"] = False
                        update_movie_icons()
                    YukiData.timer_logos_update_lock = False
            except BrokenPipeError:
                if not YukiData.is_multiprocessing_failed:
                    YukiData.is_multiprocessing_failed = True
                    show_exception(
                        "multiprocessing Manager failed "
                        "(BrokenPipeError), entering broken state"
                    )
            except Exception:
                if not YukiData.exiting:
                    logger.warning(traceback.format_exc())

        def timer_record_3():
            try:
                activerec_list_value = (
                    YukiGUI.activerec_list.verticalScrollBar().value()
                )
                YukiGUI.activerec_list.clear()
                for sch0 in sch_recordings:
                    counted_time0 = format_seconds(
                        time.time() - sch_recordings[sch0][1]
                    )
                    channel_name0 = sch_recordings[sch0][3]
                    file_name0 = sch_recordings[sch0][2]
                    file_size0 = "WAITING"
                    if os.path.isfile(file_name0):
                        file_size0 = convert_size(os.path.getsize(file_name0))
                    YukiGUI.activerec_list.addItem(
                        channel_name0 + "\n" + counted_time0 + " " + file_size0
                    )
                YukiGUI.activerec_list.verticalScrollBar().setValue(
                    activerec_list_value
                )
                pl_text = "REC / " + _("Scheduler")
                if YukiGUI.activerec_list.count() != 0:
                    YukiData.recViaScheduler = True
                    YukiGUI.lbl2.setText(pl_text)
                    YukiGUI.lbl2.show()
                else:
                    if YukiData.recViaScheduler:
                        logger.info(
                            "Record via scheduler ended, waiting"
                            " for ffmpeg process completion..."
                        )
                        record_post_action()
                    YukiData.recViaScheduler = False
                    if YukiGUI.lbl2.text() == pl_text:
                        YukiGUI.lbl2.hide()
            except Exception:
                if not YukiData.exiting:
                    logger.warning(traceback.format_exc())

        def timer_record_2():
            try:
                if YukiData.is_recording != YukiData.is_recording_old:
                    YukiData.is_recording_old = YukiData.is_recording
                    if YukiData.is_recording:
                        set_record_stop_icon()
                    else:
                        set_record_icon()
                status = _("No planned recordings")
                sch_items = [
                    str(YukiGUI.schedulers.item(i1).text())
                    for i1 in range(YukiGUI.schedulers.count())
                ]
                i3 = -1
                for sch_item in sch_items:
                    i3 += 1
                    status = _("Waiting for record")
                    sch_item = [i2.split(": ")[1] for i2 in sch_item.split("\n") if i2]
                    channel_name_rec = sch_item[0]
                    current_time = time.strftime("%d.%m.%Y %H:%M:%S", time.localtime())
                    start_time_1 = sch_item[1]
                    end_time_1 = sch_item[2]
                    array_name = (
                        str(channel_name_rec)
                        + "_"
                        + str(start_time_1)
                        + "_"
                        + str(end_time_1)
                    )
                    if start_time_1 == current_time:
                        if array_name not in sch_recordings:
                            st_planned = (
                                "Starting planned record"
                                + " (start_time='{}' end_time='{}' channel='{}')"
                            )
                            logger.info(
                                st_planned.format(
                                    start_time_1, end_time_1, channel_name_rec
                                )
                            )
                            sch_recordings[array_name] = do_start_record(array_name)
                            YukiData.ffmpeg_processes.append(sch_recordings[array_name])
                    if end_time_1 == current_time:
                        if array_name in sch_recordings:
                            YukiGUI.schedulers.takeItem(i3)
                            stop_planned = (
                                "Stopping planned record"
                                + " (start_time='{}' end_time='{}' channel='{}')"
                            )
                            logger.info(
                                stop_planned.format(
                                    start_time_1, end_time_1, channel_name_rec
                                )
                            )
                            do_stop_record(array_name)
                            sch_recordings.pop(array_name)
                    if sch_recordings:
                        status = _("Recording")
                YukiGUI.statusrec_lbl.setText("{}: {}".format(_("Status"), status))
            except Exception:
                if not YukiData.exiting:
                    logger.warning(traceback.format_exc())

        def timer_bitrate():
            try:
                if YukiGUI.streaminfo_win.isVisible():
                    if "video" in stream_info.data:
                        stream_info.data["video"][0].setText(
                            stream_info.data["video"][1][_("Average Bitrate")]
                        )
                    if "audio" in stream_info.data:
                        stream_info.data["audio"][0].setText(
                            stream_info.data["audio"][1][_("Average Bitrate")]
                        )
            except Exception:
                if not YukiData.exiting:
                    logger.warning(traceback.format_exc())

        def timer_channels_redraw():
            try:
                YukiData.ic += 0.1
                # redraw every 15 seconds
                if YukiData.ic > (
                    14.9 if not YukiData.mp_manager_dict["logos_inprogress"] else 2.9
                ):
                    YukiData.ic = 0
                    redraw_channels()
                YukiData.ic3 += 0.1
                # redraw every 15 seconds
                if YukiData.ic3 > (
                    14.9
                    if not YukiData.mp_manager_dict["logosmovie_inprogress"]
                    else 2.9
                ):
                    YukiData.ic3 = 0
                    update_movie_icons()
            except BrokenPipeError:
                if not YukiData.is_multiprocessing_failed:
                    YukiData.is_multiprocessing_failed = True
                    show_exception(
                        "multiprocessing Manager failed "
                        "(BrokenPipeError), entering broken state"
                    )
            except Exception:
                if not YukiData.exiting:
                    logger.warning(traceback.format_exc())

        def timer_record():
            try:
                YukiData.ic1 += 0.1
                if YukiData.ic1 > 0.9:
                    YukiData.ic1 = 0
                    # executing every second
                    if YukiData.is_recording:
                        if not YukiData.recording_time:
                            YukiData.recording_time = time.time()
                        record_time = format_seconds(
                            time.time() - YukiData.recording_time
                        )
                        if os.path.isfile(YukiData.record_file):
                            record_size = convert_size(
                                os.path.getsize(YukiData.record_file)
                            )
                            YukiGUI.lbl2.setText(
                                "REC " + record_time + " - " + record_size
                            )
                        else:
                            YukiData.recording_time = time.time()
                            YukiGUI.lbl2.setText(_("Waiting for record"))
                win.update()
                if (time.time() > YukiData.time_stop) and YukiData.time_stop != 0:
                    YukiData.time_stop = 0
                    if not YukiData.gl_is_static:
                        YukiData.state.hide()
                        win.update()
                    else:
                        YukiData.state.setTextYuki("")
            except Exception:
                if not YukiData.exiting:
                    logger.warning(traceback.format_exc())

        def timer_check_tvguide_obsolete():
            try:
                if win.isVisible():
                    check_connection()
                    try:
                        if YukiData.player.video_bitrate:
                            bitrate_arr = [
                                _("bps") + " ",
                                _("kbps"),
                                _("Mbps"),
                                _("Gbps"),
                                _("Tbps"),
                            ]
                            video_bitrate = " - " + str(
                                format_bytes(YukiData.player.video_bitrate, bitrate_arr)
                            )
                        else:
                            video_bitrate = ""
                    except Exception:
                        video_bitrate = ""
                    try:
                        audio_codec = YukiData.player.audio_codec.split(" ")[0].strip()
                    except Exception:
                        audio_codec = "no audio"
                    try:
                        codec = YukiData.player.video_codec.split(" ")[0].strip()
                        width = YukiData.player.width
                        height = YukiData.player.height
                    except Exception:
                        codec = "png"
                        width = 800
                        height = 600
                    if YukiData.player.avsync:
                        avsync = str(round(YukiData.player.avsync, 2))
                        deavsync = round(YukiData.player.avsync, 2)
                        if deavsync < 0:
                            deavsync = deavsync * -1
                        if deavsync > 0.999:
                            avsync = f"<span style='color: #B58B00;'>{avsync}</span>"
                    else:
                        avsync = "0.0"
                    if (
                        not (codec.lower() == "png" and width == 800 and height == 600)
                    ) and (width and height):
                        if YukiData.settings["hidebitrateinfo"]:
                            YukiGUI.label_video_data.setText("")
                            YukiGUI.label_avsync.setText("")
                        else:
                            YukiGUI.label_video_data.setText(
                                f"  {width}x{height}"
                                f" - {codec} / {audio_codec}{video_bitrate} -"
                            )
                            YukiGUI.label_avsync.setText(f"A-V {avsync}")
                        if loading.text() == _("Loading..."):
                            hideLoading()
                    else:
                        YukiGUI.label_video_data.setText("")
                        YukiGUI.label_avsync.setText("")
                    YukiData.ic2 += 0.1
                    if YukiData.ic2 > 29.9:
                        YukiData.ic2 = 0
                        if (
                            YukiData.settings["epg"]
                            and not YukiData.epg_pool_running
                            and not YukiData.epg_failed
                        ):
                            is_actual = True
                            if YukiData.epg_update_date != 0:
                                is_actual = (
                                    time.time() - YukiData.epg_update_date
                                ) < 60 * 60 * 24 * 2  # 2 days
                            if not check_programmes_actual() or not is_actual:
                                logger.info("EPG is outdated, updating it...")
                                purge_epg_cache()
                                epg_update()
            except Exception:
                if not YukiData.exiting:
                    logger.warning(traceback.format_exc())

        def timer_tvguide_progress():
            try:
                if not YukiData.thread_tvguide_progress_lock:
                    YukiData.thread_tvguide_progress_lock = True
                    try:
                        if YukiData.epg_pool_running:
                            if (
                                "epg_progress" in YukiData.mp_manager_dict
                                and YukiData.mp_manager_dict["epg_progress"]
                            ):
                                YukiData.static_text = YukiData.mp_manager_dict[
                                    "epg_progress"
                                ]
                                YukiData.state.setTextYuki(is_previous=True)
                    except Exception:
                        pass
                    YukiData.thread_tvguide_progress_lock = False
            except BrokenPipeError:
                if not YukiData.is_multiprocessing_failed:
                    YukiData.is_multiprocessing_failed = True
                    show_exception(
                        "multiprocessing Manager failed "
                        "(BrokenPipeError), entering broken state"
                    )
            except Exception:
                if not YukiData.exiting:
                    logger.warning(traceback.format_exc())

        def timer_update_time():
            try:
                YukiGUI.scheduler_clock.setText(get_current_time())
            except Exception:
                if not YukiData.exiting:
                    logger.warning(traceback.format_exc())

        def timer_osc():
            try:
                if (
                    "osc" not in options
                    or "no" in str(options["osc"]).lower().strip()
                    or "false" in str(options["osc"]).lower().strip()
                    or not options["osc"]
                ):
                    if not YukiData.osc_info_shown:
                        YukiData.osc_info_shown = True
                        logger.info("libmpv OSC disabled")
                    set_mpv_osc(False)
                else:
                    if not YukiData.osc_info_shown:
                        YukiData.osc_info_shown = True
                        logger.info("libmpv OSC enabled")
                    if win.isVisible():
                        if YukiData.playing_url:
                            set_mpv_osc(True)
                        else:
                            set_mpv_osc(False)
            except Exception:
                if not YukiData.exiting:
                    logger.warning(traceback.format_exc())

        YukiData.prev_cursor = QtGui.QCursor.pos()

        def timer_cursor():
            try:
                show_cursor = False
                cursor_offset = (
                    QtGui.QCursor.pos().x()
                    - YukiData.prev_cursor.x()
                    + QtGui.QCursor.pos().y()
                    - YukiData.prev_cursor.y()
                )
                if cursor_offset < 0:
                    cursor_offset = cursor_offset * -1
                if cursor_offset > 5:
                    YukiData.prev_cursor = QtGui.QCursor.pos()
                    if (time.time() - YukiData.last_cursor_moved) > 0.3:
                        YukiData.last_cursor_moved = time.time()
                        YukiData.last_cursor_time = time.time() + 1
                        show_cursor = True
                show_cursor_really = True
                if not show_cursor:
                    show_cursor_really = time.time() < YukiData.last_cursor_time
                if YukiData.fullscreen:
                    try:
                        if show_cursor_really:
                            win.container.unsetCursor()
                        else:
                            win.container.setCursor(QtCore.Qt.CursorShape.BlankCursor)
                    except Exception:
                        pass
                else:
                    try:
                        win.container.unsetCursor()
                    except Exception:
                        pass
            except Exception:
                if not YukiData.exiting:
                    logger.warning(traceback.format_exc())

        def timer_after_record():
            try:
                cur_recording = False
                if not YukiGUI.lbl2.isVisible():
                    if "REC / " not in YukiGUI.lbl2.text():
                        cur_recording = is_ffmpeg_recording() is False
                    else:
                        cur_recording = is_recording_func() is not True
                    if cur_recording:
                        YukiGUI.showLoading2()
                    else:
                        YukiGUI.hideLoading2()
            except Exception:
                if not YukiData.exiting:
                    logger.warning(traceback.format_exc())

        def timer_shortcuts():
            try:
                if not YukiData.fullscreen:
                    menubar_new_st = win.menuBar().isVisible()
                    if menubar_new_st != YukiData.menubar_state:
                        YukiData.menubar_state = menubar_new_st
                        if YukiData.menubar_state:
                            setShortcutState(False)
                        else:
                            setShortcutState(True)
            except Exception:
                if not YukiData.exiting:
                    logger.warning(traceback.format_exc())

        def timer_mouse():
            try:
                if win.isVisible():
                    if (
                        YukiData.state.isVisible()
                        and YukiData.state.text().startswith(_("Volume"))
                        and not is_show_volume()
                    ):
                        YukiData.state.hide()
                    YukiGUI.label_volume.setText(f"{int(YukiData.player.volume)}%")
                    if YukiData.settings["panelposition"] != 2:
                        dockWidget_playlist.setFixedWidth(DOCKWIDGET_PLAYLIST_WIDTH)
                    if YukiData.fullscreen:
                        # Check cursor inside window
                        cur_pos = QtGui.QCursor.pos()
                        is_inside_window = (
                            (
                                cur_pos.x() > win.pos().x() - 1
                                and cur_pos.x() < (win.pos().x() + win.width())
                            )
                            and (
                                cur_pos.y() > win.pos().y() - 1
                                and cur_pos.y() < (win.pos().y() + win.height())
                            )
                            and (win.hasFocus() or YukiData.dockWidget_playlistVisible)
                        )
                        # Playlist
                        if YukiData.settings["showplaylistmouse"]:
                            cursor_x = win.container.mapFromGlobal(
                                QtGui.QCursor.pos()
                            ).x()
                            win_width = win.width()
                            if YukiData.settings["panelposition"] in (0, 2):
                                is_cursor_x = cursor_x > win_width - (
                                    YukiGUI.fullscreenPlaylistWidth + 10
                                )
                            else:
                                is_cursor_x = cursor_x < (
                                    YukiGUI.fullscreenPlaylistWidth + 10
                                )
                            if (
                                is_cursor_x
                                and cursor_x < win_width
                                and is_inside_window
                            ) or YukiGUI.playlistFullscreenIsResized:
                                if not YukiData.dockWidget_playlistVisible:
                                    YukiData.dockWidget_playlistVisible = True
                                    show_playlist_fullscreen()
                            else:
                                YukiData.dockWidget_playlistVisible = False
                                hide_playlist_fullscreen()
                        # Control panel
                        if YukiData.settings["showcontrolsmouse"]:
                            cursor_y = win.container.mapFromGlobal(
                                QtGui.QCursor.pos()
                            ).y()
                            win_height = win.height()
                            is_cursor_y = cursor_y > win_height - (
                                dockWidget_controlPanel.height() + 250
                            )
                            if (
                                is_cursor_y
                                and cursor_y < win_height
                                and is_inside_window
                            ):
                                if not YukiData.dockWidget_controlPanelVisible:
                                    YukiData.dockWidget_controlPanelVisible = True
                                    show_controlpanel_fullscreen()
                            else:
                                YukiData.dockWidget_controlPanelVisible = False
                                hide_controlpanel_fullscreen()
                    if YukiData.settings["rewindenable"]:
                        # Check cursor inside window
                        cur_pos = QtGui.QCursor.pos()
                        is_inside_window = (
                            cur_pos.x() > win.pos().x() - 1
                            and cur_pos.x() < (win.pos().x() + win.width())
                        ) and (
                            cur_pos.y() > win.pos().y() - 1
                            and cur_pos.y() < (win.pos().y() + win.height())
                        )
                        # Rewind
                        cursor_y = win.container.mapFromGlobal(QtGui.QCursor.pos()).y()
                        win_height = win.height()
                        is_cursor_y = cursor_y > win_height - (
                            dockWidget_controlPanel.height() + 250
                        )
                        if (
                            is_cursor_y
                            and cursor_y < win_height
                            and is_inside_window
                            and YukiData.playing_channel
                            and YukiData.playing_channel in YukiData.array
                            and YukiData.current_prog1
                            and not YukiData.check_playlist_visible
                            and not YukiData.check_controlpanel_visible
                        ):
                            if not YukiData.rewindWidgetVisible:
                                YukiData.rewindWidgetVisible = True
                                win.resize_rewind()
                                YukiGUI.rewind.show()
                        else:
                            YukiData.rewindWidgetVisible = False
                            if YukiGUI.rewind.isVisible():
                                if YukiData.rewind_value:
                                    if (
                                        YukiData.rewind_value
                                        != YukiGUI.rewind_slider.value()
                                    ):
                                        YukiGUI.rewind_slider.doMouseReleaseEvent()
                                YukiGUI.rewind.hide()
            except Exception:
                if not YukiData.exiting:
                    logger.warning(traceback.format_exc())

        def timer_dockwidget_controlpanel_resize():
            try:
                if YukiGUI.start_label.text() and YukiGUI.start_label.isVisible():
                    if (
                        dockWidget_controlPanel.height()
                        != DOCKWIDGET_CONTROLPANEL_HEIGHT_HIGH
                    ):
                        dockWidget_controlPanel.setFixedHeight(
                            DOCKWIDGET_CONTROLPANEL_HEIGHT_HIGH
                        )
                else:
                    if (
                        dockWidget_controlPanel.height()
                        != DOCKWIDGET_CONTROLPANEL_HEIGHT_LOW
                    ):
                        dockWidget_controlPanel.setFixedHeight(
                            DOCKWIDGET_CONTROLPANEL_HEIGHT_LOW
                        )
            except Exception:
                if not YukiData.exiting:
                    logger.warning(traceback.format_exc())

        @idle_function
        def show_hide_playlist(*args, **kwargs):
            if not YukiData.fullscreen:
                if dockWidget_playlist.isVisible():
                    YukiData.playlist_hidden = True
                    dockWidget_playlist.hide()
                else:
                    YukiData.playlist_hidden = False
                    dockWidget_playlist.show()

        def lowpanel_ch():
            if dockWidget_controlPanel.isVisible():
                YukiData.controlpanel_hidden = True
                dockWidget_controlPanel.hide()
            else:
                YukiData.controlpanel_hidden = False
                dockWidget_controlPanel.show()

        def set_playback_speed(spd):
            try:
                logger.info(f"Set speed to {spd}")
                YukiData.player.speed = spd
                try:
                    if YukiData.event_handler:
                        YukiData.event_handler.on_metadata()
                except Exception:
                    show_exception(traceback.format_exc())
            except Exception:
                show_exception(f"set_playback_speed failed\n{traceback.format_exc()}")

        def mpv_seek(secs):
            try:
                if YukiData.playing_channel:
                    logger.info(f"Seeking to {secs} seconds")
                    YukiData.player.command("seek", secs)
            except Exception:
                show_exception(f"mpv_seek failed\n{traceback.format_exc()}")

        def mpv_frame_step():
            logger.info("frame-step")
            YukiData.player.command("frame-step")

        def mpv_frame_back_step():
            logger.info("frame-back-step")
            YukiData.player.command("frame-back-step")

        funcs = {
            "show_sort": show_sort,
            "key_t": show_hide_playlist,
            "esc_handler": esc_handler,
            "mpv_fullscreen": mpv_fullscreen,
            "mpv_fullscreen_2": mpv_fullscreen,
            "open_stream_info": open_stream_info,
            "mpv_mute": mpv_mute,
            "key_quit": app.quit,
            "mpv_play": mpv_play_pause,
            "mpv_stop": mpv_stop,
            "do_screenshot": do_screenshot,
            "show_tvguide": show_tvguide,
            "do_record": do_record,
            "prev_channel": prev_channel,
            "next_channel": next_channel,
            "(lambda: my_up_binding())": (lambda: my_up_binding_execute()),
            "(lambda: my_down_binding())": (lambda: my_down_binding_execute()),
            "show_timeshift": show_archive,
            "show_scheduler": show_scheduler,
            "showhideeverything": showhideeverything,
            "show_settings": lambda: YukiGUI.show_settings(),
            "(lambda: set_playback_speed(1.00))": (lambda: set_playback_speed(1.00)),
            "app.quit": app.quit,
            "show_playlists": show_playlists,
            "reload_playlist": reload_playlist,
            "force_update_epg": force_update_epg_act,
            "main_channel_settings": main_channel_settings,
            "show_playlist_editor": YukiGUI.show_playlist_editor,
            "my_down_binding_execute": my_down_binding_execute,
            "my_up_binding_execute": my_up_binding_execute,
            "(lambda: mpv_seek(-10))": (lambda: mpv_seek(-10)),
            "(lambda: mpv_seek(10))": (lambda: mpv_seek(10)),
            "(lambda: mpv_seek(-60))": (lambda: mpv_seek(-60)),
            "(lambda: mpv_seek(60))": (lambda: mpv_seek(60)),
            "(lambda: mpv_seek(-600))": (lambda: mpv_seek(-600)),
            "(lambda: mpv_seek(600))": (lambda: mpv_seek(600)),
            "lowpanel_ch_1": lowpanel_ch_1,
            "show_tvguide_2": show_tvguide_2,
            "show_multi_epg": show_multi_epg,
            # INTERNAL
            "do_record_1_INTERNAL": do_record,
            "mpv_mute_1_INTERNAL": mpv_mute,
            "mpv_play_1_INTERNAL": mpv_play_pause,
            "mpv_play_2_INTERNAL": mpv_play_pause,
            "mpv_play_3_INTERNAL": mpv_play_pause,
            "mpv_play_4_INTERNAL": mpv_play_pause,
            "mpv_stop_1_INTERNAL": mpv_stop,
            "mpv_stop_2_INTERNAL": mpv_stop,
            "next_channel_1_INTERNAL": next_channel,
            "prev_channel_1_INTERNAL": prev_channel,
            "(lambda: my_up_binding())_INTERNAL": (lambda: my_up_binding_execute()),
            "(lambda: my_down_binding())_INTERNAL": (lambda: my_down_binding_execute()),
            "mpv_frame_step": mpv_frame_step,
            "mpv_frame_back_step": mpv_frame_back_step,
        }

        if os.path.isfile(Path(LOCAL_DIR) / "shortcuts.json"):
            try:
                with open(
                    Path(LOCAL_DIR) / "shortcuts.json", encoding="utf8"
                ) as shortcuts_file_tmp:
                    shortcuts_tmp = json.loads(shortcuts_file_tmp.read())[
                        "current_profile"
                    ]["keys"]
                    YukiData.main_shortcuts = shortcuts_tmp
                    for shortcut_name2 in main_shortcuts_default.copy():
                        if shortcut_name2 not in YukiData.main_shortcuts:
                            logger.warning(
                                f"Shortcut '{shortcut_name2}' not "
                                "found in shortcuts.json, using default"
                            )
                            YukiData.main_shortcuts[
                                shortcut_name2
                            ] = main_shortcuts_default.copy()[shortcut_name2]
                    logger.info("shortcuts.json found, using it as shortcut settings")
            except Exception:
                logger.warning("failed to read shortcuts.json, using default shortcuts")
                logger.warning(traceback.format_exc())
                YukiData.main_shortcuts = main_shortcuts_default.copy()
        else:
            logger.info("No shortcuts.json found, using default shortcuts")
            YukiData.main_shortcuts = main_shortcuts_default.copy()

        seq = get_seq()

        def setShortcutState(st1):
            YukiData.shortcuts_state = st1
            for shortcut_arr in shortcuts:
                for shortcut in shortcuts[shortcut_arr]:
                    if shortcut.key() in seq:
                        shortcut.setEnabled(st1)

        def reload_shortcuts():
            for shortcut_1 in shortcuts:
                if not shortcut_1.endswith("_INTERNAL"):
                    sc_new_shortcut = QtGui.QKeySequence(
                        YukiData.main_shortcuts[shortcut_1]
                    )
                    for shortcut_2 in shortcuts[shortcut_1]:
                        shortcut_2.setKey(sc_new_shortcut)
            reload_menubar_shortcuts()

        all_shortcuts = YukiData.main_shortcuts.copy()
        all_shortcuts.update(main_shortcuts_internal)
        for kbd in all_shortcuts:
            if kbd in funcs:
                shortcuts[kbd] = [
                    # Main window
                    QtGui.QShortcut(
                        QtGui.QKeySequence(all_shortcuts[kbd]),
                        win,
                        activated=funcs[kbd],
                    ),
                    # Control panel widget
                    QtGui.QShortcut(
                        QtGui.QKeySequence(all_shortcuts[kbd]),
                        YukiGUI.controlpanel_widget,
                        activated=funcs[kbd],
                    ),
                    # Playlist widget
                    QtGui.QShortcut(
                        QtGui.QKeySequence(all_shortcuts[kbd]),
                        YukiGUI.playlist_widget,
                        activated=funcs[kbd],
                    ),
                ]
            else:
                logger.warning(f"Unknown shortcut '{kbd}'!")
                if kbd in YukiData.main_shortcuts:
                    YukiData.main_shortcuts.pop(kbd)
        all_shortcuts = False

        setShortcutState(False)

        app.aboutToQuit.connect(myExitHandler)

        vol_remembered = 100
        volume_option = read_option("volume")
        if volume_option is not None:
            vol_remembered = int(volume_option)
            YukiData.volume = vol_remembered
        YukiData.firstVolRun = False

        def restore_compact_state():
            try:
                compactstate = read_option("compactstate")
                if compactstate:
                    if compactstate["compact_mode"]:
                        showhideeverything()
                    else:
                        if compactstate["playlist_hidden"]:
                            show_hide_playlist()
                        if compactstate["controlpanel_hidden"]:
                            lowpanel_ch()
            except Exception:
                logger.warning(traceback.format_exc())

        @async_gui_blocking_function
        def epg_update(*args, **kwargs):
            if YukiData.settings["epg"]:
                if YukiData.epg_pool_running:
                    logger.info("EPG already updating")
                else:
                    if YukiData.first_boot:
                        YukiData.first_boot = False
                        if YukiData.settings["donotupdateepg"]:
                            logger.info("EPG update at boot disabled")
                            return

                    YukiData.epg_update_date = time.time()
                    YukiData.epg_pool_running = True
                    thread_tvguide_update_start()

                    YukiData.epg_pool = get_context("spawn").Pool(1)
                    (
                        epg_failed,
                        epg_outdated,
                        YukiData.epg_array,
                    ) = YukiData.epg_pool.apply(
                        epg_worker,
                        (
                            YukiData.settings,
                            YukiData.mp_manager_dict,
                        ),
                    )

                    YukiData.epg_pool.close()
                    YukiData.epg_pool = None

                    if epg_outdated:
                        thread_tvguide_update_outdated()
                    elif epg_failed:
                        thread_tvguide_update_error()
                    else:
                        thread_tvguide_update_end()
                    YukiData.epg_failed = epg_outdated or epg_failed
                    YukiData.epg_pool_running = False

                    redraw_channels()

        if YukiData.settings["m3u"] and m3u_exists:
            win.show()
            init_mpv_player()
            win.raise_()
            win.setFocus(QtCore.Qt.FocusReason.PopupFocusReason)
            win.activateWindow()
            try:
                combobox_index = read_option("comboboxindex")
                if combobox_index:
                    if combobox_index["m3u"] == YukiData.settings["m3u"]:
                        if combobox_index["index"] < YukiData.combobox.count():
                            YukiData.combobox.setCurrentIndex(combobox_index["index"])
            except Exception:
                logger.warning(traceback.format_exc())

            screensaver_register()

            def after_mpv_init():
                if YukiData.needs_resize:
                    logger.info("Fix window size")
                    win.resize(WINDOW_SIZE[0], WINDOW_SIZE[1])
                    qr = win.frameGeometry()
                    qr.moveCenter(
                        QtGui.QScreen.availableGeometry(
                            QtWidgets.QApplication.primaryScreen()
                        ).center()
                    )
                    win.move(qr.topLeft())
                if not playLastChannel():
                    logger.info("Show splash")
                    mpv_override_play(str(YukiData.icons_folder / "main.png"))
                    YukiData.player.pause = True
                else:
                    logger.info("Playing last channel, splash turned off")
                restore_compact_state()

            after_mpv_init()

            YukiGUI.fullscreenPlaylistWidth = read_option("fullscreen_playlist_width")
            YukiGUI.fullscreenPlaylistHeight = read_option("fullscreen_playlist_height")

            if not YukiGUI.fullscreenPlaylistWidth:
                YukiGUI.fullscreenPlaylistWidth = DOCKWIDGET_PLAYLIST_WIDTH

            YukiData.ic, YukiData.ic1, YukiData.ic2, YukiData.ic3 = 0, 0, 0, 0
            timers_array = {}
            timers = {
                timer_shortcuts: 25,
                timer_mouse: 50,
                timer_cursor: 50,
                timer_channels_redraw: 100,
                timer_record: 100,
                timer_record_2: 1000,
                timer_record_3: 1000,
                timer_osc: 100,
                timer_check_tvguide_obsolete: 100,
                timer_tvguide_progress: 100,
                timer_update_time: 1000,
                timer_logos_update: 1000,
                timer_after_record: 50,
                timer_bitrate: 5000,
                timer_dockwidget_controlpanel_resize: 50,
            }
            for timer in timers:
                timers_array[timer] = QtCore.QTimer()
                timers_array[timer].timeout.connect(timer)
                timers_array[timer].start(timers[timer])

            epg_update()
        else:
            YukiData.first_start = True
            show_playlists()
            moveWindowToCenter(gui_playlists_data.playlists_win)
            gui_playlists_data.playlists_win.show()
            gui_playlists_data.playlists_win.raise_()
            gui_playlists_data.playlists_win.setFocus(
                QtCore.Qt.FocusReason.PopupFocusReason
            )
            gui_playlists_data.playlists_win.activateWindow()

        app_exit_code = app.exec()
        if YukiData.do_save_settings:
            start_args = sys.argv
            if "python" not in sys.executable:
                start_args.pop(0)
            subprocess.Popen([sys.executable] + start_args)
        sys.exit(app_exit_code)
    except Exception:
        show_exception(traceback.format_exc())
        try:
            myExitHandler_before()
        except Exception:
            pass
        kill_active_childs()
        kill_process_childs(os.getpid(), signal.SIGKILL)
        try:
            app.quit()
        except Exception:
            pass
        sys.exit(1)
