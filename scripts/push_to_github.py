import sys
import os
import getpass
from dulwich.repo import Repo
from dulwich.porcelain import push

def do_push():
    repo_path = "C:\\repo gen"
    repo = Repo(repo_path)
    
    remote_url = "https://github.com/mrayees3042-arch/repo-testing.git"
    print(f"Target remote: {remote_url}")
    
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token and len(sys.argv) > 1:
        token = sys.argv[1]
        
    if not token:
        print("Please enter your GitHub Personal Access Token (PAT) with 'repo' scope:")
        token = input("GitHub Token: ").strip()
        
    if not token:
        print("No token provided. Aborting push.")
        return
        
    # Push using token
    auth_url = f"https://mrayees3042-arch:{token}@github.com/mrayees3042-arch/repo-testing.git"
    print(f"Pushing to {remote_url} on branch 'main'...")
    try:
        push(repo, auth_url, "refs/heads/main:refs/heads/main")
        print("Successfully pushed to GitHub!")
    except Exception as e:
        print(f"Push failed: {e}")

if __name__ == '__main__':
    do_push()
