#!/usr/bin/env python

import logging
from typing import Any, Dict, List, Tuple
from rich.progress import Progress, TaskID
import os
import shlex
import click
import requests
import rich
from rich.prompt import Confirm
from contextlib import contextmanager
from rich import box
from rich.table import Table
from pyaml_env import parse_config
from pyhelper_utils.shell import run_command
from pyhelper_utils.runners import function_runner_with_pdb
from pyhelper_utils.notifications import send_slack_message
import yaml


def base_table() -> Table:
    table = Table(
        title="Releases status report",
        show_lines=True,
        box=box.ROUNDED,
        expand=False,
    )
    table.add_column("Repository", style="cyan", no_wrap=True)
    table.add_column("Branch", style="magenta")
    table.add_column("Version", style="green")
    table.add_column("Changelog", style="green")
    table.add_column("Released", style="green")

    return table


@contextmanager
def change_git_branch(repo: str, branch: str, progress: Progress, verbose: bool) -> Any:
    _, user_branch, _ = run_command(command=shlex.split("git branch --show-current"), verify_stderr=False)

    if verbose:
        progress.console.print(f"{repo}: User branch: {user_branch}")
        progress.console.print(f"{repo}: Checkout branch: {branch}")

    if user_branch != branch:
        run_command(command=shlex.split(f"git checkout {branch}"), verify_stderr=False)

    if verbose:
        progress.console.print(f"{repo}: Check if {branch} is clean")

    _, dirty_git, _ = run_command(command=shlex.split("git status --porcelain"), verify_stderr=False)

    if dirty_git:
        if verbose:
            progress.console.print(f"{repo}: {branch} is dirty, stashing")

        run_command(shlex.split("git stash"), verify_stderr=False)

    if verbose:
        progress.console.print(f"{repo}: Pulling {branch} from origin")

    run_command(shlex.split(f"git pull origin {branch}"), verify_stderr=False)
    yield
    if verbose:
        progress.console.print(f"{repo}: Checkout back to last user branch: {user_branch}")

    current_branch = run_command(
        shlex.split("git branch --show-current"),
        verify_stderr=False,
    )

    if current_branch != user_branch:
        run_command(
            shlex.split(f"git checkout {user_branch}"),
            verify_stderr=False,
        )

    if dirty_git:
        if verbose:
            progress.console.print(f"{repo}: popping stash back for {branch}")

        run_command(shlex.split("git stash pop"), verify_stderr=False, check=False)


@contextmanager
def change_directory(path: str, progress: Progress, verbose: bool) -> Any:
    current_path = os.getcwd()
    if verbose:
        progress.console.print(f"Current path: {current_path}")
        progress.console.print(f"Changing directory to {path}")

    os.chdir(path)
    yield

    if verbose:
        progress.console.print(f"Changing directory back to {current_path}")

    os.chdir(current_path)


def get_repositories(progress: Progress, verbose: bool, repositories: Dict[str, List[str]] | str) -> dict:
    final_repositories = {}

    if isinstance(repositories, str):
        repos = yaml.safe_load(requests.get(repositories).content.decode("utf-8"))
        for repo_name, data in repos.items():
            if not data["release"]:
                continue

            branches = data["branches"]

            if verbose:
                progress.console.print(f"Found {repo_name} with branches {branches}")

            final_repositories[repo_name] = branches

    else:
        for repo_url, branches in repositories.items():
            repo = repo_url.split("/")[-1]
            if verbose:
                progress.console.print(f"Found {repo} with branches {branches}")
            final_repositories[repo] = branches

    return final_repositories


def process_config(config_file: str, progress: Progress, verbose: bool) -> Dict:
    config_data: Dict = {}
    if config_file:
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
            exit(1)
    return config_data


def skip_repository(
    config_data: Dict,
    repo_name: str,
    progress: Progress,
    verbose: bool,
    task: TaskID,
    task_progress: int,
    repo_task: TaskID,
) -> bool:
    include_repositories = config_data.get("include_repositories")
    if include_repositories and repo_name not in include_repositories:
        if verbose:
            progress.console.print(f"{repo_name} is not in include_repositories, skipping")

        progress.update(repo_task, advance=task_progress, refresh=True)
        progress.update(task, advance=task_progress, refresh=True)
        return True

    return False


