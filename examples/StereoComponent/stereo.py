import cv2

from depthai_sdk import OakCamera
from depthai_sdk.components.stereo_component import WLSLevel
from depthai_sdk.visualize.configs import StereoColor

with OakCamera() as oak:
    stereo = oak.create_stereo('400p', fps=30)
    stereo.config_postprocessing(
        colorize=StereoColor.GRAY,
        colormap=cv2.COLORMAP_BONE,
        wls_filter=True,
        wls_level=WLSLevel.MEDIUM,
        wls_lambda=8000,
        wls_sigma=1.5
    )

    oak.visualize(stereo.out.depth)
    oak.start(blocking=True)
