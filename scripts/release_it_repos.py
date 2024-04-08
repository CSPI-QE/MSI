#!/usr/bin/env python

import logging
import os
import re
import subprocess
import shlex
import click
import requests
import yaml
import rich
from rich.prompt import Confirm
from contextlib import contextmanager
from simple_logger.logger import get_logger


LOGGER = get_logger("release-it-repos")


@contextmanager
def change_git_branch(repo, branch):
    user_branch = (
        subprocess.run(
            shlex.split("git branch --show-current"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        .stdout.decode("utf-8")
        .strip()
    )

    LOGGER.debug(f"{repo}: User branch: {user_branch}")
    LOGGER.debug(f"{repo}: Checkout branch: {branch}")

    subprocess.run(
        shlex.split(f"git checkout {branch}"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    LOGGER.debug(f"{repo}: Check if {branch} is clean")
    git_status = subprocess.run(
        shlex.split("git status --porcelain"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if dirty_git := git_status.stdout.decode("utf-8"):
        LOGGER.debug(f"{repo}: {branch} is dirty, stashing")
        subprocess.run(shlex.split("git stash"))

    LOGGER.debug(f"{repo}: Pulling {branch} from origin")
    subprocess.run(
        shlex.split(f"git pull origin {branch}"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    yield
    LOGGER.debug(f"{repo}: Checkout back to last user branch: {user_branch}")
    subprocess.run(shlex.split(f"git checkout {user_branch}"))
    if dirty_git:
        LOGGER.debug(f"{repo}: popping stash back for {branch}")
        subprocess.run(shlex.split("git stash pop"))


@contextmanager
def change_directory(path):
    current_path = os.getcwd()
    LOGGER.debug(f"Current path: {current_path}")
    LOGGER.debug(f"Changing directory to {path}")
    os.chdir(path)
    yield
    LOGGER.debug(f"Changing directory back to {current_path}")
    os.chdir(current_path)


def get_repositories():
    repos = requests.get("https://raw.githubusercontent.com/CSPI-QE/MSI/main/REPOS_INVENTORY.md").content
    for line in repos.decode("utf-8").splitlines():
        if re.findall(r"\[.*]\(.*\)", line):
            repo_data = [section.strip() for section in line.split("|") if section]
            if len(repo_data) < 4:
                continue

            if ":heavy_check_mark:" in repo_data[2]:
                repo_name = re.findall(r"\[.*]", repo_data[0])[0].strip("[").rstrip("]")
                branches = [br.strip("`") for br in repo_data[3].split()]
                LOGGER.debug(f"Found {repo_name} with branches {branches}")
                yield (repo_name, branches)


@click.command("installer")
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    show_default=True,
    help="Make release for all repositories without asking",
)
@click.option(
    "-g",
    "--git-base-dir",
    default=os.getenv("GIT_BASE_DIR"),
    type=click.Path(exists=True),
    show_default=True,
    help="Git base directory",
)
@click.option("-d", "--dry-run", is_flag=True, help="Dry run")
@click.option("-v", "--verbose", is_flag=True, help="Verbose")
def main(yes, git_base_dir, dry_run, verbose):
    if verbose:
        LOGGER.level = logging.DEBUG
    else:
        logging.disable(logging.CRITICAL)

    repositories_mapping = {}
    config_file = os.path.join(os.path.expanduser("~"), ".config", "release-it-check", "config.yaml")
    if os.path.isfile(config_file):
        LOGGER.debug(f"Found config file for repositories mapping: {config_file}")
        with open(config_file) as fd:
            repositories_mapping = yaml.safe_load(fd.read())

    for repo_data in get_repositories():
        LOGGER.debug(f"Working on {repo_data}")
        repo_name, branches = repo_data[0], repo_data[1]
        repo_name = repositories_mapping.get(repo_name, repo_name)
        repo_path = os.path.join(git_base_dir, repo_name)
        with change_directory(repo_path):
            for branch in branches:
                rich.print(f"\nWorking on {repo_name} branch {branch} ...")
                with change_git_branch(repo=repo_name, branch=branch):
                    LOGGER.debug(
                        f"Running release-it --changelog to check if need to make release for {repo_name} branch {branch}"
                    )
                    res = subprocess.run(
                        shlex.split("release-it --changelog"),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    out = res.stdout.decode("utf-8")
                    if "undefined" in out or not out:
                        LOGGER.debug(f"{repo_name} branch {branch} has no changes, skipping")
                        continue

                    LOGGER.debug(
                        f"Running release-it --release-version to get next release version {repo_name} branch {branch}"
                    )
                    next_release = subprocess.run(
                        shlex.split("release-it --release-version"),
                        stdout=subprocess.PIPE,
                    )
                    rich.print(f"\n[{repo_name}]\n{out}\n")
                    if dry_run:
                        continue

                    if yes:
                        user_input = True
                    else:
                        user_input = Confirm.ask(
                            f"Do you want to make a new release [{next_release.stdout.decode('utf-8').strip()}] for {repo_name} on branch {branch}?"
                        )
                    if user_input:
                        try:
                            LOGGER.debug(
                                f"Running release-it patch --ci to make release for {repo_name} branch {branch}"
                            )
                            os.system("release-it patch --ci")
                            rich.print("\n")
                        except Exception as exp:
                            LOGGER.error(f"Failed to make release for {repo_name} branch {branch} with error: {exp}")

                    else:
                        continue


if __name__ == "__main__":
    main()
