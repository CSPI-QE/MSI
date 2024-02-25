#!/usr/bin/env python

import os
import tomllib
import subprocess
import shlex


def main():
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

            print(f"Updating {dep}")
            subprocess.run(shlex.split(f"poetry update {dep}"))
            for group, deps in group_deps.items():
                for dep in deps:
                    if dep == "python":
                        continue

                print(f"Updating group {group} {dep}")
                subprocess.run(shlex.split(f"poetry update {dep}"))

    else:
        print("Skipping because it does not have a pyproject.toml")


if __name__ == "__main__":
    main()
