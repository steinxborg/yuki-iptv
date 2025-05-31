#
# Copyright (c) 2024, 2025 liya <liyaastrova@proton.me>
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
import os.path
import logging
import hashlib
import traceback
from pathlib import Path
from PyQt6 import QtCore
from functools import partial
from gi.repository import Gio, GLib
from yuki_iptv.i18n import _
from yuki_iptv.misc import YukiData
from yuki_iptv.gui import win_show_raise
from yuki_iptv.threads import (
    idle_function,
    async_gui_blocking_function,
    execute_in_main_thread,
)
from yuki_iptv.gui_playlists import playlist_selected

logger = logging.getLogger(__name__)


class YukiMPRISData:
    callback = None
    get_options = None
    mpris_bus = None
    mpris_failed = False
    mpris_node = None
    register_ids = []


with open(
    Path(os.path.dirname(os.path.abspath(__file__))) / "org.mpris.MediaPlayer2.xml", "r"
) as mpris_xml_file:
    mpris_xml = mpris_xml_file.read()
    YukiMPRISData.mpris_node = Gio.DBusNodeInfo.new_for_xml(mpris_xml)


def mpris_handle_method_call(
    connection, sender, object_path, interface_name, method_name, params, invocation
):
    # logger.debug(
    #     f"object_path = {object_path} interface_name = {interface_name} "
    #     f"method_name = {method_name} params = {params.unpack()}"
    # )
    if interface_name == "org.freedesktop.DBus.Properties" and method_name == "Get":
        invocation.return_value(
            GLib.Variant.new_tuple(
                GLib.Variant(
                    "v",
                    YukiMPRISData.get_options()[params.unpack()[0]][params.unpack()[1]],
                )
            )
        )
    elif (
        interface_name == "org.freedesktop.DBus.Properties" and method_name == "GetAll"
    ):
        invocation.return_value(
            GLib.Variant.new_tuple(
                GLib.Variant("a{sv}", YukiMPRISData.get_options()[params.unpack()[0]])
            )
        )
    else:
        invocation.return_value(
            YukiMPRISData.callback((interface_name, method_name, params))
        )


def mpris_on_bus_acquired(connection, name):
    logger.debug(f"Bus acquired for name {name}")
    for interface in YukiMPRISData.mpris_node.interfaces:
        # TODO: implement TrackList interface
        if interface.name != "org.mpris.MediaPlayer2.TrackList":
            logger.debug(f"Registering {interface.name}")
            # DeprecationWarning: Gio.DBusConnection.register_object is deprecated
            # https://gitlab.gnome.org/GNOME/pygobject/-/issues/688
            register_object = (
                "register_object_with_closures2"
                if hasattr(connection, "register_object_with_closures2")
                else "register_object"
            )
            YukiMPRISData.register_ids.append(
                getattr(connection, register_object)(
                    "/org/mpris/MediaPlayer2",
                    interface,
                    mpris_handle_method_call,
                    None,
                    None,
                )
            )


def mpris_on_connection_lost(connection, name):
    logger.warning(f"Lost connection to name {name}")
    YukiMPRISData.mpris_failed = True


def start_mpris(pid, callback, get_options):
    YukiMPRISData.callback = callback
    YukiMPRISData.get_options = get_options
    return Gio.bus_own_name(
        Gio.BusType.SESSION,
        f"org.mpris.MediaPlayer2.yuki_iptv.instance{pid}",
        Gio.BusNameOwnerFlags.NONE,
        mpris_on_bus_acquired,
        lambda _connection, name: logger.info(f"Name acquired: {name}"),
        mpris_on_connection_lost,
    )


