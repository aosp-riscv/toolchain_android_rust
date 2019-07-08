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
import glob
import os
import os.path
import subprocess

import config_toml
import paths


def parse_args():
    """Parses arguments and returns the parsed structure."""
    parser = argparse.ArgumentParser('Build the Rust Toolchain')
    parser.add_argument('--build-name', type=str, default='dev',
                        help='Release name for the dist result')
    return parser.parse_args()


def main():
    """Runs the configure-build-fixup-dist pipeline."""
    args = parse_args()
    build_name = args.build_name
    # We take DIST_DIR through an environment variable rather than an
    # argument to match the interface for traditional Android builds.
    dist_dir = os.environ['DIST_DIR']

    # Pre-create target directories
    os.makedirs(paths.out_path(), exist_ok=True)
    os.makedirs(dist_dir, exist_ok=True)

    # Configure
    config_toml.configure()

    # Build
    env = dict(os.environ)
    cmake_bindir = paths.cmake_prebuilt('bin')
    env['PATH'] = f'{cmake_bindir}:{env["PATH"]}'
    subprocess.run([paths.rustc_path('x.py'), '--stage', '3', 'install'],
                   cwd=paths.rustc_path(), env=env, check=True)

    # Fixup
    # The Rust build doesn't have an option to auto-strip binaries, so we do
    # it here.
    # We don't attempt to strip .rlibs since it prevents building Rust binaries.
    # We don't attempt to strip anything under rustlib/ since these include
    # both debug symbols which we may want to link into user code and Rust
    # metadata needed at build time.
    libs = glob.glob(paths.out_path('lib', '*.so'))
    subprocess.run(['strip', '-S'] + libs + [
        paths.out_path('bin', 'rustc'),
        paths.out_path('bin', 'cargo'),
        paths.out_path('bin', 'rustdoc')],
                   check=True)

    # Dist
    tarball_path = os.path.join(dist_dir, f'rust-{build_name}.tar.xz')
    subprocess.run(['tar', 'cJf', tarball_path, '.'], cwd=paths.out_path(),
                   check=True)

if __name__ == '__main__':
    main()
