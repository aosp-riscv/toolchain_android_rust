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
import build_platform

THIS_DIR = os.path.realpath(os.path.dirname(__file__))

STAGE0_RUST_VERSION = '1.40.0'
CLANG_REVISION = 'r377782'


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

def stdlib_srcs(*args):
    """Generates a path relative to the directory to install stdlib sources."""
    return out_path('src', 'stdlibs', *args)

def rust_prebuilt(*args):
    """Generates a path relative to the rust prebuilt directory."""
    return workspace_path('prebuilts', 'rust', build_platform.prebuilt(),
                          STAGE0_RUST_VERSION, *args)


def llvm_prebuilt(*args):
    """Generates a path relative to the LLVM prebuilt directory."""
    clang_name = 'clang-{0}'.format(CLANG_REVISION)
    return workspace_path('prebuilts', 'clang', 'host',
                          build_platform.prebuilt(), clang_name, *args)


def cmake_prebuilt(*args):
    """Generates a path relative to the Cmake prebuilt directory."""
    return workspace_path('prebuilts', 'cmake', build_platform.prebuilt(),
                          *args)


def build_tools_prebuilt(*args):
    """Generates a path relative to the build-tools prebuilt directory."""
    return workspace_path('prebuilts', 'build-tools', 'path',
                          build_platform.prebuilt(), *args)


def curl_prebuilt(*args):
    """Generates a path relative to the curl prebuilt directory."""
    return workspace_path('prebuilts', 'android-emulator-build', 'curl',
                          build_platform.prebuilt_full(), *args)


def ndk(*args):
    """Generates a path relative to the prebuilt NDK.

    Use of the NDK should eventually be removed so as to make this a Platform
    target, but is used for now as a transition stage.
    """
    return workspace_path('toolchain', 'prebuilts', 'ndk', 'r20', *args)


def extract_arch(target):
    """Extracts from a target the android-style arch"""
    canon_arch = target.split('-')[0]
    if canon_arch == 'aarch64':
        return 'arm64'
    return canon_arch


def ndk_sysroot(*args):
    """Generates a path relative to the NDK sysroot."""
    return ndk('sysroot', *args)


def plat_ndk_sysroot(target, *args):
    """Generates a path relative to the NDK platform-specific sysroot.

    This sysroot is incomplete, and contains only the object files, not the
    headers. However, the primary sysroot has the object files behind an
    additional level of indirection for the API level which platform clang
    does not look through.
    """
    return ndk('platforms', 'android-29', 'arch-' + extract_arch(target),
               *args)


def gcc_libdir(target, *args):
    """Locates the directory with the gcc library target prebuilts."""
    canon_arch = target.split('-')[0]
    return workspace_path('prebuilts', 'gcc', build_platform.prebuilt(),
                          canon_arch, target + '-4.9', 'lib', 'gcc', target,
                          '4.9.x', *args)
