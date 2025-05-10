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
import time
import logging
import traceback
import webbrowser
from PyQt6 import QtGui
from functools import partial
from yuki_iptv.misc import YukiData
from yuki_iptv.i18n import _, ngettext
from yuki_iptv.options import read_option
from yuki_iptv.exception_handler import show_exception
from yuki_iptv.threads import idle_function, async_gui_blocking_function

logger = logging.getLogger(__name__)


class YukiMenubarData:
    menubar_ready = False
    first_run = False
    menubars = {}
    data = {}
    cur_vf_filters = []
    keyboard_sequences = []
    str_offset = " " * 44


def yuki_mpv_seek(secs):
    logger.info(f"Seeking to {secs} seconds")
    YukiMenubarData.player.command("seek", secs)


def yuki_mpv_set_speed(speed):
    logger.info(f"Set speed to {speed}")
    YukiMenubarData.player.speed = speed


def yuki_trackset(track, track_type):
    YukiMenubarData.yuki_track_set(track, track_type)
    YukiMenubarData.redraw_menubar()


def send_mpv_command(name, act, cmd):
    logger.info(f'Sending mpv command: "{name} {act} \\"{cmd}\\""')
    YukiMenubarData.player.command(name, act, cmd)


def get_active_vf_filters():
    return YukiMenubarData.cur_vf_filters


def apply_vf_filter(vf_filter, checkbox):
    try:
        if checkbox.isChecked():
            send_mpv_command(
                vf_filter.split("::::::::")[0], "add", vf_filter.split("::::::::")[1]
            )
            YukiMenubarData.cur_vf_filters.append(vf_filter)
        else:
            send_mpv_command(
                vf_filter.split("::::::::")[0], "remove", vf_filter.split("::::::::")[1]
            )
            YukiMenubarData.cur_vf_filters.remove(vf_filter)
    except Exception:
        exc = traceback.format_exc()
        logger.error(f"Error in vf-filter apply: {exc}")
        show_exception(exc, _("Error applying filters"))


def get_seq():
    return YukiMenubarData.keyboard_sequences


def qkeysequence(seq):
    sequence = QtGui.QKeySequence(seq)
    YukiMenubarData.keyboard_sequences.append(sequence)
    return sequence


def kbd(shortcut_name):
    return qkeysequence(YukiData.main_shortcuts[shortcut_name])


def reload_menubar_shortcuts():
    YukiMenubarData.playlists.setShortcut(kbd("show_playlists"))
    YukiMenubarData.reloadPlaylist.setShortcut(kbd("reload_playlist"))
    YukiMenubarData.m3uEditor.setShortcut(kbd("show_playlist_editor"))
    YukiMenubarData.exitAction.setShortcut(kbd("app.quit"))
    YukiMenubarData.playpause.setShortcut(kbd("mpv_play"))
    YukiMenubarData.stop.setShortcut(kbd("mpv_stop"))
    YukiMenubarData.frame_step.setShortcut(kbd("mpv_frame_step"))
    YukiMenubarData.frame_back_step.setShortcut(kbd("mpv_frame_back_step"))
    YukiMenubarData.normalSpeed.setShortcut(kbd("(lambda: set_playback_speed(1.00))"))
    YukiMenubarData.prevchannel.setShortcut(kbd("prev_channel"))
    YukiMenubarData.nextchannel.setShortcut(kbd("next_channel"))
    YukiMenubarData.fullscreen.setShortcut(kbd("mpv_fullscreen"))
    YukiMenubarData.compactmode.setShortcut(kbd("showhideeverything"))
    YukiMenubarData.csforchannel.setShortcut(kbd("main_channel_settings"))
    YukiMenubarData.screenshot.setShortcut(kbd("do_screenshot"))
    YukiMenubarData.muteAction.setShortcut(kbd("mpv_mute"))
    YukiMenubarData.volumeMinus.setShortcut(kbd("my_down_binding_execute"))
    YukiMenubarData.volumePlus.setShortcut(kbd("my_up_binding_execute"))
    YukiMenubarData.showhideplaylistAction.setShortcut(kbd("key_t"))
    YukiMenubarData.showhidectrlpanelAction.setShortcut(kbd("lowpanel_ch_1"))
    YukiMenubarData.streaminformationAction.setShortcut(kbd("open_stream_info"))
    YukiMenubarData.showepgAction.setShortcut(kbd("show_tvguide_2"))
    YukiMenubarData.forceupdateepgAction.setShortcut(kbd("force_update_epg"))
    YukiMenubarData.sortAction.setShortcut(kbd("show_sort"))
    YukiMenubarData.settingsAction.setShortcut(kbd("show_settings"))
    sec_keys_1 = [
        kbd("(lambda: mpv_seek(-10))"),
        kbd("(lambda: mpv_seek(10))"),
        kbd("(lambda: mpv_seek(-60))"),
        kbd("(lambda: mpv_seek(60))"),
        kbd("(lambda: mpv_seek(-600))"),
        kbd("(lambda: mpv_seek(600))"),
    ]
    i = -1
    for sec in YukiMenubarData.secs:
        i += 1
        sec.setShortcut(qkeysequence(sec_keys_1[i]))


