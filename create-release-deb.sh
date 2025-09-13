#!/usr/bin/env bash
set -Eeuo pipefail
dpkg-buildpackage -uc -b
