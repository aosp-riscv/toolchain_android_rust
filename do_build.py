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
import subprocess
import sys

import build_platform
import config_toml
import paths


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
        "library/term",
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


def parse_args():
    """Parses arguments and returns the parsed structure."""
    parser = argparse.ArgumentParser('Build the Rust Toolchain')
    parser.add_argument('--build-name', type=str, default='dev',
                        help='Release name for the dist result')
    parser.add_argument('--no-patch-abort',
                        help='Don\'t abort on patch failure. \
                        Useful for local development.')
    return parser.parse_args()


def main():
    """Runs the configure-build-fixup-dist pipeline."""
    args = parse_args()
    build_name = args.build_name

    #
    # Update environment variables
    #

    env = dict(os.environ)
    env['PATH'] = os.pathsep.join(
        [p.as_posix() for p in [
          paths.rust_prebuilt('bin'),
          paths.cmake_prebuilt('bin'),
          paths.ninja_prebuilt(),
          paths.curl_prebuilt('lib'),
          paths.build_tools_prebuilt(),
        ]] + [env['PATH']])

    # Only adjust the library path on Linux - on OSX, use the devtools curl
    if build_platform.system() == 'linux':
        if 'LIBRARY_PATH' in env:
            old_library_path = ':{0}'.format(env['LIBRARY_PATH'])
        else:
            old_library_path = ''
        env['LIBRARY_PATH'] = '{0}{1}'.format(paths.curl_prebuilt('lib'), old_library_path)

    env['DESTDIR'] = paths.out_path()

    #
    # Initialize directories
    #

    paths.out_path().mkdir(exist_ok=True)

    # We take DIST_DIR through an environment variable rather than an
    # argument to match the interface for traditional Android builds.
    dist_dir = os.environ.get('DIST_DIR')
    if dist_dir:
        dist_dir = Path(dist_dir).resolve()
    else:
        dist_dir = paths.workspace_path('dist')

    dist_dir.mkdir(exist_ok=True)

    #
    # Apply patches
    #

    for filepath in sorted(paths.patches_path().glob('rustc-*')):
        with filepath.open(mode='rb') as file:
            p = subprocess.Popen(['patch', '-p1', '-N', '-r', '-'],
                                 cwd=paths.rustc_path(), stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE)
            out, _ = p.communicate(file.read())

            # Print output for logging purposes.
            print("Applying patch: " + filepath.as_posix())
            print(out)

            if p.returncode != 0 and not args.no_patch_abort:
                print("Build failed when applying patch {}"
                        .format(filepath.as_posix()))
                print("If developing locally, try the --no-patch-abort flag")
                sys.exit(p.returncode)

    #
    # Configure Rust
    #
    # Because some patches may have touched vendored source we will rebuild
    # Cargo.lock
    #

    config_toml.configure()

    # Trigger bootstrap to trigger vendoring
    #
    # Call is not checked because this is *expected* to fail - there isn't a
    # user facing way to directly trigger the bootstrap, so we give it a
    # no-op to perform that will require it to write out the cargo config.
    subprocess.call([paths.rustc_path('x.py'), '--help'],
                    cwd=paths.rustc_path(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Offline fetch to regenerate lockfile
    res = subprocess.check_output(
        [paths.rust_prebuilt('bin', 'cargo'), 'fetch', '--offline'],
        cwd=paths.rustc_path(), env=env)

    #
    # Build
    #
    ec = subprocess.Popen([paths.rustc_path('x.py'), '--stage', '3', 'install'],
                          cwd=paths.rustc_path(), env=env).wait()
    if ec != 0:
        print("Build stage failed with error {}".format(ec))
        sys.exit(ec)

    # Install sources
    if build_platform.system() == 'linux':
        shutil.rmtree(paths.stdlib_srcs(), ignore_errors=True)
        for stdlib in STDLIB_SOURCES:
            shutil.copytree(paths.rustc_path(stdlib), paths.stdlib_srcs(stdlib))

    # Fixup
    # The Rust build doesn't have an option to auto-strip binaries, so we do
    # it here.
    # We don't attempt to strip .rlibs since it prevents building Rust binaries.
    # We don't attempt to strip anything under rustlib/ since these include
    # both debug symbols which we may want to link into user code and Rust
    # metadata needed at build time.
    libs = list(paths.out_path('lib').glob('*.so'))
    subprocess.check_call(['strip', '-S'] + libs + [
        paths.out_path('bin', 'rustc'),
        paths.out_path('bin', 'cargo'),
        paths.out_path('bin', 'rustdoc')])

    # Install the libc++ library to lib64/
    if build_platform.system() == 'darwin':
        libcxx_name = 'libc++.dylib'
    else:
        libcxx_name = 'libc++.so.1'
    lib64_path = paths.out_path('lib64')
    if not lib64_path.exists():
        lib64_path.mkdir()
    shutil.copy2(paths.cxx_linker_path(libcxx_name),
                 paths.out_path('lib64', libcxx_name))

    # Some stdlib crates might include Android.mk or Android.bp files.
    # If they do, filter them out.
    if build_platform.system() == 'linux':
        for f in paths.stdlib_srcs().glob('**/Android.{mk,bp}'):
            f.unlink()

    # Dist
    tarball_path = dist_dir / 'rust-{0}.tar.gz'.format(build_name)
    subprocess.check_call(['tar', 'czf', tarball_path, '.'],
                          cwd=paths.out_path())

if __name__ == '__main__':
    main()
