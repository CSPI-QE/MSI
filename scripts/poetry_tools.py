#!/usr/bin/env python

import os
import tomllib
import subprocess
import shlex


def get_all_deps():
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
    for dep in get_all_deps():
        print(f"Updating {dep}")
        subprocess.run(shlex.split(f"poetry update {dep}"))


if __name__ == "__main__":
    update_all_deps()
