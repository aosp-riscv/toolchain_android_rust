"""build_platform provides various ways of naming the environment we are
building under for the purpose of selecting the correct paths and targets.
"""

import platform

def system() -> str:
    """Returns a canonicalized OS type. Will be one of 'linux' or 'darwin'
    as Windows is unsupported at the moment."""
    sys = platform.system()
    if sys == 'Linux':
        return 'linux'
    if sys == 'Darwin':
        return 'darwin'
    raise RuntimeError("Unknown System: " + sys)

def is_linux() -> bool:
    return platform.system() == 'Linux'

def is_darwin() -> bool:
    return platform.system() == 'Darwin'

def prebuilt() -> str:
    """Returns the prebuilt subdirectory for prebuilts which do not use
    subarch specialization."""
    return system() + '-x86'

def prebuilt_full() -> str:
    """Returns the prebuilt subdirectory for prebuilts which have subarch
    specialization available.
    """
    return system() + '-x86_64'

def triple() -> str:
    """Returns the target triple of the build environment."""
    build_os = system()
    if build_os == 'linux':
        return 'x86_64-unknown-linux-gnu'
    if build_os == 'darwin':
        return 'x86_64-apple-darwin'
    raise RuntimeError("Unknown OS: " + build_os)

def alt_triples() -> list[str]:
    """Returns the multilib targets for the build environment."""
    build_os = system()
    if build_os == 'linux':
        return ['i686-unknown-linux-gnu']
    if build_os == 'darwin':
        return []
    raise RuntimeError("Unknown OS: " + build_os)

def rpath_origin() -> str:
    """Returns the string used to indicate the root loader context"""
    if is_darwin():
        return '@loader_path'
    else:
        return '$ORIGIN'
