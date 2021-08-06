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

CONFIG_TOML_TEMPLATE:           Path = TEMPLATES_PATH / 'config.toml.template'
DEVICE_CC_WRAPPER_TEMPLATE:     Path = TEMPLATES_PATH / 'device_cc_wrapper.template'
DEVICE_LINKER_WRAPPER_TEMPLATE: Path = TEMPLATES_PATH / 'device_linker_wrapper.template'
DEVICE_TARGET_TEMPLATE:         Path = TEMPLATES_PATH / 'device_target.template'
HOST_CC_WRAPPER_TEMPLATE:       Path = TEMPLATES_PATH / 'host_cc_wrapper.template'
HOST_CXX_WRAPPER_TEMPLATE:      Path = TEMPLATES_PATH / 'host_cxx_wrapper.template'
HOST_LINKER_WRAPPER_TEMPLATE:   Path = TEMPLATES_PATH / 'host_linker_wrapper.template'
HOST_TARGET_TEMPLATE:           Path = TEMPLATES_PATH / 'host_target.template'

CARGO_PATH:  Path = RUST_PREBUILT_PATH   / 'bin' / 'cargo'
RUSTC_PATH:  Path = RUST_PREBUILT_PATH   / 'bin' / 'rustc'
PYTHON_PATH: Path = PYTHON_PREBUILT_PATH / 'bin' / 'python3'
CC_PATH:     Path = LLVM_PREBUILT_PATH   / 'bin' / 'clang'
CXX_PATH:    Path = LLVM_PREBUILT_PATH   / 'bin' / 'clang++'
AR_PATH:     Path = LLVM_PREBUILT_PATH   / 'bin' / 'llvm-ar'
RANLIB_PATH: Path = LLVM_PREBUILT_PATH   / 'bin' / 'llvm-ranlib'
CXXSTD_PATH: Path = LLVM_PREBUILT_PATH   / 'include' / 'c++' / 'v1'

LD_SELECTOR: str = '-fuse-ld=lld' if build_platform.system() == 'linux' else ''

LD_RPATH_BUILDTIME = '-rpath ' + LLVM_CXX_RUNTIME_PATH.as_posix()

CXX_RPATH_BUILDTIME = '-Wl,-rpath,' + LLVM_CXX_RUNTIME_PATH.as_posix()
CXX_RPATH_RUNTIME   = '-Wl,-rpath,' + (
    '@loader_path/../lib64' if build_platform.system() == 'darwin' else '\\$ORIGIN/../lib64')

CXX_LINKER_FLAGS = CXX_RPATH_BUILDTIME + ' ' + CXX_RPATH_RUNTIME


def instantiate_template_exec(template_path: Path, output_path: Path, **kwargs):
    instantiate_template_file(template_path, output_path, make_exec=True, **kwargs)

def instantiate_template_file(template_path: Path, output_path: Path, make_exec: bool = False, **kwargs) -> None:
    with open(template_path) as template_file:
        template = Template(template_file.read())
        with open(output_path, 'w') as output_file:
            output_file.write(template.substitute(**kwargs))
    if make_exec:
        output_path.chmod(output_path.stat().st_mode | stat.S_IEXEC)


def host_config(target: str, sysroot_flags: str) -> str:
    cc_wrapper_name     = OUT_PATH_WRAPPERS / ('clang-%s' % target)
    cxx_wrapper_name    = OUT_PATH_WRAPPERS / ('clang++-%s' % target)
    linker_wrapper_name = OUT_PATH_WRAPPERS / ('linker-%s' % target)

    instantiate_template_exec(
        HOST_CC_WRAPPER_TEMPLATE,
        cc_wrapper_name,
        real_cc=CC_PATH,
        target=target,
        sysroot_flags=sysroot_flags)

    instantiate_template_exec(
        HOST_CXX_WRAPPER_TEMPLATE,
        cxx_wrapper_name,
        real_cxx=CXX_PATH,
        cxxstd=CXXSTD_PATH,
        target=target,
        sysroot_flags=sysroot_flags)

    instantiate_template_exec(
        HOST_LINKER_WRAPPER_TEMPLATE,
        linker_wrapper_name,
        real_cxx=CXX_PATH,
        ld_selector=LD_SELECTOR,
        sysroot_flags=sysroot_flags,
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
    cc_wrapper_name = OUT_PATH_WRAPPERS / ('clang-%s' % target)
    linker_wrapper_name = OUT_PATH_WRAPPERS / ('linker-%s' % target)

    instantiate_template_exec(
        DEVICE_CC_WRAPPER_TEMPLATE,
        cc_wrapper_name,
        real_cc=CC_PATH,
        target=target,
        sysroot=plat_ndk_sysroot_path(target),
        ndk_includes=NDK_INCLUDE_PATH,
        target_includes=target_includes_path(target))

    instantiate_template_exec(
        DEVICE_LINKER_WRAPPER_TEMPLATE,
        linker_wrapper_name,
        real_cc=CC_PATH,
        target=target,
        sysroot=plat_ndk_sysroot_path(target),
        sys_dir=plat_ndk_llvm_libs_path(target))

    with open(DEVICE_TARGET_TEMPLATE, 'r') as template_file:
        return Template(template_file.read()).substitute(
            target=target, cc=cc_wrapper_name, linker=linker_wrapper_name, ar=AR_PATH)


def configure():
    """Generates config.toml for the rustc build."""
    sysroot = None
    # Apple removed the normal sysroot at / on Mojave+, so we need
    # to go hunt for it on OSX
    # On pre-Mojave, this command will output the empty string.
    if build_platform.system() == 'darwin':
        output = subprocess.check_output(
            ['xcrun', '--sdk', 'macosx', '--show-sdk-path'])
        sysroot = output.rstrip().decode('utf-8')
    host_sysroot_flags = ("--sysroot " + sysroot) if sysroot else ""

    host_configs = '\n'.join(
        [host_config(target, host_sysroot_flags) for target in HOST_TARGETS])
    device_configs = '\n'.join(
        [device_config(target) for target in DEVICE_TARGETS])

    all_targets = '[' + ','.join(
        ['"' + target + '"' for target in ALL_TARGETS]) + ']'

    instantiate_template_file(
        CONFIG_TOML_TEMPLATE,
        OUT_PATH_RUST_SOURCE / 'config.toml',
        llvm_ldflags=LD_RPATH_BUILDTIME,
        all_targets=all_targets,
        cargo=CARGO_PATH,
        rustc=RUSTC_PATH,
        python=PYTHON_PATH,
        host_configs=host_configs,
        device_configs=device_configs)
