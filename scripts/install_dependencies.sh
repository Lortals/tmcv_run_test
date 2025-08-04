#!/bin/bash

CURDIR=$( cd "$( dirname "$0" )" && pwd )
DEPDIR=$( dirname ${CURDIR} )/dependencies
echo -e "\033[0;32m$0: ${CURDIR} => ${DEPDIR} \033[0m"

if [ ! -d ${DEPDIR} ] ; then mkdir -p ${DEPDIR}; fi

################################################################################# 
# HM-18.0
################################################################################# 
echo -e "\033[0;32mBuild HM-18.0 \033[0m"
HMDIR=${DEPDIR}/HM-18.0
if [ $( uname ) == "Linux" ]
then
  HMENC=${HMDIR}/bin/TAppEncoderStatic
  HMDEC=${HMDIR}/bin/TAppDecoderStatic
else
  HMENC=${HMDIR}/bin/vs16/msvc-19.29/x86_64/release/TAppEncoder.exe  
  HMDEC=${HMDIR}/bin/vs16/msvc-19.29/x86_64/release/TAppDecoder.exe  
fi 

# Clone 
if [ ! -d ${HMDIR} ]
then 
  git clone https://vcgit.hhi.fraunhofer.de/jvet/HM.git -b HM-18.0 ${HMDIR}
else 
  echo "${HMDIR} already exist"
fi 

# Build HM with HIGH_BITDEPTH for 12 bits depth
if [ ! -f ${HMENC} ]
then 
  mkdir ${HMDIR}/build   
  cmake -H${HMDIR} -B${HMDIR}/build -DHIGH_BITDEPTH=OFF
  cmake --build ${HMDIR}/build --config Release --parallel ${NUMBER_OF_PROCESSORS}
  if [ $( uname ) == "Linux" ]; then chmod 755 ${HMENC} ${HMDEC}; fi
else
  echo "${HMBIN} already exist"
fi

################################################################################# 
# VTM 23.11
################################################################################# 

echo -e "\033[0;32mBuild VTM 23.11 \033[0m"
VTMDIR=${DEPDIR}/VTM-23.11 
if [ $( uname ) == "Linux" ]
then
  VTMENC=${VTMDIR}/bin/umake/gcc-9.4/x86_64/release/EncoderApp
  VTMDEC=${VTMDIR}/bin/umake/gcc-9.4/x86_64/release/DecoderApp
else
  VTMENC=${VTMDIR}/bin/vs16/msvc-19.29/x86_64/release/EncoderApp.exe 
  VTMDEC=${VTMDIR}/bin/vs16/msvc-19.29/x86_64/release/DecoderApp.exe 
fi 

# Clone VTM
if [ ! -d ${VTMDIR} ]
then 
  git clone https://vcgit.hhi.fraunhofer.de/jvet/VVCSoftware_VTM.git -b VTM-23.11 ${VTMDIR}
else 
  echo "${VTMDIR} already exist"
fi 

# Build 
if [ ! -f ${VTMENC} ]
then 
  mkdir ${VTMDIR}/build
  cmake -H${VTMDIR} -B${VTMDIR}/build 
  cmake --build ${VTMDIR}/build --config Release --parallel ${NUMBER_OF_PROCESSORS}
  if [ $( uname ) == "Linux" ]; then chmod 755 ${VTMENC} ${VTMDEC}; fi
else
  echo "${VTMENC} already exist"
fi

################################################################################# 
# VTM 23.11 Rext 
################################################################################# 

echo -e "\033[0;32mBuild VTM 23.11 Rext \033[0m"
VTMDIR=${DEPDIR}/VTM-23.11-Rext
if [ $( uname ) == "Linux" ]
then
  VTMREXTENC=${VTMDIR}/bin/umake/gcc-9.4/x86_64/release/EncoderApp
  VTMREXTDEC=${VTMDIR}/bin/umake/gcc-9.4/x86_64/release/DecoderApp
else
  VTMREXTENC=${VTMDIR}/bin/vs16/msvc-19.29/x86_64/release/EncoderApp.exe 
  VTMREXTDEC=${VTMDIR}/bin/vs16/msvc-19.29/x86_64/release/DecoderApp.exe 
fi 

# Clone VTM
if [ ! -d ${VTMDIR} ]
then 
  git clone https://vcgit.hhi.fraunhofer.de/jvet/VVCSoftware_VTM.git -b VTM-23.11 ${VTMDIR}
else 
  echo "${VTMDIR} already exist"
fi 

