from typing import Dict, Any, Union

import numpy as np

from .abstract_recorder import *


class VideoRecorder(Recorder):
    """
    Writes encoded streams raw (.mjpeg/.h264/.hevc) or directly to mp4 container.
    Writes unencoded streams to mp4 using cv2.VideoWriter
    """
    _closed = False
    _writers: Dict[str, Any]

    def __init__(self):
        self.path = None
        self._stream_type = dict()
        self._writer = dict()

    def __getitem__(self, item):
        return self._writer[item]

    # TODO device is not used
    def update(self, path: Path, device: dai.Device, xouts: List['XoutFrames']):
        """
        Update the recorder with new streams.
        Args:
            path: Path to save the output. Either a folder or a file.
            device: Device to get the streams from.
            xouts: List of output streams.
        """
        self.path = path
        if path.suffix == '':  # If no extension, create a folder
            self.path.mkdir(parents=True, exist_ok=True)

        for xout in xouts:
            name = xout.name
            stream = OakStream(xout)
            fourcc = stream.fourcc()  # TODO add default fourcc? stream.fourcc() can be None.
            if stream.isRaw():
                from .video_writers.video_writer import VideoWriter
                self._writer[name] = VideoWriter(self.path, name, fourcc, xout.fps)
            else:
                try:
                    from .video_writers.av_writer import AvWriter
                    self._writer[name] = AvWriter(self.path, name, fourcc, xout.fps)
                except Exception as e:
                    # TODO here can be other errors, not only import error
                    print('Exception while creating AvWriter: ', e)
                    print('Falling back to FileWriter, saving uncontainerized encoded streams.')
                    from .video_writers.file_writer import FileWriter
                    self._writer[name] = FileWriter(self.path, name, fourcc)

    def write(self, name: str, frame: Union[np.ndarray, dai.ImgFrame]):
        self._writer[name].write(frame)

    def add_to_buffer(self, name: str, frame: Union[np.ndarray, dai.ImgFrame]):
        self._writer[name].add_to_buffer(frame)

    def close(self):
        if self._closed: return
        self._closed = True
        print("Video Recorder saved stream(s) to folder:", str(self.path))
        # Close opened files
        for name, writer in self._writer.items():
            writer.close()
