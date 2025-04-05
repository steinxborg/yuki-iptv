#
# Copyright (c) 2025 liya <liyaastrova@proton.me>
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
import io
import json
import base64
import logging
import binascii
import traceback
import threading
from xml.etree.ElementTree import iterparse
from yuki_iptv.qt import show_exception
from yuki_iptv.request import request

KEY_LEN = 32
logger = logging.getLogger(__name__)


def parse_keys(j):
    key = ""
    if "keys" in j:
        keys = j["keys"]
        if keys:
            if "k" in keys[0]:
                raw_key = keys[0]["k"]
                if "kty" in keys[0] and keys[0]["kty"] == "oct":
                    binary_key = base64.urlsafe_b64decode(
                        raw_key + "=" * (4 - len(raw_key) % 4)
                    )
                    key = binascii.hexlify(binary_key).decode("utf-8")
                elif len(str(raw_key)) == KEY_LEN:
                    key = str(raw_key)
            elif "key" in keys[0] and len(str(keys[0]["key"])) == KEY_LEN:
                key = str(keys[0]["key"])
    return key


def extract_cenc_decryption_key_from_kodiprop(line):
    key = ""
    try:
        if line.startswith("#KODIPROP:inputstream.adaptive.license_key="):
            line = line.replace("#KODIPROP:inputstream.adaptive.license_key=", "", 1)
            if "{" in line:
                key = parse_keys(json.loads(line))
            elif ":" in line:
                key = line.split(":")[1]
            elif len(str(line)) == KEY_LEN:
                key = str(line)
        elif line.startswith("#KODIPROP:inputstream.adaptive.drm_legacy="):
            line = line.replace(
                "#KODIPROP:inputstream.adaptive.drm_legacy=", "", 1
            ).split("|")
            if line and "clearkey" in line[0]:
                if len(line) > 1:
                    if line[1].startswith("http://") or line[1].startswith("https://"):
                        key = f"__LICENSE_URL__{line[1]}"
                    elif ":" in line[1]:
                        key = line[1].split(":")[1]
                    elif len(str(line[1])) == KEY_LEN:
                        key = str(line[1])
                else:
                    key = "__LICENSE_URL_PROVIDED_BY_MANIFEST__"
        elif line.startswith("#KODIPROP:inputstream.adaptive.drm="):
            line = line.replace("#KODIPROP:inputstream.adaptive.drm=", "", 1)
            if "{" in line:
                j = json.loads(line)
                if "org.w3.clearkey" in j and not j["org.w3.clearkey"]:
                    key = "__LICENSE_URL_PROVIDED_BY_MANIFEST__"
                elif (
                    "org.w3.clearkey" in j
                    and "license" in j["org.w3.clearkey"]
                    and "keyids" in j["org.w3.clearkey"]["license"]
                ):
                    keyids = j["org.w3.clearkey"]["license"]["keyids"]
                    if keyids:
                        key = keyids[next(iter(keyids))]
                elif (
                    "org.w3.clearkey" in j
                    and "license" in j["org.w3.clearkey"]
                    and "server_url" in j["org.w3.clearkey"]["license"]
                ):
                    key = (
                        "__LICENSE_URL__"
                        + j["org.w3.clearkey"]["license"]["server_url"]
                    )
                elif "org.w3.clearkey" in j and "keyids" in j["org.w3.clearkey"]:
                    keyids = j["org.w3.clearkey"]["keyids"]
                    if keyids:
                        key = keyids[next(iter(keyids))]
                elif (
                    "clearkey" in j
                    and "license" in j["clearkey"]
                    and "keyids" in j["clearkey"]["license"]
                ):
                    keyids = j["clearkey"]["license"]["keyids"]
                    if keyids:
                        key = keyids[next(iter(keyids))]
    except Exception:
        logger.warning("DRM key extraction from KODIPROP failed")
        logger.warning(traceback.format_exc())
    if not isinstance(key, str):
        logger.warning("Extracted DRM key is not a string")
        key = ""
    return key


