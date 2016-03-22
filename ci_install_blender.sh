#!/bin/sh
if [ ! -e "blender/blender" ]; then
    mkdir blender

    # download the newest blender version
    wget http://download.blender.org/release/Blender2.77/blender-2.77-linux-glibc211-x86_64.tar.bz2

    # Extract the archive
    tar jxf blender-2.77-linux-glibc211-x86_64.tar.bz2 -C blender --strip-components 1

fi