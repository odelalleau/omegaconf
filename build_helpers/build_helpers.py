import codecs
import distutils.log
import errno
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from setuptools import Command
from setuptools.command import build_py, develop, sdist  # type: ignore

# The code below is heavily inspired (=~copied) from Hydra.


class ANTLRCommand(Command):  # type: ignore
    """Generate parsers using ANTLR."""

    description = "Run ANTLR"
    user_options: List[str] = []

    def run(self) -> None:
        """Run command."""
        build_dir = Path(__file__).parent.absolute()
        project_root = build_dir.parent
        for grammar in [
            Path("omegaconf") / "grammar" / "Interpolation.g4",
        ]:
            command = [
                "java",
                "-jar",
                str(build_dir / "bin" / "antlr-4.8-complete.jar"),
                "-Dlanguage=Python3",
                "-o",
                str(project_root / "omegaconf" / "grammar" / "gen"),
                "-Xexact-output-dir",
                "-visitor",
                str(project_root / grammar),
            ]

            self.announce(
                f"Generating parser for Python3: {command}", level=distutils.log.INFO,
            )

            subprocess.check_call(command)

    def initialize_options(self) -> None:
        pass

    def finalize_options(self) -> None:
        pass


class BuildPyCommand(build_py.build_py):  # type: ignore
    def run(self) -> None:
        if not self.dry_run:
            self.run_command("clean")
            run_antlr(self)
        build_py.build_py.run(self)


class CleanCommand(Command):  # type: ignore
    """
    Our custom command to clean out junk files.
    """

    description = "Cleans out generated and junk files we don't want in the repo"
    dry_run: bool
    user_options: List[str] = []

    def run(self) -> None:
        root = Path(__file__).parent.parent.absolute()
        files = find(
            root=root,
            include_files=["^omegaconf/grammar/gen/.*"],
            include_dirs=[
                "^omegaconf\\.egg-info$",
                "\\.eggs$",
                "^\\.mypy_cache$",
                "^\\.nox$",
                "^\\.pytest_cache$",
                ".*/__pycache__$",
                "^__pycache__$",
                "^build$",
                "^dist$",
            ],
            scan_exclude=["^.git$", "^.nox/.*$"],
            excludes=[".*\\.gitignore$", ".*/__init__.py"],
        )

        if self.dry_run:
            print("Dry run! Would clean up the following files and dirs:")
            print("\n".join(sorted(map(str, files))))
        else:
            for f in files:
                if f.exists():
                    if f.is_dir():
                        shutil.rmtree(f, ignore_errors=True)
                    else:
                        f.unlink()

    def initialize_options(self) -> None:
        pass

    def finalize_options(self) -> None:
        pass


class DevelopCommand(develop.develop):  # type: ignore
    def run(self) -> None:
        if not self.dry_run:
            run_antlr(self)
        develop.develop.run(self)


class SDistCommand(sdist.sdist):  # type: ignore
    def run(self) -> None:
        if not self.dry_run:
            self.run_command("clean")
            run_antlr(self)
        sdist.sdist.run(self)


def find(
    root: Path,
    include_files: List[str],
    include_dirs: List[str],
    excludes: List[str],
    rbase: Optional[Path] = None,
    scan_exclude: Optional[List[str]] = None,
) -> List[Path]:
    if rbase is None:
        rbase = Path()
    if scan_exclude is None:
        scan_exclude = []
    files = []
    scan_root = root / rbase
    for path in scan_root.iterdir():
        path = rbase / path.name
        if matches(scan_exclude, path):
            continue

        if path.is_dir():
            if matches(include_dirs, path):
                if not matches(excludes, path):
                    files.append(path)
            else:
                ret = find(
                    root=root,
                    include_files=include_files,
                    include_dirs=include_dirs,
                    excludes=excludes,
                    rbase=path,
                    scan_exclude=scan_exclude,
                )
                files.extend(ret)
        else:
            if matches(include_files, path) and not matches(excludes, path):
                files.append(path)

    return files


def find_version(*file_paths: List[str]) -> str:
    root = Path(__file__).parent.parent.absolute()
    with codecs.open(root / Path(*file_paths), "r") as fp:  # type: ignore
        version_file = fp.read()
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


def matches(patterns: List[str], path: Path) -> bool:
    string = str(path).replace("\\", "/")
    for pattern in patterns:
        if re.match(pattern, string):
            return True
    return False


def run_antlr(cmd: Command) -> None:
    try:
        cmd.announce("Generating parsers with antlr4", level=distutils.log.INFO)
        cmd.run_command("antlr")
    except OSError as e:
        if e.errno == errno.ENOENT:
            msg = f"| Unable to generate parsers: {e} |"
            msg = "=" * len(msg) + "\n" + msg + "\n" + "=" * len(msg)
            cmd.announce(f"{msg}", level=distutils.log.FATAL)
            sys.exit(1)
        else:
            raise
