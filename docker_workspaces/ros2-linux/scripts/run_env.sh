#!/bin/bash

ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source $ROOT/print_color.sh

function usage(){
    print_info "Usage: run_env.sh"
    print_info "Author: Vishnuprasad Prachandabhanu"
}

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
    echo "Usage: $0 -v humble|rolling -u manipulation|navigation|both -s true|false -i image_name -b|-r"
    echo -e "\t-v Select ROS version"
    echo -e "\t-u Select usage of the image"
    echo -e "\t-s Enable simulation"
    echo -e "\t-i Image Name"
    echo -e "\t-b Build mode"
    echo -e "\t-r Run mode"
    echo -e "\t-h Show help"
    exit 1
}

while getopts "v:u:s:i:brh" opt
do
    case "$opt" in
        v) ROS_VERSION="$OPTARG" ;;
        u) ROS_USAGE="$OPTARG" ;;
        s) SIMULATION="$OPTARG" ;;
        i) FINAL_IMAGE="$OPTARG" ;;
        b) BUILD=true ;;
        r) RUN=true ;;
        h | ?) help ;;
    esac
done

if [[ -z "$ROS_VERSION" ]]; then
    echo "Select ROS Version"
    help
fi

if [[ -z "$ROS_USAGE" ]]; then
    echo "Select the docker usage is mandatory"
    help
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

# DOCKERFILES=()
DOCKER_COMMON_DIR="${ROOT}/../common"
DOCKER_COMMON_SEARCH_DIR=(${DOCKER_COMMON_DIR})
BASE_FILE="${DOCKER_COMMON_SEARCH_DIR}/Dockerfile.base"
IMAGE_NAME="ubuntu2204"
${ROOT}/build_image.sh $BASE_FILE "" $IMAGE_NAME
DOCKERFILES+=(${BASE_FILE})

if [[ "$BUILD" == false && "$RUN" == false ]] || [[ "$BUILD" == true && "$RUN" == true ]]; then
    echo "You must specify either a build(-b) or run(-r) mode"
    help
elif [[ "$BUILD" == true ]]; then
    if [[ "$ROS_VERSION" == "rolling" ]]; then
        DOCKER_DIR="${ROOT}/../rolling"
        DOCKER_SEARCH_DIR=(${DOCKER_DIR})
        DOCKERFILE="${DOCKER_SEARCH_DIR}/Dockerfile.rolling"
        if [[ -f "${DOCKERFILE}" ]]; then
            # DOCKERFILES+=(${DOCKERFILE})
            BASE="${IMAGE_NAME}"
            IMAGE_NAME="${IMAGE_NAME}.rolling"
            ${ROOT}/build_image.sh $DOCKERFILE $BASE $IMAGE_NAME
        fi
    elif [[ "$ROS_VERSION" == "humble" ]]; then
        DOCKER_DIR="${ROOT}/../humble"
        DOCKER_SEARCH_DIR=(${DOCKER_DIR})
        DOCKERFILE="${DOCKER_SEARCH_DIR}/Dockerfile.humble"
        if [[ -f "${DOCKERFILE}" ]]; then
            BASE="${IMAGE_NAME}"
            IMAGE_NAME="${IMAGE_NAME}.humble"
            ${ROOT}/build_image.sh $DOCKERFILE $BASE $IMAGE_NAME
        fi
    else
        print_error "Check your command again!"
        help
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
        print_error "Check your command again!"
        help
    fi
    
    if [[ "$SIMULATION" == true ]]; then
        DOCKERFILE="${DOCKER_COMMON_SEARCH_DIR}/Dockerfile.gazebo"
        if [[ -f "${DOCKERFILE}" ]]; then
            BASE="${BASE}.gazeo"
            ${ROOT}/build_image.sh $DOCKERFILE $BASE
        fi
    fi

    DOCKERFILE="${DOCKER_COMMON_SEARCH_DIR}/Dockerfile.user"
    if [[ -f "${DOCKERFILE}" ]]; then
        ${ROOT}/build_image.sh $DOCKERFILE $IMAGE_NAME $FINAL_IMAGE
    fi
# elif [[ "$RUN" == true ]]; then
fi