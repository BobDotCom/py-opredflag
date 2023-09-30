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
import asyncio
import json
import os
import sys
from typing import Literal

import aiohttp
from async_lru import alru_cache

from .enums import Compatibility, VersionComparison

if sys.version_info < (3, 11):
    from typing_extensions import NotRequired, TypedDict
else:
    from typing import NotRequired, TypedDict

__all__ = ("Updater",)


class FileVersion(TypedDict):
    """An oprf version file version entry."""

    version: str | None
    path: str


class UpdaterData(TypedDict):
    """Output data entry from the updater."""

    key: str
    path: str
    old_version: str
    new_version: NotRequired[str]
    reason: NotRequired[str]
    multi_key: bool


def format_data(data: UpdaterData) -> str:
    """Format :class:`UpdaterData` into a human-readable string.

    Parameters
    ----------
    data:
        Data to format

    Returns
    -------
    str
        The formatted data
    """
    versions = "{old_version}"
    if "new_version" in data:
        versions += "->{new_version}"
    reason = f"{data['key']} {versions}"
    reason += " ({reason})" if "reason" in data else ""
    reason += " ({path})" if data["multi_key"] else ""
    return reason.format_map(data)


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


class Updater:
    """The base updater class which handles the whole process.

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

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        directory: str = ".",
        version_json: str = "oprf-versions.json",
        repository: str = "NikolaiVChr/OpRedFlag",
        branch: str = "master",
        include: str = "*",
        exclude: str = "",
        compatibility: Compatibility = Compatibility.MINOR,
        strict: bool = False,
    ):
        """Initialize the updater."""
        # pylint: disable=too-many-arguments
        self.directory = directory
        self.version_json = os.path.join(directory, version_json)
        self.repository = repository
        self.branch = branch
        self.include = include
        self.exclude = exclude
        self.compatibility = compatibility
        self.strict = strict
        self.session: aiohttp.ClientSession | None = None
        self._remote_version_data: dict[str, FileVersion] | None = None
        self.data: dict[
            Literal["fetched", "skipped", "up-to-date"], list[UpdaterData]
        ] = {
            "fetched": [],
            "skipped": [],
            "up-to-date": [],
        }
        self.pending_write_files: dict[str, str] = {}

        with open(self.version_json, encoding="utf-8") as f_obj:
            self.local_version_data: dict[
                str, FileVersion | list[FileVersion]
            ] = json.load(f_obj)

    def write_files(self) -> None:
        """:meta private: Write all scheduled files."""
        for filepath, value in self.pending_write_files.items():
            with open(filepath, "w", encoding="utf-8") as f_obj:
                f_obj.write(value)

    @property
    def remote_version_data(self) -> dict[str, FileVersion]:
        """:meta private: Version data fetched from the remote repository, raises if unset."""
        if self._remote_version_data is None:
            raise RuntimeError("Version unset")
        return self._remote_version_data

    @remote_version_data.setter
    def remote_version_data(self, value: dict[str, FileVersion]) -> None:
        self._remote_version_data = value

    def build_remote_url(self, path: str) -> str:
        """:meta private: Build a URL to fetch a file from."""
        return (
            f"https://raw.githubusercontent.com/{self.repository}/{self.branch}/{path}"
        )

    def save_version_data(self) -> None:
        """:meta private: Save the local versions file."""
        with open(self.version_json, "w", encoding="utf-8") as f_obj:
            json.dump(self.local_version_data, f_obj, indent=2)

    @alru_cache(ttl=30, typed=True)
    async def fetch_remote_version_data(self) -> None:
        """:meta private: Fetch remote version data."""
        if self.session is None:
            raise RuntimeError("Session unset")
        async with self.session.get(
            self.build_remote_url("versions.json"), timeout=30
        ) as response:
            self.remote_version_data = await response.json(content_type="text/plain")

    @alru_cache(ttl=30, typed=True)
    async def fetch_file(self, path: str) -> str:
        """:meta private: Fetch a file."""
        if self.session is None:
            raise RuntimeError("Session unset")
        async with self.session.get(
            self.build_remote_url(path), timeout=30
        ) as response:
            response.raise_for_status()
            return await response.text()

    async def update_file(
        self, key: str, data: FileVersion, multi_key: bool = False
    ) -> None:
        """:meta private: Update a file by key.

        Parameters
        ----------
        key:
            The oprf-versions.json key for this file
        data:
            The local data we have saved for this file
        multi_key:
            If there are multiple files for this key, specifies path in script output
        """

        async def fetch_data() -> None:
            self.pending_write_files[
                os.path.join(self.directory, data["path"])
            ] = await self.fetch_file(self.remote_version_data[key]["path"])
            self.data["fetched"].append(
                UpdaterData(
                    key=key,
                    path=data["path"],
                    old_version=data["version"] or "null",
                    new_version=self.remote_version_data[key]["version"] or "null",
                    multi_key=multi_key,
                )
            )
            data["version"] = self.remote_version_data[key]["version"]

        match compare_versions(
            self.remote_version_data[key]["version"], data["version"]
        ):
            case VersionComparison.NEWER_MAJOR:
                # Remote is a major version bump ahead of us
                if self.compatibility == Compatibility.MAJOR:
                    await fetch_data()
                else:
                    self.data["skipped"].append(
                        UpdaterData(
                            key=key,
                            path=data["path"],
                            old_version=data["version"] or "null",
                            new_version=self.remote_version_data[key]["version"]
                            or "null",
                            reason="Major version newer than local",
                            multi_key=multi_key,
                        )
                    )
            case VersionComparison.NEWER_MINOR:
                # Remote is a minor version bump ahead of us
                if self.compatibility in (Compatibility.MAJOR, Compatibility.MINOR):
                    await fetch_data()
                else:
                    self.data["skipped"].append(
                        UpdaterData(
                            key=key,
                            path=data["path"],
                            old_version=data["version"] or "null",
                            new_version=self.remote_version_data[key]["version"]
                            or "null",
                            reason="Minor version newer than local",
                            multi_key=multi_key,
                        )
                    )
            case VersionComparison.NEWER_PATCH | VersionComparison.UNKNOWN:
                # Remote is a minor/patch version bump ahead of us, or we don't have a saved version yet
                await fetch_data()
            case VersionComparison.OLDER_MAJOR | VersionComparison.OLDER_MINOR | VersionComparison.OLDER_PATCH:
                data_obj = UpdaterData(
                    key=key,
                    path=data["path"],
                    old_version=data["version"] or "null",
                    new_version=self.remote_version_data[key]["version"] or "null",
                    reason="Newer than remote",
                    multi_key=multi_key,
                )
                if self.strict:
                    raise RuntimeError(format_data(data_obj))
                self.data["skipped"].append(data_obj)
            case VersionComparison.EQUAL:
                self.data["up-to-date"].append(
                    UpdaterData(
                        key=key,
                        path=data["path"],
                        old_version=data["version"] or "null",
                        multi_key=multi_key,
                    )
                )

    def get_keys(self) -> list[str]:
        """:meta private: Get keys."""
        if self.include == "*":
            keys_to_check = list(self.local_version_data.keys())
        elif self.include == "":
            keys_to_check = []
        else:
            keys_to_check = self.include.split(",")

        if self.exclude != "":
            for k in self.exclude.split(","):
                keys_to_check.remove(k)

        return keys_to_check

    async def run(self) -> list[str]:
        """Run the update.

        Returns
        -------
        list[str]
            The script output, split by newlines
        """
        self.session = aiohttp.ClientSession()
        try:
            await self.fetch_remote_version_data()

            keys_to_check = self.get_keys()

            # TODO: When upgraded to 3.11, use asyncio.TaskGroup for main runner
            #       https://docs.python.org/3.11/library/asyncio-task.html#task-groups

            # Old:
            # coros = []
            # coros.append()
            # await asyncio.gather(coros)

            # New:
            # async with asyncio.TaskGroup() as tg:
            #     tg.create_task()

            coros = []

            for k, val in {
                k: self.local_version_data[k] for k in keys_to_check
            }.items():
                if isinstance(val, list):
                    for data_part in val:
                        coros.append(self.update_file(k, data_part, True))
                else:
                    coros.append(self.update_file(k, val))
            await asyncio.gather(*coros)

            output = []
            for key, values in self.data.items():
                if key == "fetched":
                    if len(values) > 0:
                        print("\n".join(map(format_data, values)))
                    continue
                if len(values) > 0:
                    output.append(f"{key.title()}:")
                for item in values:
                    output.append(f"\t{format_data(item)}")

            self.write_files()
            self.save_version_data()
            return output
        except BaseException:  # pylint: disable=try-except-raise
            # We don't actually want to catch exceptions, we're just using this for the "finally" block
            raise
        finally:
            await self.session.close()
