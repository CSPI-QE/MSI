#!/usr/bin/env python

import os
import tomllib
import subprocess
import shlex
import json


def get_all_deps():
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


def update_all_deps():
    """
    Updates all dependencies in pyproject.toml
    """
    for dep in get_all_deps():
        print(f"Updating {dep}")
        subprocess.run(shlex.split(f"poetry update {dep}"))


def generate_renovate_json():
    """
    Generates renovate.json for renovatebot, add all poetry dependencies to matchPackagePatterns
    in order to force renovate to update all dependencies in one PR.
    """
    _json = {
        "$schema": "https://docs.renovatebot.com/renovate-schema.json",
        "packageRules": [{"matchPackagePatterns": get_all_deps(), "groupName": "poetry-deps"}],
    }
    with open("renovate.json", "w") as fd:
        fd.write(json.dumps(_json))


if __name__ == "__main__":
    update_all_deps()
