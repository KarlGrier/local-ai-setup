"""A read-only code tool for the agents (phase 4; the user, 2026-10-24 - built 10-27). LDR_DEEP_CODE=1.

The agents can look at a project's real source instead of guessing from web pages: a shallow clone of one public GitHub
repo at one tag / branch / commit into a capped scratch folder ($TMPDIR/code-tool/<research>, deleted when the research
ends), searched with grep (file:line hits), a tree listing and line-range reads - search first, never whole files into
the context - plus the repo's issues, PRs and commit messages through the public GitHub API without any token.

Tools: code_search, code_read, code_tree, github_issues, github_commits. Only code_read, an opened issue / PR and a commit
list become citable sources ([N], with the GitHub link of the lines read; the evidence store keeps the exact text, so the
citation check verifies claims against it); search hits and listings only point the way.

Rules (the user, 10-24):
  * never build, run or install anything from a clone: files are only read as text; no submodules, no LFS, no hooks,
    symlinks checked out as plain files;
  * never the user's gh login or any key: git runs with HOME / XDG_CONFIG_HOME in the scratch folder, no global or
    system config and no credential helper; the API calls carry no Authorization header;
  * a clone is capped (LDR_DEEP_CODE_MAX_MB, default 400 MB; watched during the clone too) and deleted after the run.

Without the variable nothing here runs. A log of every call goes to the research's folder (code-tool.jsonl).

10-27 (the user, after the code-tool grading):
  * pinned to the user's version (Fix 1): a project the task (or else the setup profile) names with a version - e.g.
    "Strata v0.2.4" - is opened at that tag when the agent gives no ref; another ref of a pinned project can still be
    read, but every result and citation says "OTHER VERSION ... the user runs v0.2.4; not evidence for that version";
  * the GitHub API is spared: the default branch comes from `git ls-remote`, commit lists from a blob-less shallow
    clone (`git log`), the size pre-check is gone (the clone's own cap stays); API answers are cached for the run; the
    core (60 an hour) and search (10 a minute) limits are tracked apart (one counter mixed them: the "6 left" on 10-27
    was the search minute, the hourly core limit never went below 39); per run at most LDR_DEEP_CODE_API_MAX core calls
    (50) and LDR_DEEP_CODE_SEARCH_MAX searches (30), and 10 core calls are always left for other programs.

10-29 (engine scope, deep/enginescope.py; LDR_DEEP_FIX version): when the task is about one engine of a multi-engine
project (Strata's DeepSeek engine), a read of a file or doc part of another engine (Strata's Qwen engine) says so above
its lines, and search hits in such files carry [OTHER ENGINE ...]. The evidence keeps the plain text.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

MAX_MB = float(os.environ.get("LDR_DEEP_CODE_MAX_MB", "400"))     # one clone's size on disk
CLONE_TIMEOUT_S = float(os.environ.get("LDR_DEEP_CODE_CLONE_S", "300"))
GREP_HITS = 40                  # hits returned by one grep (the total is reported)
READ_LINES = 120                # lines returned by one read
LINE_CHARS = 240                # a returned line is cut here
TREE_ENTRIES = 200
TEXT_MAX_BYTES = 2 * 1024 * 1024  # larger files are not searched or read (data, generated code)
REPO_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}$")
REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
API_MAX = int(os.environ.get("LDR_DEEP_CODE_API_MAX", "50"))          # core API calls per run (not cached ones)
SEARCH_MAX = int(os.environ.get("LDR_DEEP_CODE_SEARCH_MAX", "30"))    # issue searches per run
API_RESERVE = int(os.environ.get("LDR_DEEP_CODE_API_RESERVE", "10"))  # core calls always left for other programs
HISTORY_DEPTH = 400             # commits fetched (blob-less) for a commit list
VER_RE = re.compile(r"(?<![\w./-])([A-Za-z][\w.+-]{1,40}?)\s+(?:version\s+|release\s+)?(v?\d+\.\d+(?:\.\d+){0,2})(?![\w.])")
GH_URL_RE = re.compile(r"github\.com/([A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100})")


PIN_STOP = set("""the its a an and or of to in on for with by at from as is was be than about version release table size
up over under only at least most v vs per pcie pci gen ddr ddr4 ddr5 cuda usb""".split())


def _pin_matches(text: str):
    """(project, version) pairs: a version with a v, or after a capitalised name; common words left out."""
    for m in VER_RE.finditer(text or ""):
        raw = m.group(1).strip("\"'`*(")
        name, ver = raw.lower(), m.group(2)
        if not raw or name in PIN_STOP or len(name) < 3:
            continue
        if ver.startswith("v") or raw[0].isupper():
            yield name, ver


def derive_pins(task: str, profile: str = "") -> dict[str, str]:
    """Project name (lower case) -> the version the user runs: from the task first; from the setup profile only where
    it names one version for that project (it may describe two installs)."""
    pins: dict[str, str] = {}
    for name, ver in _pin_matches(task):
        pins.setdefault(name, ver)
    prof: dict[str, set] = {}
    for name, ver in _pin_matches(profile):
        prof.setdefault(name, set()).add(ver)
    for k, vs in prof.items():
        if k not in pins and len(vs) == 1:
            pins[k] = next(iter(vs))
    return pins


GH_PAGE_RE = re.compile(r"https?://(?:www\.)?(github\.com|raw\.githubusercontent\.com)/([A-Za-z0-9][A-Za-z0-9-]{0,38})/"
                        r"([A-Za-z0-9._-]{1,100})(?:/([^?#]*))?", re.I)


def _ver(v: str) -> tuple | None:
    m = re.match(r"^v?(\d+)\.(\d+)(?:\.(\d+))?(?:\.(\d+))?$", v or "")
    return tuple(int(x or 0) for x in m.groups()) if m else None


def version_note(url: str, pins: dict[str, str] | None) -> str:
    """The version a GitHub page of a pinned project is about, when it is not the user's (10-28, the bundle rerun:
    main-branch docs and code, the releases list and a fork's proposal in an issue were written up as the user's
    v0.2.4). "" for a page at the pinned tag, an older tag's release notes, or a project with no pin."""
    m = GH_PAGE_RE.match(url or "")
    if not m or not pins:
        return ""
    name = m.group(3).removesuffix(".git")
    tag = pins.get(name.lower())
    if not tag:
        return ""
    parts = [p for p in (m.group(4) or "").split("/") if p]
    user = f"the user runs {name} {tag}"
    if m.group(1).lower().startswith("raw."):
        ref = parts[0] if parts else ""
    elif parts and parts[0] in ("blob", "tree", "blame", "commits", "raw") and len(parts) > 1:
        ref = parts[1]
    elif parts and parts[0] == "releases":
        if len(parts) > 2 and parts[1] == "tag":
            ref = parts[2]
            older = _ver(ref) is not None and _ver(tag) is not None and _ver(ref) <= _ver(tag)
            return "" if older else f"OTHER VERSION (release {ref}): {user}; not evidence for that version"
        return (f"RELEASE NOTES OF EVERY VERSION, newest first: only the {tag} entry and older ones describe the user's "
                f"{name} {tag}")
    elif parts and parts[0] in ("issues", "pull", "discussions"):
        return (f"ISSUE / PR: a discussion or proposal (it may describe a fork or an unmerged change); not evidence of "
                f"what {name} {tag} has unless its code shows it")
    elif parts and parts[0] in ("commit", "compare"):
        return f"A SINGLE COMMIT / COMPARISON: not shown to be in {name} {tag}"
    elif not parts:
        ref = "the default branch"
    else:
        return ""
    if ref == tag:
        return ""
    if SHA_RE.match(ref):
        return f"AT COMMIT {ref[:12]}: not shown to be {name} {tag}"
    return f"OTHER VERSION ({ref}): {user}; not evidence for that version"


