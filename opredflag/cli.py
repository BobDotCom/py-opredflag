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

from .updater.cli import updater_parser

parser = argparse.ArgumentParser(prog="oprf", description="py-opredflag CLI")
sub = parser.add_subparsers(required=True)

parser_updater = sub.add_parser(
    "updater",
    description="A script which automatically updates OPRF standard asset files from the OpRedFlag repository",
)
updater_parser(parser_updater)


def cli() -> None:
    """Run the CLI."""
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    cli()
