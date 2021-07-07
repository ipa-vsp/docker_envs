# docker_envs

## GUI with docker
1. Install [Nvidia docker2](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
2. Add `runtime: nvidia` in docker compose
3. If there is problem with GUI in docker then run `xhost +` or `xhost -`
4. To avoid the vulnerablity use this instead of above,
    - `xhost +SI:localuser:$(id -un)`
    - To allow root in container access to X, run `xhost +SI:localuser:root`

## GUI with docker in Windows
1. Download [VcXsrv](https://sourceforge.net/projects/vcxsrv/) and install.
  - check the box **Disable access control**

Possible ros containers
```
version: '2'
services:
  master:
    build: .
    container_name: master
    command:
      - roscore
    environment:
      - "ROS_IP=172.19.0.100"
    networks:
      ros_net:
        ipv4_address: 172.19.0.100
    ports:
      - "11311:11311"
      - "33690:33690"

  talker:
    build: .
    container_name: talker
    environment:
      - "ROS_IP=172.19.0.101"
      - "ROS_MASTER_URI=http://172.19.0.100:11311"
    command: rosrun roscpp_tutorials talker
    networks:
      ros_net:
        ipv4_address: 172.19.0.101

  listener:
    build: .
    container_name: listener
    environment:
      - "ROS_IP=172.19.0.102"
      - "ROS_MASTER_URI=http://172.19.0.100:11311"
    command: rosrun roscpp_tutorials listener
    networks:
      ros_net:
        ipv4_address: 172.19.0.102

networks:
  ros_net:
    driver: bridge
    ipam:
      driver: default
      config:
      - subnet: 172.19.0.0/24
        gateway: 172.19.0.1
```