# Update RExt__HIGH_BIT_DEPTH_SUPPORT
#   from: #define RExt__HIGH_BIT_DEPTH_SUPPORT                      0           
#   to:   #define RExt__HIGH_BIT_DEPTH_SUPPORT                      1         
FILE=${VTMDIR}/source/Lib/CommonLib/TypeDef.h
SRC=
if [ "$( cat ${FILE} | grep "#define RExt__HIGH_BIT_DEPTH_SUPPORT                      1" )" != "" ]
then 
  echo "${FILE} already patched: $( cat ${FILE} | grep "#define RExt__HIGH_BIT_DEPTH_SUPPORT" )"
else
  echo "${FILE} not patch. run sed command"
  sed -i 's/#define RExt__HIGH_BIT_DEPTH_SUPPORT                      0/#define RExt__HIGH_BIT_DEPTH_SUPPORT                      1/' ${FILE}
  if [ "$( cat ${FILE} | grep "#define RExt__HIGH_BIT_DEPTH_SUPPORT                      1" )" != "" ]
  then 
    echo "${FILE} correcly patched: $( cat ${FILE} | grep "#define RExt__HIGH_BIT_DEPTH_SUPPORT" )"
  else
    echo "error the sed command"
    echo "Please edit ${FILE} manualy"
    exit
  fi
fi 

# Update m_pixelPredErr
#   from: m_pixelPredErr\[y\]\[x\] = err \* err;      
#   to:   m_pixelPredErr\[y\]\[x\] = static_cast<int>( err \* err );    
FILE=${VTMDIR}/source/Lib/EncoderLib/EncSlice.cpp
if [ "$( cat ${FILE} | grep "m_pixelPredErr\[y\]\[x\] = static_cast<int>( err \* err );" )" != "" ]
then 
  echo "${FILE} already patched: $( cat ${FILE} | grep "m_pixelPredErr\[y\]\[x\] = static_cast<int>( err * err );" )"
else
  echo "${FILE} not patch. run sed command"
  sed -i 's/m_pixelPredErr\[y\]\[x\] = err \* err;/m_pixelPredErr[y][x] = static_cast<int>( err \* err );/' ${FILE}
  if [ "$( cat ${FILE} | grep "m_pixelPredErr\[y\]\[x\] = static_cast<int>( err \* err );" )" != "" ]
  then 
    echo "${FILE} correcly patched: $( cat ${FILE} | grep "m_pixelPredErr\[y\]\[x\] = static_cast<int>( err \* err );" )"
  else
    echo "error the sed command"
    echo "Please edit ${FILE} manualy"
    exit
  fi
fi 

# Update m_pixelRecDis
#   from: m_pixelRecDis\[y\]\[x\] = err \* err;      
#   to:   m_pixelRecDis\[y\]\[x\] = static_cast<int>( dis \* dis );    
if [ "$( cat ${FILE} | grep "m_pixelRecDis\[y\]\[x\] = static_cast<int>( dis \* dis );" )" != "" ]
then 
  echo "${FILE} already patched: $( cat ${FILE} | grep "m_pixelRecDis\[y\]\[x\] = static_cast<int>( dis * dis );" )"
else
  echo "${FILE} not patch. run sed command"
  sed -i 's/m_pixelRecDis\[y\]\[x\] = dis \* dis;/m_pixelRecDis[y][x] = static_cast<int>( dis \* dis );/' ${FILE}
  if [ "$( cat ${FILE} | grep "m_pixelRecDis\[y\]\[x\] = static_cast<int>( dis \* dis );" )" != "" ]
  then 
    echo "${FILE} correcly patched: $( cat ${FILE} | grep "m_pixelRecDis\[y\]\[x\] = static_cast<int>( dis \* dis );" )"
  else
    echo "error the sed command"
    echo "Please edit ${FILE} manualy"
    exit
  fi
fi 

# Build VTM with RExt__HIGH_BIT_DEPTH_SUPPORT for 16 bits depth
if [ ! -f ${VTMREXTENC} ]
then 
  mkdir ${VTMDIR}/build   
  cmake -H${VTMDIR} -B${VTMDIR}/build 
  cmake --build ${VTMDIR}/build --config Release --parallel ${NUMBER_OF_PROCESSORS}
  if [ $( uname ) == "Linux" ]; then chmod 755 ${VTMREXTENC} ${VTMREXTDEC}; fi
else
  echo "${VTMREXTENC} already exist"
fi

################################################################################# 

echo "HM       ENCODER BINARY PATH = ${HMENC}"
echo "HM       DECODER BINARY PATH = ${HMDEC}"
echo "VTM      ENCODER BINARY PATH = ${VTMENC}"
echo "VTM      DECODER BINARY PATH = ${VTMDEC}"
echo "VTM-Rext ENCODER BINARY PATH = ${VTMREXTENC}"
echo "VTM-Rext DECODER BINARY PATH = ${VTMREXTDEC}"

# Save path in json file
JSON_FILE="${DEPDIR}/binary_path.json"
cat > "$JSON_FILE" <<EOF
{
  "hm": {
    "encoder": "${HMENC}",
    "decoder": "${HMDEC}"
  },
  "vtm": {
    "encoder": "${VTMENC}",
    "decoder": "${VTMDEC}"
  },
  "vtr": {
    "encoder": "${VTMREXTENC}",
    "decoder": "${VTMREXTDEC}"
  }
}
EOF
echo "JSON saved to $JSON_FILE"