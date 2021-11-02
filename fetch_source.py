#!/usr/bin/env python3
# Copyright (C) 2021 The Android Open Source Project
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


import argparse
import re
import subprocess

from paths import RUST_SOURCE_PATH

BRANCH_NAME: str = "rust-update-source-%s"

COMMAND_GIT_ADD:      str = "git add ."
COMMAND_GIT_AMEND:    str = "git commit --amend --no-edit"
COMMAND_GIT_CHECKOUT: str = "git checkout %s"
COMMAND_GIT_COMMIT:   str = "git commit --no-verify -m 'Importing rustc-%s'"
COMMAND_GIT_DIFF:     str = "git diff --cached --quiet"
COMMAND_GIT_RM:       str = "git rm -fr *"
COMMAND_GIT_TEST:     str = "git rev-parse --verify %s"
COMMAND_FETCH:        str = "curl --proto '=https' --tlsv1.2 -f %s | tar xz --strip-components=1"
COMMAND_REPO:         str = "repo start %s"

GIT_REFERENCE_BRANCH: str = 'aosp/master'

RUSTC_SOURCE_URL_VERSION_TEMPLATE: str = "https://static.rust-lang.org/dist/rustc-%s-src.tar.gz"
RUSTC_SOURCE_URL_BETA            : str = "https://static.rust-lang.org/dist/rustc-beta-src.tar.gz"
RUSTC_SOURCE_URL_NIGHTLY         : str = "https://static.rust-lang.org/dist/rustc-nightly-src.tar.gz"

VERSION_PATTERN : re.Pattern = re.compile("\d+\.\d+\.\d+")

branch_existed: bool = False

#
# Command execution
#

def exec_rustc_src_command(command: str, check=False, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) -> subprocess.CompletedProcess:
    return subprocess.run(command, shell=True, cwd=RUST_SOURCE_PATH, check=check,
                          stdout=stdout, stderr=stderr)


def handle_rustc_src_command(command: str, error_string: str, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL) -> None:
    result = exec_rustc_src_command(command, stdout=stdout, stderr=stderr)
    if result.returncode != 0:
        print("{}:\n{}".format(error_string, result.stderr))
        exit(-2)

#
# String operations
#

def construct_archive_url(build_type: str, rust_version: str) -> str:
    if build_type == 'nightly':
        return RUSTC_SOURCE_URL_NIGHTLY
    elif build_type == 'beta':
        return RUSTC_SOURCE_URL_BETA
    else:
        return RUSTC_SOURCE_URL_VERSION_TEMPLATE % rust_version


def get_extra_tag(build_type: str) -> str:
    if build_type:
        return '-' + build_type
    else:
        return ''


def version_string_type(arg_string: str) -> str:
    if VERSION_PATTERN.match(arg_string):
        return arg_string
    else:
        raise argparse.ArgumentTypeError("Version string is not properly formatted")

#
# Git helpers
#

def git_branch_exists(branch_name: str) -> bool:
    return exec_rustc_src_command(COMMAND_GIT_TEST % branch_name).returncode == 0


def git_get_branch_target(branch_name: str) -> str:
    return exec_rustc_src_command(COMMAND_GIT_TEST % branch_name, check=True, stdout=subprocess.PIPE).stdout.rstrip()

#
# Program logic
#

def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Fetch and unpack a Rust source archive')

    exclusive_group = parser.add_mutually_exclusive_group()
    exclusive_group.add_argument("-b", "--beta", dest="build_type", action="store_const",
        default='', const='beta', help="fetch the beta archive")
    exclusive_group.add_argument("-n", "--nightly", dest="build_type", action="store_const",
        default='', const='nightly', help="fetch the nightly archive")
    parser.add_argument("-o", "--overwrite", dest="overwrite", action="store_true",
        help="Overwrite an existing branch if it exists")

    parser.add_argument("rust_version", action="store", type=version_string_type)

    return parser.parse_args()


def setup_git_branch(branch_name: str, overwrite: bool) -> None:
    print('')
    if git_branch_exists(branch_name):
        global branch_existed
        branch_existed = True

        if overwrite:
            print("Checking out branch %s" % branch_name)
            handle_rustc_src_command(COMMAND_GIT_CHECKOUT % branch_name,
                                     "Error checking out branch to overwrite")
        else:
            print("Branch %s already exists and the 'overwrite' option was not set" % branch_name)
            exit(-1)

    else:
        print("Creating branch %s" % branch_name)
        command_repo = COMMAND_REPO % branch_name
        handle_rustc_src_command(command_repo, "Error creating repo for source update")


def clean_repository() -> None:
    print("Deleting old files")
    handle_rustc_src_command(COMMAND_GIT_RM, "Error deleting old files from git")


def fetch_archive(build_type: str, rust_version: str) -> None:
    archive_url = construct_archive_url(build_type, rust_version)
    print("Fetching archive %s\n" % archive_url)
    handle_rustc_src_command(
        COMMAND_FETCH % archive_url,
        "Error fetching source for Rust version %s" % rust_version,
        stdout=None,
        stderr=None)


def commit_files(branch_name: str, rustc_version: str) -> None:
    global branch_existed

    print()
    handle_rustc_src_command(COMMAND_GIT_ADD, "Error adding new files to git")

    if exec_rustc_src_command(COMMAND_GIT_DIFF).returncode == 0:
        print("No update to source")
        exit(0)
    elif branch_existed and (git_get_branch_target(branch_name) != git_get_branch_target(GIT_REFERENCE_BRANCH)):
        print("Amending previous commit")
        handle_rustc_src_command(COMMAND_GIT_AMEND,
                                "Error amending previous commit")
    else:
        print("Commiting new files")
        handle_rustc_src_command(COMMAND_GIT_COMMIT % rustc_version,
                                "Error committing new files to git")


def main() -> None:
    args         = parse_args()
    rust_version = args.rust_version + get_extra_tag(args.build_type)
    branch_name  = BRANCH_NAME % rust_version

    setup_git_branch(branch_name, args.overwrite)
    clean_repository()
    fetch_archive(args.build_type, rust_version)
    commit_files(branch_name, rust_version)

    exit(0)


if __name__ == '__main__':
    main()