def get_repository_data_for_release(
    repo_name: str,
    progress: Progress,
    task: TaskID,
    task_progress: int,
    verbose: bool,
    config_data: Dict,
    branches: List[str],
    repositories_mapping: Dict,
    git_base_dir: str,
) -> Tuple:
    repo_task = progress.add_task(f"  [yellow]{repo_name} ", total=len(branches))
    repo_path = None
    _repo_name = None

    if verbose:
        progress.console.print(f"Working on {repo_name} with branches {branches}")

    if not skip_repository(
        config_data=config_data,
        repo_name=repo_name,
        progress=progress,
        verbose=verbose,
        task=task,
        task_progress=task_progress,
        repo_task=repo_task,
    ):
        _repo_name = repositories_mapping.get(repo_name, repo_name)
        repo_path = os.path.join(git_base_dir, repo_name)

    return repo_task, _repo_name, repo_path


def make_release_for_branch(
    yes: bool,
    table: Table,
    dry_run: bool,
    repo_name: str,
    branch: str,
    progress: Progress,
    verbose: bool,
    task_progress: int,
    repo_task: TaskID,
    slack_msg_dict: Dict,
) -> Tuple:
    slack_msg_dict[repo_name][branch] = {}
    branch_task = progress.add_task(f"    [blue]{branch} ", total=task_progress)
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

        _, changelog, _ = run_command(
            shlex.split("release-it --changelog"),
            verify_stderr=False,
        )

        if "undefined" in changelog or not changelog:
            if verbose:
                progress.console.print(f"{repo_name} branch {branch} has no changes, skipping")

            progress.update(branch_task, advance=task_progress, refresh=True)
            progress.update(repo_task, advance=task_progress, refresh=True)
            return slack_msg_dict, table

        if verbose:
            progress.console.print(
                f"Running release-it --release-version to get next release version {repo_name} branch {branch}"
            )

        _, next_release, _ = run_command(
            shlex.split("release-it --release-version"),
            verify_stderr=False,
        )

        if verbose:
            progress.console.print(f"\n[{repo_name}]\n{changelog}\n")

        if dry_run:
            slack_msg_dict[repo_name][branch][next_release] = changelog
            table.add_row(
                repo_name,
                branch,
                next_release,
                changelog,
                "Dry Run",
            )
            progress.update(branch_task, advance=task_progress, refresh=True)
            progress.update(repo_task, advance=task_progress, refresh=True)
            return slack_msg_dict, table

        if yes:
            make_release = True
        else:
            make_release = Confirm.ask(
                f"Do you want to make a new release [{next_release}] for {repo_name} on branch {branch}?"
            )
        if make_release:
            try:
                if verbose:
                    progress.console.print(
                        f"Running release-it patch --ci to make release for {repo_name} branch {branch}"
                    )

                run_command(
                    shlex.split("release-it patch --ci"),
                    verify_stderr=False,
                )
                slack_msg_dict[repo_name][branch][next_release] = changelog
                table.add_row(
                    repo_name,
                    branch,
                    next_release,
                    changelog,
                    "Yes",
                )
                progress.update(branch_task, advance=task_progress, refresh=True)
                progress.update(repo_task, advance=task_progress, refresh=True)

            except Exception as exp:
                progress.console.print(f"Failed to make release for {repo_name} branch {branch} with error: {exp}")
                table.add_row(
                    repo_name,
                    branch,
                    next_release,
                    changelog,
                    "Failed",
                )
                progress.update(branch_task, advance=task_progress, refresh=True)
                progress.update(repo_task, advance=task_progress, refresh=True)

        else:
            table.add_row(
                repo_name,
                branch,
                next_release,
                changelog,
                "No",
            )
            progress.update(branch_task, advance=task_progress, refresh=True)
            progress.update(repo_task, advance=task_progress, refresh=True)

    return slack_msg_dict, table


