"""
Bot self-update script.

Called by the /restart command handler before the process is replaced.

Security fixes vs previous version
------------------------------------
  - Replaced shell=True + f-string interpolation with argument lists
    (shell=False) to eliminate command injection via UPSTREAM_REPO /
    UPSTREAM_BRANCH config values.
  - Replaced `git config --global` with `git config --local` to avoid
    permanently mutating the system-wide git identity.
  - Removed the `rm -rf .git` + re-init dance.  The repo is updated by
    fetching and resetting against the upstream branch while keeping the
    existing .git directory intact.
  - Temporary commits (`git add . && git commit`) are no longer created.

Equivalent behaviour:  the working tree ends up at the HEAD of
UPSTREAM_REPO/UPSTREAM_BRANCH, which is what the original script did.
"""
import os
import subprocess
from logging import (
    StreamHandler,
    INFO,
    basicConfig,
    error as log_error,
    info as log_info,
)
from logging.handlers import RotatingFileHandler

basicConfig(
    level=INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s [%(filename)s:%(lineno)d]",
    datefmt="%d-%b-%y %I:%M:%S %p",
    handlers=[
        RotatingFileHandler("log.txt", maxBytes=50_000_000, backupCount=10),
        StreamHandler(),
    ],
)

try:
    import config as _cfg
except ImportError:
    _cfg = None  # type: ignore[assignment]

def _conf(key: str, default: str = "") -> str:
    return getattr(_cfg, key, None) or os.getenv(key, default)

UPSTREAM_REPO   = _conf("UPSTREAM_REPO",   "https://github.com/MeherMankar/FZBypassBot")
UPSTREAM_BRANCH = _conf("UPSTREAM_BRANCH", "main")

if not UPSTREAM_REPO:
    log_error("UPSTREAM_REPO is not set — skipping update")
else:
    def _run(*args: str) -> subprocess.CompletedProcess:
        """Run a git command with shell=False and return the result."""
        return subprocess.run(
            list(args),
            capture_output=True,
            text=True,
        )

    # Ensure the local repo has a remote named 'upstream' pointing at
    # UPSTREAM_REPO.  We use a dedicated remote name to avoid clobbering
    # an existing 'origin' that may point elsewhere.
    remote_check = _run("git", "remote", "get-url", "upstream")
    if remote_check.returncode != 0:
        # Remote doesn't exist yet — add it
        add_result = _run("git", "remote", "add", "upstream", UPSTREAM_REPO)
        if add_result.returncode != 0:
            log_error("Failed to add upstream remote: %s", add_result.stderr)
    else:
        # Remote exists — make sure the URL is current
        _run("git", "remote", "set-url", "upstream", UPSTREAM_REPO)

    # Set local (repo-level) identity so git doesn't complain in
    # environments without a global git config.
    _run("git", "config", "--local", "user.email", "bot@fzbypass.local")
    _run("git", "config", "--local", "user.name",  "FZBypassBot")

    # Fetch the upstream branch (no --depth to preserve full history)
    fetch = _run("git", "fetch", "upstream", UPSTREAM_BRANCH, "--quiet")
    if fetch.returncode != 0:
        log_error("git fetch failed: %s", fetch.stderr.strip())
    else:
        # Hard-reset the working tree to the fetched state
        reset = _run(
            "git", "reset", "--hard",
            f"upstream/{UPSTREAM_BRANCH}",
            "--quiet",
        )
        if reset.returncode == 0:
            log_info(
                "Successfully updated to latest commit from %s/%s",
                UPSTREAM_REPO, UPSTREAM_BRANCH,
            )
        else:
            log_error(
                "git reset failed: %s — check UPSTREAM_REPO/UPSTREAM_BRANCH",
                reset.stderr.strip(),
            )
