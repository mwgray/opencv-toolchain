import argparse
import logging as log
import os
import subprocess
import time
import urllib


def downloadAndExtractNDK_Linux():
    downloadAndExtractNDK("android-ndk-r15c-linux-x86_64.zip", "android-ndk-r15c-linux")


def downloadAndExtractNDK_Mac():
    downloadAndExtractNDK("android-ndk-r15c-darwin-x86_64.zip", "android-ndk-r15c-darwin")


def downloadAndExtractNDK(file, where):
    downloadAndExtract("https://dl.google.com/android/repository/%s" % file, where)


def downloadAndExtract(url, where):
    testfile = urllib.URLopener()
    filename = "%s.zip" % where

    if os.path.isfile(filename):
        log.debug("%s is already downloaded", filename)
    else:
        log.debug("Downloading %s to %s", url, filename)
        testfile.retrieve(url, filename)

    if os.path.isdir(where):
        log.debug("%s is already extracted", where)
    else:
        log.debug("Extracting %s to %s", filename, where)
        subprocess.call(["unzip",
                         "-o",
                         filename,
                         "-d",
                         where
                         ])


def setupDockcrossImage(image):
    log.debug("Setting up dockcross image for %s" % image)
    subprocess.call(["docker", "build", "-t", "android-python-%s" % image, "docker/%s" % image])


def setupPrerequisites():
    downloadAndExtractNDK_Mac()
    downloadAndExtractNDK_Linux()
    # setupDockcrossImage("linux-armv7")
    setupDockcrossImage("linux-x86")


def buildNumpy(api, abi):
    # start docker with /working mapped and run python build script

    command = ["docker", "run", "--rm",
               "-v", "%s:/working" % os.getcwd(),
               "android-python-%s" % abi, "bash", "-c",
               "cd /working;"
               "python build-numpy-docker.py --api=%s --abi=%s" % (api, abi),
               ]
    subprocess.call(command)


def buildOpenCV(abi):
    workingDirectory = os.getcwd()

    env = os.environ.copy()

    # where the python include files are located
    env["PYTHON2_INCLUDE_DIR"] = "%s/python-lib/include/python2.7/" % workingDirectory

    # which .so file should the build process link against
    env["PYTHON2_LIBRARY"] = "%s/python-%s/lib/libpython2.7.so" % (workingDirectory, abi)

    # where the python executable _for the target platform_ is located
    env["PYTHON2_EXECUTABLE"] = "%s/python-%s/bin/python2" % (workingDirectory, abi)

    # where to find the NumPy include files
    env["PYTHON2_NUMPY_INCLUDE_DIRS"] = "%s/numpy/dist/numpy/core/include" % workingDirectory

    # where the Android ndk is deployed
    env["ANDROID_NDK"] = "%s/android-ndk-r15c-darwin/android-ndk-r15c" % workingDirectory

    # where the Android sdk is deployed
    env["ANDROID_SDK"] = "%s/android-sdk" % workingDirectory

    # where to build everything
    subprocess.call(["mkdir", "opencv-android-build-android"])

    # where the base of the OpenCV project is
    opencv_working_dir = "%s/opencv-android-build-android/" % workingDirectory
    opencv_path = "%s/opencv" % workingDirectory

    proc = subprocess.Popen(["python", "build_sdk.py", opencv_working_dir, opencv_path, "--abi=%s" % abi],
                            cwd="./opencv/platforms/android", env=env)
    proc.communicate()
    proc.wait()


def testOpenCV(abi):
    # TODO: fix hard pathing in android.toolchain.cmake
    subprocess.call(["adb", "push", "opencv-android-build-android/o4a/lib/%s/cv2.so" % abi, "/sdcard/Download"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build OpenCV + Python for Android SDK')
    parser.add_argument('--api',
                        default="26",
                        help="Which api version to use for custom toolchain")
    parser.add_argument('--abi',
                        choices=["x86", "arm64-v8a", "armeabi-v7a"],
                        default="x86",
                        help="Which abi to build for")
    args = parser.parse_args()

    log.basicConfig(format='%(message)s', level=log.DEBUG)
    log.debug("Args: %s", args)

    setupPrerequisites()
    buildNumpy(args.api, args.abi)
    log.debug("Now for some hacks.  Manually edit android.toolchain.cmake:1386 to point to libpython2.7.so.\n"
             "Then press enter to continue building OpenCV")
    raw_input("")
    buildOpenCV(args.abi)
    testOpenCV(args.abi)