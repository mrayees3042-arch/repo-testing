import os
from dulwich.repo import Repo
from dulwich.porcelain import status, add, commit

repo_dir = "C:\\repo gen"
repo = Repo(repo_dir)

# Add all files except ignored ones
add(repo, paths=[
    "backend",
    "frontend",
    "work",
    "ux-audit-after",
    "build.py",
    "main.py",
    "README.md",
    "PROJECT_STATUS.md",
    "RepoGen-S7-Setup.spec",
    "RepoGen-S7.spec",
    "test_snap7.py",
    "test_verification.py",
    "test_simulator_live.py",
    ".gitignore"
])

commit_id = commit(
    repo,
    message=b"Fix RepoGen S7: BOOL normalization, transport failure auto-recovery, and full UI/UX overhaul",
    author=b"Alan & Collaborator <team@repogen.local>",
    committer=b"Alan & Collaborator <team@repogen.local>"
)

print(f"Committed successfully: {commit_id.decode('ascii')}")
