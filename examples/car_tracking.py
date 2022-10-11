from depthai import UsbSpeed

from depthai_sdk import OakCamera, AspectRatioResizeMode

with OakCamera(recording='cars-tracking-above-01') as oak:
    color = oak.create_camera('color')
    nn = oak.create_nn('vehicle-detection-0202', color, tracker=True)
    nn.config_nn(aspectRatioResizeMode=AspectRatioResizeMode.STRETCH)

    visualizer = oak.visualize(nn.out.tracker)
    visualizer.configure_output(
        show_fps=True,
        img_scale=1.0,
    ).configure_tracking(
        line_thickness=5
    ).configure_text(
        font_thickness=1,
    )

    oak.start(blocking=True)
