"""build_platform provides various ways of naming the environment we are
building under for the purpose of selecting the correct paths and targets.
"""

import platform

def os():
    """Returns a canonicalized OS type. Will be one of Linux or Darwin
    as Windows is unsupported at the moment."""
    system = platform.system()
    if system == 'Linux':
        return 'linux'
    if system == 'Darwin':
        return 'darwin'
    raise RuntimeError("Unknown System: " + system)

def prebuilt():
    """Returns the prebuilt subdirectory for prebuilts which do not use
    subarch specialization."""
    return os() + '-x86'

def prebuilt_full():
    """Returns the prebuilt subdirectory for prebuilts which have subarch
    specialization available.
    """
    return os() + '-x86_64'

def triple():
    """Returns the target triple of the build environment."""
    build_os = os()
    if build_os == 'linux':
        return 'x86_64-unknown-linux-gnu'
    if build_os == 'darwin':
        return 'x86_64-apple-darwin'
    raise RuntimeError("Unknown OS: " + build_os)
