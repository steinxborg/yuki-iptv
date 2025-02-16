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
import uuid
import signal
import logging
import urllib.parse
from PyQt6 import QtCore
from yuki_iptv.i18n import _
from yuki_iptv.settings import parse_settings
from yuki_iptv.kill_process_childs import kill_process_childs

# TODO: YouTube recording is horribly broken, needs fix
# for example, how to correctly stop yt-dlp?

logger = logging.getLogger(__name__)


class YukiData:
    ffmpeg_proc = None
    ffmpeg_processes = None
    show_record_exception = None


def is_ffmpeg_recording():
    ret = -2
    if YukiData.ffmpeg_proc:
        if YukiData.ffmpeg_proc.processId() == 0:
            YukiData.ffmpeg_proc = None
            ret = True
        else:
            ret = False
    return ret


def exit_handler(process, exit_code, exit_status):
    is_ok = True
    if exit_code != 0:
        is_ok = False
    if exit_code == 255:
        is_ok = True
    if not is_ok or exit_status != QtCore.QProcess.ExitStatus.NormalExit:
        ffmpeg_proc_program = process.program()
        is_killed = False
        try:
            is_killed = process._yuki_killed
        except Exception:
            pass
        if not is_killed and not (
            ("yt-dlp" in ffmpeg_proc_program) and exit_code == int(signal.SIGTERM)
        ):
            logger.warning("ffmpeg process crashed")
            if YukiData.show_record_exception:
                standard_output = process.readAllStandardOutput()
                try:
                    standard_output = bytes(standard_output).decode("utf-8")
                    standard_output = "\n".join(standard_output.split("\n")[-15:])
                except Exception:
                    pass
                standard_error = process.readAllStandardError()
                try:
                    standard_error = bytes(standard_error).decode("utf-8")
                    standard_error = "\n".join(standard_error.split("\n")[-15:])
                except Exception:
                    pass
                YukiData.show_record_exception(
                    _("ffmpeg crashed!") + "\n"
                    "" + _("exit code:") + " " + str(exit_code) + ""
                    "\nstdout:\n" + str(standard_output) + ""
                    "\nstderr:\n" + str(standard_error)
                )


def is_youtube_url(url):
    return urllib.parse.urlparse(url).netloc in (
        "youtube.com",
        "www.youtube.com",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
        "youtu.be",
        "www.youtu.be",
    )


def record(
    input_url,
    out_file,
    channel_name,
    http_referer,
    get_ua_ref_for_channel,
    is_return=False,
):
    settings, settings_loaded = parse_settings()
    if http_referer == "Referer: ":
        http_referer = ""
    useragent_ref, referer_ref = get_ua_ref_for_channel(channel_name)
    user_agent = useragent_ref
    origin_add = ""
    if referer_ref:
        http_referer = f"Referer: {referer_ref}"
        originURL = ""
        if referer_ref.endswith("/"):
            originURL = referer_ref[:-1]
        if originURL:
            origin_add = "Origin: " + originURL + "\r\n"
    logger.info(f"Using user agent '{user_agent}' for record channel '{channel_name}'")
    logger.info(f"HTTP headers: '{http_referer}'")
    uuid_add = ""
    uuid_arr = []
    if settings["uuid"]:
        uuid_add = "X-Playback-Session-Id: " + str(uuid.uuid1()) + "\r\n"
        uuid_arr = ["-headers", uuid_add]
    if input_url.startswith("http://") or input_url.startswith("https://"):
        arr = [
            "-nostats",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-user_agent",
            user_agent,
            "-headers",
            http_referer + "\r\n" + uuid_add + origin_add,
            "-i",
            input_url,
            "-map",
            "-0:s?",
            "-sn",
            "-map",
            "-0:d?",
            "-map",
            "-0:t?",
            "-codec",
            "copy",
            "-max_muxing_queue_size",
            "4096",
            out_file,
        ]
    else:
        arr = (
            [
                "-nostats",
                "-hide_banner",
                "-loglevel",
                "warning",
            ]
            + uuid_arr
            + [
                "-i",
                input_url,
                "-map",
                "-0:s?",
                "-sn",
                "-map",
                "-0:d?",
                "-map",
                "-0:t?",
                "-codec",
                "copy",
                "-max_muxing_queue_size",
                "4096",
                out_file,
            ]
        )
    process = "ffmpeg"
    if is_youtube_url(input_url):
        process = "yt-dlp"
        logger.info(f"YouTube detected, using {process} for recording")
        arr = [
            "--merge-output-format",
            "mkv",
            "--no-part",
            "--output",
            out_file,
            input_url,
        ]
    if not is_return:
        YukiData.ffmpeg_proc = QtCore.QProcess()
        YukiData.ffmpeg_proc.start(process, arr)
        YukiData.ffmpeg_proc.finished.connect(
            lambda exit_code, exit_status: exit_handler(
                YukiData.ffmpeg_proc, exit_code, exit_status
            )
        )
    else:
        ffmpeg_ret_proc = QtCore.QProcess()
        ffmpeg_ret_proc.start(process, arr)
        ffmpeg_ret_proc.finished.connect(
            lambda exit_code, exit_status: exit_handler(
                ffmpeg_ret_proc, exit_code, exit_status
            )
        )
        return ffmpeg_ret_proc


def record_return(
    input_url, out_file, channel_name, http_referer, get_ua_ref_for_channel
):
    return record(
        input_url, out_file, channel_name, http_referer, get_ua_ref_for_channel, True
    )


def terminate_record_process(proc):
    program = proc.program()
    if "yt-dlp" in program or "youtube-dl" in program:
        kill_process_childs(proc)
        proc.terminate()
    else:
        proc._yuki_killed = True
        proc.kill()


def stop_record():
    if YukiData.ffmpeg_proc:
        terminate_record_process(YukiData.ffmpeg_proc)


def init_record(show_exception, ffmpeg_processes):
    YukiData.show_record_exception = show_exception
    YukiData.ffmpeg_processes = ffmpeg_processes
