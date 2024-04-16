import yaml
import click


@click.command("generate-inventory-markdown")
def generate_inverntory_markfown():
    markdown = """
# Repository inventory

Do not edit this file. Edit `repositories.yaml` instead, and run `generate_inventory.py`

Template for a new GitHub python repository: [python-template-repository](https://github.com/RedHatQE/python-template-repository)

| Name  | Container | Release | Tags |
|---|---|---|---|
"""

    with open("scripts/repositories.yaml") as rfd:
        repos = yaml.safe_load(rfd)

    check_mark = ":heavy_check_mark:"
    x_mark = ":x:"
    for name, data in repos.items():
        branches = " ".join([f"`{br}`" for br in data["branches"]])
        container = x_mark
        if data["container"]:
            container = f"[{check_mark}]({data['container_url']})"

        release = x_mark
        if data["release"]:
            release = f"[{check_mark}]({data['release_url']})"

        markdown += f"| [{name}]({data['github_url']}) | {container} | {release} | {branches} |\n"

    with open("REPOS_INVENTORY.md", "w") as wfd:
        wfd.write(markdown)


if __name__ == "__main__":
    generate_inverntory_markfown()
