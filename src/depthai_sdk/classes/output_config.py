from abc import abstractmethod
from pathlib import Path
from typing import Optional, Callable, List

import depthai as dai

from depthai_sdk import FramePacket
from depthai_sdk.callback_context import CallbackContext
from depthai_sdk.oak_outputs.syncing import SequenceNumSync
from depthai_sdk.oak_outputs.xout import XoutFrames
from depthai_sdk.oak_outputs.xout_base import XoutBase
from depthai_sdk.record import Record
from depthai_sdk.recorders.video_recorder import VideoRecorder
from depthai_sdk.visualize import Visualizer


class BaseConfig:
    @abstractmethod
    def setup(self, pipeline: dai.Pipeline, device, names: List[str]) -> List[XoutBase]:
        raise NotImplementedError()


class OutputConfig(BaseConfig):
    """
    Saves callbacks/visualizers until the device is fully initialized. I'll admit it's not the cleanest solution.
    """
    visualizer: Optional[Visualizer]  # Visualization
    output: Callable  # Output of the component (a callback)
    callback: Callable  # Callback that gets called after syncing

    def __init__(self, output: Callable,
                 callback: Callable,
                 visualizer: Visualizer = None,
                 record_path: Optional[str] = None):
        self.output = output
        self.callback = callback
        self.visualizer = visualizer
        self.record_path = record_path

    def find_new_name(self, name: str, names: List[str]):
        while True:
            arr = name.split(' ')
            num = arr[-1]
            if num.isnumeric():
                arr[-1] = str(int(num) + 1)
                name = " ".join(arr)
            else:
                name = f"{name} 2"
            if name not in names:
                return name

    def setup(self, pipeline: dai.Pipeline, device, names: List[str]) -> List[XoutBase]:
        xoutbase: XoutBase = self.output(pipeline, device)
        xoutbase.setup_base(self.callback)

        if xoutbase.name in names:  # Stream name already exist, append a number to it
            xoutbase.name = self.find_new_name(xoutbase.name, names)
        names.append(xoutbase.name)

        recorder = None
        if self.record_path:
            recorder = VideoRecorder()
            recorder.update(Path(self.record_path), device, [xoutbase])

        if self.visualizer:
            xoutbase.setup_visualize(self.visualizer, xoutbase.name, recorder)

        return [xoutbase]


class RecordConfig(BaseConfig):
    rec: Record
    outputs: List[Callable]

    def __init__(self, outputs: List[Callable], rec: Record):
        self.outputs = outputs
        self.rec = rec

    def setup(self, pipeline: dai.Pipeline, device: dai.Device, _) -> List[XoutBase]:
        xouts: List[XoutFrames] = []
        for output in self.outputs:
            xoutbase: XoutFrames = output(pipeline, device)
            xoutbase.setup_base(None)
            xouts.append(xoutbase)

        self.rec.setup_base(None)
        self.rec.start(device, xouts)

        return [self.rec]


class SyncConfig(BaseConfig, SequenceNumSync):
    outputs: List[Callable]
    cb: Callable
    visualizer: Visualizer

    def __init__(self, outputs: List[Callable], callback: Callable, visualizer: Visualizer = None):
        self.outputs = outputs
        self.cb = callback
        self.visualizer = visualizer

        SequenceNumSync.__init__(self, len(outputs))

        self.packets = dict()

    def new_packet(self, ctx: CallbackContext, _=None):
        # print('new packet', packet, packet.name, 'seq num',packet.imgFrame.getSequenceNum())
        packet = ctx.packet
        synced = self.sync(
            packet.imgFrame.getSequenceNum(),
            packet.name,
            packet
        )
        if synced:
            self.cb(synced) if self.visualizer is None else self.cb(synced, self.visualizer)

    def setup(self, pipeline: dai.Pipeline, device: dai.Device, _) -> List[XoutBase]:
        xouts = []
        for output in self.outputs:
            xoutbase: XoutBase = output(pipeline, device)
            xoutbase.setup_base(self.new_packet)
            xouts.append(xoutbase)

            if self.visualizer:
                xoutbase.setup_visualize(self.visualizer, xoutbase.name)

        return xouts
