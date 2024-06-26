# Tutorial

!!! warning
    The information in the tutorial is outdated.

Create a new repository using `r3 init`:

```
r3 init path/to/repository
```

Data files or directories can be added to the repository using the `commit-data`
command. The command returns the path to the job within the repository, that can be
used to specifiy dependencies later.

```bash
$ r3 commit-data container-v1.sif --tag container
/repository/jobs/123abc...
```

Prepare your job in a directory, including a config file. For example:

```yaml
# r3.yaml
commit:
  ignore: [/__pycache__]

dependencies:
  - item: /repository/jobs/123abc...
    source: container-v1.sif
    destination: &container container.sif

environment:
  container: *container
  gpus: none

commands:
  run: python run.py
  done: ls output/test

parameters:
  name: World
```

```python
# run.py
import yaml

with open("r3.yaml", "r") as config_file:
    parameters = yaml.safe_load(config_file).get("parameters", {})

name = parameters.get("name", "World")

with open("output/test", "w") as output_file:
    output_file.write(f"Hello {name}!")
```

To facilitate developing jobs, dependencies for uncomitted jobs can be checked out
using `r3 dev checkout`.

Now commit your job to the repository:
```
r3 commit path/to/job path/to/repository
```

Per default, the repository path is read from the environment variable `R3_REPOSITORY`.
So the following works as well:
```
export R3_REPOSITORY=path/to/repository
r3 commit path/to/job
```

Checking out jobs from the repository will copy the job files and symlink the output
directory and dependencies:
```
r3 checkout /repository/jobs/by_hash/123abc... work/dir
```
