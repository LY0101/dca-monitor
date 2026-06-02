"""
Fetch live data, export index.html, commit, and push to GitHub Pages.

Usage:
  python publish.py          # update + push
  python publish.py --save   # update + push + save to history.csv (use on the 1st)
"""

import argparse
import subprocess
import sys
from datetime import date

def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"ERROR running {' '.join(cmd)}")
        print(result.stderr)
        sys.exit(1)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true",
                        help="Also save to history.csv (run on the 1st of each month)")
    args = parser.parse_args()

    # 1. Generate index.html
    print("Fetching live data and generating index.html...")
    cmd = [sys.executable, "main.py", "--html"]
    if args.save:
        cmd.append("--save")
    run(cmd)

    # 2. Stage index.html (and history.csv if --save)
    files = ["index.html"]
    if args.save:
        files.append("history.csv")
    run(["git", "add"] + files)

    # 3. Check if there's anything to commit
    status = run(["git", "status", "--porcelain"], check=False)
    if not status.stdout.strip():
        print("Nothing changed — index.html is already up to date.")
        return

    # 4. Commit
    today = date.today().isoformat()
    run(["git", "commit", "-m", f"Update {today}"])

    # 5. Push
    print("Pushing to GitHub...")
    run(["git", "push"])

    print(f"\nDone. Site will refresh in ~30 seconds.")

if __name__ == "__main__":
    main()
