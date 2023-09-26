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
import json
import os
from typing import TypedDict

import requests

from .enums import Compatibility, VersionComparison

__all__ = ("update_assets",)


class FileVersion(TypedDict):
    """An oprf version file version entry."""

    version: str | None
    path: str


def compare_versions(first: str | None, second: str | None) -> VersionComparison:
    """Compare two semantic version strings.

    Parameters
    ----------
    first:
        The first version
    second:
        The second version

    Returns
    -------
    :class:`~.VersionComparision`
        The comparison result
    """
    if first is None or second is None:
        return VersionComparison.UNKNOWN

    val1 = [int(val) for val in first.split(".")]
    val2 = [int(val) for val in second.split(".")]

    ret = None
    if val1[0] > val2[0]:
        ret = VersionComparison.NEWER_MAJOR
    elif val1[:2] > val2[:2]:
        ret = VersionComparison.NEWER_MINOR
    elif val1 > val2:
        ret = VersionComparison.NEWER_PATCH
    elif val1 == val2:
        ret = VersionComparison.EQUAL
    elif val2[0] > val1[0]:
        ret = VersionComparison.OLDER_MAJOR
    elif val2[:2] > val1[:2]:
        ret = VersionComparison.OLDER_MINOR
    elif val2 > val1:
        ret = VersionComparison.OLDER_PATCH

    if ret is None:
        raise RuntimeError("Unreachable code")

    return ret


def update_assets(
    directory: str = ".",
    version_json: str = "oprf-versions.json",
    repository: str = "NikolaiVChr/OpRedFlag",
    branch: str = "master",
    include: str = "*",
    exclude: str = "",
    compatibility: Compatibility = Compatibility.MINOR,
    strict: bool = False,
) -> None:
    """Update OPRF standard asset files from the OpRedFlag repository.

    Parameters
    ----------
    directory:
        Local root directory
    version_json:
        Location of local versions.json file
    repository:
        Location of OpRedFlag asset GitHub repository, in User/Repo format
    branch:
        The branch of the repository to use
    include:
        Files to update, separated by commas
    exclude:
        Files to skip, separated by commas
    compatibility: :class:`~.Compatibility`
        Compatibility level, will only allow updates of this level or lower
    strict:
        Fail if local file versions are newer than remote
    """
    # pylint: disable=too-many-arguments,too-many-locals
    version_json = os.path.join(directory, version_json)

    with open(version_json, encoding="utf-8") as f_obj:
        local_version_data: dict[str, FileVersion | list[FileVersion]] = json.load(
            f_obj
        )

    def build_remote_url(path: str) -> str:
        return f"https://raw.githubusercontent.com/{repository}/{branch}/{path}"

    def save_local_version_data() -> None:
        with open(version_json, "w", encoding="utf-8") as f_obj:
            json.dump(local_version_data, f_obj, indent=2)

    with requests.get(build_remote_url("versions.json"), timeout=30) as response:
        remote_version_data: dict[str, FileVersion] = response.json()

    if include == "*":
        keys_to_check = list(local_version_data.keys())
    elif include == "":
        keys_to_check = []
    else:
        keys_to_check = include.split(",")

    if exclude != "":
        for k in exclude.split(","):
            keys_to_check.remove(k)

    def run_update(key: str, data: FileVersion, multi_key: bool = False) -> None:
        post = f" ({data['path']})" if multi_key else ""

        def fetch_data() -> None:
            with requests.get(
                build_remote_url(remote_version_data[key]["path"]), timeout=30
            ) as response:
                response.raise_for_status()
                with open(
                    os.path.join(directory, data["path"]), "w", encoding="utf-8"
                ) as f_obj:
                    f_obj.write(response.text)
            print(
                f"Fetched {key} {data['version']}->{remote_version_data[key]['version']}{post}"
            )
            data["version"] = remote_version_data[key]["version"]

        match compare_versions(remote_version_data[key]["version"], data["version"]):
            case VersionComparison.NEWER_MAJOR:
                # Remote is a major version bump ahead of us
                if compatibility == Compatibility.MAJOR:
                    fetch_data()
                else:
                    print(
                        f"Remote {key} ({remote_version_data[key]['version']}) is a major version newer than ours "
                        f"({data['version']}), skipping.{post}"
                    )
            case VersionComparison.NEWER_MINOR:
                # Remote is a minor version bump ahead of us
                if compatibility in (Compatibility.MAJOR, Compatibility.MINOR):
                    fetch_data()
                else:
                    print(
                        f"Remote {key} ({remote_version_data[key]['version']}) is a minor version newer than ours "
                        f"({data['version']}), skipping.{post}"
                    )
            case VersionComparison.NEWER_PATCH | VersionComparison.UNKNOWN:
                # Remote is a minor/patch version bump ahead of us, or we don't have a saved version yet
                fetch_data()
            case VersionComparison.OLDER_MAJOR | VersionComparison.OLDER_MINOR | VersionComparison.OLDER_PATCH:
                newer_msg = (
                    f"Local {key} ({data['version']}) is newer than remote "
                    f"({remote_version_data[key]['version']})"
                )
                if strict:
                    raise RuntimeError(newer_msg + post)
                print(f"{newer_msg}, skipping.{post}")
            case VersionComparison.EQUAL:
                print(f"{key} is up-to-date ({data['version']}){post}")
        save_local_version_data()

    for k, val in {k: local_version_data[k] for k in keys_to_check}.items():
        if isinstance(val, list):
            for data_part in val:
                run_update(k, data_part, True)
        else:
            run_update(k, val)
