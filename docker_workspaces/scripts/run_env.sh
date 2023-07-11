#!/bin/bash

ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source $ROOT/print_color.sh

ON_EXIT=()
function cleanup {
    for command in "${ON_EXIT[@]}"
    do
        $command &>/dev/null
    done
}
trap cleanup EXIT

help()
{
    echo ""
    echo "Usage: $0 -o 22.04|20.04|18.04|16.04 -v humble|rolling|noetic|kinetic -u manipulation|navigation|both -s true|false -i image_name -b|-r -w dev_ws"
    echo -e "\t-o Select OS version 22.04 or 20.04"
    echo -e "\t-v Select ROS version"
    echo -e "\t-u Select usage of the image"
    echo -e "\t-s Enable simulation"
    echo -e "\t-i Image Name"
    echo -e "\t-b Build mode"
    echo -e "\t-r Run mode"
    echo -e "\t-w Attach your workspace only required while run (-r)"
    echo -e "\t-h Show help"
    exit 1
}

while getopts "o:v:u:s:i:w:brh" opt
do
    case "$opt" in
        o) OS_VERSION="$OPTARG" ;;
        v) ROS_VERSION="$OPTARG" ;;
        u) ROS_USAGE="$OPTARG" ;;
        s) SIMULATION="$OPTARG" ;;
        i) FINAL_IMAGE="$OPTARG" ;;
        b) BUILD=true ;;
        r) RUN=true ;;
        w) WORKSPACE="$OPTARG" ;;
        h | ?) help ;;
    esac
done

if [[ -z "$OS_VERSION" ]]; then
    echo "Select ROS Version | Default: rolling"
    OS_VERSION="22.04"
fi

if [[ -z "$ROS_VERSION" ]]; then
    echo "Select ROS Version | Default: rolling"
    ROS_VERSION=""
fi

if [[ -z "$ROS_USAGE" ]]; then
    echo "Select the docker usage| Default: manipulation"
    ROS_USAGE=""
fi

if [[ -z "$FINAL_IMAGE" ]]; then
    echo "Provide Image Name mandatory"
    help
fi

if [[ -z "$SIMULATION" ]]; then
    echo "Default simulation is disable in the docker image"
    SIMULATION=false
fi

if [[ -z "$BUILD" ]]; then
    BUILD=false
fi

if [[ -z "$RUN" ]]; then
    RUN=false
fi

DOCKER_COMMON_DIR="${ROOT}/../common"
DOCKER_COMMON_SEARCH_DIR=(${DOCKER_COMMON_DIR})
BASE_FILE="${DOCKER_COMMON_SEARCH_DIR}/Dockerfile.base"
IMAGE_NAME="myenvos:${OS_VERSION}"


if [[ "$BUILD" == false && "$RUN" == false ]] || [[ "$BUILD" == true && "$RUN" == true ]]; then
    echo "You must specify either a build(-b) or run(-r) mode"
    help
