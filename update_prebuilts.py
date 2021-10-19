#!/usr/bin/env python3
#
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

"""Fetch prebuilt archives and prepare a prebuilt commit"""

import argparse
import inspect
from os import replace
from pathlib import Path
import re
import shutil
import sys
from typing import Union, Tuple

import build_platform
from paths import *
from utils import *


ANDROID_BP: str = "Android.bp"

BRANCH_NAME_TEMPLATE: str = "rust-update-prebuilts-%s"

BUILD_SERVER_ARCHIVE_PATTERN: str = "rust-%s.tar.gz"
BUILD_SERVER_TARGET_DEFAULT: str = "linux"
BUILD_SERVER_TARGET_MAP = {
  "darwin-x86": "darwin_mac",
  "linux-x86":  "linux"}

HOST_ARCHIVE_PATTERN: str = "rust-%s-%s.tar.gz"
HOST_TARGET_DEFAULT:  str = "linux-x86"

MANIFEST_TAG: str = "manifest"

RLIB_NAME_PATTERN: re.Pattern = re.compile("libstd-([a-zA-z\d]+)\.rlib")

RUST_PREBUILT_REPO: GitRepo = GitRepo(RUST_PREBUILT_PATH)

#
# String operations
#

def artifact_ident_type(arg: str) -> Union[int, Path]:
    try:
        return int(arg)
    except (SyntaxError, ValueError):
        return Path(arg).resolve()


def make_branch_name(version: str, is_local: bool) -> str:
    branch_name = BRANCH_NAME_TEMPLATE % version
    if is_local:
        branch_name += "-local"
    return branch_name


def make_commit_message(version: str, prebuilt_ident: Union[int, Path], issue: int) -> str:
    commit_message: str = f"rustc-{version}"
    if isinstance(prebuilt_ident, int):
        commit_message += f" Build {prebuilt_ident}\n"
    else:
        commit_message += " Local Build\n"

    if issue:
        commit_message += f"\nBug: {issue}"

    commit_message += "\nTest: m rust"

    return commit_message

#
# Google3 wrappers
#

class ensure_gcert_valid:
    def __init__(self) -> None:
        self.gcert_checked = False

    def __call__(self):
        """Ensure gcert valid for > 1 hour."""
        if not self.gcert_checked:
            if quiet_command("gcertstatus -quiet -check_ssh=false -check_remaining=1h") < 0:
                handle_command("gcert", "Failed to obtain authentication credentials")
            self.gcert_checked = True



def fetch_build_server_artifact(target: str, build_id: int, build_server_name: str, host_name: str = None) -> Path:
    host_name = host_name or build_server_name
    DOWNLOADS_PATH.mkdir(exist_ok=True)
    dest: Path = DOWNLOADS_PATH / host_name

    if dest.exists():
        print(f"Artifact {build_server_name} has already been downloaded as {host_name}")

    else:
        ensure_gcert_valid()

        command: str = f"{FETCH_ARTIFACT_PATH} --target={target} --bid={build_id} {build_server_name} {dest}"

        print(f"Downloading build server artifact {build_server_name} for target {target}")
        handle_command(
            command,
            f"Failed to fetch build server artifact {build_server_name} for target {target}")

    return dest

#
# Program logic
#

def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=inspect.getdoc(sys.modules[__name__]))

    parser.add_argument(
        "prebuilt_ident", metavar="IDENT", type=artifact_ident_type,
        help="Build number to pull from the server or path to archive")
    parser.add_argument(
        "version", metavar="VERSION", type=version_string_type,
        help="Rust version string (e.g. 1.55.0)")

    parser.add_argument(
        "-b", "--branch", metavar="NAME", dest="branch",
        help="Branch name to use for this prebuilt update")
    parser.add_argument(
        "-i", "--issue", "--bug", metavar="NUMBER", dest="issue", type=int,
        help="Issue number to include in commit message")
    parser.add_argument(
        "-o", "--overwrite", dest="overwrite", action="store_true",
        help="Overwrite the target branch if it exists")

    return parser.parse_args()


def prepare_prebuilt_artifact(ident: Union[int, Path]) -> Tuple[dict[str, Path], Path]:
    if isinstance(ident, Path):
        if ident.exists():
            return ({build_platform.prebuilt(): ident}, None)
        else:
            print(f"Provided prebuilt archive does not exist: {ident.as_posix()}")
            exit(-1)
    else:
        artifact_path_map: dict[str, Path] = {}

        manifest_name:      str = f"manifest_{ident}.xml"
        bs_archive_name:    str = BUILD_SERVER_ARCHIVE_PATTERN % ident
        host_manifest_path: str = fetch_build_server_artifact(BUILD_SERVER_TARGET_DEFAULT, ident, manifest_name)

        for target, bs_target in BUILD_SERVER_TARGET_MAP.items():
            artifact_path_map[target] = fetch_build_server_artifact(
                bs_target, ident, bs_archive_name, HOST_ARCHIVE_PATTERN % (ident, target))

        print()
        return (artifact_path_map, host_manifest_path)


