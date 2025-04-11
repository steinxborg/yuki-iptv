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
import os.path
import logging
import traceback
from pathlib import Path
from gi.repository import Gio, GLib

logger = logging.getLogger(__name__)

with open(
    Path(os.path.dirname(os.path.abspath(__file__))) / "org.mpris.MediaPlayer2.xml", "r"
) as mpris_xml_file:
    mpris_xml = mpris_xml_file.read()
mpris_node = Gio.DBusNodeInfo.new_for_xml(mpris_xml)


class YukiData:
    callback = None
    get_options = None
    mpris_bus = None


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
                    YukiData.get_options()[params.unpack()[0]][params.unpack()[1]],
                )
            )
        )
    elif (
        interface_name == "org.freedesktop.DBus.Properties" and method_name == "GetAll"
    ):
        invocation.return_value(
            GLib.Variant.new_tuple(
                GLib.Variant("a{sv}", YukiData.get_options()[params.unpack()[0]])
            )
        )
    else:
        invocation.return_value(
            YukiData.callback((interface_name, method_name, params))
        )


def mpris_on_bus_acquired(connection, name):
    logger.debug(f"Bus acquired for name {name}")
    register_ids = []
    for interface in mpris_node.interfaces:
        # TODO implement TrackList interface
        if interface.name != "org.mpris.MediaPlayer2.TrackList":
            logger.debug(f"Registering {interface.name}")
            register_ids.append(
                connection.register_object(
                    "/org/mpris/MediaPlayer2",
                    interface,
                    mpris_handle_method_call,
                    None,
                    None,
                )
            )


def start_mpris(pid, callback, get_options):
    YukiData.callback = callback
    YukiData.get_options = get_options
    return Gio.bus_own_name(
        Gio.BusType.SESSION,
        f"org.mpris.MediaPlayer2.yuki_iptv.instance{pid}",
        Gio.BusNameOwnerFlags.NONE,
        mpris_on_bus_acquired,
        lambda _connection, name: logger.info(f"Name acquired: {name}"),
        lambda _connection, name: logger.warning(f"Lost connection to name {name}"),
    )


def emit_mpris_change(interface_name, variable):
    if YukiData.mpris_bus is None:
        try:
            YukiData.mpris_bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except Exception:
            logger.warning(traceback.format_exc())
    try:
        YukiData.mpris_bus.emit_signal(
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
        logger.warning(traceback.format_exc())


def mpris_seeked(position):
    if YukiData.mpris_bus is None:
        try:
            YukiData.mpris_bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except Exception:
            logger.warning(traceback.format_exc())
    try:
        YukiData.mpris_bus.emit_signal(
            None,
            "/org/mpris/MediaPlayer2",
            "org.mpris.MediaPlayer2.Player",
            "Seeked",
            GLib.Variant.new_tuple(GLib.Variant("x", position)),
        )
    except Exception:
        logger.warning(traceback.format_exc())
