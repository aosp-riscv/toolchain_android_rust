#
# Copyright (C) 2019 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

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
