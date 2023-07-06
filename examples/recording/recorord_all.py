from depthai_sdk import OakCamera, RecordType

with OakCamera() as oak:
    cams = oak.create_all_cameras()
    cams_isp = [cam.out.isp for cam in cams]
    leftSocket = oak.calibration.getStereoLeftCameraId()
    rightSocket = oak.calibration.getStereoRightCameraId()

    leftCam = None
    rightCam = None
    for cam in cams:
        if leftSocket == cam.get_socket():
            leftCam = cam
        if rightSocket == cam.get_socket():
            rightCam = cam
    if leftCam is None or rightCam is None:
        print("Left or right camera not found")
    else:
        stereo = oak.create_stereo(left=leftCam, right=rightCam)
        oak.visualize(stereo)
    # Sync & save all streams
    oak.record(cams_isp, './record', RecordType.VIDEO)
    oak.visualize(cams_isp, fps=True)

    oak.start(blocking=True)
