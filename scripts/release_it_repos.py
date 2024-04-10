#!/usr/bin/env python

from rich.progress import Progress
import os
import re
import subprocess
import shlex
import click
import requests
import rich
from rich.prompt import Confirm
from contextlib import contextmanager
from rich import box
from rich.table import Table
from pyaml_env import parse_config


def base_table() -> Table:
    table = Table(
        title="Cluster Configuration Report",
        show_lines=True,
        box=box.ROUNDED,
        expand=False,
    )
    table.add_column("Repository", style="cyan", no_wrap=True)
    table.add_column("Branch", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Version", style="green")
    table.add_column("Changelog", style="green")
    table.add_column("Released", style="green")

    return table


@contextmanager
def change_git_branch(repo: str, branch: str, progress: Progress, verbose: bool):
    user_branch = (
        subprocess.run(
            shlex.split("git branch --show-current"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        .stdout.decode("utf-8")
        .strip()
    )

    if verbose:
        progress.console.print(f"{repo}: User branch: {user_branch}")
        progress.console.print(f"{repo}: Checkout branch: {branch}")

    if user_branch != branch:
        subprocess.run(
            shlex.split(f"git checkout {branch}"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    if verbose:
        progress.console.print(f"{repo}: Check if {branch} is clean")

    git_status = subprocess.run(
        shlex.split("git status --porcelain"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if dirty_git := git_status.stdout.decode("utf-8"):
        if verbose:
            progress.console.print(f"{repo}: {branch} is dirty, stashing")

        subprocess.run(shlex.split("git stash"), stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    if verbose:
        progress.console.print(f"{repo}: Pulling {branch} from origin")

    subprocess.run(
        shlex.split(f"git pull origin {branch}"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    yield
    if verbose:
        progress.console.print(f"{repo}: Checkout back to last user branch: {user_branch}")

    current_branch = (
        subprocess.run(
            shlex.split("git branch --show-current"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        .stdout.decode("utf-8")
        .strip()
    )

    if current_branch != user_branch:
        subprocess.run(
            shlex.split(f"git checkout {user_branch}"),
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

    if dirty_git:
        if verbose:
            progress.console.print(f"{repo}: popping stash back for {branch}")

        subprocess.run(shlex.split("git stash pop"), stderr=subprocess.PIPE, stdout=subprocess.PIPE)


@contextmanager
def change_directory(path: str, progress: Progress, verbose: bool):
    current_path = os.getcwd()
    if verbose:
        progress.console.print(f"Current path: {current_path}")
        progress.console.print(f"Changing directory to {path}")

    os.chdir(path)
    yield

    if verbose:
        progress.console.print(f"Changing directory back to {current_path}")

    os.chdir(current_path)


def get_repositories(progress: Progress, verbose: bool) -> dict:
    repositories = {}
    repos = requests.get("https://raw.githubusercontent.com/CSPI-QE/MSI/main/REPOS_INVENTORY.md").content
    for line in repos.decode("utf-8").splitlines():
        if re.findall(r"\[.*]\(.*\)", line):
            repo_data = [section.strip() for section in line.split("|") if section]
            if len(repo_data) < 4:
                continue

            if ":heavy_check_mark:" in repo_data[2]:
                repo_name = re.findall(r"\[.*]", repo_data[0])[0].strip("[").rstrip("]")
                branches = [br.strip("`") for br in repo_data[3].split()]
                if verbose:
                    progress.console.print(f"Found {repo_name} with branches {branches}")
                repositories[repo_name] = branches

    return repositories


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
    show_default=True,
    help="Git base directory",
)
@click.option("-d", "--dry-run", is_flag=True, help="Dry run")
@click.option("-v", "--verbose", is_flag=True, help="Verbose")
def main(yes: bool, git_base_dir: str, dry_run: bool, verbose: bool):
    table = base_table()

    with Progress() as progress:
        repositories = get_repositories(progress=progress, verbose=verbose)
        task_progress = 1
        task = progress.add_task("[green]Checking for releases ", total=len(repositories))
        config_data = {}
        config_file = os.path.join(os.path.expanduser("~"), ".config", "release-it-check", "config.yaml")
        if os.path.isfile(config_file):
            if verbose:
                progress.console.print(f"Found config file: {config_file}")

            config_data = parse_config(config_file)
            if not config_data:
                progress.console.print(f"Failed to parse config file: {config_file}")
                exit(1)

            if verbose:
                progress.console.print(f"Config data: {config_data}")

        elif verbose:
            progress.console.print(f"Config file {config_file} does not exist")

        git_base_dir = config_data.get("git_base_dir", git_base_dir)
        repositories_mapping = config_data.get("repositories-mapping", {})
        include_repositories = config_data.get("include-repositories", [])

        if not os.path.isdir(git_base_dir):
            progress.console.print(f"Git base directory {git_base_dir} does not exist")
            exit(1)

        for repo_name, branches in repositories.items():
            repo_task = progress.add_task(f"[yellow]Repository {repo_name} ", total=task_progress)
            if verbose:
                progress.console.print(f"Working on {repo_name} with branches {branches}")

            if include_repositories and repo_name not in include_repositories:
                if verbose:
                    progress.console.print(f"{repo_name} is not in include_repositories, skipping")

                progress.update(repo_task, advance=task_progress, refresh=True)
                progress.update(task, advance=task_progress, refresh=True)
                continue

            repo_name = repositories_mapping.get(repo_name, repo_name)
            repo_path = os.path.join(git_base_dir, repo_name)

            with change_directory(path=repo_path, progress=progress, verbose=verbose):
                for branch in branches:
                    with change_git_branch(
                        repo=repo_name,
                        branch=branch,
                        progress=progress,
                        verbose=verbose,
                    ):
                        if verbose:
                            progress.console.print(
                                f"Running release-it --changelog to check if need to make release for {repo_name} branch {branch}"
                            )

                        res = subprocess.run(
                            shlex.split("release-it --changelog"),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        changelog = res.stdout.decode("utf-8")
                        if "undefined" in changelog or not changelog:
                            if verbose:
                                progress.console.print(f"{repo_name} branch {branch} has no changes, skipping")

                            progress.update(repo_task, advance=task_progress, refresh=True)
                            progress.update(task, advance=task_progress, refresh=True)
                            continue
                        if verbose:
                            progress.console.print(
                                f"Running release-it --release-version to get next release version {repo_name} branch {branch}"
                            )

                        next_release = subprocess.run(
                            shlex.split("release-it --release-version"),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        next_release = next_release.stdout.decode("utf-8").strip()

                        if verbose:
                            progress.console.print(f"\n[{repo_name}]\n{changelog}\n")

                        if dry_run:
                            table.add_row(
                                repo_name,
                                branch,
                                "Yes",
                                next_release,
                                changelog,
                                "Dry Run",
                            )
                            progress.update(repo_task, advance=task_progress, refresh=True)
                            progress.update(task, advance=task_progress, refresh=True)
                            continue

                        if yes:
                            user_input = True
                        else:
                            user_input = Confirm.ask(
                                f"Do you want to make a new release [{next_release}] for {repo_name} on branch {branch}?"
                            )
                        if user_input:
                            table.add_row(
                                repo_name,
                                branch,
                                "Yes",
                                next_release,
                                changelog,
                                "Yes",
                            )
                            try:
                                if verbose:
                                    progress.console.print(
                                        f"Running release-it patch --ci to make release for {repo_name} branch {branch}"
                                    )

                                subprocess.run(
                                    shlex.split("release-it patch --ci"),
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                )
                                progress.update(repo_task, advance=task_progress, refresh=True)
                                progress.update(task, advance=task_progress, refresh=True)

                            except Exception as exp:
                                progress.console.print(
                                    f"Failed to make release for {repo_name} branch {branch} with error: {exp}"
                                )
                                progress.update(repo_task, advance=task_progress, refresh=True)
                                progress.update(task, advance=task_progress, refresh=True)

                        else:
                            table.add_row(
                                repo_name,
                                branch,
                                "Yes",
                                next_release,
                                changelog,
                                "No",
                            )
                            progress.update(
                                repo_task,
                                advance=task_progress,
                                refresh=True,
                            )
                            progress.update(task, advance=task_progress, refresh=True)
                            continue

        progress.update(task, advance=task_progress, refresh=True)

    if table.rows:
        rich.print(table)
    else:
        rich.print("/n[yellow][bold]No new content found for any repositories[not bold][not yellow]")


if __name__ == "__main__":
    main()