def process_repositories_releases(
    repositories: Dict[str, List[str]],
    progress: Progress,
    verbose: bool,
    config_data: Dict,
    task_progress: int,
    repositories_mapping: Dict,
    git_base_dir: str,
    dry_run: bool,
    yes: bool,
    table: Table,
    slack_msg_dict: Dict,
) -> Tuple[Dict, Table]:
    task = progress.add_task("[green]Checking for releases ", total=len(repositories))
    for repo_name, branches in repositories.items():
        slack_msg_dict[repo_name] = {}

        repo_task, repo_name, repo_path = get_repository_data_for_release(
            repo_name=repo_name,
            progress=progress,
            task=task,
            branches=branches,
            git_base_dir=git_base_dir,
            config_data=config_data,
            verbose=verbose,
            repositories_mapping=repositories_mapping,
            task_progress=task_progress,
        )
        if not all([repo_name, repo_path, repo_task]):
            continue

        with change_directory(path=repo_path, progress=progress, verbose=verbose):
            for branch in branches:
                slack_msg_dict, table = make_release_for_branch(
                    repo_name=repo_name,
                    branch=branch,
                    progress=progress,
                    repo_task=repo_task,
                    task_progress=task_progress,
                    verbose=verbose,
                    dry_run=dry_run,
                    yes=yes,
                    slack_msg_dict=slack_msg_dict,
                    table=table,
                )

        progress.update(task, advance=task_progress, refresh=True)

    return slack_msg_dict, table


@click.command("release-it-repos")
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
@click.option(
    "--pdb",
    help="Drop to `ipdb` shell on exception",
    is_flag=True,
)
@click.option("-c", "--config-file", show_default=True, help="Config file")
@click.option("-d", "--dry-run", is_flag=True, help="Run the program but do not make any releases")
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
def main(yes: bool, git_base_dir: str, config_file: str, dry_run: bool, verbose: bool, pdb: bool) -> None:
    if not verbose:
        logging.disable(logging.CRITICAL)

    table = base_table()
    progress = Progress()
    config_data = process_config(config_file=config_file, progress=progress, verbose=verbose)
    git_base_dir = config_data.get("git_base_dir", git_base_dir)

    if not os.path.isdir(git_base_dir):
        progress.console.print(f"Git base directory {git_base_dir} does not exist")
        exit(1)

    slack_msg_dict: Dict = {}
    _repositories = config_data.get(
        "repositories", "https://raw.githubusercontent.com/CSPI-QE/MSI/main/manifests/repositories.yaml"
    )
    repositories = get_repositories(progress=progress, verbose=verbose, repositories=_repositories)

    repositories_mapping = config_data.get("repositories-mapping", {})

    process_repositories_releases_kwargs = {
        "progress": progress,
        "verbose": verbose,
        "yes": yes,
        "git_base_dir": git_base_dir,
        "repositories_mapping": repositories_mapping,
        "table": table,
        "task_progress": 1,
        "dry_run": dry_run,
        "config_data": config_data,
        "repositories": repositories,
        "slack_msg_dict": slack_msg_dict,
    }
    if verbose or pdb:
        _slack_msg_dict, _table = process_repositories_releases(**process_repositories_releases_kwargs)
    else:
        with progress:
            _slack_msg_dict, _table = process_repositories_releases(**process_repositories_releases_kwargs)

    if _table.rows:
        rich.print(table)

        if not dry_run:
            if slack_webhook_url := config_data.get(
                "slack-webhook-url", os.environ.get("RELEASE_IT_SLACK_WEBHOOK_URL")
            ):
                slack_msg = ""
                for repo_name, data in _slack_msg_dict.items():
                    for branch, changelog in data.items():
                        for next_release, changelog in changelog.items():
                            changelog_str = "\n".join([f"  {cl}" for cl in changelog.splitlines()])
                            slack_msg += f"{repo_name}\n  {branch}\n    {next_release}    {changelog_str}\n\n"

                send_slack_message(message=slack_msg, webhook_url=slack_webhook_url)

    else:
        rich.print("[yellow][bold]No new content found for any repositories[not bold][not yellow]")


if __name__ == "__main__":
    function_runner_with_pdb(main)
