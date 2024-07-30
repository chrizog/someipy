#!/bin/sh

rm -rf build install
mkdir -p build
cd build
cmake ..
make
make install
cd ..