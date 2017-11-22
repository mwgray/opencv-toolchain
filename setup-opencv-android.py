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


def cloneNumpy():
    if os.path.isdir("numpy"):
        log.debug("NumPy already found")
    else:
        log.debug("Cloning NumPy")
        subprocess.call(["git", "clone", "https://github.com/numpy/numpy.git"])

        log.debug("Checking out v1.12.0 tag")
        subprocess.call(["git", "-C", "numpy", "checkout", "tags/v1.12.0"])


def cloneOpenCV():
    if os.path.isdir("opencv"):
        log.debug("OpenCV already found")
    else:
        log.debug("Cloning OpenCV")
        subprocess.call(["git", "clone", "https://github.com/mwgray/opencv.git"])

        log.debug("Checking out python branch")
        subprocess.call(["git", "-C", "opencv", "checkout", "python"])


def setupDockcrossImage(image):
    executable = "./dockcross-%s" % image
    if os.path.isfile(executable):
        log.debug("%s already found" % executable)
    else:
        log.debug("Setting up dockcross image for %s" % image)
        executableFile = open(executable, "w")
        subprocess.call(["docker", "run", "--rm", "dockcross/%s" % image], stdout=executableFile)
        subprocess.call(["chmod", "+x", executable])


def cloneDockCross():
    if os.path.isdir("dockcross"):
        log.debug("dockcross already found")
    else:
        log.debug("Cloning dockcross")
        subprocess.call(["git", "clone", "https://github.com/dockcross/dockcross.git"])

    setupDockcrossImage("linux-armv7")
    setupDockcrossImage("linux-x86")


def setupPrerequisites():
    downloadAndExtractNDK_Mac()
    downloadAndExtractNDK_Linux()
    cloneNumpy()
    cloneOpenCV()
    cloneDockCross()

def buildNumpy(api, abi):
    # start docker with /working mapped and run python build script
    subprocess.call(["./dockcross-linux-x86", "-a", "-v %s:/working" % os.getcwd(), "bash", "-c",
                     "python build-numpy-docker.py --api=%s --abi=%s" % (api, abi)])


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

    log.debug("Press Enter to begin downloading and installing prerequisites()...")
    raw_input("")
    setupPrerequisites()
    log.debug("Before continuing, ensure there is an Android device with Termux installed attached to the machine.")
    raw_input("")
    setupTermux()
    log.debug("Termux should be building numpy and packages.  Wait until this is done to continue.")
    raw_input("")
    pullTermuxFiles(args.abi)
    log.debug("Now for some hacks.  Manually edit android.toolchain.cmake:1386 to point to libpython2.7.so.\n"
              "Then press enter to continue building OpenCV")
    raw_input("")
    buildOpenCV(args.abi)
    log.debug("OpenCV is built.  Press a key to test on device.")
    raw_input("")
    testOpenCV(args.abi)