def init_menubar(data):
    # File
    YukiMenubarData.playlists = QtGui.QAction(_("&Playlists"), data)
    YukiMenubarData.playlists.setShortcut(kbd("show_playlists"))
    YukiMenubarData.playlists.triggered.connect(
        lambda: YukiMenubarData.show_playlists()
    )

    YukiMenubarData.reloadPlaylist = QtGui.QAction(_("&Update current playlist"), data)
    YukiMenubarData.reloadPlaylist.setShortcut(kbd("reload_playlist"))
    YukiMenubarData.reloadPlaylist.triggered.connect(
        lambda: YukiMenubarData.reload_playlist()
    )

    YukiMenubarData.m3uEditor = QtGui.QAction(
        _("P&laylist editor") + YukiMenubarData.str_offset, data
    )
    YukiMenubarData.m3uEditor.setShortcut(kbd("show_playlist_editor"))
    YukiMenubarData.m3uEditor.triggered.connect(
        lambda: YukiData.YukiGUI.show_playlist_editor()
    )

    YukiMenubarData.exitAction = QtGui.QAction(_("&Exit"), data)
    YukiMenubarData.exitAction.setShortcut(kbd("app.quit"))
    YukiMenubarData.exitAction.triggered.connect(lambda: YukiMenubarData.app_quit())

    # Play
    YukiMenubarData.playpause = QtGui.QAction(_("&Play / Pause"), data)
    YukiMenubarData.playpause.setShortcut(kbd("mpv_play"))
    YukiMenubarData.playpause.triggered.connect(lambda: YukiMenubarData.mpv_play())

    YukiMenubarData.stop = QtGui.QAction(_("&Stop"), data)
    YukiMenubarData.stop.setShortcut(kbd("mpv_stop"))
    YukiMenubarData.stop.triggered.connect(lambda: YukiMenubarData.mpv_stop())

    YukiMenubarData.frame_step = QtGui.QAction(_("&Frame step"), data)
    YukiMenubarData.frame_step.setShortcut(kbd("mpv_frame_step"))
    YukiMenubarData.frame_step.triggered.connect(
        lambda: YukiMenubarData.mpv_frame_step()
    )

    YukiMenubarData.frame_back_step = QtGui.QAction(_("Fra&me back step"), data)
    YukiMenubarData.frame_back_step.setShortcut(kbd("mpv_frame_back_step"))
    YukiMenubarData.frame_back_step.triggered.connect(
        lambda: YukiMenubarData.mpv_frame_back_step()
    )

    YukiMenubarData.secs = []
    sec_keys = [
        kbd("(lambda: mpv_seek(-10))"),
        kbd("(lambda: mpv_seek(10))"),
        kbd("(lambda: mpv_seek(-60))"),
        kbd("(lambda: mpv_seek(60))"),
        kbd("(lambda: mpv_seek(-600))"),
        kbd("(lambda: mpv_seek(600))"),
    ]
    sec_i18n = [
        ngettext("-%d second", "-%d seconds", 10) % 10,
        ngettext("+%d second", "+%d seconds", 10) % 10,
        ngettext("-%d minute", "-%d minutes", 1) % 1,
        ngettext("+%d minute", "+%d minutes", 1) % 1,
        ngettext("-%d minute", "-%d minutes", 10) % 10,
        ngettext("+%d minute", "+%d minutes", 10) % 10,
    ]
    sec_i = -1
    for i in ((10, "seconds", 10), (1, "minutes", 60), (10, "minutes", 600)):
        for sign in ("-", "+"):
            sec_i += 1
            sec = QtGui.QAction(sec_i18n[sec_i], data)
            sec.setShortcut(qkeysequence(sec_keys[sec_i]))
            sec.triggered.connect(
                partial(yuki_mpv_seek, i[2] * -1 if sign == "-" else i[2])
            )
            YukiMenubarData.secs.append(sec)

    YukiMenubarData.normalSpeed = QtGui.QAction(_("&Normal speed"), data)
    YukiMenubarData.normalSpeed.triggered.connect(partial(yuki_mpv_set_speed, 1.00))
    YukiMenubarData.normalSpeed.setShortcut(kbd("(lambda: set_playback_speed(1.00))"))

    YukiMenubarData.speeds = []

    for speed in (0.25, 0.5, 0.75, 1.25, 1.5, 1.75):
        spd_action = QtGui.QAction(f"{speed}x", data)
        spd_action.triggered.connect(partial(yuki_mpv_set_speed, speed))
        YukiMenubarData.speeds.append(spd_action)

    YukiMenubarData.prevchannel = QtGui.QAction(_("&Previous"), data)
    YukiMenubarData.prevchannel.triggered.connect(
        lambda: YukiMenubarData.prev_channel()
    )
    YukiMenubarData.prevchannel.setShortcut(kbd("prev_channel"))

    YukiMenubarData.nextchannel = QtGui.QAction(_("&Next"), data)
    YukiMenubarData.nextchannel.triggered.connect(
        lambda: YukiMenubarData.next_channel()
    )
    YukiMenubarData.nextchannel.setShortcut(kbd("next_channel"))

    # Video
    YukiMenubarData.fullscreen = QtGui.QAction(_("&Fullscreen"), data)
    YukiMenubarData.fullscreen.triggered.connect(
        lambda: YukiMenubarData.mpv_fullscreen()
    )
    YukiMenubarData.fullscreen.setShortcut(kbd("mpv_fullscreen"))

    YukiMenubarData.compactmode = QtGui.QAction(_("&Compact mode"), data)
    YukiMenubarData.compactmode.triggered.connect(
        lambda: YukiMenubarData.showhideeverything()
    )
    YukiMenubarData.compactmode.setShortcut(kbd("showhideeverything"))

    YukiMenubarData.csforchannel = QtGui.QAction(
        _("&Video settings") + YukiMenubarData.str_offset, data
    )
    YukiMenubarData.csforchannel.triggered.connect(
        lambda: YukiMenubarData.main_channel_settings()
    )
    YukiMenubarData.csforchannel.setShortcut(kbd("main_channel_settings"))

    YukiMenubarData.screenshot = QtGui.QAction(_("&Screenshot"), data)
    YukiMenubarData.screenshot.triggered.connect(
        lambda: YukiMenubarData.do_screenshot()
    )
    YukiMenubarData.screenshot.setShortcut(kbd("do_screenshot"))

    # Video filters
    YukiMenubarData.vf_postproc = QtGui.QAction(_("&Postprocessing"), data)
    YukiMenubarData.vf_postproc.setCheckable(True)

    YukiMenubarData.vf_deblock = QtGui.QAction(_("&Deblock"), data)
    YukiMenubarData.vf_deblock.setCheckable(True)

    YukiMenubarData.vf_dering = QtGui.QAction(_("De&ring"), data)
    YukiMenubarData.vf_dering.setCheckable(True)

    YukiMenubarData.vf_debanding = QtGui.QAction(
        _("Debanding (&gradfun)") + YukiMenubarData.str_offset, data
    )
    YukiMenubarData.vf_debanding.setCheckable(True)

    YukiMenubarData.vf_noise = QtGui.QAction(_("Add n&oise"), data)
    YukiMenubarData.vf_noise.setCheckable(True)

    YukiMenubarData.vf_phase = QtGui.QAction(_("&Autodetect phase"), data)
    YukiMenubarData.vf_phase.setCheckable(True)

    # Audio
    YukiMenubarData.muteAction = QtGui.QAction(_("&Mute audio"), data)
    YukiMenubarData.muteAction.triggered.connect(lambda: YukiMenubarData.mpv_mute())
    YukiMenubarData.muteAction.setShortcut(kbd("mpv_mute"))

    YukiMenubarData.volumeMinus = QtGui.QAction(_("V&olume -"), data)
    YukiMenubarData.volumeMinus.triggered.connect(
        lambda: YukiMenubarData.my_down_binding_execute()
    )
    YukiMenubarData.volumeMinus.setShortcut(kbd("my_down_binding_execute"))

    YukiMenubarData.volumePlus = QtGui.QAction(_("Vo&lume +"), data)
    YukiMenubarData.volumePlus.triggered.connect(
        lambda: YukiMenubarData.my_up_binding_execute()
    )
    YukiMenubarData.volumePlus.setShortcut(kbd("my_up_binding_execute"))

    # Audio filters
    YukiMenubarData.af_extrastereo = QtGui.QAction(_("&Extrastereo"), data)
    YukiMenubarData.af_extrastereo.setCheckable(True)

    YukiMenubarData.af_karaoke = QtGui.QAction(_("&Karaoke"), data)
    YukiMenubarData.af_karaoke.setCheckable(True)

    YukiMenubarData.af_earvax = QtGui.QAction(
        _("&Headphone optimization") + YukiMenubarData.str_offset, data
    )
    YukiMenubarData.af_earvax.setCheckable(True)

    YukiMenubarData.af_volnorm = QtGui.QAction(_("Volume &normalization"), data)
    YukiMenubarData.af_volnorm.setCheckable(True)

    # View
    YukiMenubarData.showhideplaylistAction = QtGui.QAction(
        _("Show/hide playlist"), data
    )
    YukiMenubarData.showhideplaylistAction.triggered.connect(
        lambda: YukiMenubarData.showhideplaylist()
    )
    YukiMenubarData.showhideplaylistAction.setShortcut(kbd("key_t"))

    YukiMenubarData.showhidectrlpanelAction = QtGui.QAction(
        _("Show/hide controls panel"), data
    )
    YukiMenubarData.showhidectrlpanelAction.triggered.connect(
        lambda: YukiMenubarData.lowpanel_ch_1()
    )
    YukiMenubarData.showhidectrlpanelAction.setShortcut(kbd("lowpanel_ch_1"))

    YukiMenubarData.streaminformationAction = QtGui.QAction(
        _("Stream Information"), data
    )
    YukiMenubarData.streaminformationAction.triggered.connect(
        lambda: YukiMenubarData.open_stream_info()
    )
    YukiMenubarData.streaminformationAction.setShortcut(kbd("open_stream_info"))

    YukiMenubarData.showepgAction = QtGui.QAction(_("TV guide"), data)
    YukiMenubarData.showepgAction.triggered.connect(
        lambda: YukiMenubarData.show_tvguide_2()
    )
    YukiMenubarData.showepgAction.setShortcut(kbd("show_tvguide_2"))

    YukiMenubarData.multiepgAction = QtGui.QAction(_("Multi-EPG"), data)
    YukiMenubarData.multiepgAction.triggered.connect(
        lambda: YukiMenubarData.show_multi_epg()
    )
    YukiMenubarData.multiepgAction.setShortcut(kbd("show_multi_epg"))

    YukiMenubarData.forceupdateepgAction = QtGui.QAction(_("&Update TV guide"), data)
    YukiMenubarData.forceupdateepgAction.triggered.connect(
        lambda: YukiMenubarData.force_update_epg()
    )
    YukiMenubarData.forceupdateepgAction.setShortcut(kbd("force_update_epg"))

    # Options
    YukiMenubarData.sortAction = QtGui.QAction(_("&Channel sort"), data)
    YukiMenubarData.sortAction.triggered.connect(lambda: YukiMenubarData.show_sort())
    YukiMenubarData.sortAction.setShortcut(kbd("show_sort"))

    YukiMenubarData.shortcutsAction = QtGui.QAction("&" + _("Shortcuts"), data)
    YukiMenubarData.shortcutsAction.triggered.connect(
        lambda: YukiMenubarData.show_shortcuts()
    )

    YukiMenubarData.settingsAction = QtGui.QAction(_("&Settings"), data)
    YukiMenubarData.settingsAction.triggered.connect(
        lambda: YukiData.YukiGUI.show_settings()
    )
    YukiMenubarData.settingsAction.setShortcut(kbd("show_settings"))

    # Help
    YukiMenubarData.aboutAction = QtGui.QAction(_("&About yuki-iptv"), data)
    YukiMenubarData.aboutAction.triggered.connect(lambda: YukiMenubarData.show_help())

    # Empty (track list)
    def get_empty_action():
        empty_action = QtGui.QAction("<{}>".format(_("empty")), data)
        empty_action.setEnabled(False)
        return empty_action

    YukiMenubarData.get_empty_action = get_empty_action

    # Filters mapping
    YukiMenubarData.filter_mapping = {
        "vf::::::::lavfi=[pp]": YukiMenubarData.vf_postproc,
        "vf::::::::lavfi=[pp=vb/hb]": YukiMenubarData.vf_deblock,
        "vf::::::::lavfi=[pp=dr]": YukiMenubarData.vf_dering,
        "vf::::::::lavfi=[gradfun]": YukiMenubarData.vf_debanding,
        "vf::::::::lavfi=[noise=alls=9:allf=t]": YukiMenubarData.vf_noise,
        "vf::::::::lavfi=[phase=A]": YukiMenubarData.vf_phase,
        "af::::::::lavfi=[extrastereo]": YukiMenubarData.af_extrastereo,
        "af::::::::lavfi=[stereotools=mlev=0.015625]": YukiMenubarData.af_karaoke,
        "af::::::::lavfi=[earwax]": YukiMenubarData.af_earvax,
        "af::::::::lavfi=[acompressor]": YukiMenubarData.af_volnorm,
    }
    for vf_filter in YukiMenubarData.filter_mapping:
        YukiMenubarData.filter_mapping[vf_filter].triggered.connect(
            partial(
                apply_vf_filter, vf_filter, YukiMenubarData.filter_mapping[vf_filter]
            )
        )


