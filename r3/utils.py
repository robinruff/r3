import hashlib
from pathlib import Path
from typing import Iterable, List, Optional
import pygit2


def find_files(path: Path, ignore_patterns: Iterable[str]) -> List[Path]:
    return [child.relative_to(path) for child in _find_files(path, ignore_patterns)]


def _find_files(path: Path, ignore_patterns: Iterable[str]) -> Iterable[Path]:
    if not all(pattern.startswith("/") for pattern in ignore_patterns):
        raise NotImplementedError(
            "Only absolute ignore patterns (starting with /) are supported for now."
        )

    for child in path.iterdir():
        if _is_ignored(child, ignore_patterns):
            continue

        if child.is_file():
            yield child

        elif child.is_dir():
            prefix = f"/{child.name}"
            ignore_patterns = [
                pattern[len(prefix) :]
                for pattern in ignore_patterns
                if pattern.startswith(prefix)
            ]
            yield from _find_files(child, ignore_patterns)


def _is_ignored(path: Path, ignore_patterns: Iterable[str]):
    return any(pattern == f"/{path.name}" for pattern in ignore_patterns)


def hash_file(path: Path, chunk_size: int = 2**16) -> str:
    hash = hashlib.sha256()

    with open(path, "rb") as file:
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            hash.update(chunk)

    return hash.hexdigest()


def hash_str(string: str) -> str:
    return hashlib.sha256(string.encode()).hexdigest()


def git_commit_exists(repository: Path, commit: str) -> bool:
    try:
        repo = pygit2.Repository(repository)
        commit = repo.revparse_single(commit)
    except KeyError:
        return False
    return isinstance(commit, pygit2.Commit)


def git_path_exists(
    repository: Path,
    commit: Optional[str] = None,
    path: Optional[Path] = None,
) -> bool:
    commit = commit or "HEAD~1"
    path = path or Path(".")

    if not repository.is_dir():
        return False

    if path == Path("."):
        return git_commit_exists(repository, commit)

    path = (Path(repository) / Path(path)).resolve().relative_to(repository)
    # Check if git repo exists
    try:
        repo = pygit2.Repository(repository)
    except pygit2.GitError:
        return False
    # Check if git commit exists
    try:
        commit = repo.revparse_single(commit)
    except KeyError:
        return False

    tree = commit.tree
    # traverse commit tree with the given path
    current_tree = tree
    for part in path.parts:
        try:
            current_tree = repo[current_tree[part].id]
        except KeyError:
            return False
    return True


def git_get_remote_head(repository: Path, remote: str = "origin") -> str:
    # Setup SSH keys
    keypair = pygit2.KeypairFromAgent('git')
    callbacks = pygit2.RemoteCallbacks(credentials=keypair)

    # Get repo as pygit object
    try:
        repo = pygit2.Repository(repository)
    except pygit2.GitError:
        raise ValueError(f"The given path ({repository}) is not a git repository.")

    # List remote revs (== `git ls-remote {remote} HEAD`)
    remote_revs = repo.remotes[remote].ls_remotes(callbacks=callbacks)
    # Get HEAD of remote and return it
    head_rev = [rev for rev in remote_revs if rev['name'] == 'HEAD'][0]
    return head_rev['oid']


def git_get_remote_branch_head(
    repository: Path, branch: str, remote: str = "origin"
) -> Optional[str]:
    # Setup SSH keys
    keypair = pygit2.KeypairFromAgent('git')
    callbacks = pygit2.RemoteCallbacks(credentials=keypair)

    # Get repo as pygit object
    try:
        repo = pygit2.Repository(repository)
    except pygit2.GitError:
        raise ValueError(f"The given path ({repository}) is not a git repository.")

    # List remote revs (== `git ls-remote {remote} {branch}`)
    remote_revs = repo.remotes[remote].ls_remotes(callbacks=callbacks)
    # Get HEAD of remote and return it
    branch_rev = [rev for rev in remote_revs if rev['name'] == 'refs/heads/' + branch][0]
    return branch_rev['oid']


def git_get_remote_tag_head(
    repository: Path, tag: str, remote: str = "origin"
) -> Optional[str]:
    # Setup SSH keys
    keypair = pygit2.KeypairFromAgent('git')
    callbacks = pygit2.RemoteCallbacks(credentials=keypair)

    # Get repo as pygit object
    try:
        repo = pygit2.Repository(repository)
    except pygit2.GitError:
        raise ValueError(f"The given path ({repository}) is not a git repository.")

    # `git fetch {remote}`
    repo.remotes[remote].fetch(callbacks=callbacks)

    remote_revs = repo.remotes[remote].ls_remotes(callbacks=callbacks)
    tag_rev = [rev for rev in remote_revs if rev['name'] == 'refs/tags/' + tag + '^{}'][0]
    return tag_rev['oid']
