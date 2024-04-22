#!/usr/bin/env python

import os
import tomllib
import subprocess
import shlex
import json
from typing import List


def get_all_deps() -> List[str]:
    """
    Returns all dependencies in pyproject.toml
    """
    all_deps = []
    if os.path.isfile("pyproject.toml"):
        with open("pyproject.toml", "rb") as fd:
            pyproject = tomllib.load(fd)

        deps = pyproject.get("tool", {}).get("poetry", {}).get("dependencies")
        group_deps = pyproject.get("tool", {}).get("poetry", {}).get("group", {})
        if not deps and not group_deps:
            print("Skipping because it does not have a dependencies")
            exit(0)

        for dep in deps:
            if dep == "python":
                continue

            all_deps.append(dep)

        for _, deps in group_deps.items():
            for dep in deps.get("dependencies"):
                if dep == "python":
                    continue

                all_deps.append(dep)

    else:
        print("Skipping because it does not have a pyproject.toml")

    return all_deps


def update_all_deps() -> None:
    """
    Updates all dependencies in pyproject.toml
    """
    for dep in get_all_deps():
        print(f"Updating {dep}")
        subprocess.run(shlex.split(f"poetry update {dep}"))


def generate_renovate_json() -> None:
    """
    Generates renovate.json for renovatebot, add all poetry dependencies to matchPackagePatterns
    in order to force renovate to update all dependencies in one PR.
    """
    file_name = "renovate.json"
    pkgs_rules = {"matchPackagePatterns": get_all_deps(), "groupName": "poetry-deps"}
    if os.path.isfile(file_name):
        with open(file_name, "r") as fd:
            _json = json.load(fd)

        match_package_patterns_idx = None
        for idx, match_package_pattern in enumerate(_json.get("packageRules", [])):
            if [*match_package_pattern][0] == "matchPackagePatterns":
                match_package_patterns_idx = idx
                break

        if match_package_patterns_idx is not None:
            _json["packageRules"].pop(match_package_patterns_idx)

        _json.setdefault("packageRules", []).append(pkgs_rules)

    else:
        _json = {
            "$schema": "https://docs.renovatebot.com/renovate-schema.json",
            "packageRules": [pkgs_rules],
        }
    with open(file_name, "w") as fd:
        fd.write(json.dumps(_json))


if __name__ == "__main__":
    pass