class CodeToolError(Exception):
    """A refusal or failure the agent is told about (bad repo name, over the cap, path outside the clone, ...)."""


def _dir_mb(path: Path) -> float:
    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total / 2 ** 20


def parse_repo(spec: str) -> tuple[str, str | None]:
    """'owner/repo', 'owner/repo@ref' or a github.com URL (…/tree/<ref>) -> ('owner/repo', ref or None)."""
    s = spec.strip()
    ref = None
    m = re.match(r"^(?:https?://)?(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+?)(?:\.git)?(?:/tree/([^\s#?]+))?/?$", s)
    if m:
        s, ref = f"{m.group(1)}/{m.group(2)}", m.group(3)
    elif "@" in s:
        s, ref = s.split("@", 1)
    if not REPO_RE.match(s):
        raise CodeToolError(f"not a GitHub repo name: {spec!r} (use owner/repo, owner/repo@tag or a github.com URL)")
    if ref is not None and not REF_RE.match(ref):
        raise CodeToolError(f"not a usable tag / branch / commit: {ref!r}")
    return s, ref


class Repo:
    """One read-only clone. Every path the agent gives is resolved inside the clone; .git is never shown."""

    def __init__(self, name: str, ref: str, root: Path, log=None, user_ref: str | None = None):
        self.name, self.ref, self.root, self._log = name, ref, root, log
        self.user_ref = user_ref          # the user's version of this project, when it is pinned and differs from ref

    @property
    def label(self) -> str:
        """'owner/name@ref', with the OTHER VERSION warning when the user runs another version."""
        if self.user_ref and self.user_ref != self.ref:
            return (f"{self.name}@{self.ref} - OTHER VERSION: the user runs {self.user_ref}; not evidence for that "
                    f"version")
        return f"{self.name}@{self.ref}"

    # ---- helpers
    def _path(self, rel: str) -> Path:
        rel = (rel or ".").strip().lstrip("/")
        p = (self.root / rel).resolve()
        if p != self.root and self.root not in p.parents:
            raise CodeToolError(f"path outside the repo: {rel!r}")
        if ".git" in p.relative_to(self.root).parts:
            raise CodeToolError("the .git folder is not part of the code")
        return p

    def url(self, rel: str, line: int | None = None, end: int | None = None) -> str:
        """The GitHub link of a file (and line range) at this clone's ref - the citation for a hit or a read."""
        u = f"https://github.com/{self.name}/blob/{self.ref}/{rel}"
        if line:
            u += f"#L{line}" + (f"-L{end}" if end and end != line else "")
        return u

    def _note(self, kind: str, **kw):
        if self._log:
            self._log(dict(tool=kind, repo=self.name, ref=self.ref, **kw))

    # ---- the agent's calls
    def grep(self, pattern: str, path: str = ".", glob: str | None = None, ignore_case: bool = False,
             fixed: bool = False, max_hits: int = GREP_HITS) -> dict:
        """Lines matching `pattern` (extended regex, or a plain string with fixed=True) under `path`, optionally only in
        files matching `glob` (e.g. '*.cpp'). Returns up to max_hits {file, line, text} and the total count."""
        if not pattern or len(pattern) > 300:
            raise CodeToolError("give a pattern of 1-300 characters")
        base = self._path(path)
        cmd = ["grep", "-rnIH", "--exclude-dir=.git", "--no-messages", "--color=never"]
        cmd += ["-F"] if fixed else ["-E"]
        if ignore_case:
            cmd.append("-i")
        if glob:
            if not re.match(r"^[\w.*?\[\]{},-]{1,60}$", glob):
                raise CodeToolError(f"not a file glob: {glob!r}")
            cmd.append(f"--include={glob}")
        cmd += ["-e", pattern, "--", str(base)]
        t0 = time.time()
        try:
            out = subprocess.run(cmd, capture_output=True, timeout=30, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8"})
        except subprocess.TimeoutExpired:
            raise CodeToolError("the search took over 30 s: narrow the path or the pattern")
        hits, total = [], 0
        for raw in out.stdout.splitlines():
            line = raw.decode("utf-8", "replace")
            m = re.match(r"^(.*?):(\d+):(.*)$", line)
            if not m:
                continue
            f = Path(m.group(1))
            try:
                if f.stat().st_size > TEXT_MAX_BYTES:
                    continue
                rel = str(f.relative_to(self.root))
            except (OSError, ValueError):
                continue
            total += 1
            if len(hits) < max_hits:
                hits.append({"file": rel, "line": int(m.group(2)), "text": m.group(3).strip()[:LINE_CHARS]})
        self._note("grep", pattern=pattern, path=path, glob=glob, total=total, s=round(time.time() - t0, 2))
        return {"repo": self.name, "ref": self.ref, "pattern": pattern, "total": total, "hits": hits,
                "more": max(0, total - len(hits))}

    def files(self, glob: str, path: str = ".", limit: int = 100) -> dict:
        """Files whose name matches `glob` (e.g. 'ds4_*.cpp', '*server*.py') under `path`."""
        base = self._path(path)
        out = []
        for root, dirs, fs in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d != ".git")
            for f in sorted(fs):
                if fnmatch.fnmatch(f, glob):
                    out.append(str((Path(root) / f).relative_to(self.root)))
        self._note("files", glob=glob, path=path, total=len(out))
        return {"repo": self.name, "ref": self.ref, "glob": glob, "total": len(out), "files": out[:limit]}

    def tree(self, path: str = ".", depth: int = 2) -> dict:
        """The folders and files under `path`, `depth` levels deep (sizes in KB, lines for text files under 2 MB)."""
        base = self._path(path)
        if not base.is_dir():
            raise CodeToolError(f"not a folder: {path!r}")
        depth = max(1, min(int(depth), 4))
        rows, cut = [], False
        for root, dirs, fs in os.walk(base):
            r = Path(root)
            level = len(r.relative_to(base).parts)
            dirs[:] = sorted(d for d in dirs if d != ".git") if level + 1 < depth else []
            for d in (sorted(x for x in os.listdir(r) if (r / x).is_dir() and x != ".git") if level < depth else []):
                rows.append(f"{(r / d).relative_to(self.root)}/")
            for f in sorted(fs):
                p = r / f
                try:
                    size = p.lstat().st_size
                except OSError:
                    continue
                rows.append(f"{p.relative_to(self.root)}  ({size // 1024} KB)")
            if len(rows) > TREE_ENTRIES:
                rows, cut = rows[:TREE_ENTRIES], True
                break
        self._note("tree", path=path, depth=depth, entries=len(rows))
        return {"repo": self.name, "ref": self.ref, "path": path, "entries": rows, "cut": cut}

    def read(self, path: str, start: int = 1, end: int | None = None) -> dict:
        """Lines start..end (at most READ_LINES) of one file, numbered - after a grep, read around the hit."""
        p = self._path(path)
        if not p.is_file():
            raise CodeToolError(f"not a file: {path!r}")
        if p.stat().st_size > TEXT_MAX_BYTES:
            raise CodeToolError(f"{path} is over 2 MB (data or generated code): grep it instead")
        with open(p, "rb") as fh:
            if b"\0" in fh.read(8192):
                raise CodeToolError(f"{path} is a binary file")
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, int(start))
        if start > len(lines):
            raise CodeToolError(f"{path} has {len(lines)} lines; start_line {start} is past its end")
        stop = int(end) if end else 0
        if stop < start:                     # no end, or an end before the start (10-27 smoke: 8060-1990): a full window
            stop = start + READ_LINES - 1
        end = min(len(lines), stop, start + READ_LINES - 1)
        rel = str(p.relative_to(self.root))
        body = [f"{i}: {lines[i - 1][:LINE_CHARS]}" for i in range(start, end + 1)]
        self._note("read", path=rel, start=start, end=end)
        return {"repo": self.name, "ref": self.ref, "file": rel, "start": start, "end": end, "lines_total": len(lines),
                "text": "\n".join(body), "url": self.url(rel, start, end)}


