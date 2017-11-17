import argparse
import logging as log
import os
import subprocess
import time
import urllib
import zipfile

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build OpenCV + Python for Android SDK')
    parser.add_argument("--working-dir", default='.', help="Working directory (and output)")
    parser.add_argument('--runtime', choices=['android', 'termux'], default='android',
                        help="Indicates runtime environment.")
    parser.add_argument('--abi',
                        choices=["x86", "arm64-v8a", "armeabi-v7a"],
                        default=["x86"],
                        help="Which abi to build for")
    args = parser.parse_args()

    log.basicConfig(format='%(message)s', level=log.DEBUG)
    log.debug("Args: %s", args)


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
        ndkZip = zipfile.ZipFile(filename, 'r')
        ndkZip.extractall(where)


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
    # docker run --rm dockcross/linux-armv7 > ./dockcross-linux-armv7
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
    # docker is just needed for android target
    cloneDockCross()


def sendTermuxCommand(command):
    log.info("Sending termux command over adb: %s" % command)
    # try to setup storage
    subprocess.call(["adb", "shell", "input", "keyboard", "text", "\"%s\"" % command])

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


def pullTermuxFiles():
    subprocess.call(["adb", "pull", "/sdcard/Download/termux.zip"])
    ndkZip = zipfile.ZipFile("termux.zip", 'r')
    ndkZip.extractall("termux")


def buildOpenCV():
    workingDirectory = os.getcwd()

    env = os.environ.copy()

    opencv_working_dir = "%s/opencv-android-build/" % workingDirectory
    opencv_path = "%s/opencv" % workingDirectory

    # where the python include files are located
    env["PYTHON2_INCLUDE_DIR"] = "%s/termux/files/usr/include/python2.7/" % workingDirectory

    # which .so file should the build process link against
    env["PYTHON2_LIBRARY"] = "%s/termux/files/usr/lib/libpython2.7.so" % workingDirectory

    # where the python executable _for the target platform_ is located
    env["PYTHON2_EXECUTABLE"] = "%s/termux/files/usr/bin/python2" % workingDirectory

    # where to find the NumPy include files
    env["PYTHON2_NUMPY_INCLUDE_DIRS"] = "%s/termux/site-packages/numpy/core/include" % workingDirectory

    # where the Android ndk is deployed
    env["ANDROID_NDK"] = "%s/android-ndk-r15c-darwin/android-ndk-r15c" % workingDirectory

    # where the Android sdk is deployed
    env["ANDROID_SDK"] = "%s/android-sdk" % workingDirectory

    # where to build everything
    opencv_working_dir = "%s/opencv-android-build/" % workingDirectory
    subprocess.call(["mkdir", "opencv-android-build"])

    # where the base of the OpenCV project is
    opencv_working_dir = "%s/opencv-android-build/" % workingDirectory
    opencv_path = "%s/opencv" % workingDirectory

    proc = subprocess.Popen(["python", "build_sdk.py", opencv_working_dir, opencv_path, "--abi=%s" % args.abi],
                            cwd="./opencv/platforms/android", env=env)
    proc.communicate()
    proc.wait()


def testOpenCV():
    # TODO: fix hard pathing in android.toolchain.cmake
    subprocess.call(["adb", "push", "opencv-android-build/o4a/lib/%s/cv2.so" % args.abi, "/sdcard/Download"])

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

    # setupTermux()
    # pullTermuxFiles()
    # buildOpenCV()
    # testOpenCV()
