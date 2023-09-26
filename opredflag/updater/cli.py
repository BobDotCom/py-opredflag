"""
Py-opredflag
Copyright (C) 2023  BobDotCom

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import argparse

from .core import update_assets
from .enums import Compatibility

__all__ = ("updater_parser",)


# @dataclass
# class UpdaterArgs:
#     """"""
#     # pylint: disable=too-many-instance-attributes
#     directory: str
#     repository: str
#     branch: str
#     version_json: str
#     include: str
#     exclude: str
#     compatibility: Compatibility
#     strict: bool


def updater_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    """Add updater arguments to parser."""
    parser.add_argument(
        "-d",
        "--directory",
        help="Local root directory",
        required=False,
        default=".",
    )
    parser.add_argument(
        "-r",
        "--repository",
        help='Location of OpRedFlag asset GitHub repository, in User/Repo format. Default: "NikolaiVChr/OpRedFlag"',
        required=False,
        default="NikolaiVChr/OpRedFlag",
    )
    parser.add_argument(
        "-b",
        "--branch",
        help='The branch of the repository to use. Default: "master"',
        required=False,
        default="master",
    )
    parser.add_argument(
        "-v",
        "--version-json",
        help='Location of local versions.json file. Default: "oprf-versions.json"',
        required=False,
        default="oprf-versions.json",
    )
    parser.add_argument(
        "-i",
        "--include",
        help='Files to update, separated by commas. Default: "*"',
        required=False,
        default="*",
    )
    parser.add_argument(
        "-e",
        "--exclude",
        help='Files to skip, separated by commas. Default: ""',
        required=False,
        default="",
    )
    parser.add_argument(
        "-c",
        "--compatibility",
        help='Compatibility level, will only allow updates of this level or lower. Default "minor"',
        # action="store_true",
        required=False,
        default=Compatibility.MINOR,
        type=Compatibility,
        choices=list(Compatibility),
    )
    parser.add_argument(
        "-s",
        "--strict",
        help="Fail if local file versions are newer than remote",
        action="store_true",
    )
    parser.set_defaults(func=cli_func)
    return parser


def cli_func(args: argparse.Namespace) -> None:
    """Execute the update_assets function from the CLI."""
    update_assets(
        args.directory,
        args.version_json,
        args.repository,
        args.branch,
        args.include,
        args.exclude,
        args.compatibility,
        args.strict,
    )
