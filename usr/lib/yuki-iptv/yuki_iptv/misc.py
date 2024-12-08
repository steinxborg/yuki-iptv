#
# Copyright (c) 2021, 2022 Astroncia
# Copyright (c) 2023, 2024 liya <liyaastrova@proton.me>
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
# License - https://creativecommons.org/licenses/by/4.0/
#
import time
import threading

MAIN_WINDOW_TITLE = "yuki-iptv"
WINDOW_SIZE = (1200, 650)
DOCKWIDGET_CONTROLPANEL_HEIGHT = int(WINDOW_SIZE[1] / 10)
DOCKWIDGET_CONTROLPANEL_HEIGHT_OFFSET = 10
DOCKWIDGET_CONTROLPANEL_HEIGHT_HIGH = (
    DOCKWIDGET_CONTROLPANEL_HEIGHT + DOCKWIDGET_CONTROLPANEL_HEIGHT_OFFSET
)
DOCKWIDGET_CONTROLPANEL_HEIGHT_LOW = DOCKWIDGET_CONTROLPANEL_HEIGHT_HIGH - (
    DOCKWIDGET_CONTROLPANEL_HEIGHT_OFFSET + 10
)
DOCKWIDGET_PLAYLIST_WIDTH = int((WINDOW_SIZE[0] / 2) - 200)
TVGUIDE_WIDTH = int(WINDOW_SIZE[0] / 5)
BCOLOR = "#A2A3A3"

UPDATE_BR_INTERVAL = 5

AUDIO_SAMPLE_FORMATS = {
    "u16": "unsigned 16 bits",
    "s16": "signed 16 bits",
    "s16p": "signed 16 bits, planar",
    "flt": "float",
    "float": "float",
    "fltp": "float, planar",
    "floatp": "float, planar",
    "dbl": "double",
    "dblp": "double, planar",
}

MPV_OPTIONS_LINK = "https://mpv.io/manual/master/#options"


class stream_info:
    pass


class YukiData:
    archive_epg = None
    array = None
    channel_logos_process = None
    channel_logos_request_old = None
    channel_sets = None
    channel_sort = None
    combobox = None
    current_group = None
    currentMaximized = None
    currentMoviesGroup = None
    currentWidthHeight = None
    dockWidget_controlPanelVisible = None
    dockWidget_playlistVisible = None
    do_save_settings = None
    epg_array = {}
    epg_pool_running = False
    epg_pool = None
    epg_data = None
    epg_failed = False
    epg_icons = None
    epg_ready = None
    epg_selected_date = None
    epg_thread_2 = None
    epg_update_date = 0
    epg_update_allowed = None
    epg_updating = None
    event_handler = None
    favourite_sets = None
    ffmpeg_processes = None
    first_boot = True
    first_change = None
    first_playmode_change = None
    firstVolRun = None
    force_turnoff_osc = None
    fullscreen = None
    gl_is_static = None
    ic = None
    ic1 = None
    ic2 = None
    ic3 = None
    isControlPanelVisible = None
    isPlaylistVisible = None
    is_recording = None
    is_recording_old = None
    item_selected = None
    last_cursor_moved = None
    last_cursor_time = None
    main_keybinds = None
    menubar_state = None
    movie_logos_process = None
    movie_logos_request_old = None
    mpv_osc_enabled = None
    mp_manager_dict = None
    old_value = None
    player = None
    player_tracks = None
    playing = None
    playing_archive = None
    playing_channel = None
    playing_group = None
    playing_url = None
    prev_cursor = None
    previous_text = None
    prog_match_arr = None
    record_file = None
    recording_time = None
    recViaScheduler = None
    rewindWidgetVisible = None
    right_click_menu = None
    row0 = None
    settings = None
    state = None
    static_text = None
    stopped = None
    search = ""
    thread_tvguide_progress_lock = None
    thread_tvguide_update_pt2_e2 = None
    timer_logos_update_lock = None
    time_stop = None
    tvguide_lbl = None
    tvguide_sets = None
    VOLUME_SLIDER_WIDTH = None
    x_conn = None
    resume_playback = False
    compact_mode = False
    playlist_hidden = False
    controlpanel_hidden = False
    fullscreen_locked = False
    selected_shortcut_row = -1
    shortcuts_state = False
    use_dark_icon_theme = False
    playmodeIndex = 0
    serie_selected = False
    movies = {}
    series = {}
    osc = -1
    volume = 100
    needs_resize = False
    first_start = False
    streaminfo_win_visible = False
    current_prog1 = None
    check_playlist_visible = False
    check_controlpanel_visible = False
    rewind_value = None
    xtream_list_old = set()
    xtream_list_lock = False
    xtream_expiration_list = {}
    is_xtream = False
    # MPRIS
    mpris_loop = None
    mpris_ready = False
    mpris_running = False
    mpris_select_playlist = None
    is_loading = False
    old_playing_url = ""


stream_info.video_properties = {}
stream_info.audio_properties = {}
stream_info.video_bitrates = []
stream_info.audio_bitrates = []

DOCKWIDGET_CONTROLPANEL_HEIGHT = max(DOCKWIDGET_CONTROLPANEL_HEIGHT, 0)
DOCKWIDGET_PLAYLIST_WIDTH = max(DOCKWIDGET_PLAYLIST_WIDTH, 0)


def get_current_time():
    return time.strftime("%d.%m.%y %H:%M", time.localtime())


def format_bytes(bytes1, hbnames):
    idx = 0
    while bytes1 >= 1024 and idx + 1 < len(hbnames):
        bytes1 = bytes1 / 1024
        idx += 1
    return f"{bytes1:.1f} {hbnames[idx]}"


def format_seconds(seconds):
    return time.strftime("%H:%M:%S", time.gmtime(seconds))


def convert_size(size_bytes):
    return format_bytes(
        size_bytes, ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    )


def decode(s):
    if isinstance(s, bytes):
        s = s.decode("utf-8")
    return s


# Used as a decorator to run things in the background (GUI blocking)
def async_gui_blocking_function(func):
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        return thread

    return wrapper