def unpack_prebuilt_artifacts(artifact_path_map: dict[str, Path], manifest_path: Path, version: str, overwrite: bool) -> None:
    for target, artifact_path in artifact_path_map.items():
        target_and_version_path: Path = RUST_PREBUILT_PATH / target / version
        if target_and_version_path.exists():
            if overwrite:
                # Empty out the existing directory so we can overwrite the contents
                RUST_PREBUILT_REPO.rm(target_and_version_path / '*')
            else:
                print(f"Directory {target_and_version_path} already exists and the 'overwrite' option was not set")
                exit(-1)
        else:
            target_and_version_path.mkdir()

        print(f"Extracting archive {artifact_path.name} for {target}/{version}")
        handle_quiet_command(f"tar -xzf {artifact_path}",
                             f"Failed to extract prebuilt artifact for {target}/{version}",
                             cwd=target_and_version_path)

        if manifest_path and target == HOST_TARGET_DEFAULT:
            shutil.copy(manifest_path, target_and_version_path)

        RUST_PREBUILT_REPO.add(target_and_version_path)


def get_rlib_suffix(platform: str, version: str, arch: str) -> Path:
    libdir_path: Path = RUST_PREBUILT_PATH / platform / version / "lib" / "rustlib" / arch / "lib"

    for lib_path in libdir_path.iterdir():
        match_data: re.Match = RLIB_NAME_PATTERN.match(lib_path.name)
        if match_data:
            return match_data.group(1)

    print(f"Unable to find standard library for {platform} / {version} / {arch}")
    exit(-1)


def get_library_suffixes(version: str) -> dict[str, dict[str, str]]:
    LIB_PATH_IDENTS: dict[str, list[str]] = {
        "linux-x86": [
            "x86_64-unknown-linux-gnu",
            "i686-unknown-linux-gnu"
        ],
        "darwin-x86": [
            "x86_64-apple-darwin"
        ]
    }

    return {
        platform: {arch: get_rlib_suffix(platform, version, arch) for arch in suffix_list}
            for platform, suffix_list in LIB_PATH_IDENTS.items()
    }


def update_root_build_file(version: str) -> None:
    ROOT_BUILD_FILE_PATH: Path = RUST_PREBUILT_PATH / ANDROID_BP
    with open(ROOT_BUILD_FILE_PATH, "r+") as f:
        replace_file_contents(f, re.sub(VERSION_PATTERN, version, f.read()))

    # Add the file to Git after we are sure it has been written to and closed.
    RUST_PREBUILT_REPO.add(ROOT_BUILD_FILE_PATH)


def update_platform_build_files(version: str) -> None:
    for platform, arch_suffixes in get_library_suffixes(version).items():

        platform_build_file_path = RUST_PREBUILT_PATH / platform / ANDROID_BP
        with open(platform_build_file_path, "r+") as f:
            file_contents = f.read()

            # Update rust version
            file_contents = re.sub(VERSION_PATTERN, version, file_contents)

            # Update library suffixes
            for arch, new_suffix in arch_suffixes.items():
                extract_suffix_pattern: re.Pattern = re.compile(f"{arch}\/lib\/{RLIB_NAME_PATTERN.pattern}")
                match_data: re.Match = extract_suffix_pattern.search(file_contents)

                if match_data:
                    file_contents = re.sub(match_data.group(1), new_suffix, file_contents)
                else:
                    print(f"Failed to extract old suffix value for {platform}/{arch}")
                    exit(-1)

            replace_file_contents(f, file_contents)

        # Add the file to Git after we are sure it has been written to and
        # closed.
        RUST_PREBUILT_REPO.add(platform_build_file_path)


def update_build_files(version: str) -> None:
    update_root_build_file(version)
    update_platform_build_files(version)


def main():
    args = parse_args()
    branch_name: str = args.branch or make_branch_name(args.version, isinstance(args.prebuilt_ident, Path))

    print()
    artifact_path_map, manifest_path = prepare_prebuilt_artifact(args.prebuilt_ident)
    RUST_PREBUILT_REPO.create_or_checkout(branch_name, args.overwrite)
    unpack_prebuilt_artifacts(artifact_path_map, manifest_path, args.version, args.overwrite)
    update_build_files(args.version)
    commit_message = make_commit_message(args.version, args.prebuilt_ident, args.issue)
    RUST_PREBUILT_REPO.amend_or_commit(commit_message)
    print("Done")

    exit(0)


if __name__ == "__main__":
    main()