## Ubuntu with Nvdia
```
version: '3.9'

services:
    base-os-cuda.humble.user:
        # depends_on:
        #     - base-os-cuda.humble.dep
        build:
            context: .
            dockerfile: Dockerfile.user
            args:
                - BASE_IMAGE=base-os-cuda.humble.dep
        image: base-os-cuda.humble.user
        user: admin:1000
        deploy:
            resources:
                reservations:
                    devices:
                        - driver: nvidia
                          count: all
                          capabilities: [gpu]
        stdin_open: true
        privileged: true
        tty: true
        network_mode: "host"
        volumes:
            - /tmp/.X11-unix:/tmp/.X11-unix:ro
            - /etc/localtime:/etc/localtime:ro
            - ../../src:/home/admin/colcon_ws/src # workspace file
        environment:
            - DISPLAY=$DISPLAY
            - NVIDIA_VISIBLE_DEVICES=all
            - NVIDIA_DRIVER_CAPABILITIES=all
        entrypoint: /usr/local/bin/scripts/workspace-entrypoint.sh
        command: tail -f /dev/null # bash -c "top"
```

## Windows with Nvidia
For installation: [docker_gui_windows11](https://github.com/prachandabhanu/docker_gui_windows11.git)

```
version: '3.9'

services:
    base-os-cuda.humble.dep.user:
        # depends_on:
        #     - base-os-cuda.humble.dep
        build:
            context: .
            dockerfile: Dockerfile.user
            args:
                - BASE_IMAGE=base-os-cuda.humble.dep
        image: base-os-cuda.humble.dep.user
        user: admin:1000
        deploy:
            resources:
                reservations:
                    devices:
                        - driver: nvidia
                          count: all
                          capabilities: [gpu]
        stdin_open: true
        privileged: true
        tty: true
        network_mode: "host"
        volumes:
            - \\wsl.localhost\Ubuntu-20.04\mnt\wslg:/tmp
            - ../../kuka_iiwa7_ros2:/home/admin/colcon_ws/src
        environment:
            - DISPLAY=:0
            - NVIDIA_VISIBLE_DEVICES=all
            - NVIDIA_DRIVER_CAPABILITIES=all
        entrypoint: /usr/local/bin/scripts/workspace-entrypoint.sh
        command: tail -f /dev/null # bash -c "top"
```
