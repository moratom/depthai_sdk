import time
from threading import Thread
from typing import Dict, Any
from queue import Queue
import rclpy
from rclpy.node import Node
from depthai_sdk.integrations.ros.ros_base import RosBase


def ros_thread(queue: Queue):
    print('Initing ros2')
    rclpy.init()
    node = rclpy.create_node('DepthAI_SDK')
    publishers = dict()

    while rclpy.ok():
        msgs: Dict[str, Any] = queue.get(block=True)
        for topic, msg in msgs.items():
            print('ros publishing', type(msg), 'to', topic)
            if topic not in publishers:
                publishers[topic] = node.create_publisher(type(msg), topic, 10)
            publishers[topic].publish(msg)
        rclpy.spin_once(node, timeout_sec=0.001)  # 100ms timeout


class Ros2Streaming(RosBase):
    queue: Queue

    def __init__(self):
        self.queue = Queue(30)
        self.process = Thread(target=ros_thread, args=(self.queue,))
        self.process.start()
        super().__init__()

    # def update(self): # By RosBase
    # def new_msg(self): # By RosBase

    def new_ros_msg(self, topic: str, ros_msg):
        print('new ros msg', topic, 'qsize', self.queue.qsize())
        self.queue.put({topic: ros_msg})
