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

"""Code common to different scripts in the Rust toolchain"""


import argparse
from pathlib import Path
import re
import subprocess
from typing import TextIO


GIT_REFERENCE_BRANCH: str = 'aosp/master'

SUBPROCESS_RUN_DEFAULTS: dict[str, str] = {'shell': True}

SUBPROCESS_RUN_QUIET_DEFAULTS: dict[str, str] = {
    'stdout': subprocess.DEVNULL,
    'stderr': subprocess.DEVNULL,
    'shell': True
}

VERSION_PATTERN : re.Pattern = re.compile("\d+\.\d+\.\d+")

#
# Type Functions
#

def version_string_type(arg_string: str) -> str:
    if VERSION_PATTERN.match(arg_string):
        return arg_string
    else:
        raise argparse.ArgumentTypeError("Version string is not properly formatted")

#
# Subprocess helpers
#

def handle_command(command: str, error_message: str, *args, **kwargs) -> subprocess.CompletedProcess:
    result = subprocess.run(command, *args, **(kwargs | SUBPROCESS_RUN_DEFAULTS))
    if result.returncode != 0:
        print(error_message)
        exit(-1)

    return result


def handle_quiet_command(command: str, error_message: str, *args, **kwargs) -> int:
    return handle_command(command, error_message, *args, **(kwargs | SUBPROCESS_RUN_QUIET_DEFAULTS)).returncode


def quiet_command(command: str, *args, **kwargs) -> int:
    return subprocess.run(command, *args, **(kwargs | SUBPROCESS_RUN_QUIET_DEFAULTS)).returncode

#
# Git
#

# TODO: Shell-escape the command inputs
class GitRepo:
    COMMAND_GIT_BRANCH_TEST: str = "git rev-parse --verify %s"

    def __init__(self, repo_path: Path) -> None:
        self.path = repo_path

    def add(self, pattern: str='.') -> None:
        handle_quiet_command(
            f"git add {pattern}",
            "Failed to add files matching pattern '%s' to Git repo %s" %
                (pattern, self.path),
            cwd=self.path)

    def amend(self) -> None:
        handle_quiet_command(
            "git commit --amend --no-edit",
            "Failed to amend previous commit for Git repo %s" % self.path,
            cwd=self.path)

    def amend_or_commit(self, commit_message: str) -> None:
        if not self.diff():
            print("No files updated")
        elif (self.branch_target() !=
              self.branch_target(GIT_REFERENCE_BRANCH)):

            print("Amending previous commit")
            self.amend()
        else:
            print("Committing new files")
            self.commit(commit_message)

    def branch_exists(self, branch_name: str) -> bool:
        return quiet_command(self.COMMAND_GIT_BRANCH_TEST % branch_name, cwd=self.path) == 0

    def branch_target(self, branch_name: str = "HEAD") -> str:
        return handle_command(
            self.COMMAND_GIT_BRANCH_TEST % branch_name,
            "Failed to get target hash for branch '%s' of Git repo %s" %
                (branch_name, self.path),
            cwd=self.path,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL).stdout.rstrip()

    def checkout(self, branch_name: str) -> None:
        handle_quiet_command(
            f"git checkout {branch_name}",
            "Failed to checkout branch '%s' for Git repo %s" %
                (branch_name, self.path),
            cwd=self.path)

    def commit(self, message: str) -> None:
        handle_quiet_command(
            f"git commit --no-verify -m '{message}'",
            "Failed to create commit for Git repo %s" % self.path,
            cwd=self.path)

    def create_or_checkout(self, branch_name: str, overwrite: bool) -> bool:
        """Create or checkout a branch, returning true if a new branch was created"""
        if self.branch_exists(branch_name):
            if overwrite:
                print("Checking out branch %s" % branch_name)
                self.checkout(branch_name)
                return False
            else:
                print("Branch %s already exists and the 'overwrite' option was not set" % branch_name)
                exit(-1)
        else:
            print("Creating branch %s" % branch_name)
            repo_start(self.path, branch_name)
            return True

    def diff(self) -> bool:
        retcode = quiet_command("git diff --cached --quiet", cwd=self.path)

        if retcode == 0:
            return False
        elif retcode == 1:
            return True
        else:
            "Failed to compute diff for Git repo %s" % self.path
            exit(-1)


    def rm(self, pattern: str) -> None:
        handle_quiet_command(
            f"git rm -fr {pattern}",
            "Failed to remove files matching pattern '%s' from Git repo %s" %
                (pattern, self.path),
            cwd=self.path)

#
# Repo helper
#

def repo_start(path: Path, branch_name: str) -> None:
    handle_quiet_command(
        f"repo start {branch_name}",
        "Failed to 'repo init' branch '%s' for Git repo %s" % (path, branch_name),
        cwd=path)

#
# File helpers
#

def replace_file_contents(f: TextIO, new_contents: str) -> None:
    f.seek(0)
    f.write(new_contents)
    f.truncate()
    f.flush()
