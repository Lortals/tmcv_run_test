#!/bin/bash

CURDIR=$( cd "$( dirname "$0" )" && pwd ) 
MAINDIR=$( dirname ${CURDIR} )
echo -e "\033[0;32m$0: ${MAINDIR}  \033[0m"

# Parameters
OUTDIR=$( dirname ${MAINDIR} )/test_quantize
SRCPLY=/g/gs/mpeg_20250707/m71763_bartender_stable/track_pos/frame%03d_pos.ply
RENDERPATH=$(dirname ${MAINDIR})/mpeg-3d-renderer/bin/windows/Release/PccAppRenderer.exe
PREPROCESSPATH=$(dirname ${MAINDIR})/mpeg-gsc-tools/pre_post_processing/gs_pre_process.py
POSTPROCESSPATH=$(dirname ${MAINDIR})/mpeg-gsc-tools/pre_post_processing/gs_post_process.py

# Check
if [ ! -f ${RENDERPATH}      ] ; then echo "${RENDERPATH     } not exists"; exit -1; fi
if [ ! -f ${PREPROCESSPATH}  ] ; then echo "${PREPROCESSPATH } not exists"; exit -1; fi
if [ ! -f ${POSTPROCESSPATH} ] ; then echo "${POSTPROCESSPATH} not exists"; exit -1; fi

# Functions
function formatCmd() {
  local f=${1}
  for s in ${2}; do
    if [ $s == "--" ]; then
      f=${f//${s}/ \\\\\\n    ${s}}
    else
      f=${f// ${s}/ \\\\\\n   ${s}}
    fi
  done
  echo -e "$f" | sed 's/ *\\$/ \\/'
}

# Main loops  
IDX=1
for CFG in $( ls ${MAINDIR}/cfg/*/*.cfg )
do 
  TEST=$(basename $( dirname ${CFG}))_$(basename  ${CFG%.???})
  echo -e "\033[0;32m${TEST} ${IDX}\033[0m"  
  TESTDIR=${OUTDIR}/$(printf %02d ${IDX} )_${TEST}
  if [ ! -d ${TESTDIR} ] ; then mkdir -p  ${TESTDIR}; fi
  LOGENC="${TESTDIR}/${TEST}_enc.log"
  LOGDEC="${TESTDIR}/${TEST}_dec.log"

  # Quantize
  if [ ! -f ${OUTDIR}/frame000_q18-12.ply ]     
  then 
    python ${PREPROCESSPATH} \
      -i  $( printf ${SRCPLY} 0 ) \
      -o  ${OUTDIR}/frame000_q18-12.ply \
      -c  ${OUTDIR}/frame000_q18-12.cfg
  else
    echo "  ${OUTDIR}/frame000_q18-12.ply already exists"
  fi

  # Encode
  if [ ! -f "${LOGENC}" ] || ! tail -n 1 "${LOGENC}" | grep -q "^Time:" 
  then 
    echo -e "\033[0;32m$TEST encode \033[0m"
    CMD="python.exe encode.py  \
      -c              ${CFG} \
      -i              ${OUTDIR}/frame000_q18-12.ply \
      -b              ${TESTDIR}/test.v3c \
      -r              ${TESTDIR}/test_rec_%04d.ply \
      --bit_depth_pos 18 \
      --bit_depth_att 12 \
      -n              1 \
      -v "
    formatCmd "$CMD" "-- -c -i -b -r -d -n -v  >" | tee -a "$LOGENC"
    eval "$CMD" 2>&1 | tee -a "$LOGENC"
    if [ "${PIPESTATUS[0]}" != 0 ]; then
      echo "Encoder failed" | tee -a "$LOGENC"
      exit 1
    fi
  else
    echo "  ${LOGENC} already exists"
  fi

  # Decode
  if [ ! -f "${LOGDEC}" ] || ! tail -n 1 "${LOGDEC}" | grep -q "^Time:" 
  then 
    echo -e "\033[0;32m$TEST decode \033[0m"
    CMD="python.exe decode.py  \
      -b              ${TESTDIR}/test.v3c \
      -d              ${TESTDIR}/test_dec_%04d.ply \
      -v "
    formatCmd "$CMD" "-- -c -i -b -r -d -n -v  >" | tee -a "$LOGDEC"
    eval "$CMD" 2>&1 | tee -a "$LOGDEC"
    if [ "${PIPESTATUS[0]}" != 0 ]; then
      echo "Decoder failed" | tee -a "$LOGDEC"
      exit 1
    fi
  else
    echo "  ${LOGDEC} already exists"
  fi

  # Dequantize
  if [ ! -f ${TESTDIR}/test_dec_0000_dequant.ply ]     
  then 
    python ${POSTPROCESSPATH} \
      -i  $( printf ${TESTDIR}/test_dec_%04d.ply 0 ) \
      -o  $( printf ${TESTDIR}/test_dec_%04d_dequant.ply 0 ) \
      -c  ${OUTDIR}/frame000_q18-12.cfg
  else
    echo "  ${TESTDIR}/test_dec_%04d_dequant already exists"
  fi

  # Renderer
  ${RENDERPATH} \
    -f ${TESTDIR}/test_dec_%04d_dequant.ply \
    -g 1  \
    --SrcFile=${SRCPLY} 

  IDX=$(( IDX + 1)) 
done