import argparse
import logging as log
import os
import subprocess

def build_custom_toolchain(api, abi):
    toolchain_id = "toolchain-%s-%s" % (api, abi)

    if os.path.isdir(toolchain_id):
        log.info("toolchain `%s` already found" % toolchain_id)
    else:
        log.info("creating toolchain `%s`" % toolchain_id)

        # need to chmod 755 the script before running it
        subprocess.call(["chmod",
                         "755",
                         "android-ndk-r15c-linux/android-ndk-r15c/build/tools/make-standalone-toolchain.sh"]);

        subprocess.call([
            "android-ndk-r15c-linux/android-ndk-r15c/build/tools/make-standalone-toolchain.sh",
            "--platform=%s" % api,
            "--arch=%s" % abi,
            "--package-dir=./%s" % toolchain_id,
            "--install-dir=./%s" % toolchain_id,
            "--verbose"
        ]);


def build_numpy(api, abi):
    env = os.environ.copy()
    toolchain_id = "toolchain-%s-%s" % (api, abi)

    # remap the compilers that python will use
    # TODO: need to ensure the compiler names match the toolchain name
    env["CC"] = "../%s/bin/i686-linux-android-clang" % toolchain_id
    env["CCX"] = "../%s/bin/i686-linux-android-clang++" % toolchain_id
    env["LDSHARED"] = "../%s/bin/i686-linux-android-clang" % toolchain_id

    # Compier flags; include the usr include directory
    env["CFLAGS"] = "-I/usr/include/"

    # Linker flags; include libpython and build as a shared lib
    env["LDFLAGS"] = "/working/python-%s/lib/libpython2.7.so -shared" % abi

    proc = subprocess.Popen(["python", "setup.py", "bdist_egg"],
                            cwd="/working/numpy", env=env)
    proc.communicate()
    proc.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build OpenCV + Python for Android SDK')
    parser.add_argument('--api',
                        default="26",
                        help="Which api version to use for custom toolchain")
    parser.add_argument('--abi',
                        choices=["x86", "arm64-v8a", "armeabi-v7a"],
                        default="armeabi-v7a",
                        help="Which abi to build for")
    args = parser.parse_args()

    log.error("Building NumPy")

    toolchainAbi = {
        "x86": "x86",
        "armeabi-v7a": "arm",
        "arm64-v8a": "arm64",
    }[args.abi];

    build_custom_toolchain(args.api, toolchainAbi)
    build_numpy(args.api, toolchainAbi)
