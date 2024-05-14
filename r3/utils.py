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


def _get_pygit2_repo(repository_path: Path) -> pygit2.Repository:
    try:
        repo = pygit2.Repository(repository_path)
    except pygit2.GitError:
        raise ValueError(f"The given path ({repository}) is not a git repository.")
    return repo


def _get_pygit2_remote_callback(username: str = "git") -> pygit2.RemoteCallbacks:
    keypair = pygit2.KeypairFromAgent(username)
    callbacks = pygit2.RemoteCallbacks(credentials=keypair)
    return callbacks


def git_get_remote_head(repository: Path, remote: str = "origin") -> str:

    # Get repo as pygit object
    repo = _get_pygit2_repo(repository)
    # Get pygit2 callbacks for git authentication at remote
    callbacks = _get_pygit2_remote_callback()

    # List remote revs (== `git ls-remote {remote} HEAD`)
    remote_revs = repo.remotes[remote].ls_remotes(callbacks=callbacks)
    # Find HEAD rev
    head_rev = next((rev for rev in remote_revs if rev["name"] == "HEAD"), None)
    assert head_rev is not None # assumption: there is always a HEAD reference for the remote
    # Return commit hash of HEAD rev
    return head_rev["oid"].hex


def git_get_remote_branch_head(
    repository: Path, branch: str, remote: str = "origin"
) -> Optional[str]:
    # Get repo as pygit object
    repo = _get_pygit2_repo(repository)
    # Get pygit2 callbacks for git authentication at remote
    callbacks = _get_pygit2_remote_callback()

    # List remote revs (== `git ls-remote {remote} {branch}`)
    remote_revs = repo.remotes[remote].ls_remotes(callbacks=callbacks)

    print(remote_revs, branch)
    # Get HEAD of remote and return it

    branch_rev = next((rev for rev in remote_revs if rev["name"] == f"refs/heads/{branch}"), None)
    if branch_rev is None:
        return None
    return branch_rev["oid"].hex


def git_get_remote_tag_head(
    repository: Path, tag: str, remote: str = "origin"
) -> Optional[str]:
    # Get repo as pygit object
    repo = _get_pygit2_repo(repository)
    # Get pygit2 callbacks for git authentication at remote
    callbacks = _get_pygit2_remote_callback()

    # `git fetch {remote}`
    repo.remotes[remote].fetch(callbacks=callbacks)

    remote_revs = repo.remotes[remote].ls_remotes(callbacks=callbacks)
    tag_rev = next((rev for rev in remote_revs if rev["name"] == f"refs/tags/{tag}^{{}}"), None)
    if tag_rev is None:
        return None
    return tag_rev["oid"].hex

def git_clone_repository(repository_url: str, repository_path: Path):

    # Makes cloned repo a mirror of the remote
    def init_remote(repo, name, url):
        # Create the remote with a mirroring url
        remote = repo.remotes.create(name, url, "+refs/*:refs/*")
        # And set the configuration option to true for the push command
        mirror_var = f"remote.{name.decode()}.mirror"
        repo.config[mirror_var] = True
        return remote

    callbacks = _get_pygit2_remote_callback()
    repo = pygit2.clone_repository(repository_url, repository_path, callbacks=callbacks, bare=True, remote=init_remote)


def git_fetch_repository(repository_path: Path, remote: str = "origin"):

    callbacks = _get_pygit2_remote_callback()
    repo = _get_pygit2_repo(repository_path)
    repo.remotes[remote].fetch(callbacks=callbacks)
