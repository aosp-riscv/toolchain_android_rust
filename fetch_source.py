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


import argparse

from paths import RUST_SOURCE_PATH
from utils import *

BRANCH_NAME_TEMPLATE: str = "rust-update-source-%s"

COMMAND_FETCH: str = "curl --proto '=https' --tlsv1.2 -f %s | tar xz --strip-components=1"

COMMIT_MESSAGE: str = "Importing rustc-%s"

GIT_REFERENCE_BRANCH: str = 'aosp/master'

RUST_REPO: GitRepo = GitRepo(RUST_SOURCE_PATH)

RUST_SOURCE_URL_VERSION_TEMPLATE: str = "https://static.rust-lang.org/dist/rustc-%s-src.tar.gz"
RUST_SOURCE_URL_BETA            : str = "https://static.rust-lang.org/dist/rustc-beta-src.tar.gz"
RUST_SOURCE_URL_NIGHTLY         : str = "https://static.rust-lang.org/dist/rustc-nightly-src.tar.gz"

branch_existed: bool = False

#
# String operations
#

def construct_archive_url(build_type: str, rust_version: str) -> str:
  if build_type == 'nightly':
    return RUST_SOURCE_URL_NIGHTLY
  elif build_type == 'beta':
    return RUST_SOURCE_URL_BETA
  else:
    return RUST_SOURCE_URL_VERSION_TEMPLATE % rust_version


def get_extra_tag(build_type: str) -> str:
  if build_type:
    return '-' + build_type
  else:
    return ''

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
  if RUST_REPO.branch_exists(branch_name):
    global branch_existed
    branch_existed = True

    if overwrite:
      print("Checking out branch %s" % branch_name)
      RUST_REPO.checkout(branch_name)

    else:
      print("Branch %s already exists and the 'overwrite' option was not set" % branch_name)
      exit(-1)

  else:
    print("Creating branch %s" % branch_name)
    repo_start(RUST_SOURCE_PATH, branch_name)


def clean_repository() -> None:
  print("Deleting old files")
  RUST_REPO.rm('*')


def fetch_archive(build_type: str, rust_version: str) -> None:
  archive_url = construct_archive_url(build_type, rust_version)
  print("Fetching archive %s\n" % archive_url)
  handle_command(
    COMMAND_FETCH % archive_url,
    "Error fetching source for Rust version %s" % rust_version,
    cwd=RUST_SOURCE_PATH)


def commit_files(branch_name: str, rustc_version: str) -> None:
  global branch_existed

  print()
  RUST_REPO.add('.')

  if RUST_REPO.diff() == 0:
    print("No update to source")
    exit(0)

  elif branch_existed and (RUST_REPO.branch_target(branch_name) != RUST_REPO.branch_target(GIT_REFERENCE_BRANCH)):
    print("Amending previous commit")
    RUST_REPO.amend()
  else:
    print("Committing new files")
    RUST_REPO.commit(COMMIT_MESSAGE % rustc_version)


def main() -> None:
  args         = parse_args()
  rust_version = args.rust_version + get_extra_tag(args.build_type)
  branch_name  = BRANCH_NAME_TEMPLATE % rust_version

  setup_git_branch(branch_name, args.overwrite)
  clean_repository()
  fetch_archive(args.build_type, rust_version)
  commit_files(branch_name, rust_version)

  exit(0)


if __name__ == '__main__':
  main()