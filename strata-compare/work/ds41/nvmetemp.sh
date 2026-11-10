#!/bin/bash
# nvmetemp.sh - 10-23 (the user): the model drive's temperature every 30 s during the DeepSeek arms (no sudo: the kernel's
# nvme hwmon). nvme0 = Samsung SSD 9100 PRO 2TB (the model files): Composite (temp1, warning 83 C = where its thermal
# throttling starts, critical 87 C, temp1_alarm = the drive's critical-temperature warning bit), Sensor 1 / 2, and the
# drive's read rate over the 30 s (/sys/block/$(bash /home/USER/ai-speed-testing/strata-compare/work/ds41/model_drive.sh disk)/stat). SMART's throttle counters need root (/dev/nvme0 is 0600).
# Log: logs/ds41/nvme-temp.tsv. Ends after 8 h (or $1 hours; 10-25: 24 for the rest of the round) or when
# tmp/ds41-nvmetemp.stop exists.
SC=/home/USER/ai-speed-testing/strata-compare; L=$SC/logs/ds41/nvme-temp.tsv
H=$(for h in /sys/class/hwmon/hwmon*; do [ "$(cat $h/name 2>/dev/null)" = nvme ] && [ "$(readlink -f $h/device | sed 's#.*/##')" = $(bash /home/USER/ai-speed-testing/strata-compare/work/ds41/model_drive.sh) ] && echo $h; done | head -1)
[ -n "$H" ] || { echo "no hwmon for nvme0"; exit 1; }
[ -s $L ] || echo -e "time\tcomposite_c\tsensor1_c\tsensor2_c\talarm\tread_MBps" > $L
rm -f $SC/tmp/ds41-nvmetemp.stop
prev=$(awk '{print $3}' /sys/block/$(bash /home/USER/ai-speed-testing/strata-compare/work/ds41/model_drive.sh disk)/stat); end=$(( $(date +%s) + ${1:-8} * 3600 ))
while [ $(date +%s) -lt $end ] && [ ! -e $SC/tmp/ds41-nvmetemp.stop ]; do
  sleep 30
  cur=$(awk '{print $3}' /sys/block/$(bash /home/USER/ai-speed-testing/strata-compare/work/ds41/model_drive.sh disk)/stat)
  echo -e "$(date '+%F %T')\t$(( $(cat $H/temp1_input) / 1000 ))\t$(( $(cat $H/temp2_input 2>/dev/null || echo 0) / 1000 ))\t$(( $(cat $H/temp3_input 2>/dev/null || echo 0) / 1000 ))\t$(cat $H/temp1_alarm 2>/dev/null || echo -)\t$(( (cur - prev) * 512 / 30 / 1000000 ))" >> $L
  prev=$cur
done
