# Personal PKGBUILD Repository

This repository is a collection of PKGBUILDs that I maintain for my personal use.

I use [`paru`](https://github.com/Morganamilo/paru) as my AUR helper.
Add the following to `paru.conf` to access this PKGBUILD repository.
```ini
# Custom PKGBUILD Repositories
# (see paru.conf(5) - PKGBUILD REPOSITORY SECTION)

[AUR-jdujava]
Url = https://github.com/jdujava/AUR-jdujava
# Alternatively use a path to a local clone
# Path = /path/to/repository/AUR-jdujava
```

## Desktop packages

`base-jdujava` is the maintained package selection. The custom packages use
public source repositories, just like the older dwm and slstatus builds:

| Package | Source | Branch |
| --- | --- | --- |
| `mango-jd-git` | [mango-jd](https://github.com/jdujava/mango-jd) | `desktop` |
| `waybar-jd-git` | [waybar-jd](https://github.com/jdujava/waybar-jd) | `desktop` |
| `fmenu-git` | [fmenu](https://github.com/jdujava/fmenu) | `master` |

With this repository configured in Paru:

```sh
paru -S --needed mango-jd-git waybar-jd-git fmenu-git base-jdujava
```

Packages install under `/usr`; call `mango` and `waybar` by name.
For development, use each source repository's native Meson or Make commands to
install under `/usr/local`. With `/usr/local/bin` before `/usr/bin` in `PATH`,
development binaries override the packages without changing launch commands.
Remove the development binary to return to the packaged version; existing Zsh
shells may need `rehash`. Builds and installs do not restart the running desktop.

## Maintenance

Publish source changes before publishing the corresponding PKGBUILDs.
Mango, Waybar and Fmenu use complete Git history for their revision counts;
package versions do not depend on which tags a clone happens to contain.
After a deliberate history rewrite, check upgrade ordering with `vercmp`.

After editing a recipe, regenerate metadata in that package directory:

```sh
makepkg --printsrcinfo > .SRCINFO
```

Run the repository's metadata and version regression tests with:

```sh
python3 -B -m unittest discover -s tests
```

Build individual packages with `makepkg`; install normally through Paru.
No local source imports, dotfiles build wrappers or metadata-refresh scripts
are required.

## Migration

Install the package selection through Paru and deploy dotfiles separately.
Clone source repositories only when developing them; there is no need to copy
build directories or keep a source-backup/export workflow in this repository.
Git restores committed and pushed source, not uncommitted edits; keep those in
your normal file backups.
