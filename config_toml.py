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
import paths
import stat

host_targets = ['x86_64-unknown-linux-gnu']
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
            wrapper_name = paths.this_path('clang-with-lld-%s' % target)
            with open(wrapper_name, 'w') as f:
                f.write("""\
#!/bin/sh
{real_cc} $* -fuse-ld=lld
""".format(real_cc=paths.ndk_cc(target, 29)))
            s = os.stat(wrapper_name)
            os.chmod(wrapper_name, s.st_mode | stat.S_IEXEC)
            return """\
[target.{target}]
cc="{cc}"
ar="{ar}"
android-ndk="{ndk}"
""".format(ndk=paths.ndk(), ar=ar, cc=wrapper_name, target=target)

        host_configs = '\n'.join(
            [host_config(target) for target in host_targets])
        device_configs = '\n'.join(
            [device_config(target) for target in device_targets])

        all_targets_config = '[' + ','.join(
            ['"' + target + '"' for target in all_targets]) + ']'
        config_toml.write("""\
[llvm]
ninja = true
targets = "AArch64;ARM;X86"
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
