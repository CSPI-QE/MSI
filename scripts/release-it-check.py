#!/usr/bin/env python

import os
import re
import subprocess
import shlex
import click
import requests
import yaml


def get_repositories():
    repositories = {}
    repos = requests.get(
        "https://raw.githubusercontent.com/CSPI-QE/MSI/main/REPOS_INVENTORY.md"
    ).content
    for line in repos.decode("utf-8").splitlines():
        if re.findall(r"\[.*]\(.*\)", line):
            repo_data = [section.strip() for section in line.split("|") if section]
            if len(repo_data) < 4:
                continue

            if repo_data[2] == ":heavy_check_mark:":
                repo_name = re.findall(r"\[.*]", repo_data[0])[0].strip("[").rstrip("]")
                repositories[repo_name] = [br.strip("`") for br in repo_data[3].split()]

    return repositories


@click.command("installer")
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    show_default=True,
    help="Answer yes to all prompts",
)
def main(yes):
    repositories_mapping = {}
    config_file = os.path.join(
        os.path.expanduser("~"), ".config", "release-it-check", "config.yaml"
    )
    if os.path.isfile(config_file):
        with open(config_file) as fd:
            repositories_mapping = yaml.safe_load(fd.read())

    git_base_dir = os.getenv("GIT_BASE_DIR")
    if not git_base_dir:
        print("GIT_BASE_DIR not set")
        exit(1)

    current_path = os.getcwd()
    for repo_name, branches in get_repositories().items():
        repo_name = repositories_mapping.get(repo_name, repo_name)
        repo_path = os.path.join(git_base_dir, repo_name)
        os.chdir(repo_path)
        current_branch = subprocess.run(
            shlex.split("git branch --show-current"), stdout=subprocess.PIPE
        )
        for branch in branches:
            print(f"\nWorking on {repo_name} branch {branch} ...")
            try:
                subprocess.run(
                    shlex.split(f"git checkout {branch}"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                subprocess.run(
                    shlex.split(f"git pull origin {branch}"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            except Exception:
                subprocess.run(
                    shlex.split(
                        f"git checkout {current_branch.stdout.decode('utf-8').strip()}"
                    ),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                continue

            res = subprocess.run(
                shlex.split("release-it --changelog"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            out = res.stdout.decode("utf-8")
            if "undefined" in out or not out:
                os.system(
                    f"git checkout {current_branch.stdout.decode('utf-8').strip()}"
                )
                continue

            next_release = subprocess.run(
                shlex.split("release-it --release-version"), stdout=subprocess.PIPE
            )
            print(f"\n[{repo_name}]\n{out}\n")
            if yes:
                user_input = "y"
            else:
                user_input = input(
                    f"Do you want to make a new release "
                    f"[{next_release.stdout.decode('utf-8').strip()}] for {repo_name} on branch {branch}? [y/n]"
                )
            if user_input.lower() == "y":
                os.chdir(os.path.join(git_base_dir, repo_name))
                try:
                    os.system("release-it patch --ci")
                    print("\n")
                except Exception:
                    pass
            else:
                continue

        subprocess.run(
            shlex.split(
                f"git checkout {current_branch.stdout.decode('utf-8').strip()}"
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        os.chdir(current_path)


if __name__ == "__main__":
    main()
