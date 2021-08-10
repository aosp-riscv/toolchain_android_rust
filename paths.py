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

from pathlib import Path
import build_platform

STAGE0_RUST_VERSION = '1.54.0'
CLANG_REVISION = 'r428724'
CLANG_NAME: str = 'clang-{0}'.format(CLANG_REVISION)

TOOLCHAIN_PATH:   Path = Path(__file__).parent.resolve()
WORKSPACE_PATH:   Path = (TOOLCHAIN_PATH / '..' / '..').resolve()
RUST_SOURCE_PATH: Path = (TOOLCHAIN_PATH / '..' / 'rustc').resolve()

PATCHES_PATH:   Path = TOOLCHAIN_PATH / 'patches'
TEMPLATES_PATH: Path = TOOLCHAIN_PATH / 'templates'

OUT_PATH:             Path = WORKSPACE_PATH / 'out'
OUT_PATH_RUST_SOURCE: Path = OUT_PATH / 'rustc'
OUT_PATH_PACKAGE:     Path = OUT_PATH / 'package'
OUT_PATH_STDLIB_SRCS: Path = OUT_PATH_PACKAGE / 'src' / 'stdlibs'
OUT_PATH_WRAPPERS:    Path = OUT_PATH / 'wrappers'

PREBUILT_PATH:         Path = WORKSPACE_PATH / 'prebuilts'
RUST_PREBUILT_PATH:    Path = PREBUILT_PATH / 'rust' / build_platform.prebuilt() / STAGE0_RUST_VERSION
LLVM_PREBUILT_PATH:    Path = PREBUILT_PATH / 'clang' / 'host' / build_platform.prebuilt() / CLANG_NAME
LLVM_CXX_RUNTIME_PATH: Path = LLVM_PREBUILT_PATH / 'lib64'

# We live at      prebuilts/rust/${BUILD_PLATFORM}/${VERSION}/bin
# libc++ lives at prebuilts/clang/host/${BUILD_PLATFORM}
#                 /clang-${CLANG_REVISION}/lib64
ANDROID_CXX_RUNTIME_PATH: Path = (
    WORKSPACE_PATH / '..' / '..' / 'clang' / 'host' /
        build_platform.prebuilt() / CLANG_NAME / 'lib64').resolve()

PYTHON_PREBUILT_PATH:      Path = PREBUILT_PATH / 'python' / build_platform.prebuilt()
CMAKE_PREBUILT_PATH:       Path = PREBUILT_PATH / 'cmake' / build_platform.prebuilt()
NINJA_PREBUILT_PATH:       Path = PREBUILT_PATH / 'ninja' / build_platform.prebuilt()
BUILD_TOOLS_PREBUILT_PATH: Path = PREBUILT_PATH / 'build-tools' / 'path' / build_platform.prebuilt()
CURL_PREBUILT_PATH:        Path = PREBUILT_PATH / 'android-emulator-build' / 'cur' / build_platform.prebuilt_full()

# Use of the NDK should eventually be removed so as to make this a Platform
# target, but is used for now as a transition stage.
NDK_PATH:         Path = WORKSPACE_PATH / 'toolchain' / 'prebuilts' / 'ndk' / 'r20'
NDK_SYSROOT_PATH: Path = NDK_PATH / 'sysroot'
NDK_INCLUDE_PATH: Path = NDK_SYSROOT_PATH / 'usr' / 'include'
NDK_LLVM_PATH:    Path = NDK_PATH / 'toolchains' / 'llvm' / 'prebuilts' / 'linux-x86_64'

def target_includes_path(target) -> Path:
    """Generates a path relative to the target-specific NDK include dir."""
    return NDK_INCLUDE_PATH / normalize_target(target)


def plat_ndk_llvm_libs_path(target) -> Path:
    """Generates a path relative to the target's LLVM NDK sysroot libs"""
    return NDK_LLVM_PATH / 'sysroot' / 'usr' / 'lib' / normalize_target(target)


def plat_ndk_sysroot_path(target) -> Path:
    """Generates a path relative to the NDK platform-specific sysroot.

    This sysroot is incomplete, and contains only the object files, not the
    headers. However, the primary sysroot has the object files behind an
    additional level of indirection for the API level which platform clang
    does not look through.
    """
    return NDK_PATH / 'platforms' / 'android-29' / ('arch-' + extract_arch(target))


def gcc_libdir_path(target) -> Path:
    """Locates the directory with the gcc library target prebuilts."""
    return NDK_LLVM_PATH / 'lib' / 'gcc' / normalize_target(target) / '4.9.x'


def extract_arch(target):
    """Extracts from a target the android-style arch"""
    canon_arch = target.split('-')[0]
    if canon_arch == 'aarch64':
        return 'arm64'
    if canon_arch == 'armv7':
        return 'arm'
    if canon_arch == 'i686':
        return 'x86'
    return canon_arch


def normalize_target(target):
    """Translates triples into their general form."""
    if target == 'armv7-linux-androideabi':
        return 'arm-linux-androideabi'
    return target