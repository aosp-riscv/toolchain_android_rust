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
"""Handles generation of config.toml for the rustc build."""

import subprocess
import stat
from string import Template

import build_platform
from paths import *


HOST_TARGETS: list[str] = [build_platform.triple()] + build_platform.alt_triples()
DEVICE_TARGETS: list[str] = ['aarch64-linux-android', 'armv7-linux-androideabi',
                  'x86_64-linux-android', 'i686-linux-android']

ALL_TARGETS: list[str] = HOST_TARGETS + DEVICE_TARGETS

ANDROID_TARGET_VERSION: str = '31'

CONFIG_TOML_TEMPLATE:           Path = TEMPLATES_PATH / 'config.toml.template'
DEVICE_CC_WRAPPER_TEMPLATE:     Path = TEMPLATES_PATH / 'device_cc_wrapper.template'
DEVICE_LINKER_WRAPPER_TEMPLATE: Path = TEMPLATES_PATH / 'device_linker_wrapper.template'
DEVICE_TARGET_TEMPLATE:         Path = TEMPLATES_PATH / 'device_target.template'
HOST_CC_WRAPPER_TEMPLATE:       Path = TEMPLATES_PATH / 'host_cc_wrapper.template'
HOST_CXX_WRAPPER_TEMPLATE:      Path = TEMPLATES_PATH / 'host_cxx_wrapper.template'
HOST_LINKER_WRAPPER_TEMPLATE:   Path = TEMPLATES_PATH / 'host_linker_wrapper.template'
HOST_TARGET_TEMPLATE:           Path = TEMPLATES_PATH / 'host_target.template'

LD_SELECTOR:         str = '-fuse-ld=lld' if build_platform.system() == 'linux' else ''
MACOSX_VERSION_FLAG: str = '-mmacosx-version-min=10.14'

LLVM_LIBPATH_ARGUMENT: str = '-L' + LLVM_CXX_RUNTIME_PATH.as_posix()

CXX_RPATH_BUILDTIME: str = '-Wl,-rpath,' + LLVM_CXX_RUNTIME_PATH.as_posix()
CXX_RPATH_RUNTIME:   str = '-Wl,-rpath,' + (
    '@loader_path/../lib64' if build_platform.system() == 'darwin' else '\\$ORIGIN/../lib64')

CXX_LINKER_FLAGS_BUILDTIME = LLVM_LIBPATH_ARGUMENT      + ' ' + CXX_RPATH_BUILDTIME
CXX_LINKER_FLAGS           = CXX_LINKER_FLAGS_BUILDTIME + ' ' + CXX_RPATH_RUNTIME


def instantiate_template_exec(template_path: Path, output_path: Path, **kwargs):
    instantiate_template_file(template_path, output_path, make_exec=True, **kwargs)

def instantiate_template_file(template_path: Path, output_path: Path, make_exec: bool = False, **kwargs) -> None:
    with open(template_path) as template_file:
        template = Template(template_file.read())
        with open(output_path, 'w') as output_file:
            output_file.write(template.substitute(**kwargs))
    if make_exec:
        output_path.chmod(output_path.stat().st_mode | stat.S_IEXEC)


def host_config(target: str, macosx_flags: str, bin_search_flags: str) -> str:
    cc_wrapper_name     = OUT_PATH_WRAPPERS / ('clang-%s' % target)
    cxx_wrapper_name    = OUT_PATH_WRAPPERS / ('clang++-%s' % target)
    linker_wrapper_name = OUT_PATH_WRAPPERS / ('linker-%s' % target)

    instantiate_template_exec(
        HOST_CC_WRAPPER_TEMPLATE,
        cc_wrapper_name,
        real_cc=CC_PATH,
        target=target,
        macosx_flags=macosx_flags,
        bin_search_flags=bin_search_flags)

    instantiate_template_exec(
        HOST_CXX_WRAPPER_TEMPLATE,
        cxx_wrapper_name,
        real_cxx=CXX_PATH,
        target=target,
        macosx_flags=macosx_flags,
        bin_search_flags=bin_search_flags,
        cxxstd=CXXSTD_PATH)

    instantiate_template_exec(
        HOST_LINKER_WRAPPER_TEMPLATE,
        linker_wrapper_name,
        real_cxx=CXX_PATH,
        ld_selector=LD_SELECTOR,
        target=target,
        macosx_flags=macosx_flags,
        bin_search_flags=bin_search_flags,
        cxx_linker_flags=CXX_LINKER_FLAGS)

    with open(HOST_TARGET_TEMPLATE, 'r') as template_file:
        return Template(template_file.read()).substitute(
            target=target,
            cc=cc_wrapper_name,
            cxx=cxx_wrapper_name,
            linker=linker_wrapper_name,
            ar=AR_PATH,
            ranlib=RANLIB_PATH)


def device_config(target: str) -> str:
    cc_wrapper_name     = OUT_PATH_WRAPPERS / ('clang-%s' % target)
    linker_wrapper_name = OUT_PATH_WRAPPERS / ('linker-%s' % target)

    clang_target = target + ANDROID_TARGET_VERSION

    instantiate_template_exec(
        DEVICE_CC_WRAPPER_TEMPLATE,
        cc_wrapper_name,
        real_cc=CC_PATH,
        target=clang_target,
        sysroot=NDK_SYSROOT_PATH)

    instantiate_template_exec(
        DEVICE_LINKER_WRAPPER_TEMPLATE,
        linker_wrapper_name,
        real_cc=CC_PATH,
        target=clang_target,
        sysroot=NDK_SYSROOT_PATH)

    with open(DEVICE_TARGET_TEMPLATE, 'r') as template_file:
        return Template(template_file.read()).substitute(
            target=target,
            cc=cc_wrapper_name,
            linker=linker_wrapper_name,
            ar=AR_PATH)


def configure():
    """Generates config.toml and compiler wrapers for the rustc build."""
    macosx_flags = ''
    linux_bin_search_flags = ''

    if build_platform.system() == 'darwin':
        # Apple removed the normal sysroot at / on Mojave+, so we need
        # to go hunt for it on OSX
        # On pre-Mojave, this command will output the empty string.
        output = subprocess.check_output(
            ['xcrun', '--sdk', 'macosx', '--show-sdk-path'])
        macosx_flags = (
            MACOSX_VERSION_FLAG +
            " --sysroot " + output.rstrip().decode('utf-8'))
    else:
        # On Linux build hosts we need to set the path to the gcc toolchain.
        linux_bin_search_flags = "-B " + GCC_TOOLCHAIN_PATH.as_posix()

    host_configs = '\n'.join(
        [host_config(target, macosx_flags, linux_bin_search_flags) for target in HOST_TARGETS])
    device_configs = '\n'.join(
        [device_config(target) for target in DEVICE_TARGETS])

    all_targets = '[' + ','.join(
        ['"' + target + '"' for target in ALL_TARGETS]) + ']'

    instantiate_template_file(
        CONFIG_TOML_TEMPLATE,
        OUT_PATH_RUST_SOURCE / 'config.toml',
        llvm_ldflags=LD_SELECTOR + ' ' + CXX_LINKER_FLAGS_BUILDTIME,
        all_targets=all_targets,
        cargo=CARGO_PATH,
        rustc=RUSTC_PATH,
        python=PYTHON_PATH,
        host_configs=host_configs,
        device_configs=device_configs)
