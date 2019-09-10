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

import os
import stat

import build_platform
import paths

host_targets = [build_platform.triple()]
device_targets = ['aarch64-linux-android', 'arm-linux-androideabi']
all_targets = host_targets + device_targets


def configure():
    """Generates config.toml for the rustc build."""
    with open(paths.rustc_path('config.toml'), 'w') as config_toml:
        cargo = paths.rust_prebuilt('bin', 'cargo')
        rustc = paths.rust_prebuilt('bin', 'rustc')
        cc = paths.llvm_prebuilt('bin', 'clang')
        cxx = paths.llvm_prebuilt('bin', 'clang++')
        ar = paths.llvm_prebuilt('bin', 'llvm-ar')
        ranlib = paths.llvm_prebuilt('bin', 'llvm-ranlib')

        def host_config(target):
            return """\
[target.{target}]
cc = "{cc}"
cxx = "{cxx}"
ar = "{ar}"
ranlib = "{ranlib}"
""".format(cc=cc, cxx=cxx, ar=ar, ranlib=ranlib, target=target)

        def device_config(target):
            wrapper_name = paths.this_path('clang-%s' % target)
            with open(wrapper_name, 'w') as f:
                f.write("""\
#!/bin/sh
{real_cc} $* -fuse-ld=lld --target={target} --sysroot={sysroot} \
        -L{gcc_libdir} -isystem {sys_includes} -isystem {sys_includes}/{target}
""".format(real_cc=cc, sysroot=paths.plat_ndk_sysroot(target),
           sys_includes=paths.ndk_sysroot('usr', 'include'), target=target,
           gcc_libdir=paths.gcc_libdir(target)))
            s = os.stat(wrapper_name)
            os.chmod(wrapper_name, s.st_mode | stat.S_IEXEC)
            return """\
[target.{target}]
cc="{cc}"
ar="{ar}"
""".format(ar=ar, cc=wrapper_name, target=target)

        host_configs = '\n'.join(
            [host_config(target) for target in host_targets])
        device_configs = '\n'.join(
            [device_config(target) for target in device_targets])

        all_targets_config = '[' + ','.join(
            ['"' + target + '"' for target in all_targets]) + ']'
        config_toml.write("""\
[llvm]
ninja = true
[build]
target = {all_targets_config}
cargo = "{cargo}"
rustc = "{rustc}"
docs = false
submodules = false
locked-deps = true
vendor = true
full-bootstrap = true
extended = true
tools = ["cargo"]
cargo-native-static = true
[install]
prefix = "/"
sysconfdir = "etc"
[rust]
channel = "dev"
remap-debuginfo = true
{host_configs}
{device_configs}
""".format(cargo=cargo,
           rustc=rustc,
           cc=cc,
           cxx=cxx,
           ar=ar,
           ranlib=ranlib,
           host_configs=host_configs,
           device_configs=device_configs,
           all_targets_config=all_targets_config))