def extract_cenc_decryption_key_from_url(url):
    key = ""
    try:
        if "$OPT:" in url:
            opts = url.split("$OPT:")[1:]
            url = url.split("$OPT:")[0]
            for opt in opts:
                for i in ("decryption_key", "cryptokey"):
                    if f"{i}=" in opt:
                        key_match = re.findall(rf"{i}=([0-9a-zA-Z]{{{KEY_LEN}}})", opt)
                        if key_match:
                            key = key_match[0]
    except Exception:
        logger.warning("DRM key extraction from URL failed")
        logger.warning(traceback.format_exc())
    if not isinstance(key, str):
        logger.warning("Extracted DRM key is not a string")
        key = ""
    return url, key


def convert_kid_to_license_server_format(kid):
    step1 = kid.replace("-", "")
    step2 = binascii.unhexlify(step1)
    step3 = base64.urlsafe_b64encode(step2).decode("utf-8").replace("==", "")
    return step3


def convert_key(key, url, useragent, referer):
    if key.startswith("__LICENSE_URL_"):
        if threading.current_thread() == threading.main_thread():
            show_exception(
                "drm.convert_key is running in main thread. "
                "This should not happen! Aborting operation."
            )
            return ""
        logger.info("Needs connection to license URL")

        headers = {"User-Agent": useragent}
        if referer:
            headers["Referer"] = referer
            originURL = ""
            if referer.endswith("/"):
                originURL = referer[:-1]
            if originURL:
                headers["Origin"] = originURL

        logger.info("Fetching MPD...")
        req = request(url, method="GET", headers=headers, stream=True, timeout=(35, 35))

        logger.info("Parsing XML...")
        kid = ""
        license_url = ""
        for event, elem in iterparse(io.BytesIO(req.content)):
            if event == "end":
                if (
                    elem.tag.lower().endswith("laurl")
                    and key == "__LICENSE_URL_PROVIDED_BY_MANIFEST__"
                    and (
                        elem.text.strip().startswith("http://")
                        or elem.text.strip().startswith("https://")
                    )
                    and not license_url
                ):
                    license_url = elem.text.strip()
                if "{urn:mpeg:cenc:2013}default_KID" in elem.attrib and not kid:
                    kid = elem.attrib["{urn:mpeg:cenc:2013}default_KID"]
                if "{urn:mpeg:cenc:2013}default_kid" in elem.attrib and not kid:
                    kid = elem.attrib["{urn:mpeg:cenc:2013}default_kid"]
        if kid:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"KID: {kid}")
            logger.info("Converting KID to license request format...")
            kid = convert_kid_to_license_server_format(kid)
        else:
            logger.warning("KID NOT FOUND!")
            raise Exception("KID NOT FOUND!")

        if key.startswith("__LICENSE_URL__"):
            logger.info("License URL is defined")
            license_url = key.replace("__LICENSE_URL__", "", 1)
        elif key == "__LICENSE_URL_PROVIDED_BY_MANIFEST__":
            logger.info("License URL is provided by manifest")

        if not license_url:
            logger.warning("Cannot determine license URL!")
            raise Exception("Cannot determine license URL!")
        else:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"License URL: {license_url}")

            logger.info("Sending license request to the server...")
            license_request = {"kids": [kid], "type": "temporary"}
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"License request: {str(license_request)}")

            req = request(
                license_url,
                method="POST",
                headers=headers,
                json=license_request,
                stream=True,
                timeout=(35, 35),
            )
            logger.info(f"Status code: {req.status_code}")
            content = req.content
            logger.info(f"{len(content)} bytes")
            content = content.decode("utf-8")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Response: {content}")

            logger.info("Parsing key...")
            _key = parse_keys(json.loads(content))
            if _key:
                key = _key
            else:
                logger.warning("Cannot parse key!")
                raise Exception("Cannot parse key!")
    return key
