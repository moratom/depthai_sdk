import cv2
import numpy as np

from depthai_sdk import OakCamera, DetectionPacket, AspectRatioResizeMode
from depthai_sdk.callback_context import CallbackContext

NN_WIDTH, NN_HEIGHT = 513, 513
N_CLASSES = 21


def process_mask(output_tensor):
    class_colors = [[0, 0, 0], [0, 255, 0]]
    class_colors = np.asarray(class_colors, dtype=np.uint8)

    output = output_tensor.reshape(NN_WIDTH, NN_HEIGHT)
    output_colors = np.take(class_colors, output, axis=0)
    return output_colors


def callback(ctx: CallbackContext):
    packet: DetectionPacket = ctx.packet

    frame = packet.frame
    mask = packet.img_detections.mask

    output_colors = process_mask(mask)
    output_colors = cv2.resize(output_colors, (frame.shape[1], frame.shape[0]))

    frame = cv2.addWeighted(frame, 1, output_colors, 0.2, 0)
    cv2.imshow('DeepLabV3 person segmentation', frame)


with OakCamera() as oak:
    color = oak.create_camera('color', resolution='1080p')
    nn = oak.create_nn('deeplabv3p_person', color)
    nn.config_nn(aspectRatioResizeMode=AspectRatioResizeMode.STRETCH)

    oak.callback(nn, callback=callback)
    oak.start(blocking=True)
