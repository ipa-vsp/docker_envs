# docker_envs

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