elif [[ "$BUILD" == true ]]; then
    ${ROOT}/build_image.sh $BASE_FILE $OS_VERSION $IMAGE_NAME

    if [[ "$ROS_VERSION" == "rolling" ]]; then
        print_warning "Rolling"
        DOCKER_DIR="${ROOT}/../ros2"
        DOCKER_SEARCH_DIR=(${DOCKER_DIR})
        DOCKERFILE="${DOCKER_SEARCH_DIR}/Dockerfile.rolling"
        if [[ -f "${DOCKERFILE}" ]]; then
            BASE="${IMAGE_NAME}"
            IMAGE_NAME="${IMAGE_NAME}.rolling"
            ${ROOT}/build_image.sh $DOCKERFILE $BASE $IMAGE_NAME
        fi
    elif [[ "$ROS_VERSION" == "humble" ]]; then
        print_warning "Humble"
        DOCKER_DIR="${ROOT}/../ros2"
        DOCKER_SEARCH_DIR=(${DOCKER_DIR})
        DOCKERFILE="${DOCKER_SEARCH_DIR}/Dockerfile.humble"
        if [[ -f "${DOCKERFILE}" ]]; then
            BASE="${IMAGE_NAME}"
            IMAGE_NAME="${IMAGE_NAME}.humble"
            ${ROOT}/build_image.sh $DOCKERFILE $BASE $IMAGE_NAME
        fi
    elif [[ "$ROS_VERSION" == "noetic" ]]; then
        DOCKER_DIR="${ROOT}/../ros1"
        DOCKER_SEARCH_DIR=(${DOCKER_DIR})
        DOCKERFILE="${DOCKER_SEARCH_DIR}/Dockerfile.noetic"
        if [[ -f "${DOCKERFILE}" ]]; then
            BASE="${IMAGE_NAME}"
            IMAGE_NAME="${IMAGE_NAME}.noetic"
            ${ROOT}/build_image.sh $DOCKERFILE $BASE $IMAGE_NAME
        fi
    elif [[ "$ROS_VERSION" == "kinetic" ]]; then
        DOCKER_DIR="${ROOT}/../ros1"
        DOCKER_SEARCH_DIR=(${DOCKER_DIR})
        DOCKERFILE="${DOCKER_SEARCH_DIR}/Dockerfile.kinetic"
        if [[ -f "${DOCKERFILE}" ]]; then
            BASE="${IMAGE_NAME}"
            IMAGE_NAME="${IMAGE_NAME}.kinetic"
            ${ROOT}/build_image.sh $DOCKERFILE $BASE $IMAGE_NAME
        fi
    else
        print_warning "ROS version is not selected. Check your command again!"
    fi

    if [[ "$ROS_USAGE" == "manipulation" ]]; then
        DOCKERFILE="${DOCKER_COMMON_SEARCH_DIR}/Dockerfile.moveit"
        if [[ -f "${DOCKERFILE}" ]]; then
            BASE="${IMAGE_NAME}"
            IMAGE_NAME="${IMAGE_NAME}.moveit"
            ${ROOT}/build_image.sh $DOCKERFILE $BASE $IMAGE_NAME
        fi
    elif [[ "$ROS_USAGE" == "navigation" ]]; then
        DOCKERFILE="${DOCKER_COMMON_SEARCH_DIR}/Dockerfile.nav2"
        if [[ -f "${DOCKERFILE}" ]]; then
            BASE="${IMAGE_NAME}"
            IMAGE_NAME="${IMAGE_NAME}.nav2"
            ${ROOT}/build_image.sh $DOCKERFILE $BASE $IMAGE_NAME
        fi
    elif [[ "$ROS_USAGE" == "both" ]]; then
        DOCKERFILE="${DOCKER_COMMON_SEARCH_DIR}/Dockerfile.both"
        if [[ -f "${DOCKERFILE}" ]]; then
            BASE="${IMAGE_NAME}"
            IMAGE_NAME="${IMAGE_NAME}.both"
            ${ROOT}/build_image.sh $DOCKERFILE $BASE $IMAGE_NAME
        fi
    else
        print_warning "Check your command again!"
    fi

    if [[ "$SIMULATION" == true ]]; then
        DOCKERFILE="${DOCKER_COMMON_SEARCH_DIR}/Dockerfile.gazebo"
        if [[ -f "${DOCKERFILE}" ]]; then
            BASE="${IMAGE_NAME}"
            IMAGE_NAME="${IMAGE_NAME}.gazebo"
            ${ROOT}/build_image.sh $DOCKERFILE $BASE $IMAGE_NAME
        fi
    fi

    DOCKERFILE="${DOCKER_COMMON_SEARCH_DIR}/Dockerfile.user"
    if [[ -f "${DOCKERFILE}" ]]; then
        ${ROOT}/build_image.sh $DOCKERFILE $IMAGE_NAME $FINAL_IMAGE
    fi

elif [[ "$RUN" == true ]]; then
    if [[ -z "$WORKSPACE" ]]; then
        echo "Workspace path is not selected"
        echo $WORKSPACE
        help
    fi
    CONTAINER="${FINAL_IMAGE}_container"

    DOCKER_ARGS=()
    DOCKER_ARGS+=("-e DISPLAY=$DISPLAY")
    DOCKER_ARGS+=("-v /tmp/.X11-unix:/tmp/.X11-unix:ro")
    DOCKER_ARGS+=("-v $HOME/.Xauthority:/home/admin/.Xauthority:rw")
    DOCKER_ARGS+=("-v /etc/timezone:/etc/timezone:ro")
    DOCKER_ARGS+=("-v /etc/localtime:/etc/localtime:ro")
    DOCKER_ARGS+=("-v $WORKSPACE:/home/admin/colcon_ws:rw")

    if type nvidia-smi &>/dev/null; then
        GPU_ATTACHED=(`nvidia-smi -a | grep "Attached GPUs"`)
        if [ ! -z $GPU_ATTACHED ]; then
            DOCKER_ARGS+=("--gpus=all")
            DOCKER_ARGS+=("-e NVIDIA_VISIBLE_DEVICES=all")
            DOCKER_ARGS+=("-e NVIDIA_DRIVER_CAPABILITIES=all")
            print_info "Using nvidia GPU"
        fi
    fi

    docker run -it \
               --rm \
               --net=host \
               --privileged \
               --user="admin:1000" \
               --entrypoint /usr/local/bin/scripts/workspace-entrypoint.sh \
               --name "$CONTAINER" \
               ${DOCKER_ARGS[@]} \
               $FINAL_IMAGE \
               bash
fi

function usage() {
    print_info "Author: Vishnuprasad Prachandabhanu"
}

usage
exit 0
