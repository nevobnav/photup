#!/usr/bin/env bash
#This script fetches the current state of the photup service. If its not running, then the 
# system does a reboot. This is called as a cronjob to occur daily at 6am.

DATE=`date '+%Y-%m-%d %H:%M:%S'`
if [ "$(systemctl show -p SubState --value photup)" != "running" ]; then
    echo "$DATE - Photup is not running - moving forward and rebooting system"
    /sbin/reboot
else
    echo "$DATE - Photup is still running - not rebooting this time. Try again tomorrow!"
fi




