"""build_platform provides various ways of naming the environment we are
building under for the purpose of selecting the correct paths and targets.
"""

import platform

def system():
    """Returns a canonicalized OS type. Will be one of 'linux' or 'darwin'
    as Windows is unsupported at the moment."""
    sys = platform.system()
    if sys == 'Linux':
        return 'linux'
    if sys == 'Darwin':
        return 'darwin'
    raise RuntimeError("Unknown System: " + sys)

def prebuilt():
    """Returns the prebuilt subdirectory for prebuilts which do not use
    subarch specialization."""
    return system() + '-x86'

def prebuilt_full():
    """Returns the prebuilt subdirectory for prebuilts which have subarch
    specialization available.
    """
    return system() + '-x86_64'

def triple():
    """Returns the target triple of the build environment."""
    build_os = system()
    if build_os == 'linux':
        return 'x86_64-unknown-linux-gnu'
    if build_os == 'darwin':
        return 'x86_64-apple-darwin'
    raise RuntimeError("Unknown OS: " + build_os)
