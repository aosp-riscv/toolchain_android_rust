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

CONFIG_TOML_TEMPLATE:       Path = TEMPLATES_PATH / 'config.toml.template'
DEVICE_CC_WRAPPER_TEMPLATE: Path = TEMPLATES_PATH / 'device_cc_wrapper.template'
DEVICE_TARGET_TEMPLATE:     Path = TEMPLATES_PATH / 'device_target.template'
HOST_CC_WRAPPER_TEMPLATE:   Path = TEMPLATES_PATH / 'host_cc_wrapper.template'
HOST_CXX_WRAPPER_TEMPLATE:  Path = TEMPLATES_PATH / 'host_cxx_wrapper.template'
HOST_TARGET_TEMPLATE:       Path = TEMPLATES_PATH / 'host_target.template'

# Add the path at which libc++ can be found in Android checkouts
CXX_LINKER_FLAGS: str = ' -Wl,-rpath,'
if build_platform.system() == 'darwin':
    CXX_LINKER_FLAGS += '@loader_path/../lib64'
    CXX_LINKER_FLAGS += ' -mmacosx-version-min=10.14'
else:
    CXX_LINKER_FLAGS += '\\$ORIGIN/../lib64'
# Add the path at which libc++ can be found during the build
CXX_LINKER_FLAGS += (' -L' + LLVM_CXX_RUNTIME_PATH.as_posix() +
                     ' -Wl,-rpath,' + LLVM_CXX_RUNTIME_PATH.as_posix())

LD_OPTIONS: str = None
if build_platform.system() == 'linux':
    LD_OPTIONS = '-fuse-ld=lld -Wno-unused-command-line-argument'
else:
    LD_OPTIONS = ''


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
    cc_wrapper_name  = OUT_PATH_WRAPPERS / ('clang-%s' % target)
    cxx_wrapper_name = OUT_PATH_WRAPPERS / ('clang++-%s' % target)

    instantiate_template_exec(
        HOST_CC_WRAPPER_TEMPLATE,
        cc_wrapper_name,
        real_cc=CC_PATH,
        ld_option=LD_OPTIONS,
        target=target,
        sysroot_flags=sysroot_flags)

    instantiate_template_exec(
        HOST_CXX_WRAPPER_TEMPLATE,
        cxx_wrapper_name,
        real_cxx=CXX_PATH,
        ld_option=LD_OPTIONS,
        target=target,
        sysroot_flags=sysroot_flags,
        cxxstd=CXXSTD_PATH,
        cxx_linker_flags=CXX_LINKER_FLAGS)

    with open(HOST_TARGET_TEMPLATE, 'r') as template_file:
        return Template(template_file.read()).substitute(
            target=target,
            cc=cc_wrapper_name,
            cxx=cxx_wrapper_name,
            ar=AR_PATH,
            ranlib=RANLIB_PATH)


def device_config(target: str) -> str:
    cc_wrapper_name = OUT_PATH_WRAPPERS / ('clang-%s' % target)

    clang_target = target + ANDROID_TARGET_VERSION

    instantiate_template_exec(
        DEVICE_CC_WRAPPER_TEMPLATE,
        cc_wrapper_name,
        real_cc=CC_PATH,
        target=clang_target,
        sysroot=NDK_SYSROOT_PATH)

    with open(DEVICE_TARGET_TEMPLATE, 'r') as template_file:
        return Template(template_file.read()).substitute(
            target=target, cc=cc_wrapper_name, ar=AR_PATH)


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
        all_targets=all_targets,
        cargo=CARGO_PATH,
        rustc=RUSTC_PATH,
        python=PYTHON_PATH,
        host_configs=host_configs,
        device_configs=device_configs)