def emit_mpris_change(interface_name, variable):
    if not YukiMPRISData.mpris_failed:
        if YukiMPRISData.mpris_bus is None:
            try:
                YukiMPRISData.mpris_bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            except Exception:
                YukiMPRISData.mpris_failed = True
                logger.warning(traceback.format_exc())
        try:
            if YukiMPRISData.mpris_bus:
                YukiMPRISData.mpris_bus.emit_signal(
                    None,
                    "/org/mpris/MediaPlayer2",
                    "org.freedesktop.DBus.Properties",
                    "PropertiesChanged",
                    GLib.Variant(
                        "(sa{sv}as)",
                        (
                            interface_name,
                            variable,
                            {},
                        ),
                    ),
                )
            variable = None
        except Exception:
            YukiMPRISData.mpris_failed = True
            logger.warning(traceback.format_exc())


def mpris_seeked(position):
    if not YukiMPRISData.mpris_failed:
        if YukiMPRISData.mpris_bus is None:
            try:
                YukiMPRISData.mpris_bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            except Exception:
                YukiMPRISData.mpris_failed = True
                logger.warning(traceback.format_exc())
        try:
            if YukiMPRISData.mpris_bus:
                YukiMPRISData.mpris_bus.emit_signal(
                    None,
                    "/org/mpris/MediaPlayer2",
                    "org.mpris.MediaPlayer2.Player",
                    "Seeked",
                    GLib.Variant.new_tuple(GLib.Variant("x", position)),
                )
        except Exception:
            YukiMPRISData.mpris_failed = True
            logger.warning(traceback.format_exc())


