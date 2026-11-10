#!/bin/bash
# ssdlog.sh — round 15: every 10 s the model SSD's temperatures (Samsung 9100 PRO, nvme1: composite / sensor 1 / sensor 2,
# sysfs hwmon, no sudo) and its cumulative read / write sectors (/proc/diskstats) -> logs/r15/ssd.csv
WS=/home/USER/ai-speed-testing/strata-compare; OUT=$WS/logs/r15/ssd.csv
H=/sys/class/nvme/nvme1/hwmon2
[ -f $OUT ] || echo "time,composite_c,sensor1_c,sensor2_c,read_gb_cum,write_gb_cum" > $OUT
echo $$ > $WS/tmp/r15/ssdlog.pid
while true; do
  r=$(awk '$3=="nvme1n1" {printf "%.3f,%.3f", $6*512/1e9, $10*512/1e9}' /proc/diskstats)
  echo "$(date -Is),$(( $(cat $H/temp1_input) / 1000 )),$(( $(cat $H/temp2_input) / 1000 )),$(( $(cat $H/temp3_input) / 1000 )),$r" >> $OUT
  sleep 10
done
