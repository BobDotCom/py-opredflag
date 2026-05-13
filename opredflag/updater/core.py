"""
Py-opredflag.

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
import copy
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Literal, cast

import aiohttp
import semver
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


class VersionDataFile(TypedDict):
    """A version data file."""

    version: int
    last_updated: datetime
    data: dict[str, FileVersion | list[FileVersion]]


class VersionDataFileJson(TypedDict):
    """The json serializable version of a VersionDataFile type."""

    version: int
    last_updated: str
    data: dict[str, FileVersion | list[FileVersion]]


class UpdaterData(TypedDict):
    """Output data entry from the updater."""

    key: str
    path: str
    old_version: str
    new_version: NotRequired[str]
    reason: NotRequired[str]
    multi_key: bool


def load_version_data_file(file_path: str) -> VersionDataFile:
    """Load a version data file from a path."""

    with open(file_path, encoding="utf-8") as f_obj:
        version_data = update_version_data_file(json.load(f_obj))
        new_version_data: VersionDataFile = {
            **version_data,
            "last_updated": datetime.fromisoformat(version_data["last_updated"]),
        }

    return new_version_data


def dump_version_data_file(version_data: VersionDataFile, file_path: str) -> None:
    """Dump a version data file to a path."""

    new_version_data = {
        **version_data,
        "last_updated": version_data["last_updated"].isoformat(),
    }

    with open(file_path, "w", encoding="utf-8") as f_obj:
        json.dump(new_version_data, f_obj, indent=2)


def update_version_data_file(version_data: dict[Any, Any]) -> VersionDataFileJson:
    """Handle all the updates required if updating from an old file."""

    old_file_version = version_data.get("version")

    # This is meant to be recursive. Each Version will only upgrade to the next,
    #     so if multiple versions need updating, they will progress in order.
    match old_file_version:
        case None:
            # Consider this as version 0. Migrate to version 1 and recurse.
            # Set last_updated to epoch
            return update_version_data_file(
                {
                    "version": 1,
                    "last_updated": datetime.fromtimestamp(0, timezone.utc).isoformat(),
                    "data": version_data,
                }
            )
        case 1:
            # Currently up-to-date. Assume nothing to do, end recursion and return.

            # Before returning, do a quick check to make sure the data is correct.
            try:
                # We can type ignore here because we're catching value and type errors below
                datetime.fromisoformat(version_data.get("last_updated"))  # type: ignore
            except (ValueError, TypeError) as e:
                raise ValueError(
                    "Couldn't parse version file 'last_updated' value. "
                    f"Expected an ISO 8601 string, but got: {version_data.get('last_updated')!r}"
                ) from e

            if not isinstance(old_file_data := version_data.get("data"), dict):
                raise TypeError(
                    "Couldn't parse version file 'data' value. "
                    f"Expected a dict, got {type(old_file_data).__name__}: {old_file_data!r}"
                )

            # We can skip version because we've already checked it

            # Now, since we've done the checks we can cast it to the return type
            return cast(VersionDataFileJson, version_data)
        case _:
            raise ValueError(
                f"Expected file version 1, got {old_file_version!r}. Please update your version file."
            )


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
    # pylint: disable=too-many-return-statements
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

    val1 = semver.Version.parse(first)
    val2 = semver.Version.parse(second)

    if val1 > val2:
        if val1.major > val2.major:
            return VersionComparison.NEWER_MAJOR
        if val1.minor > val2.minor:
            return VersionComparison.NEWER_MINOR
        if val1.patch > val2.patch:
            return VersionComparison.NEWER_PATCH
        return VersionComparison.NEWER
    if val1 == val2:
        return VersionComparison.EQUAL
    if val2.major > val1.major:
        return VersionComparison.OLDER_MAJOR
    if val2.minor > val1.minor:
        return VersionComparison.OLDER_MINOR
    if val2.patch > val1.patch:
        return VersionComparison.OLDER_PATCH
    return VersionComparison.OLDER


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
    update_timestamp_after:
        Automatically update the `last_updated` key in the version file after this amount of days,
            even when no changes have been made. Set to 0 for always or -1 for never.
    """

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self,
        directory: str = ".",
        version_json: str = "oprf-versions.json",
        repository: str = "Op-Redflag/OpRedFlag",
        branch: str = "master",
        include: str = "*",
        exclude: str = "",
        compatibility: Compatibility = Compatibility.MINOR,
        strict: bool = False,
        update_timestamp_after: int = 30,
    ):
        """Initialize the updater."""
        # pylint: disable=too-many-arguments,too-many-positional-arguments
        self.directory = directory
        self.version_json = os.path.join(directory, version_json)
        self.repository = repository
        self.branch = branch
        self.include = include
        self.exclude = exclude
        self.compatibility = compatibility
        self.strict = strict
        self.update_timestamp_after = update_timestamp_after
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

        self.local_version_data = load_version_data_file(self.version_json)
        self.original_version_data = copy.deepcopy(self.local_version_data)

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

        # If we're actually updating, we need to update the timestamp.
        if self.original_version_data != self.local_version_data:
            self.local_version_data["last_updated"] = datetime.now(timezone.utc)

        # Also update the timestamp if it's been long enough
        if self.update_timestamp_after >= 0:
            time_since_update = (
                datetime.now(timezone.utc) - self.local_version_data["last_updated"]
            )
            if time_since_update.days >= self.update_timestamp_after:
                self.local_version_data["last_updated"] = datetime.now(timezone.utc)

        dump_version_data_file(self.local_version_data, self.version_json)

    @alru_cache(ttl=30, typed=True)
    async def fetch_remote_version_data(self) -> None:
        """:meta private: Fetch remote version data."""
        if self.session is None:
            raise RuntimeError("Session unset")
        async with self.session.get(
            self.build_remote_url("versions.json"),
        ) as response:
            self.remote_version_data = await response.json(content_type="text/plain")

    @alru_cache(ttl=30, typed=True)
    async def fetch_file(self, path: str) -> str:
        """:meta private: Fetch a file."""
        if self.session is None:
            raise RuntimeError("Session unset")
        async with self.session.get(
            self.build_remote_url(path),
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
            self.pending_write_files[os.path.join(self.directory, data["path"])] = (
                await self.fetch_file(self.remote_version_data[key]["path"])
            )
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
            case VersionComparison.NEWER_PATCH:
                # Remote is a patch version bump ahead of us
                if self.compatibility in (
                    Compatibility.MAJOR,
                    Compatibility.MINOR,
                    Compatibility.PATCH,
                ):
                    await fetch_data()
                else:
                    self.data["skipped"].append(
                        UpdaterData(
                            key=key,
                            path=data["path"],
                            old_version=data["version"] or "null",
                            new_version=self.remote_version_data[key]["version"]
                            or "null",
                            reason="Patch version newer than local",
                            multi_key=multi_key,
                        )
                    )
            case VersionComparison.NEWER | VersionComparison.UNKNOWN:
                # Remote is a pre-release ahead of us, or we don't have a saved version yet
                await fetch_data()
            # pylint: disable=line-too-long
            case (
                VersionComparison.OLDER_MAJOR
                | VersionComparison.OLDER_MINOR
                | VersionComparison.OLDER_PATCH
                | VersionComparison.OLDER
            ):  # noqa: E501
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
            keys_to_check = list(self.local_version_data["data"].keys())
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
                k: self.local_version_data["data"][k] for k in keys_to_check
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
