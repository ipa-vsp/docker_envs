#!/bin/bash

# Global variables
ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

function print_warning() {
    echo -e "\033[33mWARNING: $1\033[0m"
}

function print_info() {
    echo -e "\033[32mINFO: $1\033[0m"
}

function cleanup() {
    for command in "${ON_EXIT[@]}"
    do
        $command &>/dev/null
    done
}
trap cleanup EXIT

function help() {
    echo "Usage: $0 [-b|-r] [-o <os_version>] [-v <ros_version>] [-u <ros_usage>] [-s] [-i <image_name>] -w <workspace_path>"
    echo "  -o: OS version (24.04, 22.04, 20.04, 18.04, 16.04) | Default: 24.04"
    echo "  -v: ROS version (rolling, jazzy, iron, humble, isaachumble, noetic, kinetic) | Default: rolling"
    echo "  -u: ROS usage (manipulation, navigation, both, skip) | Default: manipulation"
    echo "  -s: Enable simulation | Default: false"
    echo "  -i: Final image name"
    echo "  -w: Workspace path (mandatory for run mode)"
    echo "  -b: Build image"
    echo "  -r: Run container"
    exit 1
}

# Default values
OS_VERSION="24.04"
ROS_VERSION="rolling"
ROS_USAGE="manipulation"
SIMULATION=false
BUILD=false
RUN=false
FINAL_IMAGE=""

while getopts "o:v:u:i:w:bsr" opt; do
    case $opt in
        o) OS_VERSION=$OPTARG ;;
        v) ROS_VERSION=$OPTARG ;;
        u) ROS_USAGE=$OPTARG ;;
        i) FINAL_IMAGE=$OPTARG ;;
        w) WORKSPACE=$OPTARG ;;
        b) BUILD=true ;;
        r) RUN=true ;;
        s) SIMULATION=true ;;
        h | ?) help ;;
    esac
done

# Basic validations
if [[ "$BUILD" == false && "$RUN" == false ]] || [[ "$BUILD" == true && "$RUN" == true ]]; then
    echo "You must specify either a build(-b) or run(-r) mode"
    help
fi

if [[ "$BUILD" == true && -z "$FINAL_IMAGE" ]]; then
    echo "Provide Image Name mandatory"
    help
fi

# Define and manage Docker images
DOCKER_COMMON_DIR="${ROOT}/../common"
DOCKER_COMMON_SEARCH_DIR=(${DOCKER_COMMON_DIR})
echo "ROS_VERSION: $ROS_VERSION"
if [[ "$ROS_VERSION" == "isaachumble" ]]; then
    BASE_FILE="${DOCKER_COMMON_SEARCH_DIR}/Dockerfile.cuda"
else
    BASE_FILE="${DOCKER_COMMON_SEARCH_DIR}/Dockerfile.base"
fi
IMAGE_NAME="myenvos:${ROS_VERSION}"

# Build section
if [[ "$BUILD" == true ]]; then
    # List all the potential Dockerfiles and their final image names
    echo "Building docker base file $BASE_FILE"
    ${ROOT}/build_image.sh "$BASE_FILE" "$OS_VERSION" "$IMAGE_NAME"
    declare -A DOCKERFILES=( ["rolling"]="${ROOT}/../ros2/Dockerfile.rolling"
                             ["jazzy"]="${ROOT}/../ros2/Dockerfile.jazzy"
                             ["iron"]="${ROOT}/../ros2/Dockerfile.iron"
                             ["humble"]="${ROOT}/../ros2/Dockerfile.humble"
                             ["isaachumble"]="${ROOT}/../ros2/Dockerfile.isaachumble"
                             ["noetic"]="${ROOT}/../ros1/Dockerfile.noetic"
                             ["kinetic"]="${ROOT}/../ros1/Dockerfile.kinetic" )

    DOCKERFILE=${DOCKERFILES[$ROS_VERSION]}
    if [[ -f "$DOCKERFILE" ]]; then
        echo "Building image $IMAGE_NAME"
        BASE="$IMAGE_NAME"
        IMAGE_NAME="$IMAGE_NAME.$ROS_VERSION"
        ${ROOT}/build_image.sh "$DOCKERFILE" "$BASE" "$IMAGE_NAME"
    else
        print_warning "ROS version is not supported. Check your command again!"
    fi

    declare -A USAGE_DOCKERFILES=( ["manipulation"]="${ROOT}/../usage/Dockerfile.moveit"
                                   ["navigation"]="${ROOT}/../usage/Dockerfile.nav2"
                                   ["both"]="${ROOT}/../usage/Dockerfile.both" )


    DOCKERFILE=${USAGE_DOCKERFILES[$ROS_USAGE]}
    if [[ $ROS_USAGE != "skip" ]]; then
        BASE="$IMAGE_NAME"
        IMAGE_NAME="$IMAGE_NAME.$ROS_USAGE"
        echo "Building image $IMAGE_NAME and file $DOCKERFILE"
        ${ROOT}/build_image.sh "$DOCKERFILE" "$BASE" "$IMAGE_NAME"
    fi

    if [[ "$SIMULATION" == true ]]; then
        DOCKERFILE="${DOCKER_COMMON_SEARCH_DIR}/Dockerfile.gazebo"
        if [[ -f "$DOCKERFILE" ]]; then
            BASE="$IMAGE_NAME"
            IMAGE_NAME="$IMAGE_NAME.gazebo"
            ${ROOT}/build_image.sh "$DOCKERFILE" "$BASE" "$IMAGE_NAME"
        fi
    fi

    DOCKERFILE="${DOCKER_COMMON_SEARCH_DIR}/Dockerfile.user"
    if [[ -f "$DOCKERFILE" ]]; then
        ${ROOT}/build_image.sh "$DOCKERFILE" "$IMAGE_NAME" "$FINAL_IMAGE"
    fi
fi

# Run section
if [[ "$RUN" == true ]]; then
    if [[ -z "$WORKSPACE" ]]; then
        echo "Workspace path is not selected"
        help
    fi

    CONTAINER="${FINAL_IMAGE}_container"

    DOCKER_ARGS=(
        "-e DISPLAY=$DISPLAY"
        "-v /tmp/.X11-unix:/tmp/.X11-unix:ro"
        "-v $HOME/.Xauthority:/home/admin/.Xauthority:rw"
        "-v /etc/timezone:/etc/timezone:ro"
        "-v /etc/localtime:/etc/localtime:ro"
        "-v $WORKSPACE:/home/admin/colcon_ws:"
        "-v $WORKSPACE:/home/admin/colcon_ws:rw"
        "--privileged"
        "--name $CONTAINER"
        "--rm"
    )

    # Check if xhost is available and allow local connections to X server
    if command -v xhost &> /dev/null; then
        xhost +local:
        # Store the command to revert xhost changes upon exit
        ON_EXIT+=("xhost -local:")
    else
        print_warning "xhost command not found. GUI might not work properly in Docker."
    fi

    # Actually run the Docker container
    docker run ${DOCKER_ARGS[@]} -it $FINAL_IMAGE bash

    # Cleanup on exit
    if [[ ${#ON_EXIT[@]} -gt 0 ]]; then
        cleanup
    fi
fi
