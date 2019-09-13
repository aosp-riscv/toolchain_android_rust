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
"""Provides path expansion to components needed for the rustc build."""

import os.path

THIS_DIR = os.path.realpath(os.path.dirname(__file__))

STAGE0_RUST_VERSION = '1.37.0'
CLANG_REVISION = 'r353983d'


def workspace_path(*args):
    """Generates a path relative to the root of the workspace."""
    return os.path.realpath(os.path.join(THIS_DIR, '..', '..', *args))


def rustc_path(*args):
    """Generates a path relative to the rustc source directory."""
    return os.path.realpath(os.path.join(THIS_DIR, '..', 'rustc', *args))


def patches_path(*args):
    """Generates a path relative to the patches directory."""
    return os.path.realpath(os.path.join(THIS_DIR, 'patches', *args))


def this_path(*args):
    """Generates a path relative to this directory."""
    return os.path.realpath(os.path.join(THIS_DIR, *args))


def out_path(*args):
    """Generates a path relative to the output directory of the build."""
    return workspace_path('out', *args)


def rust_prebuilt(*args):
    """Generates a path relative to the rust prebuilt directory."""
    return workspace_path('prebuilts', 'rust', 'linux-x86',
                          STAGE0_RUST_VERSION, *args)


def llvm_prebuilt(*args):
    """Generates a path relative to the LLVM prebuilt directory."""
    clang_name = 'clang-{0}'.format(CLANG_REVISION)
    return workspace_path('prebuilts', 'clang', 'host', 'linux-x86',
                          clang_name, *args)


def cmake_prebuilt(*args):
    """Generates a path relative to the Cmake prebuilt directory."""
    return workspace_path('prebuilts', 'cmake', 'linux-x86', *args)


def build_tools_prebuilt(*args):
    """Generates a path relative to the build-tools prebuilt directory."""
    return workspace_path('prebuilts', 'build-tools', 'path', 'linux-x86',
                          *args)


def curl_prebuilt(*args):
    """Generates a path relative to the curl prebuilt directory."""
    return workspace_path('prebuilts', 'android-emulator-build', 'curl',
                          'linux-x86_64', *args)


def ndk(*args):
    """Generates a path relative to the prebuilt NDK.

    Use of the NDK should eventually be removed so as to make this a Platform
    target, but is used for now as a transition stage.
    """
    return workspace_path('toolchain', 'prebuilts', 'ndk', 'r20', 'toolchains',
                          'llvm', 'prebuilt', 'linux-x86_64', *args)


def ndk_cc(target, abi):
    """Finds the cc for a given abi + target from the NDK.

    Similar to ndk(), this should be removed eventually to make this a Platform
    target.
    """

    # Tools have a split name for arm in the NDK, handle it here
    parts = target.split('-')
    if parts[0] == 'arm':
        parts[0] = 'armv7a'
        target = '-'.join(parts)

    return ndk('bin', target + str(abi) + '-clang')