@idle_function
def donate_message_show(*args, **kwargs):
    YukiData.state.show()
    YukiData.state.setTextYuki("Открываю браузер...")
    YukiData.time_stop = time.time() + 1


@async_gui_blocking_function
def donate_triggered(*args, **kwargs):
    donate_message_show()
    webbrowser.open("https://yoomoney.ru/to/4100118867456459")


def populate_menubar(i, menubar, data, track_list=None, playing_channel=None):
    if not YukiMenubarData.menubar_ready:
        init_menubar(data)
        YukiMenubarData.menubar_ready = True

    # File
    file_menu = menubar.addMenu(_("&File"))
    file_menu.addAction(YukiMenubarData.playlists)
    file_menu.addSeparator()
    file_menu.addAction(YukiMenubarData.reloadPlaylist)
    file_menu.addAction(YukiMenubarData.forceupdateepgAction)
    file_menu.addSeparator()
    file_menu.addAction(YukiMenubarData.m3uEditor)
    file_menu.addAction(YukiMenubarData.exitAction)

    # Play
    play_menu = menubar.addMenu(_("&Play"))
    play_menu.addAction(YukiMenubarData.playpause)
    play_menu.addAction(YukiMenubarData.stop)
    play_menu.addAction(YukiMenubarData.frame_step)
    play_menu.addAction(YukiMenubarData.frame_back_step)
    play_menu.addSeparator()
    for sec in YukiMenubarData.secs:
        play_menu.addAction(sec)
    play_menu.addSeparator()

    speed_menu = play_menu.addMenu(_("Speed"))
    speed_menu.addAction(YukiMenubarData.normalSpeed)
    for spd_action1 in YukiMenubarData.speeds:
        speed_menu.addAction(spd_action1)
    play_menu.addSeparator()
    play_menu.addAction(YukiMenubarData.prevchannel)
    play_menu.addAction(YukiMenubarData.nextchannel)

    # Video
    video_menu = menubar.addMenu(_("&Video"))
    video_track_menu = video_menu.addMenu(_("&Track"))
    video_track_menu.clear()
    video_menu.addAction(YukiMenubarData.fullscreen)
    video_menu.addAction(YukiMenubarData.compactmode)
    video_menu.addAction(YukiMenubarData.csforchannel)
    YukiMenubarData.video_menu_filters = video_menu.addMenu(_("F&ilters"))
    YukiMenubarData.video_menu_filters.addAction(YukiMenubarData.vf_postproc)
    YukiMenubarData.video_menu_filters.addAction(YukiMenubarData.vf_deblock)
    YukiMenubarData.video_menu_filters.addAction(YukiMenubarData.vf_dering)
    YukiMenubarData.video_menu_filters.addAction(YukiMenubarData.vf_debanding)
    YukiMenubarData.video_menu_filters.addAction(YukiMenubarData.vf_noise)
    YukiMenubarData.video_menu_filters.addAction(YukiMenubarData.vf_phase)
    video_menu.addSeparator()
    video_menu.addAction(YukiMenubarData.screenshot)

    # Audio
    audio_menu = menubar.addMenu(_("&Audio"))
    audio_track_menu = audio_menu.addMenu(_("&Track"))
    audio_track_menu.clear()
    YukiMenubarData.audio_menu_filters = audio_menu.addMenu(_("F&ilters"))
    YukiMenubarData.audio_menu_filters.addAction(YukiMenubarData.af_extrastereo)
    YukiMenubarData.audio_menu_filters.addAction(YukiMenubarData.af_karaoke)
    YukiMenubarData.audio_menu_filters.addAction(YukiMenubarData.af_earvax)
    YukiMenubarData.audio_menu_filters.addAction(YukiMenubarData.af_volnorm)
    audio_menu.addSeparator()
    audio_menu.addAction(YukiMenubarData.muteAction)
    audio_menu.addSeparator()
    audio_menu.addAction(YukiMenubarData.volumeMinus)
    audio_menu.addAction(YukiMenubarData.volumePlus)

    # Subtitles
    subtitles_menu = menubar.addMenu(_("&Subtitles"))
    sub_track_menu = subtitles_menu.addMenu(_("&Track"))
    sub_track_menu.clear()

    # View
    view_menu = menubar.addMenu(_("Vie&w"))
    view_menu.addAction(YukiMenubarData.showhideplaylistAction)
    view_menu.addAction(YukiMenubarData.showhidectrlpanelAction)
    view_menu.addAction(YukiMenubarData.streaminformationAction)
    view_menu.addAction(YukiMenubarData.showepgAction)
    view_menu.addAction(YukiMenubarData.multiepgAction)

    # Options
    options_menu = menubar.addMenu(_("&Options"))
    options_menu.addAction(YukiMenubarData.sortAction)
    options_menu.addSeparator()
    options_menu.addAction(YukiMenubarData.shortcutsAction)
    options_menu.addAction(YukiMenubarData.settingsAction)

    # Help
    help_menu = menubar.addMenu(_("&Help"))
    help_menu.addAction(YukiMenubarData.aboutAction)

    # Donate
    if _("&Help") == "Сп&равка":
        donate_action = menubar.addAction("П&ожертвовать")
        donate_action.triggered.connect(donate_triggered)

    YukiMenubarData.menubars[i] = [video_track_menu, audio_track_menu, sub_track_menu]