def mpris_set_volume(val):
    YukiData.YukiGUI.volume_slider.setValue(int(val * 100))
    YukiData.mpv_volume_set()


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
        if YukiData.playlists_saved[playlist]["m3u"] == YukiData.settings["m3u"]:
            current_playlist_name = playlist
            current_playlist = (
                f"{prefix}" f"{get_playlist_hash(YukiData.playlists_saved[playlist])}",
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


def mpris_callback(mpris_data):
    if mpris_data[0] == "org.mpris.MediaPlayer2" and mpris_data[1] == "Raise":
        execute_in_main_thread(partial(win_show_raise))
    elif mpris_data[0] == "org.mpris.MediaPlayer2" and mpris_data[1] == "Quit":
        QtCore.QTimer.singleShot(
            100, lambda: execute_in_main_thread(partial(YukiData.app.quit))
        )
    elif mpris_data[0] == "org.mpris.MediaPlayer2.Player" and mpris_data[1] == "Next":
        execute_in_main_thread(partial(YukiData.next_channel))
    elif (
        mpris_data[0] == "org.mpris.MediaPlayer2.Player" and mpris_data[1] == "Previous"
    ):
        execute_in_main_thread(partial(YukiData.prev_channel))
    elif mpris_data[0] == "org.mpris.MediaPlayer2.Player" and mpris_data[1] == "Pause":
        if not YukiData.player.pause:
            execute_in_main_thread(partial(YukiData.mpv_play_pause))
    elif (
        mpris_data[0] == "org.mpris.MediaPlayer2.Player"
        and mpris_data[1] == "PlayPause"
    ):
        execute_in_main_thread(partial(YukiData.mpv_play_pause))
    elif mpris_data[0] == "org.mpris.MediaPlayer2.Player" and mpris_data[1] == "Stop":
        execute_in_main_thread(partial(YukiData.mpv_stop))
    elif mpris_data[0] == "org.mpris.MediaPlayer2.Player" and mpris_data[1] == "Play":
        if YukiData.player.pause:
            execute_in_main_thread(partial(YukiData.mpv_play_pause))
    elif mpris_data[0] == "org.mpris.MediaPlayer2.Player" and mpris_data[1] == "Seek":
        # microseconds to seconds
        execute_in_main_thread(partial(mpris_seek, mpris_data[2][0] / 1000000))
    elif (
        mpris_data[0] == "org.mpris.MediaPlayer2.Player"
        and mpris_data[1] == "SetPosition"
    ):
        track_id = mpris_data[2][0]
        position = mpris_data[2][1] / 1000000  # microseconds to seconds
        if track_id != "/page/codeberg/liya/yuki_iptv/Track/NoTrack":
            execute_in_main_thread(partial(mpris_set_position, track_id, position))
    elif (
        mpris_data[0] == "org.mpris.MediaPlayer2.Player" and mpris_data[1] == "OpenUri"
    ):
        mpris_play_url = mpris_data[2].unpack()[0]
        execute_in_main_thread(
            partial(YukiData.item_clicked, mpris_play_url, mpris_play_url)
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
    elif mpris_data[0] == "org.freedesktop.DBus.Properties" and mpris_data[1] == "Set":
        mpris_data_params = mpris_data[2].unpack()
        if (
            mpris_data_params[0] == "org.mpris.MediaPlayer2"
            and mpris_data_params[1] == "Fullscreen"
        ):
            if mpris_data_params[2]:
                # Enable fullscreen
                if not YukiData.fullscreen:
                    execute_in_main_thread(partial(YukiData.mpv_fullscreen))
            else:
                # Disable fullscreen
                if YukiData.fullscreen:
                    execute_in_main_thread(partial(YukiData.mpv_fullscreen))
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
            execute_in_main_thread(
                partial(YukiData.set_playback_speed, mpris_data_params[2])
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
            execute_in_main_thread(partial(mpris_set_volume, mpris_data_params[2]))
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
    playing_url_hash = hashlib.sha512(YukiData.playing_url.encode("utf-8")).hexdigest()
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
                artUrl = YukiData.array[YukiData.playing_channel]["tvg-logo"]
    # Position in microseconds
    player_position = (
        YukiData.player.duration * 1000000 if YukiData.player.duration else 0
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
                        "xesam:url": GLib.Variant("s", YukiData.playing_url),
                        "xesam:title": GLib.Variant("s", YukiData.playing_channel),
                    },
                ),
                "Volume": GLib.Variant("d", float(YukiData.player.volume / 100)),
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
        if (YukiData.win.isVisible() and YukiData.player) or YukiData.stopped:
            break
        time.sleep(0.1)


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
        try:
            if YukiData.mpris_ready and YukiData.mpris_running:
                (
                    playback_status,
                    mpris_trackid,
                    artUrl,
                    player_position,
                ) = get_mpris_metadata()
                execute_in_main_thread(
                    partial(
                        emit_mpris_change,
                        "org.mpris.MediaPlayer2.Player",
                        {
                            "PlaybackStatus": GLib.Variant("s", playback_status),
                            "Rate": GLib.Variant("d", YukiData.player.speed),
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
                        },
                    )
                )
        except Exception:
            logger.warning(traceback.format_exc())

    def on_playpause(self):
        try:
            if YukiData.mpris_ready and YukiData.mpris_running:
                (
                    playback_status,
                    mpris_trackid,
                    artUrl,
                    player_position,
                ) = get_mpris_metadata()
                execute_in_main_thread(
                    partial(
                        emit_mpris_change,
                        "org.mpris.MediaPlayer2.Player",
                        {"PlaybackStatus": GLib.Variant("s", playback_status)},
                    )
                )
        except Exception:
            logger.warning(traceback.format_exc())

    def on_volume(self):
        try:
            if YukiData.mpris_ready and YukiData.mpris_running:
                execute_in_main_thread(
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
        except Exception:
            logger.warning(traceback.format_exc())

    def on_fullscreen(self):
        try:
            if YukiData.mpris_ready and YukiData.mpris_running:
                execute_in_main_thread(
                    partial(
                        emit_mpris_change,
                        "org.mpris.MediaPlayer2",
                        {"Fullscreen": GLib.Variant("b", YukiData.fullscreen)},
                    )
                )
        except Exception:
            logger.warning(traceback.format_exc())


def mpris_init():
    try:
        YukiData.event_handler = MPRISEventHandler()
        YukiData.mpris_loop = GLib.MainLoop()
        mpris_loop_start()
    except Exception:
        logger.warning("MPRIS init error!")
        logger.warning(traceback.format_exc())
