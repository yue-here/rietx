#!/bin/zsh
GP=~/Code/rietx-bench/tools/gsas2/GSAS-II-5.8.4/pixi/.pixi/envs/default/bin/python
HERE=${0:A:h}; mkdir -p $HERE/g2; cd $HERE/g2
for s in seed carry seedlin; do for m in default presses dm tight; do
  $GP -I -u $HERE/g2cpd.py run6 $m $s > run6_${s}_$m.log 2>&1; grep "^RUN6" run6_${s}_$m.log | cut -c1-300
done; done