class CodeTool:
    """Clones live under scratch_root/<run>/; close() (or the run's end) deletes them."""

    def __init__(self, scratch_root: str | Path, run_id: str = "run", log_path: str | Path | None = None,
                 pins: dict[str, str] | None = None, known_repos: list[str] | None = None):
        self.base = Path(scratch_root) / re.sub(r"[^\w.-]", "_", run_id)
        self.repos: dict[tuple[str, str], Repo] = {}
        self.log_path = Path(log_path) if log_path else None
        self.api = GitHubAPI(self.base / "api-cache", self._log)
        self._lock = threading.Lock()
        self.pins = {k.lower(): v for k, v in (pins or {}).items()}   # project -> version (as the text writes it)
        self.pin_tags: dict[str, str | None] = {}                     # owner/name (lower) -> the tag that exists
        self.known_repos = list(dict.fromkeys(known_repos or []))     # owner/name the task or profile links
        self.histories: dict[tuple[str, str], Path] = {}

    def _log(self, rec: dict):
        if self.log_path:
            try:
                with open(self.log_path, "a") as f:
                    f.write(json.dumps(dict(t=round(time.time(), 1), **rec)) + "\n")
            except OSError:
                pass

    def _git_env(self) -> dict:
        home = self.base / "home"
        home.mkdir(parents=True, exist_ok=True)
        return {"PATH": "/usr/bin:/bin", "HOME": str(home), "XDG_CONFIG_HOME": str(home), "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "/bin/false",
                "SSH_ASKPASS": "/bin/false", "GIT_LFS_SKIP_SMUDGE": "1", "LC_ALL": "C.UTF-8"}

    GIT_SAFE = ["-c", "credential.helper=", "-c", "core.hooksPath=/dev/null", "-c", "core.symlinks=false",
                "-c", "core.fsmonitor=false", "-c", "protocol.allow=never", "-c", "protocol.https.allow=always",
                "-c", "submodule.recurse=false", "-c", "http.followRedirects=false"]

    def _git_out(self, args: list[str], timeout: float = 60) -> str:
        """A git command that only talks to GitHub (ls-remote): its output, or a CodeToolError."""
        try:
            p = subprocess.run(["git", *self.GIT_SAFE, *args], capture_output=True, timeout=timeout, env=self._git_env(),
                               cwd=self.base if self.base.exists() else None)
        except subprocess.TimeoutExpired:
            raise CodeToolError(f"git {args[0]} took over {int(timeout)} s")
        if p.returncode != 0:
            err = p.stderr.decode("utf-8", "replace").strip()
            raise CodeToolError(f"git {args[0]} failed: {err.splitlines()[-1] if err else p.returncode}")
        return p.stdout.decode("utf-8", "replace")

    def default_branch(self, name: str) -> str:
        """The repo's default branch from `git ls-remote --symref` (no API call)."""
        self.base.mkdir(parents=True, exist_ok=True)
        out = self._git_out(["ls-remote", "--symref", f"https://github.com/{name}.git", "HEAD"])
        m = re.search(r"^ref: refs/heads/(\S+)\s+HEAD", out, re.M)
        return m.group(1) if m else "main"

    def pinned_tag(self, name: str) -> str | None:
        """The user's version of this repo as an existing tag (v-prefixed or not), or None when it is not pinned."""
        key = name.lower()
        if key in self.pin_tags:
            return self.pin_tags[key]
        ver = self.pins.get(key.split("/")[1]) or self.pins.get(key)
        tag = None
        if ver:
            cands = list(dict.fromkeys([ver, ver if ver.startswith("v") else "v" + ver, ver.lstrip("v")]))
            try:
                self.base.mkdir(parents=True, exist_ok=True)
                out = self._git_out(["ls-remote", "--tags", f"https://github.com/{name}.git",
                                     *[f"refs/tags/{c}" for c in cands]])
                have = {ln.split("refs/tags/")[-1] for ln in out.splitlines() if "refs/tags/" in ln}
                tag = next((c for c in cands if c in have), None)
            except CodeToolError:
                tag = None
            self._log(dict(tool="pin", repo=name, version=ver, tag=tag))
        self.pin_tags[key] = tag
        return tag

    def _git(self, args: list[str], cwd: Path, dest: Path):
        """git with the safe settings; the clone folder's size is watched while it runs (over the cap: killed)."""
        p = subprocess.Popen(["git", *self.GIT_SAFE, *args], cwd=cwd, env=self._git_env(), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, start_new_session=True)
        t0 = time.time()
        while p.poll() is None:
            time.sleep(1)
            over = dest.exists() and _dir_mb(dest) > MAX_MB
            if over or time.time() - t0 > CLONE_TIMEOUT_S:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
                shutil.rmtree(dest, ignore_errors=True)
                raise CodeToolError(f"clone stopped: {'over the ' + str(int(MAX_MB)) + ' MB cap' if over else 'took over ' + str(int(CLONE_TIMEOUT_S)) + ' s'}")
        err = p.stderr.read().decode("utf-8", "replace")
        if p.returncode != 0:
            raise CodeToolError(f"git {args[0]} failed: {err.strip().splitlines()[-1] if err.strip() else p.returncode}")

    def open(self, spec: str, ref: str | None = None) -> Repo:
        """The repo at `ref` (a tag, branch or commit; default: the repo's default branch), cloned once per run."""
        with self._lock:
            return self._open(spec, ref)

    def _open(self, spec: str, ref: str | None) -> Repo:
        name, ref2 = parse_repo(spec)
        ref = ref or ref2
        if ref is not None and not REF_RE.match(ref):
            raise CodeToolError(f"not a usable tag / branch / commit: {ref!r}")
        pinned = self.pinned_tag(name)
        if ref is None:
            ref = pinned or self.default_branch(name)
        key = (name.lower(), ref)
        if key in self.repos:
            return self.repos[key]
        safe_ref = re.sub(r"[^\w.-]", "_", ref)
        dest = self.base / "repos" / f"{name.replace('/', '__')}@{safe_ref}"
        shutil.rmtree(dest, ignore_errors=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://github.com/{name}.git"
        t0 = time.time()
        if SHA_RE.match(ref) and len(ref) == 40:
            dest.mkdir()
            self._git(["init", "-q"], dest, dest)
            self._git(["fetch", "-q", "--depth", "1", "--no-tags", "--no-recurse-submodules", url, ref], dest, dest)
            self._git(["checkout", "-q", "FETCH_HEAD"], dest, dest)
        else:
            self._git(["clone", "-q", "--depth", "1", "--single-branch", "--no-tags", "--no-recurse-submodules",
                       "--branch", ref, url, str(dest)], dest.parent, dest)
        mb = _dir_mb(dest)
        if mb > MAX_MB:
            shutil.rmtree(dest, ignore_errors=True)
            raise CodeToolError(f"the clone is {mb:.0f} MB, over the {int(MAX_MB)} MB cap")
        repo = Repo(name, ref, dest.resolve(), self._log, user_ref=pinned)
        self.repos[key] = repo
        self._log(dict(tool="clone", repo=name, ref=ref, mb=round(mb, 1), s=round(time.time() - t0, 1)))
        return repo

    def history(self, name: str, ref: str | None, path: str | None, limit: int = 20) -> dict:
        """Commit messages on `ref` (optionally touching `path`) from a blob-less shallow clone - git, not the API."""
        with self._lock:
            ref = ref or self.pinned_tag(name) or self.default_branch(name)
            key = (name.lower(), ref)
            dest = self.histories.get(key)
            if dest is None:
                dest = self.base / "history" / f"{name.replace('/', '__')}@{re.sub(r'[^\w.-]', '_', ref)}"
                shutil.rmtree(dest, ignore_errors=True)
                dest.parent.mkdir(parents=True, exist_ok=True)
                t0 = time.time()
                self._git(["clone", "-q", "--bare", "--filter=blob:none", f"--depth={HISTORY_DEPTH}", "--single-branch",
                           "--no-tags", "--branch", ref, f"https://github.com/{name}.git", str(dest)], dest.parent, dest)
                self.histories[key] = dest
                self._log(dict(tool="history", repo=name, ref=ref, mb=round(_dir_mb(dest), 1), s=round(time.time() - t0, 1)))
        args = ["-C", str(dest), "log", f"-n{int(limit)}", "--format=%H%x09%cs%x09%s", "HEAD"]
        if path:
            args += ["--", path.strip().lstrip("/")]
        out = self._git_out(args)
        commits = []
        for ln in out.splitlines():
            sha, date, msg = (ln.split("\t", 2) + ["", ""])[:3]
            commits.append({"sha": sha[:10], "date": date, "message": msg[:200],
                            "url": f"https://github.com/{name}/commit/{sha}"})
        self._log(dict(tool="commits", repo=name, ref=ref, path=path, n=len(commits)))
        return {"repo": name, "ref": ref, "path": path, "commits": commits, "depth": HISTORY_DEPTH}

    def pinned_repos(self) -> list[Repo]:
        """The clones at the user's version (for the version check): every pinned project the research opened or the
        task / profile links, opened now if needed."""
        names = {r.name for r in self.repos.values()} | set(self.known_repos)
        out = []
        for name in sorted(names, key=str.lower):
            tag = self.pinned_tag(name)
            if tag:
                try:
                    out.append(self.open(f"{name}@{tag}"))
                except CodeToolError:
                    continue
        return out

    def pin_labels(self) -> dict[str, str]:
        res = {name: tag for name, tag in ((n, self.pin_tags.get(n.lower())) for n in
                                           {r.name for r in self.repos.values()} | set(self.known_repos)) if tag}
        return res or dict(self.pins)

    def close(self):
        """Delete every clone and the API cache of this run."""
        shutil.rmtree(self.base, ignore_errors=True)
        self.repos.clear()

    @staticmethod
    def sweep(scratch_root: str | Path, max_age_h: float = 12):
        """Delete run folders left behind (a crashed run) older than max_age_h."""
        root = Path(scratch_root)
        if not root.is_dir():
            return
        for d in root.iterdir():
            try:
                if d.is_dir() and time.time() - d.stat().st_mtime > max_age_h * 3600:
                    shutil.rmtree(d, ignore_errors=True)
            except OSError:
                pass


class GitHubAPI:
    """Issues, PRs and commit messages of public repos through api.github.com - unauthenticated (60 calls an hour, the
    search endpoint 10 a minute), answers cached for the run."""

    ROOT = "https://api.github.com"

    def __init__(self, cache_dir: Path, log=None):
        self.cache_dir, self._log = cache_dir, log
        self.remaining = None                     # kept for old callers: the core limit's remaining calls
        self.limits: dict[str, dict] = {}         # resource ("core", "search") -> {"remaining", "reset"}
        self.used = {"core": 0, "search": 0}      # calls this run (cached answers not counted)

    def _get(self, path: str, params: dict | None = None):
        url = self.ROOT + path + ("?" + urllib.parse.urlencode(params) if params else "")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cf = self.cache_dir / (re.sub(r"[^\w.-]", "_", path + "_" + json.dumps(params or {}, sort_keys=True))[:180] + ".json")
        if cf.exists():
            return json.loads(cf.read_text())
        res = "search" if path.startswith("/search/") else "core"
        lim = self.limits.get(res, {})
        if res == "core":
            if self.used["core"] >= API_MAX:
                raise CodeToolError(f"this research's {API_MAX} GitHub API calls are used up - use code_search / code_read")
            if lim.get("remaining") is not None and lim["remaining"] <= API_RESERVE:
                wait = max(0, int(lim.get("reset", 0) - time.time()))
                raise CodeToolError(f"the GitHub API's hourly limit is nearly used up (it resets in {wait // 60} min) - "
                                    "use code_search / code_read")
        else:
            if self.used["search"] >= SEARCH_MAX:
                raise CodeToolError(f"this research's {SEARCH_MAX} issue searches are used up - open known issues by "
                                    "number, or use code_search")
            if lim.get("remaining") is not None and lim["remaining"] <= 1:
                wait = lim.get("reset", 0) - time.time()
                if 0 < wait <= 65:                 # the search limit is per minute: wait for it
                    time.sleep(wait + 1)
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "ldr-code-tool",
                                                   "X-GitHub-Api-Version": "2022-11-28"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # no proxy, no auth handler
        t0 = time.time()
        self.used[res] += 1
        try:
            with opener.open(req, timeout=30) as r:
                self._limits(r.headers, res)
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            self._limits(e.headers, res)
            if e.code in (403, 429):
                self.limits.setdefault(res, {})["remaining"] = 0
                if res == "core":
                    self.remaining = 0
                raise CodeToolError("GitHub's rate limit for calls without a key was hit - use code_search / code_read")
            if e.code == 404:
                raise CodeToolError(f"not found on GitHub: {path}")
            raise CodeToolError(f"GitHub API error {e.code} for {path}")
        except (urllib.error.URLError, TimeoutError) as e:
            raise CodeToolError(f"GitHub API unreachable: {e}")
        cf.write_text(json.dumps(data))
        if self._log:
            self._log(dict(tool="api", path=path, params=params, s=round(time.time() - t0, 2), resource=res,
                           remaining=self.limits.get(res, {}).get("remaining"), used=self.used[res]))
        return data

    def _limits(self, headers, res: str) -> None:
        if headers is None:
            return
        r = headers.get("X-RateLimit-Resource") or res
        try:
            d = {"remaining": int(headers.get("X-RateLimit-Remaining")), "reset": int(headers.get("X-RateLimit-Reset"))}
        except (TypeError, ValueError):
            return
        self.limits[r] = d
        if r == "core":
            self.remaining = d["remaining"]

    def repo_size_kb(self, name: str) -> int | None:
        try:
            return int(self._get(f"/repos/{name}").get("size") or 0)
        except CodeToolError:
            return None

    def default_branch(self, name: str) -> str:
        return self._get(f"/repos/{name}").get("default_branch") or "main"

    def search(self, name: str, terms: str, kind: str = "any", limit: int = 10) -> dict:
        """Issues and/or PRs of the repo matching `terms` (GitHub search syntax inside the repo)."""
        q = f"repo:{name} {terms}" + {"issue": " type:issue", "pr": " type:pr"}.get(kind, "")
        d = self._get("/search/issues", {"q": q, "per_page": min(limit, 30)})
        items = [{"number": i["number"], "kind": "pr" if i.get("pull_request") else "issue", "title": i["title"],
                  "state": i["state"], "created": i["created_at"][:10], "url": i["html_url"],
                  "body": (i.get("body") or "")[:600]} for i in d.get("items", [])[:limit]]
        return {"repo": name, "terms": terms, "total": d.get("total_count", 0), "items": items}

    def issue(self, name: str, number: int, comments: int = 8) -> dict:
        """One issue or PR: its text and its first comments (each cut at 1,500 characters)."""
        i = self._get(f"/repos/{name}/issues/{int(number)}")
        cs = self._get(f"/repos/{name}/issues/{int(number)}/comments", {"per_page": min(comments, 30)}) if i.get("comments") else []
        return {"repo": name, "number": i["number"], "kind": "pr" if i.get("pull_request") else "issue",
                "title": i["title"], "state": i["state"], "created": i["created_at"][:10], "url": i["html_url"],
                "body": (i.get("body") or "")[:3000],
                "comments": [{"by_maintainer": c.get("author_association") in ("OWNER", "MEMBER", "COLLABORATOR"),
                              "date": c["created_at"][:10], "text": (c.get("body") or "")[:1500]} for c in cs[:comments]]}

    def commits(self, name: str, ref: str | None = None, path: str | None = None, limit: int = 20) -> dict:
        """Recent commit messages (first line, date, short sha) on `ref`, optionally only those touching `path`."""
        params = {"per_page": min(limit, 50)}
        if ref:
            params["sha"] = ref
        if path:
            params["path"] = path
        d = self._get(f"/repos/{name}/commits", params)
        return {"repo": name, "ref": ref, "path": path,
                "commits": [{"sha": c["sha"][:10], "date": c["commit"]["committer"]["date"][:10],
                             "message": c["commit"]["message"].split("\n")[0][:200],
                             "url": c["html_url"]} for c in d[:limit]]}


# ---------------------------------------------------------------------------------------------- the agents' tools

def enabled() -> bool:
    return os.environ.get("LDR_DEEP_CODE", "").strip().lower() in ("1", "true", "yes", "on")


def scratch_root() -> Path:
    return Path(os.environ.get("LDR_DEEP_CODE_DIR") or Path(tempfile.gettempdir()) / "code-tool")


LEAD_ADDENDUM = (
    "\n\nCODE TOOL (the project's own source): when the question is about a specific open-source project - its flags, "
    "environment variables, defaults, code paths, or what works on which hardware - check it in the project's source on "
    "GitHub AT THE VERSION THE USER RUNS: code_search (grep; repo as owner/name@tag) to find where a flag, variable or "
    "function is handled, then code_read the lines around the hit and cite them. The source at that version is the "
    "strongest evidence for what the program does; blogs, docs and issues may describe other versions or other engines "
    "of the same project. code_tree shows the layout; github_issues and github_commits give the project's issues, PRs "
    "and commit messages. Search first and read short ranges - never whole files. Subagents have these tools too.")


def lead_addendum(collector: Any) -> str:
    """LEAD_ADDENDUM plus the user's versions the code tool is pinned to."""
    ct = getattr(collector, "deep_code", None)
    if ct is None or not ct.pins:
        return LEAD_ADDENDUM
    known = ", ".join(ct.known_repos)
    linked = {r.split("/")[1].lower() for r in ct.known_repos}
    shown = {k: v for k, v in ct.pins.items() if k in linked or v.startswith("v")} or ct.pins
    pins = ", ".join(f"{k} {v}" for k, v in shown.items())
    return (LEAD_ADDENDUM + f" The user's versions, from the task / setup: {pins}"
            + (f" (repos: {known})" if known else "") + ". The code tool opens a project at that version when you give "
            "no @tag; code from another version is marked OTHER VERSION and is not evidence for the user's version - "
            "say so if you use it.")


def _fmt_err(e: Exception) -> str:
    return f"CODE TOOL: {e}" if isinstance(e, CodeToolError) else f"CODE TOOL: failed ({type(e).__name__}: {e})"


def _enginescope():
    """deep/enginescope.py (10-29 engine-scope labels): inside LDR's package, else from its file next to this one (this
    file is also loaded on its own by tools/code-mcp.py); None when it cannot be loaded."""
    try:
        from . import enginescope as es
        return es
    except ImportError:
        import importlib.util
        import sys
        es = sys.modules.get("deep_enginescope")
        if es is None:
            try:
                spec = importlib.util.spec_from_file_location("deep_enginescope",
                                                              Path(__file__).with_name("enginescope.py"))
                es = importlib.util.module_from_spec(spec)
                sys.modules["deep_enginescope"] = es        # (dataclasses need the module registered)
                spec.loader.exec_module(es)
            except (OSError, ImportError, AttributeError):
                sys.modules.pop("deep_enginescope", None)
                return None
        return es


def _file_text(r: Repo, rel: str) -> str | None:
    """A file of a clone as text (the engine-scope labels place a doc by all of it), or None."""
    try:
        p = r._path(rel)
        if not p.is_file() or p.stat().st_size > TEXT_MAX_BYTES:
            return None
        return p.read_text(encoding="utf-8", errors="replace")
    except (OSError, CodeToolError):
        return None


def make_tools(collector: Any, rid: str, log_dir: str | Path | None = None, task: str = "",
               profile: str = "") -> list:
    """The code tools for one research; the clones are deleted by close(collector) when it ends. `task` and `profile`
    (the setup facts) give the user's versions (derive_pins) and the repos they link."""
    from langchain_core.tools import tool
    from loguru import logger

    from ..advanced_search_system.tools.fetch import _register_in_collector

    CodeTool.sweep(scratch_root())
    pins = derive_pins(task, profile)
    known = [m.group(1).removesuffix(".git") for m in GH_URL_RE.finditer((task or "") + "\n" + (profile or ""))
             if m.group(1).split("/")[1].lower().removesuffix(".git") in pins]
    ct = CodeTool(scratch_root(), rid, log_path=(Path(log_dir) / "code-tool.jsonl") if log_dir else None,
                  pins=pins, known_repos=known)
    collector.deep_code = ct
    store = getattr(collector, "deep_store", None)
    if store is not None:
        store.code_tool, store.pins = ct, pins
    ct._log(dict(tool="pins", pins=pins, known=known))

    def cite(url: str, title: str, text: str, focus: str) -> int:
        idx = _register_in_collector(collector, url, title, text[:400])
        store = getattr(collector, "deep_store", None)
        if store is not None:
            store.add_fetch(idx, url, title, focus, text, text)
        return idx

    # 10-29 engine-scope labels (LDR_DEEP_FIX version): a file or doc part of another engine of the task's project
    es = _enginescope()
    verdicts: dict = {}

    def engine_of(r: Repo, rel: str):
        """The engine verdict of one file of a clone (by its path; a doc by all of its text), cached for the run."""
        store = getattr(collector, "deep_store", None)
        if es is None or not es.scopes_of(store):
            return None
        key = (str(r.root), rel)
        if key not in verdicts:
            folder = es.content_dir(None, rel)
            readme = _file_text(r, folder + "README.md") if folder and rel != folder + "README.md" else None
            if readme is not None:             # a config / script / note of a bench run: placed by the run's README
                v = es.classify(r.url(rel), "", readme, es.scopes_of(store), whole=readme, pins=es.pins_of(store))
                verdicts[key] = v if v is not None and v.engine else None
            else:
                whole = _file_text(r, rel) if es._is_doc(rel) or folder else None
                verdicts[key] = es.classify(r.url(rel), "", whole or "", es.scopes_of(store), whole=whole,
                                            pins=es.pins_of(store))
        return verdicts[key]

    def hit_lines(r: Repo, hits: list[dict]) -> tuple[list[str], str]:
        """The search hits as 'file:line: text' - a hit in another engine's file or doc part with [OTHER ENGINE ...] -
        and the legend line ('' when no hit is marked)."""
        out, first, n = [], None, 0
        for h in hits:
            try:
                v = engine_of(r, h["file"])
            except Exception:  # noqa: BLE001 - a label never breaks the search
                v = None
            tag = es.short(v) if v is not None and (v.engine or v.part_at(h["line"])) else ""
            if tag:
                first, n = first or v, n + 1
            out.append(f"{h['file']}:{h['line']}: {tag + ' ' if tag else ''}{h['text']}")
        if first is None:
            return out, ""
        proj, other, own = es._names(first)
        return out, (f"\n({n} hit(s) marked [OTHER ENGINE: {proj}'s {other}] are in that engine's files or doc parts; "
                     f"the task is about its {own} - not evidence for the {own}'s flags or settings.)")

    @tool(description=(
        "Search the source code of a public GitHub project at a given version (grep, extended regex). `repo` is "
        "owner/name@tag, e.g. 'Niko1221/Strata@v0.2.4' - use the version the user runs (without @tag: the user's "
        "version when the task names one, else the default branch; another version is marked OTHER VERSION). `pattern` e.g. 'lm_begin|yoco_layer', 'layer-split', 'getenv\\(\"DS4_'. Optional `path` (a folder or "
        "file inside the repo) and `file_glob` (e.g. '*.cu', '*.py'). Returns up to 40 file:line hits and the total. "
        "Hits only point the way: read around a hit with code_read before relying on it or citing it."))
    def code_search(repo: str, pattern: str, path: str = "", file_glob: str = "", ignore_case: bool = False) -> str:
        """Description passed via ``@tool(description=...)`` above."""
        try:
            r = ct.open(repo)
            g = r.grep(pattern, path or ".", glob=file_glob or None, ignore_case=bool(ignore_case))
        except Exception as e:  # noqa: BLE001
            return _fmt_err(e)
        if not g["total"]:
            return f"No hits for /{pattern}/ in {r.label}{' under ' + path if path else ''}."
        lines, legend = hit_lines(r, g["hits"])
        more = f"\n({g['more']} more hits - narrow with path or file_glob, or a more specific pattern.)" if g["more"] else ""
        return f"{g['total']} hit(s) for /{pattern}/ in {r.label}:\n" + "\n".join(lines) + more + legend

    @tool(description=(
        "Read lines of one file of a GitHub project at a given version (at most 120 lines; numbered). `repo` as in "
        "code_search (owner/name@tag), `file` the path inside the repo as code_search shows it, `start_line` / "
        "`end_line` the range (read around a search hit, e.g. 30 lines before to 60 after). Returns a citable source "
        "[N] with the GitHub link to these lines; cite the code by that [N]. `focus`: what you are checking."))
    def code_read(repo: str, file: str, start_line: int, end_line: int = 0, focus: str = "") -> str:
        """Description passed via ``@tool(description=...)`` above."""
        try:
            r = ct.open(repo)
            d = r.read(file, int(start_line or 1), int(end_line) if end_line else None)
        except Exception as e:  # noqa: BLE001
            return _fmt_err(e)
        title = f"{r.name}@{r.ref}: {d['file']} lines {d['start']}-{d['end']} (source code)"
        if r.user_ref and r.user_ref != r.ref:
            title += f" - OTHER VERSION: the user runs {r.user_ref}; not evidence for that version"
        idx = cite(d["url"], title, d["text"], focus or file)
        logger.info(f"deep: code_read {r.name}@{r.ref} {d['file']}:{d['start']}-{d['end']} -> [{idx}]")
        rest = f"\n({d['file']} has {d['lines_total']} lines.)" if d["end"] < d["lines_total"] or d["start"] > 1 else ""
        text, label = d["text"], ""
        try:                                   # 10-29: another engine's file or doc part (the evidence keeps the text)
            v = engine_of(r, d["file"])
            n = es.note(v, (d["start"], d["end"])) if v is not None else ""
            if n:
                label, text = f"[{n}]\n", es.mark_lines(text, v)
        except Exception:  # noqa: BLE001 - a label never breaks the read
            pass
        return f"[{idx}] Title: {title}\nURL: {d['url']}\n{label}\n{text}{rest}"

    @tool(description=(
        "The layout of a GitHub project at a given version: the folders and files under `path` (default the top), "
        "`depth` levels deep (1-4). With `name_glob` (e.g. 'ds4_*.cpp', '*server*.py') it instead lists the files whose "
        "name matches, anywhere under `path`. `repo` as in code_search (owner/name@tag)."))
    def code_tree(repo: str, path: str = "", depth: int = 2, name_glob: str = "") -> str:
        """Description passed via ``@tool(description=...)`` above."""
        try:
            r = ct.open(repo)
            if name_glob:
                f = r.files(name_glob, path or ".")
                return (f"{f['total']} file(s) named {name_glob} in {r.name}@{r.ref}:\n" + "\n".join(f["files"])
                        + ("\n(more not shown)" if f["total"] > len(f["files"]) else ""))
            t = r.tree(path or ".", int(depth or 2))
        except Exception as e:  # noqa: BLE001
            return _fmt_err(e)
        return (f"{r.name}@{r.ref} {t['path']}:\n" + "\n".join(t["entries"])
                + ("\n(cut at 200 entries - give a deeper path)" if t["cut"] else ""))

    @tool(description=(
        "A GitHub project's issues and pull requests (public, no login). With `query` (GitHub search words, e.g. "
        "'layer split prompt skip') it lists matching issues / PRs (number, title, state, date, first lines); with "
        "`number` it opens one - its text and first comments, marked when a maintainer wrote them - as a citable source "
        "[N]. `kind`: 'any', 'issue' or 'pr'. `repo` is owner/name (a @tag is ignored here). The API allows about 60 "
        "calls an hour without a key: prefer code_search for what the code does."))
    def github_issues(repo: str, query: str = "", number: int = 0, kind: str = "any") -> str:
        """Description passed via ``@tool(description=...)`` above."""
        try:
            name, _ref = parse_repo(repo)
            if number:
                i = ct.api.issue(name, int(number))
                text = (f"{i['kind'].upper()} #{i['number']} ({i['state']}, {i['created']}): {i['title']}\n\n{i['body']}"
                        + "".join(f"\n\n--- comment ({'maintainer, ' if c['by_maintainer'] else ''}{c['date']}):\n{c['text']}"
                                  for c in i["comments"]))
                title = f"{name} {i['kind']} #{i['number']}: {i['title']}"
                idx = cite(i["url"], title, text, query or title)
                label = ""
                try:                           # 10-29: an issue / PR about another engine of the task's project
                    v = es.for_source(getattr(collector, "deep_store", None), i["url"], title, text) if es else None
                    label = f"[{es.note(v)}]\n" if v is not None and es.note(v) else ""
                except Exception:  # noqa: BLE001
                    label = ""
                return f"[{idx}] Title: {title}\nURL: {i['url']}\n{label}\n{text}"
            if not query:
                return "CODE TOOL: give `query` (search words) or `number` (one issue / PR)."
            s = ct.api.search(name, query, kind=kind if kind in ("issue", "pr") else "any")
        except Exception as e:  # noqa: BLE001
            return _fmt_err(e)
        if not s["items"]:
            return f"No issues / PRs in {name} match {query!r}."
        rows = [f"#{i['number']} [{i['kind']}, {i['state']}, {i['created']}] {i['title']}\n    {i['body'][:200].strip()}"
                for i in s["items"]]
        return (f"{s['total']} issue(s) / PR(s) in {name} match {query!r} (top {len(rows)}; open one with number=...):\n"
                + "\n".join(rows))

    @tool(description=(
        "Commit messages of a GitHub project (newest first): on `ref` (a tag or branch; default the @tag in `repo`, "
        "else the user's version when the task names one, else the default branch), optionally only commits that "
        "touched `path` (a file or folder). Shows what changed when - e.g. whether a flag or fix exists at the user's "
        "version. Returns a citable source [N]."))
    def github_commits(repo: str, path: str = "", ref: str = "") -> str:
        """Description passed via ``@tool(description=...)`` above."""
        try:
            name, ref2 = parse_repo(repo)
            if (ref or ref2) and SHA_RE.match(ref or ref2) and len(ref or ref2) == 40:
                c = ct.api.commits(name, ref or ref2, path or None)       # a commit id: only the API takes it
            else:
                c = ct.history(name, ref or ref2, path or None)          # git log on a blob-less shallow clone
        except Exception as e:  # noqa: BLE001
            return _fmt_err(e)
        if not c["commits"]:
            return f"No commits found in {name}@{c.get('ref')}{' for ' + path if path else ''}."
        text = "\n".join(f"{x['date']} {x['sha']} {x['message']}" for x in c["commits"])
        where = f"{c.get('ref') or 'default branch'}{'/' + path if path else ''}"
        url = f"https://github.com/{name}/commits/{c.get('ref') or 'HEAD'}" + (f"/{path}" if path else "")
        title = f"{name} commits on {where}"
        pinned = ct.pinned_tag(name)
        if pinned and c.get("ref") and c["ref"] != pinned:
            title += f" - OTHER VERSION: the user runs {pinned}"
        idx = cite(url, title, text, title)
        return f"[{idx}] Title: {title}\nURL: {url}\n\n{text}"

    return [code_search, code_read, code_tree, github_issues, github_commits]


def close(collector: Any) -> None:
    """Delete this research's clones (and its API cache)."""
    ct = getattr(collector, "deep_code", None)
    if ct is not None:
        ct.close()
        collector.deep_code = None
