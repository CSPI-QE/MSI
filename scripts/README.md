# Check and release to Pypi using [release-it](https://github.com/release-it/release-it)

Check repositories from [REPOS_INVENTORY](../REPOS_INVENTORY.md)

## Usage
set os environment to base git repositories path

```bash
export GIT_BASE_DIR=<git repositories path>
```

If local repository folder is different from the repository name override them in the config file `/home/<user>/.config/release-it-check/config.yaml`
```yaml
cloud-tools: cloud-tools-upstream
```

## Installation
run `pip install -r scripts/requirements.txt`
create link to `scripts/release-it-check.py` somewhere in your PATH

run `release-it check.py` to execute the script
