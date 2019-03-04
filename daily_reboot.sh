#!/usr/bin/env bash
#This script fetches the current state of the photup service. If its not running, then the 
# system does a reboot. This is called as a cronjob to occur daily at 6am.

if [ "$(systemctl show -p SubState --value photup)" != "running" ]; then
    echo "Photup is not running - moving forward and rebooting system"
    /sbin/reboot
else
    echo "Photup is still running - not rebooting this time. Try again tomorrow!"
fi




