#!/bin/bash

########################################################################
# To get this to work please do the following:
#   a) Modify the Site Specific Settings to match your site
#   b) Make sure that this script and the python script
#      "merge_json_files.py" are in the same directory.
#   c) Make sure the module command is defined by using $BASH_ENV
#      or define the module command here.
#   d) Make sure that LMOD_DIR is defined as well.
#
########################################################################
#  Site Specific Setting
########################################################################


  BASE_MODULE_PATH=/opt/apps/modulefiles/Core:/opt/apps/lmod/lmod/modulefiles/Core

  ADMIN_DIR=/opt/moduleData/
  RmapDir=$ADMIN_DIR/reverseMapD

  PrgEnvA=("PrgEnv-cray"  "PrgEnv-gnu" "PrgEnv-intel")

  moduleA=( "PrgEnv-cray/5.0.15"     "PrgEnv-gnu/5.0.15"   "PrgEnv-intel/5.0.15"
            "PrgEnv-cray/5.1.18"     "PrgEnv-gnu/5.1.18"   "PrgEnv-intel/5.1.18"
            "PrgEnv-cray/5.1.29"     "PrgEnv-gnu/5.1.29"   "PrgEnv-intel/5.1.29")


  #########################################################################
  # must define the module command and $LMOD_DIR:
  #########################################################################

  if [ -f "$BASH_ENV" ]; then
    source $BASH_ENV
  fi



########################################################################
#  End Site Specific Setting
########################################################################

SCRIPTDIR=$(cd $(dirname $(readlink -f $0)) && pwd)
PATH=$SCRIPTDIR:$LMOD_DIR:$PATH

cd $RmapDir

for m in "${moduleA[@]}"; do
    sn=$(dirname $m)
    v=${m##*/}
    
    module unload "${PrgEnvA[@]}"
    module load $m

    spider --preload -o jsonReverseMapT $BASE_MODULE_PATH | python -mjson.tool >  rmapT_${sn}_${v}.JSON

done

OLD=$RmapDir/jsonReverseMapT.old.json
NEW=$RmapDir/jsonReverseMapT.new.json
RESULT=$RmapDir/jsonReverseMapT.json

merge_json_files.py rmapT_${sn}_${v}.JSON > $NEW
if [ "$?" = 0 ]; then
  chmod 644 $NEW
  if [ -f $RESULT ]; then
    cp -p $RESULT $OLD
  fi
  mv $NEW $RESULT
fi

rm rmapT_*.JSON





