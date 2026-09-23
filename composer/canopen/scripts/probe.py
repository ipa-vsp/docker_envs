#!/usr/bin/env python3
"""Behavioral checks for the upstream examples, with bounded ROS waits."""

import math
import sys
import time

import rclpy
from rclpy.qos import qos_profile_sensor_data
from canopen_interfaces.msg import COData
from canopen_interfaces.srv import CORead, COTargetDouble, COWrite
from controller_manager_msgs.srv import ListControllers
from lifecycle_msgs.srv import ChangeState, GetState
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray
from std_srvs.srv import Trigger


class Probe:
    def __init__(self):
        self.node = rclpy.create_node("canopen_example_probe")

    def until(self, predicate, description, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(self.node, timeout_sec=0.1)
            if predicate():
                print(f"PASS {description}", flush=True)
                return
        raise AssertionError(f"Timed out: {description}")

    def call(self, name, service, request=None):
        client = self.node.create_client(service, name)
        try:
            if not client.wait_for_service(timeout_sec=45):
                raise AssertionError(f"Service unavailable: {name}")
            future = client.call_async(request or service.Request())
            self.until(future.done, f"service response: {name}")
            response = future.result()
            if hasattr(response, "success") and not response.success:
                raise AssertionError(f"Unsuccessful response: {name}: {response}")
            return response
        finally:
            self.node.destroy_client(client)

    def controllers(self, expected):
        def active():
            response = self.call("/controller_manager/list_controllers", ListControllers)
            states = {item.name: item.state for item in response.controller}
            return all(states.get(name) == "active" for name in expected)

        self.until(active, f"active controllers: {expected}", timeout=60)

    def feedback(self, topic, message_type, predicate, publisher=None, command=None):
        received = []
        subscription = self.node.create_subscription(
            message_type,
            topic,
            lambda msg: received.append(msg) if predicate(msg) else None,
            qos_profile_sensor_data,
        )
        try:

            def ready():
                if publisher is not None and publisher.get_subscription_count() > 0:
                    publisher.publish(command)
                return bool(received)

            self.until(ready, f"expected feedback on {topic}", timeout=45)
        finally:
            self.node.destroy_subscription(subscription)

    @staticmethod
    def position_predicate(targets):
        def matches(message):
            positions = dict(zip(message.name, message.position))
            return all(
                name in positions
                and math.isfinite(positions[name])
                and abs(positions[name] - target) < 0.05
                for name, target in targets.items()
            )

        return matches

    def service_example(self, lifecycle=False):
        manager = "/lifecycle_manager"
        if lifecycle:
            state = self.call(manager + "/get_state", GetState).current_state.id
            if state == 1:
                request = ChangeState.Request()
                request.transition.id = 1  # configure
                self.call(manager + "/change_state", ChangeState, request)
                state = self.call(manager + "/get_state", GetState).current_state.id
            if state == 2:
                request = ChangeState.Request()
                request.transition.id = 3  # activate
                self.call(manager + "/change_state", ChangeState, request)
            assert self.call(manager + "/get_state", GetState).current_state.id == 3
        # The service example config explicitly places its device under /test1.
        prefix = "/cia402_device_1" if lifecycle else "/test1/cia402_device_1"
        response = self.call(
            prefix + "/sdo_read", CORead, CORead.Request(index=0x1000, subindex=0)
        )
        assert response.data & 0xFFFF == 402, f"Unexpected device type: {response.data:#x}"
        # The lifecycle fixture leaves profile speed/acceleration at zero.
        for index, value in ((0x6081, 1000), (0x6083, 2000)):
            self.call(
                prefix + "/sdo_write",
                COWrite,
                COWrite.Request(index=index, subindex=0, data=value),
            )
        self.call(prefix + "/init", Trigger)
        self.call(prefix + "/position_mode", Trigger)
        self.call(prefix + "/target", COTargetDouble, COTargetDouble.Request(target=0.25))
        self.feedback(
            prefix + "/joint_states",
            JointState,
            self.position_predicate({"cia402_device_1": 0.25}),
        )
        if lifecycle:
            request = ChangeState.Request()
            request.transition.id = 4  # deactivate
            self.call(manager + "/change_state", ChangeState, request)
            assert self.call(manager + "/get_state", GetState).current_state.id == 2
            request.transition.id = 2  # cleanup
            self.call(manager + "/change_state", ChangeState, request)
            assert self.call(manager + "/get_state", GetState).current_state.id == 1

    def proxy_control(self):
        self.controllers(["joint_state_broadcaster", "node_1_controller"])
        # Controller SDO callbacks are upstream stubs; test its implemented PDO path.
        publisher = self.node.create_publisher(COData, "/node_1_controller/tpdo", 10)
        try:
            self.feedback(
                "/node_1_controller/rpdo",
                COData,
                lambda msg: msg.index == 0x4001 and msg.subindex == 0 and msg.data == 200,
                publisher,
                COData(index=0x4000, subindex=0, data=200),
            )
        finally:
            self.node.destroy_publisher(publisher)

    def position_control(self, robot=False):
        expected = ["joint_state_broadcaster", "forward_position_controller"]
        if not robot:
            expected.append("cia402_device_1_controller")
        self.controllers(expected)
        if not robot:
            self.call("/cia402_device_1_controller/init", Trigger)
            self.call("/cia402_device_1_controller/position_mode", Trigger)
        targets = {"joint1": 0.25, "joint2": 0.0} if robot else {"node_1": 0.25}
        publisher = self.node.create_publisher(
            Float64MultiArray, "/forward_position_controller/commands", 10
        )
        try:
            self.feedback(
                "/joint_states",
                JointState,
                self.position_predicate(targets),
                publisher,
                Float64MultiArray(data=list(targets.values())),
            )
        finally:
            self.node.destroy_publisher(publisher)


def main():
    rclpy.init()
    probe = Probe()
    try:
        scenarios = {
            "cia402_setup": probe.service_example,
            "cia402_lifecycle_setup": lambda: probe.service_example(lifecycle=True),
            "canopen_system": probe.proxy_control,
            "cia402_system": probe.position_control,
            "robot_control_setup": lambda: probe.position_control(robot=True),
        }
        scenarios[sys.argv[1]]()
    finally:
        probe.node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
