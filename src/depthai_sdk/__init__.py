from .classes.output_config import OutputConfig, VisualizeConfig
from .fps import *
from .previews import *
from .utils import *
from .managers import *
from .record import *
from .replay import *
from .components import *
from .classes import *
from .oak_outputs import *
from .oak_device import OakDevice

from typing import Optional
import depthai as dai
from pathlib import Path
from .args_parser import ArgsParser

class OakCamera:
    """
    TODO: Write useful comments for users

    Camera is the main abstraction class for the OAK cameras. It abstracts pipeline building, different camera permutations,
    AI model handling, visualization, user arguments, syncing, etc.

    This abstraction layer will internally use SDK Components.
    """

    # User should be able to access these:
    _pipeline: dai.Pipeline = None
    oak: OakDevice  # Init this object by default
    args: Dict[str, Any] = None  # User defined arguments
    replay: Optional[Replay] = None
    components: List[Component] = []  # List of components

    _usb_speed: Optional[dai.UsbSpeed] = None
    _device_name: str = None  # MxId / IP / USB port

    _out_templates: List[OutputConfig] = []

    # TODO: 
    # - available streams; query cameras, or Replay.getStreams(). Pass these to camera component

    def __init__(self,
                 device: Optional[str] = None,  # MxId / IP / USB port
                 usbSpeed: Union[None, str, dai.UsbSpeed] = None,  # Auto by default
                 recording: Optional[str] = None,
                 args: Union[bool, Dict] = True
                 ) -> None:
        """
        Args:
            device (str, optional): OAK device we want to connect to
            usb2 (bool, optional): Force USB2 mode
            recording (str, optional): Use depthai-recording - either local path, or from depthai-recordings repo
            args (None, bool, Dict): Use user defined arguments when constructing the pipeline
        """
        self._device_name = device
        self._usb_speed = parse_usb_speed(usbSpeed)
        self.oak = OakDevice()
        self._pipeline = dai.Pipeline()
        self._pipeline_built = False

        if args:
            if isinstance(args, bool):
                if args:
                    self.args = ArgsParser.parseArgs()
                    # Setup the OakCamera
                    if self.args.get('recording', None):
                        recording = self.args.get('recording', None)
                    if self.args.get('deviceId', None):
                        self._device_name = self.args.get('deviceId', None)
                    if self.args.get('usbSpeed', None):
                        self._usb_speed =  parse_usb_speed(self.args.get('usbSpeed', None))

                # else False - we don't want to parse user arguments
            else:  # Already parsed
                self.args = args

        if recording:
            self.replay = Replay(recording)
            print('available streams from recording', self.replay.getStreams())


    def _comp(self, comp: Component) -> Union[CameraComponent, NNComponent, StereoComponent]:
        self.components.append(comp)
        return comp

    def create_camera(self,
                      source: str,
                      resolution: Union[
                          None, str, dai.ColorCameraProperties.SensorResolution, dai.MonoCameraProperties.SensorResolution] = None,
                      fps: Optional[float] = None,
                      encode: Union[None, str, bool, dai.VideoEncoderProperties.Profile] = None,
                      ) -> CameraComponent:
        """
        Create Color camera
        """
        return self._comp(CameraComponent(
            self._pipeline,
            source=source,
            resolution=resolution,
            fps=fps,
            encode=encode,
            replay=self.replay,
            args=self.args,
        ))

    def create_nn(self,
                  model: Union[str, Path],
                  input: Union[CameraComponent, NNComponent, dai.Node.Output],
                  type: Optional[str] = None,
                  tracker: bool = False,  # Enable object tracker - only for Object detection models
                  spatial: Union[None, bool, StereoComponent, dai.Node.Output] = None,
                  ) -> NNComponent:
        """
        Create NN component.
        Args:
            model (str / Path): str for SDK supported model or Path to custom model's json
            input (Component / dai.Node.Output): Input to the model. If NNComponent (detector), it creates 2-stage NN
            out (str / bool): Stream results to the host
            type (str): Type of the network (yolo/mobilenet) for on-device NN result decoding
            tracker: Enable object tracker, if model is object detector (yolo/mobilenet)
            spatial: Calculate 3D spatial coordinates, if model is object detector (yolo/mobilenet) and depth stream is available
        """
        return self._comp(NNComponent(
            self._pipeline,
            model=model,
            input=input,
            nnType=type,
            tracker=tracker,
            spatial=spatial,
            args=self.args
        ))

    def create_stereo(self,
                      resolution: Union[None, str, dai.MonoCameraProperties.SensorResolution] = None,
                      fps: Optional[float] = None,
                      left: Union[None, dai.Node.Output, CameraComponent] = None,  # Left mono camera
                      right: Union[None, dai.Node.Output, CameraComponent] = None,  # Right mono camera
                      ) -> StereoComponent:
        """
        Create Stereo camera component
        """
        return self._comp(StereoComponent(
            self._pipeline,
            resolution=resolution,
            fps=fps,
            left=left,
            right=right,
            replay=self.replay,
            args=self.args,
        ))

    def _init_device(self) -> None:
        """
        Connect to the OAK camera
        """
        if self._device_name:
            deviceInfo = dai.DeviceInfo(self._device_name)
        else:
            (found, deviceInfo) = dai.Device.getFirstAvailableDevice()
            if not found:
                raise Exception("No OAK device found to connect to!")

        version = self._pipeline.getOpenVINOVersion()
        if self._usb_speed == dai.UsbSpeed.SUPER:
            self.oak.device = dai.Device(
                version=version,
                deviceInfo=deviceInfo,
                usb2Mode=True
            )
        else:
            self.oak.device = dai.Device(
                version=version,
                deviceInfo=deviceInfo,
                maxUsbSpeed=dai.UsbSpeed.SUPER if self._usb_speed is None else self._usb_speed
            )

    def config_pipeline(self,
                        xlinkChunk: Optional[int] = None,
                        calib: Optional[dai.CalibrationHandler] = None,
                        tuningBlob: Optional[str] = None,
                        openvinoVersion: Union[None, str, dai.OpenVINO.Version] = None
                        ) -> None:
        configPipeline(self._pipeline, xlinkChunk, calib, tuningBlob, openvinoVersion)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        print("Closing OAK camera")
        if self.oak.device is not None:
            self.oak.device.close()
        if self.replay:
            print("Closing replay")
            self.replay.close()

    def start(self, blocking=False) -> None:
        """
        Start the application
        """
        if not self._pipeline_built:
            self.build() # Build the pipeline

        self.oak.device.startPipeline(self._pipeline)

        self.oak.initCallbacks(self._pipeline)

        for xout in self.oak.oak_out_streams: # Start FPS counters
            xout.start_fps()

        if self.replay:
            self.replay.createQueues(self.oak.device)
            # Called from Replay module on each new frame sent to the device.
            self.replay.start(self.oak.newMsg)

        # Check if callbacks (sync/non-sync are set)
        if blocking:
            # Constant loop: get messages, call callbacks
            while True:
                time.sleep(0.001)
                if not self.poll():
                    break

    def poll(self) -> bool:
        """
        Poll events; cv2.waitKey, send controls to OAK (if controls are enabled), update, check syncs.
        True if successful.
        """
        key = cv2.waitKey(1)
        if key == ord('q'):
            return False

        # TODO: check if components have controls enabled and check whether key == `control`

        self.oak.checkSync()

        return True # TODO: check whether OAK is connectednnComp

    def build(self) -> dai.Pipeline:
        """
        Connect to the device and build the pipeline based on previously provided configuration. Configure XLink queues,
        upload the pipeline to the device. This function must only be called once!  build() is also called by start().

        @return Built dai.Pipeline
        """
        if self._pipeline_built:
            raise Exception('Pipeline can be built only once!')

        self._pipeline_built = True
        if self.replay:
            self.replay.initPipeline(self._pipeline)

        # First go through each component to check whether any is forcing an OpenVINO version
        # TODO: check each component's SHAVE usage
        for c in self.components:
            ov = c._forced_openvino_version()
            if ov:
                if self._pipeline.getRequiredOpenVINOVersion() and self._pipeline.getRequiredOpenVINOVersion() != ov:
                    raise Exception(
                        'Two components forced two different OpenVINO version! Please make sure that all your models are compiled using the same OpenVINO version.')
                self._pipeline.setOpenVINOVersion(ov)

        if self._pipeline.getRequiredOpenVINOVersion() == None:
            # Force 2021.4 as it's better supported (blobconverter, compile tool) for now.
            self._pipeline.setOpenVINOVersion(dai.OpenVINO.VERSION_2021_4)

        # Connect to the OAK camera
        self._init_device()

        # Go through each component
        for component in self.components:
            # Update the component now that we can query device info
            component._update_device_info(self._pipeline, self.oak.device, self._pipeline.getOpenVINOVersion())

        # Create XLinkOuts based on visualizers/callbacks enabled
        names = []
        for out in self._out_templates:
            xoutbase: XoutBase = out.output(self._pipeline, self.oak.device)
            xoutbase.setup_base(out.callback)

            if xoutbase.name in names: # Stream name already exist, append a number to it
                xoutbase.name = find_new_name(xoutbase.name, names)
            names.append(xoutbase.name)

            if out.vis:
                xoutbase.setup_visualize(out.vis.scale, out.vis.fps)
            self.oak.oak_out_streams.append(xoutbase)

        # User-defined arguments
        if self.args:
            self.config_pipeline(
                xlinkChunk=self.args.get('xlinkChunkSize', None),
                tuningBlob=self.args.get('cameraTuning', None),
                openvinoVersion=self.args.get('openvinoVersion', None),
            )
            self.device.setIrLaserDotProjectorBrightness(self.args.get('irDotBrightness', None) or 0)
            self.device.setIrFloodLightBrightness(self.args.get('irFloodBrightness', None) or 0)

        return self._pipeline


    def show_graph(self) -> None:
        """
        Show DepthAI Pipeline graph, which is very useful for debugging.
        """
        if not self._pipeline_built:
            self.build() # Build the pipeline

        PipelineGraph(self._pipeline.serializeToJson()['pipeline'])


    def _callback(self, output: Union[List, Callable, Component], callback: Callable, vis=None):
        if isinstance(output, List):
            for element in output:
                self._callback(element, callback, vis)
            return

        if isinstance(output, Component):
            output = output.out

        self._out_templates.append(OutputConfig(output, callback, vis))

    def visualize(self, output: Union[List, Callable, Component],
                  scale: Union[None, float, Tuple[int, int]] = None,
                  fps=False,
                  callback: Callable=None):
        """
        Visualize component output(s). This handles output streaming (OAK->host), message syncing, and visualizing.

        Args:
            output (Component/Component output): Component output(s) to be visualized. If component is passed, SDK will visualize its default output (out())
            scale: Optionally scale the frame before it's displayed
            fps: Show FPS of the output on the frame
            callback: Instead of showing the frame, pass the Packet to the callback function, where it can be displayed
        """

        self._callback(output, callback, VisualizeConfig(scale, fps))

    def callback(self, output: Union[List, Callable, Component], callback: Callable):
        """
        Create a callback for the component output(s). This handles output streaming (OAK->Host) and message syncing.

        Args:
            output: Component output(s) to be visualized. If component is passed, SDK will visualize its default output (out())
            callback: Handler function to which the Packet will be sent
        """
        self._callback(output, callback)

    @property
    def device(self) -> dai.Device:
        if not self._pipeline_built:
            raise Exception("OAK device wasn't booted yet, make sure to call oak.build() or oak.start()!")
        return self.oak.device
