# Install script for directory: C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0/install")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "Release")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "FALSE")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for each subdirectory.
  include("C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0/build/source/Lib/TLibCommon/cmake_install.cmake")
  include("C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0/build/source/Lib/TLibCommonAnalyser/cmake_install.cmake")
  include("C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0/build/source/Lib/TLibDecoder/cmake_install.cmake")
  include("C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0/build/source/Lib/TLibDecoderAnalyser/cmake_install.cmake")
  include("C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0/build/source/Lib/TLibEncoder/cmake_install.cmake")
  include("C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0/build/source/Lib/Utilities/cmake_install.cmake")
  include("C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0/build/source/App/TAppDecoder/cmake_install.cmake")
  include("C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0/build/source/App/TAppDecoderAnalyser/cmake_install.cmake")
  include("C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0/build/source/App/TAppEncoder/cmake_install.cmake")
  include("C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0/build/source/App/TAppMCTSExtractor/cmake_install.cmake")
  include("C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0/build/source/App/Parcat/cmake_install.cmake")
  include("C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0/build/source/App/SEIRemovalApp/cmake_install.cmake")
  include("C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0/build/source/App/SEIFilmGrainApp/cmake_install.cmake")

endif()

if(CMAKE_INSTALL_COMPONENT)
  set(CMAKE_INSTALL_MANIFEST "install_manifest_${CMAKE_INSTALL_COMPONENT}.txt")
else()
  set(CMAKE_INSTALL_MANIFEST "install_manifest.txt")
endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
file(WRITE "C:/Users/ricar/dev/mpeg-gsc-tmcv-m73294/dependencies/HM-18.0/build/${CMAKE_INSTALL_MANIFEST}"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
