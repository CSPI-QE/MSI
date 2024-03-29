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
pipx install -f .
```

## release-it-repos

Check and release to Pypi using [release-it](https://github.com/release-it/release-it) for all repositories under [REPOS_INVENTORY](../REPOS_INVENTORY.md)

### Usage
set os environment to base git repositories path

```bash
export GIT_BASE_DIR=<git repositories path>
```

If local repository folder is different from the repository name override them in the config file `/home/<user>/.config/release-it-check/config.yaml`
```yaml
cloud-tools: cloud-tools-upstream
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
