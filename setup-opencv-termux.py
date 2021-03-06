import argparse
import logging as log
import os
import subprocess
import time
import urllib
import zipfile


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


def sendTermuxCommand(command):
    log.info("Sending termux command over adb: %s" % command)
    # try to setup storage
    escapedCommand = ("\"%s\"" % command).replace(" ", "%s")
    subprocess.call(["adb", "shell", "input", "keyboard", "text", escapedCommand])

    # enter
    subprocess.call(["adb", "shell", "input", "keyevent", "66"])


def setupTermux():
    # copy build script to device
    subprocess.call(["adb", "push", "setup-termux.sh", "/sdcard/Download"])

    # grant sdcard access
    subprocess.call(["adb", "shell", "pm", "grant", "com.termux", "android.permission.WRITE_EXTERNAL_STORAGE"])
    subprocess.call(["adb", "shell", "pm", "grant", "com.termux", "android.permission.READ_EXTERNAL_STORAGE"])

    # run termux
    subprocess.call(["adb", "shell", "monkey", "-p", "com.termux", "1"])

    time.sleep(3)
    sendTermuxCommand("cp /sdcard/Download/setup-termux.sh .")
    sendTermuxCommand("chmod 755 setup-termux.sh")
    sendTermuxCommand("./setup-termux.sh")


def pullTermuxFiles(abi):
    subprocess.call(["adb", "pull", "/sdcard/Download/termux.zip"])
    ndkZip = zipfile.ZipFile("termux.zip", 'r')
    ndkZip.extractall("termux/%s" % abi)


def buildOpenCV(abi):
    workingDirectory = os.getcwd()

    env = os.environ.copy()

    termux_path = "%s/termux/%s" % (workingDirectory, abi)

    # where the python include files are located
    env["PYTHON2_INCLUDE_DIR"] = "%s/files/usr/include/python2.7/" % termux_path

    # which .so file should the build process link against
    env["PYTHON2_LIBRARY"] = "%s/files/usr/lib/libpython2.7.so" % termux_path

    # where the python executable _for the target platform_ is located
    env["PYTHON2_EXECUTABLE"] = "%s/files/usr/bin/python2" % termux_path

    # where to find the NumPy include files
    env["PYTHON2_NUMPY_INCLUDE_DIRS"] = "%s/site-packages/numpy/core/include" % termux_path

    # where the Android ndk is deployed
    env["ANDROID_NDK"] = "%s/android-ndk-r15c-darwin/android-ndk-r15c" % workingDirectory

    # where the Android sdk is deployed
    env["ANDROID_SDK"] = "%s/android-sdk" % workingDirectory

    # where to build everything
    subprocess.call(["mkdir", "opencv-android-build-termux"])

    # where the base of the OpenCV project is
    opencv_working_dir = "%s/opencv-android-build-termux/" % workingDirectory
    opencv_path = "%s/opencv" % workingDirectory

    proc = subprocess.Popen(["python", "build_sdk.py", opencv_working_dir, opencv_path, "--abi=%s" % abi],
                            cwd="./opencv/platforms/android", env=env)
    proc.communicate()
    proc.wait()


def testOpenCV(abi):
    subprocess.call(["adb", "push", "opencv-android-build-termux/o4a/lib/%s/cv2.so" % abi, "/sdcard/Download"])
    # upload screenshot
    subprocess.call(["adb", "push", "ss.png", "/sdcard/Download"])

    # run termux
    subprocess.call(["adb", "shell", "monkey", "-p", "com.termux", "1"])

    time.sleep(2)
    sendTermuxCommand("cp /sdcard/Download/cv2.so .")
    time.sleep(1)
    sendTermuxCommand("python2");
    time.sleep(1)
    sendTermuxCommand("import cv2");
    time.sleep(1)
    sendTermuxCommand("print(cv2.imread('/sdcard/Download/ss.png').size)");
    time.sleep(1)
    sendTermuxCommand("quit()");


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build OpenCV + Python for Android SDK')
    parser.add_argument('--abi',
                        choices=["x86", "arm64-v8a", "armeabi-v7a"],
                        default="armeabi-v7a",
                        help="Which abi to build for")
    args = parser.parse_args()

    log.basicConfig(format='%(message)s', level=log.DEBUG)
    log.debug("Args: %s", args)

    log.debug("Press Enter to begin downloading and installing NDK...")
    raw_input("")
    downloadAndExtractNDK_Mac()
    log.debug("Before continuing, ensure there is an Android device with Termux installed attached to the machine.")
    raw_input("")
    setupTermux()
    log.debug("Termux should be building numpy and packages.  Wait until this is done to continue.")
    raw_input("")
    pullTermuxFiles(args.abi)
    # TODO: fix hard pathing in android.toolchain.cmake
    log.debug("Now for some hacks.  Manually edit android.toolchain.cmake:1386 to point to libpython2.7.so.\n"
              "Then press enter to continue building OpenCV")
    raw_input("")
    buildOpenCV(args.abi)
    log.debug("OpenCV is built.  Press a key to test on device.")
    raw_input("")
    testOpenCV(args.abi)
