#!/usr/bin/env python3
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

"""Creates a tarball suitable for use as a Rust prebuilt for Android."""

import argparse
import os
import os.path
from pathlib import Path
import shutil
import source_manager
import subprocess
import sys

import build_platform
import config
from paths import *


STDLIB_SOURCES = [
        "library/alloc",
        "library/backtrace",
        "library/core",
        "library/panic_abort",
        "library/panic_unwind",
        "library/proc_macro",
        "library/profiler_builtins",
        "library/std",
        "library/stdarch",
        "library/test",
        "library/unwind",
        "vendor/backtrace",
        "vendor/cfg-if",
        "vendor/compiler_builtins",
        "vendor/getopts",
        "vendor/hashbrown",
        "vendor/libc",
        "vendor/rustc-demangle",
        "vendor/unicode-width",
]

LLVM_BUILD_PATHS_OF_INTEREST: list[str] = [
    'build.ninja',
    'cmake',
    'CMakeCache.txt',
    'CMakeFiles',
    'cmake_install.cmake',
    'compile_commands.json',
    'CPackConfig.cmake',
    'CPackSourceConfig.cmake',
    'install_manifest.txt',
    'llvm.spec'
]

def lto_type(arg: str) -> str:
    arg = arg.lower()
    if arg == 'full' or arg == 'thin':
        return arg
    elif arg == 'none':
        return None
    else:
        raise argparse.ArgumentTypeError


def parse_args() -> argparse.ArgumentParser:
    """Parses arguments and returns the parsed structure."""
    parser = argparse.ArgumentParser('Build the Rust Toolchain')
    parser.add_argument('--build-name', type=str, default='dev',
                        help='Release name for the dist result')
    parser.add_argument('--lto', type=lto_type, default='none',
                        help='Type of LTO to perform. Valid LTO \
                        types: none, thin, full')
    parser.add_argument('--no-patch-abort',
                        help='Don\'t abort on patch failure. \
                        Useful for local development.')
    return parser.parse_args()


def main():
    """Runs the configure-build-fixup-dist pipeline."""
    args = parse_args()
    build_name = args.build_name

    # Add some output padding to make the messages easier to read
    print()

    #
    # Initialize directories
    #

    OUT_PATH.mkdir(exist_ok=True)
    OUT_PATH_PACKAGE.mkdir(exist_ok=True)
    OUT_PATH_WRAPPERS.mkdir(exist_ok=True)

    # We take DIST_DIR through an environment variable rather than an
    # argument to match the interface for traditional Android builds.
    dist_dir = os.environ.get('DIST_DIR')
    if dist_dir:
        dist_dir = Path(dist_dir).resolve()
    else:
        dist_dir = WORKSPACE_PATH / 'dist'

    dist_dir.mkdir(exist_ok=True)

    #
    # Setup source files
    #

    source_manager.setup_files(
      RUST_SOURCE_PATH, OUT_PATH_RUST_SOURCE, PATCHES_PATH,
      no_patch_abort=args.no_patch_abort)

    #
    # Configure Rust
    #

    env = dict(os.environ)
    config.configure(args, env)

    # Trigger bootstrap to trigger vendoring
    #
    # Call is not checked because this is *expected* to fail - there isn't a
    # user facing way to directly trigger the bootstrap, so we give it a
    # no-op to perform that will require it to write out the cargo config.
    subprocess.call([PYTHON_PATH, OUT_PATH_RUST_SOURCE / 'x.py', '--help'],
                    cwd=OUT_PATH_RUST_SOURCE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Offline fetch to regenerate lockfile
    #
    # Because some patches may have touched vendored source we will rebuild
    # Cargo.lock
    subprocess.check_output(
        [RUST_PREBUILT_PATH / 'bin' / 'cargo', 'fetch', '--offline'],
        cwd=OUT_PATH_RUST_SOURCE, env=env)

    #
    # Build
    #
    ec = subprocess.Popen([PYTHON_PATH, OUT_PATH_RUST_SOURCE / 'x.py',
                          '--stage', '3', 'install'], cwd=OUT_PATH_RUST_SOURCE, env=env).wait()
    if ec != 0:
        print("Build stage failed with error {}".format(ec))
        tarball_path = dist_dir / 'llvm-build-config.tar.gz'
        subprocess.check_call(['tar', 'czf', tarball_path] + LLVM_BUILD_PATHS_OF_INTEREST,
            cwd=LLVM_BUILD_PATH)
        sys.exit(ec)

    # Install sources
    if build_platform.is_linux():
        shutil.rmtree(OUT_PATH_STDLIB_SRCS, ignore_errors=True)
        for stdlib in STDLIB_SOURCES:
            shutil.copytree(OUT_PATH_RUST_SOURCE / stdlib, OUT_PATH_STDLIB_SRCS / stdlib)

    # Fixup
    # The Rust build doesn't have an option to auto-strip binaries, so we do
    # it here.
    # We don't attempt to strip .rlibs since it prevents building Rust binaries.
    # We don't attempt to strip anything under rustlib/ since these include
    # both debug symbols which we may want to link into user code and Rust
    # metadata needed at build time.
    libs = list((OUT_PATH_PACKAGE / 'lib').glob('*.so'))
    subprocess.check_call(['strip', '-S'] + libs + [
        OUT_PATH_PACKAGE / 'bin' / 'rustc',
        OUT_PATH_PACKAGE / 'bin' / 'cargo',
        OUT_PATH_PACKAGE / 'bin' / 'rustdoc'])

    # Install the libc++ library to out/package/lib64/
    if build_platform.is_darwin():
        libcxx_name = 'libc++.dylib'
    else:
        libcxx_name = 'libc++.so.1'

    lib64_path = OUT_PATH_PACKAGE / 'lib64'
    lib64_path.mkdir(exist_ok=True)
    shutil.copy2(LLVM_CXX_RUNTIME_PATH / libcxx_name,
                 lib64_path / libcxx_name)

    # Some stdlib crates might include Android.mk or Android.bp files.
    # If they do, filter them out.
    if build_platform.is_linux():
        for f in OUT_PATH_STDLIB_SRCS.glob('**/Android.{mk,bp}'):
            f.unlink()

    # Dist
    print("Creating distribution archive")
    tarball_path = dist_dir / 'rust-{0}.tar.gz'.format(build_name)
    subprocess.check_call(['tar', 'czf', tarball_path, '.'],
        cwd=OUT_PATH_PACKAGE)

if __name__ == '__main__':
    main()
