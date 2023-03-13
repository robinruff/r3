"""Unit tests for ``r3.Repository``."""

import filecmp
import os
import stat
from pathlib import Path

import pytest
import yaml
from pyfakefs.fake_filesystem import FakeFilesystem

import r3

DATA_PATH = Path(__file__).parent.parent / "data"


@pytest.fixture
def repository(fs: FakeFilesystem) -> r3.Repository:
    return r3.Repository.create("/test/repository")


def get_dummy_job(fs: FakeFilesystem, name: str) -> r3.Job:
    path = DATA_PATH / "jobs" / name
    fs.add_real_directory(path, read_only=True)
    return r3.Job(path)


def test_create_fails_if_path_exists(fs: FakeFilesystem) -> None:
    path = "/rest/repository"
    fs.create_dir(path)

    with pytest.raises(FileExistsError):
        r3.Repository.create(path)


def test_create_creates_directories(fs: FakeFilesystem) -> None:
    path = Path("/test/repository")
    r3.Repository.create(path)

    assert path.exists()
    assert (path / "git").exists()
    assert (path / "jobs").exists()


def test_create_creates_config_file_with_version(fs: FakeFilesystem) -> None:
    path = Path("/test/repository")
    r3.Repository.create(path)

    assert (path / "r3.yaml").exists()

    with open(path / "r3.yaml", "r") as config_file:
        config = yaml.safe_load(config_file)

    assert "version" in config


def test_add_creates_job_folder(fs: FakeFilesystem, repository: r3.Repository) -> None:
    """Unit test for ``r3.Repository.add``.

    When adding a job, a directory should be created in ``$REPOSITORY_ROOT/jobs``.
    """
    job_paths = list((repository.path / "jobs").iterdir())
    assert len(job_paths) == 0

    job = get_dummy_job(fs, "base")
    repository.add(job)

    job_paths = list((repository.path / "jobs").iterdir())
    assert len(job_paths) == 1
    assert job_paths[0].is_dir()


def test_add_returns_the_updated_job(
    fs: FakeFilesystem, repository: r3.Repository
) -> None:
    """Unit test for ``r3.Repository.add``.

    ``r3.Repository.add`` should return the ``r3.Job`` instance within the repository.
    """
    job = get_dummy_job(fs, "base")
    assert job.repository is None
    assert not str(job.path).startswith(str(repository.path))

    job = repository.add(job)
    assert job.repository is not None
    assert str(job.path).startswith(str(repository.path))


def test_add_copies_files_write_protected(
    fs: FakeFilesystem, repository: r3.Repository
) -> None:
    """Unit test for ``r3.Repository.add``.

    When adding a job to a repository, all files should be copied to the repository. The
    files in the repository should be write protected.
    """
    original_job = get_dummy_job(fs, "base")
    assert original_job.path is not None

    added_job = repository.add(original_job)

    assert added_job.path is not None
    assert (added_job.path / "run.py").is_file()
    assert filecmp.cmp(
        added_job.path / "run.py", original_job.path / "run.py", shallow=False
    )

    mode = stat.S_IMODE(os.lstat(added_job.path / "run.py").st_mode)
    assert mode & stat.S_IWOTH == 0
    assert mode & stat.S_IWGRP == 0
    assert mode & stat.S_IWUSR == 0


def test_add_copies_nested_files(fs: FakeFilesystem, repository: r3.Repository) -> None:
    """Unit test for ``r3.Repository.add``."""
    original_job = get_dummy_job(fs, "nested")
    assert original_job.path is not None

    added_job = repository.add(original_job)

    assert added_job.path is not None
    assert (added_job.path / "code" / "run.py").is_file()
    assert filecmp.cmp(
        added_job.path / "code" / "run.py",
        original_job.path / "code" / "run.py",
        shallow=False,
    )


def test_add_loads_metadata_from_main_config(
    fs: FakeFilesystem, repository: r3.Repository
) -> None:
    """Unit test for ``r3.Repository.add``."""
    job = get_dummy_job(fs, "metadata_in_main_config")
    assert job.metadata == {"tags": ["test"]}
    assert "metadata" not in job.config

    job = repository.add(job)
    assert job.path is not None
    assert (job.path / "metadata.yaml").is_file()
    assert "metadata" not in job.config
    assert job.metadata.keys() == {"tags", "date"}
    assert job.metadata["tags"] == ["test"]
