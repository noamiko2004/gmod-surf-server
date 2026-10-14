#!/usr/bin/env bash
# Run by cron every 15 minutes (deploy.sh installs it). Starts scripts/update.sh
# once something new is out and the server is empty enough: right away when
# nobody is on, after 2 days with 3 or fewer on, after 4 days no matter what.
# The rules are in scripts/updater.py; what it waits for shows on the website's
# admin page and in update.log.
source "$(dirname "$0")/common.sh"
updater auto
