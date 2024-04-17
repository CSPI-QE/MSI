# Scripts

## Requirements

- [poetry](https://python-poetry.org/)
- [pipx](https://github.com/pypa/pipx)

## Installation

With poetry

```bash
poetry install
```

Globally

```bash
git clone https://github.com/CSPI-QE/MSI.git
cd MSI
pipx install .
```

### Update

```bash
git remote update
```

With poetry

```bash
poetry install
```

With pipx

```bash
pipx install .
```

if already installed run `pipx uninstall MSI && pipx install .`

## release-it-repos

Check and release to Pypi using [release-it](https://github.com/release-it/release-it) for all repositories under [REPOS_INVENTORY](../REPOS_INVENTORY.md)

### Usage

set os environment or in the config file to base git repositories path

```bash
export GIT_BASE_DIR=<git repositories path>
```

```yaml
git-base-dir: ~/git/
repositories: https://raw.githubusercontent.com/CSPI-QE/MSI/main/REPOS_INVENTORY.md # Either link to inventory file or list of repositories
repositories:
  https://github.com/user/repository1:
    - main
  https://github.com/user/repository2:
    - main
    - feature

repositories-mapping: # IF local repository folder is different from the repository name
  cloud-tools: cloud-tools-upstream

include-repositories: # Check only these repositories
  - cloud-tools
```

### Usage

run `poetry run release-it-repos` to execute the script
Check `poetry run release-it-repos --help` for more info

## poetry-update-repo

Update local repository dependencies
Must be run from the root of the repository

```bash
poetry run poetry-update-repo
```

## generate-inventory-markdown

Generate REPOS_INVENTORY.md file with the content from manifests/repositories.yaml file
Must be run from the root of the repository

### Usage

```bash
generate-inventory-markdown
```
