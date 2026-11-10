#!/bin/bash
# model_drive.sh [ctrl|disk] - the NVMe drive that holds the model files (strata-compare/models), found from the mount,
# not by number: NVMe names change between boots (11-03: since the 10-31 boot nvme0 = the WD SN7xx on the chipset with
# /boot/efi; the Samsung 9100 PRO with the models = nvme1). ctrl -> e.g. nvme1 (hwmon / /sys/class/nvme), disk -> nvme1n1.
src=$(df --output=source /home/USER/ai-speed-testing/strata-compare/models | tail -1)
disk=$(lsblk -no PKNAME "$src" | head -1)
[ "${1:-ctrl}" = disk ] && echo "$disk" || echo "${disk%n[0-9]*}"
