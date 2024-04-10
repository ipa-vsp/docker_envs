# ROS Network Configuration

1. Choose device ip from `ifconfig`

## Azure Kinect Docker
Currently Azure kinect driver only available for Ubuntu 18.04.
1. Build the image `cd azure` and `docker-compose up --build`. This should open the `k4aviewer`.
2. Please set your `ROS_IP` eviroment variable.
3. Run `docker-compose -f docker-compose-user.yml up`. Open two containers
    - First container launches ROS Azure Kinect driver.
    - Second Container launches RVIZ to visualize the camera data.
