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
import subprocess
import stat

import build_platform
import paths

host_targets = [build_platform.triple()] + build_platform.alt_triples()
device_targets = ['aarch64-linux-android', 'armv7-linux-androideabi',
                  'x86_64-linux-android', 'i686-linux-android']
all_targets = host_targets + device_targets


def configure():
    """Generates config.toml for the rustc build."""
    with open(paths.rustc_path('config.toml'), 'w') as config_toml:
        cargo = paths.rust_prebuilt('bin', 'cargo')
        rustc = paths.rust_prebuilt('bin', 'rustc')
        cc = paths.llvm_prebuilt('bin', 'clang')
        cxx = paths.llvm_prebuilt('bin', 'clang++')
        ar = paths.llvm_prebuilt('bin', 'llvm-ar')
        cxxstd = paths.llvm_prebuilt('include', 'c++', 'v1')
        ranlib = paths.llvm_prebuilt('bin', 'llvm-ranlib')
        # Add the path at which libc++ can be found in Android checkouts
        cxx_linker_flags = ' -Wl,-rpath,'
        if build_platform.system() == 'darwin':
            cxx_linker_flags += '@loader_path/../lib64'
        else:
            cxx_linker_flags += '\\$ORIGIN/../lib64'
        # Add the path at which libc++ can be found during the build
        cxx_linker_flags += ' -Wl,-rpath,' + paths.cxx_linker_path()

        def host_config(target):
            wrapper_name = paths.this_path('clang-%s' % target)
            cxx_wrapper_name = paths.this_path('clang++-%s' % target)

            sysroot = None
            # Apple removed the normal sysroot at / on Mojave+, so we need
            # to go hunt for it on OSX
            # On pre-Mojave, this command will output the empty string.
            if build_platform.system() == 'darwin':
                sysroot = subprocess.check_output(['xcrun', '--sdk', 'macosx',
                                                   '--show-sdk-path']).rstrip()

            if sysroot:
                sysroot_flags = "--sysroot " + sysroot
            else:
                sysroot_flags = ""

            ld_option = '-fuse-ld=lld' if build_platform.system() == 'linux' else ''

            with open(wrapper_name, 'w') as f:
                f.write("""\
#!/bin/sh
{real_cc} $* {ld_option} --target={target} {sysroot_flags}
""".format(real_cc=cc, ld_option=ld_option, target=target, sysroot_flags=sysroot_flags))

            with open(cxx_wrapper_name, 'w') as f:
                f.write("""\
#!/bin/sh
{real_cxx} -I{cxxstd} $* {ld_option} --target={target} {sysroot_flags} {cxx_linker_flags} \
        -stdlib=libc++
""".format(real_cxx=cxx, ld_option=ld_option, target=target, sysroot_flags=sysroot_flags,
           cxxstd=cxxstd,
           cxx_linker_flags=cxx_linker_flags))

            s = os.stat(wrapper_name)
            os.chmod(wrapper_name, s.st_mode | stat.S_IEXEC)
            s = os.stat(cxx_wrapper_name)
            os.chmod(cxx_wrapper_name, s.st_mode | stat.S_IEXEC)
            return """\
[target.{target}]
cc = "{cc}"
cxx = "{cxx}"
ar = "{ar}"
ranlib = "{ranlib}"
linker = "{cxx}"
""".format(cc=wrapper_name, cxx=cxx_wrapper_name, ar=ar, ranlib=ranlib, target=target)

        def device_config(target):
            wrapper_name = paths.this_path('clang-%s' % target)
            with open(wrapper_name, 'w') as f:
                f.write("""\
#!/bin/sh
{real_cc} $* -fuse-ld=lld --target={target} --sysroot={sysroot} \
        -L{gcc_libdir} -L{sys_dir} -isystem {sys_includes} \
        -isystem {target_includes}
""".format(real_cc=cc, sysroot=paths.plat_ndk_sysroot(target),
           sys_includes=paths.sys_includes(),
           target_includes=paths.target_includes(target), target=target,
           gcc_libdir=paths.gcc_libdir(target),
           sys_dir=paths.plat_ndk_llvm_libs(target)))
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
targets = "AArch64;ARM;X86"
experimental-targets = ""
use-libcxx = true
[build]
target = {all_targets_config}
cargo = "{cargo}"
rustc = "{rustc}"
verbose = 1
profiler = true
docs = false
submodules = false
locked-deps = true
vendor = true
full-bootstrap = true
extended = true
tools = ["cargo", "clippy", "rustfmt", "rust-analyzer"]
cargo-native-static = true
[install]
prefix = "/"
sysconfdir = "etc"
[rust]
channel = "dev"
remap-debuginfo = true
deny-warnings = false
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
