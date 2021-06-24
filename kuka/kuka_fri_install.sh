#!/bin/bash

echo "[----------> SpaceVecAlg <------------------]"
cd 
git clone --recursive https://github.com/costashatz/SpaceVecAlg.git
cd SpaceVecAlg
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release -DENABLE_SIMD=ON -DPYTHON_BINDING=OFF ..
make -j$(nproc)
make install

echo "[----------> RBDyn <------------------]"
cd 
git clone --recursive https://github.com/costashatz/RBDyn.git
cd RBDyn
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release -DENABLE_SIMD=ON -DPYTHON_BINDING=OFF ..
make -j$(nproc)
make install

echo "[----------> mc_rbdyn_urdf <------------------]"
cd 
git clone --recursive https://github.com/costashatz/mc_rbdyn_urdf.git
cd mc_rbdyn_urdf
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release -DENABLE_SIMD=ON -DPYTHON_BINDING=OFF ..
make -j$(nproc)
make install

echo "[----------> corrade <------------------]"
cd 
git clone https://github.com/mosra/corrade.git
cd corrade
mkdir build && cd build
cmake ..
make -j$(nproc)
make install

echo "[----------> robot_controllers <------------------]"
cd 
git clone https://github.com/epfl-lasa/robot_controllers.git
cd robot_controllers
mkdir build && cd build
cmake ..
make -j$(nproc)
make install