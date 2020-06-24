#!/usr/bin/env python
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
import errno
import glob
import os
import os.path
import shutil
import subprocess
import sys

import build_platform
import config_toml
import paths


STDLIB_SOURCES = [
        "src/liballoc",
        "src/libcore",
        "src/libpanic_abort",
        "src/libpanic_unwind",
        "src/libprofiler_builtins",
        "src/libstd",
        "src/libterm",
        "src/libtest",
        "src/libunwind",
        "src/stdarch",
        "vendor/backtrace",
        "vendor/backtrace-sys",
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
    # We take DIST_DIR through an environment variable rather than an
    # argument to match the interface for traditional Android builds.
    dist_dir = os.environ['DIST_DIR']

    # Pre-create target directories
    try:
        os.makedirs(paths.out_path())
    except OSError as exn:
        if exn.errno != errno.EEXIST:
            raise
    try:
        os.makedirs(dist_dir)
    except OSError as exn:
        if exn.errno != errno.EEXIST:
            raise

    # Apply patches
    for filename in glob.glob(paths.patches_path('rustc-*')):
        with open(filename, 'r') as file:
            p = subprocess.Popen(['patch', '-p1', '-N', '-r', '-'],
                                 cwd=paths.rustc_path(), stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE)
            out, _ = p.communicate(file.read())

            # Print output for logging purposes.
            print("Applying patch: " + filename)
            print(out)

            # Check for the presence of FAILED as the error code is the same
            # for a failed patch and an already-applied patch. This makes it
            # less painful for developers.
            if 'FAILED' in out and not args.no_patch_abort:
                print("Build failed when applying patch {}"
                        .format(filename))
                print("If developing locally, try the --no-patch-abort flag")
                sys.exit(p.returncode)


    # Configure
    config_toml.configure()

    # Since some patches may touch vendored source, rebuild Cargo.lock
    cargo = paths.rust_prebuilt('bin', 'cargo')
    # Trigger bootstrap to trigger vendoring
    # Call is not checked because this is *expected* to fail - there isn't a
    # user facing way to directly trigger the bootstrap, so we give it a
    # no-op to perform that will require it to write out the cargo config.
    subprocess.call([paths.rustc_path('x.py'), '--help'],
                    cwd=paths.rustc_path())
    env = dict(os.environ)
    env['PATH'] = os.pathsep.join([paths.rust_prebuilt('bin'), env['PATH']])
    # Offline fetch to regenerate lockfile
    subprocess.check_call([cargo, 'fetch', '--offline'], cwd=paths.rustc_path(),
                          env=env)

    # Build
    env = dict(os.environ)
    cmake_bindir = paths.cmake_prebuilt('bin')
    ninja_bindir = paths.ninja_prebuilt()
    curl_libdir = paths.curl_prebuilt('lib')
    build_tools_bindir = paths.build_tools_prebuilt()
    env['PATH'] = os.pathsep.join([build_tools_bindir, cmake_bindir, ninja_bindir,
                                   env['PATH']])

    # Only adjust the library path on Linux - on OSX, use the devtools curl
    if build_platform.system() == 'linux':
        if 'LIBRARY_PATH' in env:
            old_library_path = ':{0}'.format(env['LIBRARY_PATH'])
        else:
            old_library_path = ''
        env['LIBRARY_PATH'] = '{0}{1}'.format(curl_libdir, old_library_path)

    env['DESTDIR'] = paths.out_path()
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
    libs = glob.glob(paths.out_path('lib', '*.so'))
    subprocess.check_call(['strip', '-S'] + libs + [
        paths.out_path('bin', 'rustc'),
        paths.out_path('bin', 'cargo'),
        paths.out_path('bin', 'rustdoc')])

    # Some stdlib crates might include Android.mk or Android.bp files.
    # If they do, filter them out.
    if build_platform.system() == 'linux':
        for root, _, files in os.walk(paths.stdlib_srcs()):
            for f in files:
                if f in ('Android.mk', 'Android.bp'):
                    os.remove(os.path.join(root, f))

    # Dist
    tarball_path = os.path.join(dist_dir, 'rust-{0}.tar.gz'.format(build_name))
    subprocess.check_call(['tar', 'czf', tarball_path, '.'],
                          cwd=paths.out_path())

if __name__ == '__main__':
    main()