# Preventing memory leak
def clear_menu(menu):
    for mb_action in menu.actions():
        if mb_action.isSeparator():
            mb_action.deleteLater()
        # elif mb_action.menu():
        #    clear_menu(mb_action.menu())
        #    mb_action.menu().deleteLater()
        else:
            mb_action.deleteLater()


def recursive_filter_setstate(state):
    for act in YukiMenubarData.video_menu_filters.actions():
        if not act.isSeparator():  # or act.menu():
            act.setEnabled(state)
    for act1 in YukiMenubarData.audio_menu_filters.actions():
        if not act1.isSeparator():  # or act1.menu():
            act1.setEnabled(state)


def get_first_run():
    return YukiMenubarData.first_run


def update_menubar(track_list, playing_channel):
    # Filters enable / disable
    if playing_channel:
        recursive_filter_setstate(True)
        if not YukiMenubarData.first_run:
            YukiMenubarData.first_run = True
            try:
                vf_filters_read = read_option("vf_filters")
                if vf_filters_read:
                    for dat in vf_filters_read:
                        if dat in YukiMenubarData.filter_mapping:
                            YukiMenubarData.filter_mapping[dat].setChecked(True)
                            apply_vf_filter(dat, YukiMenubarData.filter_mapping[dat])
            except Exception:
                logger.warning(traceback.format_exc())
    else:
        recursive_filter_setstate(False)
    # Track list
    for i in YukiMenubarData.menubars:
        clear_menu(YukiMenubarData.menubars[i][0])
        clear_menu(YukiMenubarData.menubars[i][1])
        clear_menu(YukiMenubarData.menubars[i][2])
        YukiMenubarData.menubars[i][0].clear()
        YukiMenubarData.menubars[i][1].clear()
        YukiMenubarData.menubars[i][2].clear()
        if track_list and playing_channel:
            if not [x for x in track_list if x["type"] == "video"]:
                YukiMenubarData.menubars[i][0].addAction(
                    YukiMenubarData.get_empty_action()
                )
            if not [x for x in track_list if x["type"] == "audio"]:
                YukiMenubarData.menubars[i][1].addAction(
                    YukiMenubarData.get_empty_action()
                )
            # Subtitles off
            sub_off_action = QtGui.QAction(_("None"), YukiMenubarData.data)
            if YukiMenubarData.player.sid == "no" or not YukiMenubarData.player.sid:
                sub_off_action.setIcon(YukiMenubarData.circle_icon)
            sub_off_action.triggered.connect(partial(yuki_trackset, "no", "sid"))
            YukiMenubarData.menubars[i][2].addAction(sub_off_action)
            for track in track_list:
                if track["type"] == "video":
                    video_track_action = QtGui.QAction(
                        str(track["id"]), YukiMenubarData.data
                    )
                    if track["id"] == YukiMenubarData.player.vid:
                        video_track_action.setIcon(YukiMenubarData.circle_icon)
                    video_track_action.triggered.connect(
                        partial(yuki_trackset, track["id"], "vid")
                    )
                    YukiMenubarData.menubars[i][0].addAction(video_track_action)
                if track["type"] == "audio":
                    if "lang" in track:
                        audio_track_action = QtGui.QAction(
                            "{} ({})".format(track["id"], track["lang"]),
                            YukiMenubarData.data,
                        )
                    else:
                        audio_track_action = QtGui.QAction(
                            str(track["id"]), YukiMenubarData.data
                        )
                    if track["id"] == YukiMenubarData.player.aid:
                        audio_track_action.setIcon(YukiMenubarData.circle_icon)
                    audio_track_action.triggered.connect(
                        partial(yuki_trackset, track["id"], "aid")
                    )
                    YukiMenubarData.menubars[i][1].addAction(audio_track_action)
                if track["type"] == "sub":
                    if "lang" in track:
                        sub_track_action = QtGui.QAction(
                            "{} ({})".format(track["id"], track["lang"]),
                            YukiMenubarData.data,
                        )
                    else:
                        sub_track_action = QtGui.QAction(
                            str(track["id"]), YukiMenubarData.data
                        )
                    if track["id"] == YukiMenubarData.player.sid:
                        sub_track_action.setIcon(YukiMenubarData.circle_icon)
                    sub_track_action.triggered.connect(
                        partial(yuki_trackset, track["id"], "sid")
                    )
                    YukiMenubarData.menubars[i][2].addAction(sub_track_action)
        else:
            YukiMenubarData.menubars[i][0].addAction(YukiMenubarData.get_empty_action())
            YukiMenubarData.menubars[i][1].addAction(YukiMenubarData.get_empty_action())
            YukiMenubarData.menubars[i][2].addAction(YukiMenubarData.get_empty_action())


def init_yuki_iptv_menubar(data, app, menubar):
    YukiMenubarData.data = data


def init_menubar_player(
    player,
    mpv_play,
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
    app_quit,
    redraw_menubar,
    circle_icon,
    my_up_binding_execute,
    my_down_binding_execute,
    show_playlists,
    show_sort,
    force_update_epg,
    show_tvguide_2,
    show_multi_epg,
    reload_playlist,
    show_shortcuts,
    yuki_track_set,
    mpv_frame_step,
    mpv_frame_back_step,
):
    for func in locals().items():
        setattr(YukiMenubarData, func[0], func[1])
