"""Offline recipe regressions; run with python3 -m unittest discover -s tests."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = {
    "mango-jd-git": ("0.18.3", "project('mango', 'c', version : '0.18.3')\n"),
    "waybar-jd-git": ("0.15.0", "project(\n  'waybar', 'cpp',\n  version: '0.15.0',\n)\n"),
    "fmenu-git": (None, None),
}
PACKAGES = (
    "base-jdujava", "dwm-jd-git", "fmenu-git", "mango-jd-git",
    "nsxiv-jd-git", "slock-jd-git", "slstatus-jd-git", "st-jd-git", "waybar-jd-git",
)
BASH = ["bash", "--noprofile", "--norc", "-c"]


@unittest.skipUnless(shutil.which("bash") and shutil.which("git"), "requires Bash and Git")
class RecipeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pkgbuild-tests-")
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("GIT_", "FZF_", "BASH_FUNC_"))
                    and k not in {"BASH_ENV", "ENV", "SHELLOPTS", "BASHOPTS", "CDPATH"}}
        self.env.update(LC_ALL="C", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                        XDG_CONFIG_HOME=str(self.tmp), GIT_TERMINAL_PROMPT="0",
                        GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
                        GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")

    def command(self, args, cwd=None, check=True):
        result = subprocess.run(args, cwd=cwd or self.tmp, env=self.env,
                                capture_output=True, text=True, timeout=20)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def git(self, cwd, *args):
        return self.command(["git", "-c", "core.hooksPath=" + os.devnull,
                             "-c", "commit.gpgSign=false", "-c", "tag.gpgSign=false",
                             *args], cwd=cwd).stdout.strip()

    def fixture(self, name):
        repo = self.tmp / name.removesuffix("-git")
        repo.mkdir()
        self.git(repo, "init", "--quiet", "--initial-branch=main", "--template=")
        self.git(repo, "config", "core.abbrev", "12")
        content = PROJECTS[name][1]
        if content:
            (repo / "meson.build").write_text(content, encoding="utf-8")
            self.git(repo, "add", "meson.build")
        for index in range(3):
            self.git(repo, "commit", "--quiet", "--allow-empty", "-m", f"fixture {index}")
        return repo

    def pkgver(self, name, srcdir=None, failed_git=""):
        script = '''source "$1" || exit
srcdir=$2
if [[ -n $3 ]]; then
    failed_git=$3
    git() { [[ $failed_git != '*' && "$*" != "$failed_git" ]] || return 73; command git "$@"; }
fi
pkgver
'''
        return self.command(BASH + [script, "bash", str(ROOT / name / "PKGBUILD"),
                                    str(srcdir or self.tmp), failed_git], check=False)

    def rejected(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, "", "failure emitted a package version")

    def test_full_count_fixed_hash_and_tag_independence(self):
        for name, (version, _) in PROJECTS.items():
            with self.subTest(package=name):
                repo = self.fixture(name)
                head = self.git(repo, "rev-parse", "HEAD")
                untagged = self.pkgver(name)
                self.assertEqual(untagged.returncode, 0, untagged.stderr)
                prefix = re.escape(version) + r"\.r3\.g" if version else r"r3\."
                self.assertRegex(untagged.stdout, rf"\A{prefix}{head[:8]}\n\Z")
                self.git(repo, "tag", "9.9.9", "HEAD~1")
                tagged = self.pkgver(name)
                self.assertEqual(tagged.returncode, 0, tagged.stderr)
                self.assertEqual(tagged.stdout, untagged.stdout)

    def test_missing_nonrepository_and_unborn_sources(self):
        for name, (_, content) in PROJECTS.items():
            with self.subTest(package=name):
                self.rejected(self.pkgver(name))
                repo = self.tmp / name.removesuffix("-git")
                repo.mkdir()
                if content:
                    (repo / "meson.build").write_text(content, encoding="utf-8")
                self.rejected(self.pkgver(name))
                self.git(repo, "init", "--quiet", "--initial-branch=main", "--template=")
                self.rejected(self.pkgver(name))

    def test_missing_and_empty_project_versions(self):
        for name in ("mango-jd-git", "waybar-jd-git"):
            repo = self.fixture(name)
            empty = PROJECTS[name][1].replace(PROJECTS[name][0], "")
            for content in (None, "project('test', 'c')\n", empty):
                with self.subTest(package=name, content=content):
                    if content is None:
                        (repo / "meson.build").unlink()
                    else:
                        (repo / "meson.build").write_text(content, encoding="utf-8")
                    self.rejected(self.pkgver(name))

    def test_git_failures_propagate(self):
        for name in PROJECTS:
            self.fixture(name)
            for failed_git in ("*", "rev-list --count HEAD", "rev-parse HEAD"):
                with self.subTest(package=name, command=failed_git):
                    self.rejected(self.pkgver(name, failed_git=failed_git))

    def test_real_shallow_clone_is_rejected(self):
        shallow_src = self.tmp / "shallow"
        shallow_src.mkdir()
        for name in PROJECTS:
            with self.subTest(package=name):
                repo = self.fixture(name)
                clone = shallow_src / repo.name
                self.git(self.tmp, "-c", "protocol.file.allow=always", "clone", "--quiet",
                         "--depth=1", "--no-tags", repo.as_uri(), str(clone))
                self.assertEqual(self.git(clone, "rev-parse", "--is-shallow-repository"), "true")
                self.assertEqual(self.git(clone, "rev-parse", "HEAD"),
                                 self.git(repo, "rev-parse", "HEAD"))
                self.assertEqual(self.git(clone, "rev-list", "--count", "HEAD"), "1")
                self.rejected(self.pkgver(name, srcdir=shallow_src))

    @unittest.skipUnless(shutil.which("vercmp"), "requires pacman vercmp")
    def test_fmenu_upgrades_previously_installed_versions(self):
        script = 'source "$1" || exit; printf "%s:%s-%s" "${epoch:-0}" "$pkgver" "$pkgrel"'
        current = self.command(BASH + [script, "bash", str(ROOT / "fmenu-git/PKGBUILD")]).stdout
        for installed in ("r21.006cb6b-1", "r20.d38f218-1"):
            with self.subTest(installed=installed):
                self.assertGreater(int(self.command(["vercmp", current, installed]).stdout), 0)

    @unittest.skipUnless(shutil.which("makepkg"), "requires makepkg")
    def test_all_srcinfo_matches_makepkg(self):
        for name in PACKAGES:
            with self.subTest(package=name):
                expected = (ROOT / name / ".SRCINFO").read_text(encoding="utf-8")
                self.assertEqual(self.command(["makepkg", "--printsrcinfo"], cwd=ROOT / name).stdout,
                                 expected)

    @unittest.skipUnless(shutil.which("vercmp"), "requires pacman vercmp")
    def test_base_wayland_upgrade_keeps_latexindent_extras(self):
        script = ('source "$1" || exit; printf "%s:%s-%s\\n" "${epoch:-0}" "$pkgver" "$pkgrel"; '
                  'printf "%s\\n" "${optdepends[@]}"')
        version, *extras = self.command(BASH + [script, "bash", str(ROOT / "base-jdujava/PKGBUILD")]).stdout.splitlines()
        self.assertGreater(int(self.command(["vercmp", version, "1-18"]).stdout), 0)
        names = {entry.split(":", 1)[0] for entry in extras}
        for name in ("texlive-binextra", "perl-file-homedir", "perl-yaml-tiny"):
            self.assertIn(name, names)


if __name__ == "__main__":
    unittest.main()
