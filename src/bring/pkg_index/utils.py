# -*- coding: utf-8 -*-
import json
import logging
import os
import zlib
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Set

from anyio import aopen
from bring.defaults import BRING_INDEX_FILES_CACHE
from bring.pkg_index.index import BringIndexTing
from bring.pkg_index.pkg import PkgTing
from frtls.async_helpers import wrap_async_task
from frtls.downloads import download_cached_binary_file_async
from frtls.exceptions import FrklException
from rich.console import Console, ConsoleOptions, RenderResult


log = logging.getLogger("bring")


class IndexDiff(object):
    def __init__(self, index_orig: BringIndexTing, index_new: BringIndexTing):

        self._index_orig: BringIndexTing = index_orig
        self._index_new: BringIndexTing = index_new

        self._diff: Optional[Mapping[str, Any]] = None
        self._inconsistent_packages: Optional[Set[PkgTing]] = None

    async def get_diff(self) -> Mapping[str, Any]:

        if self._diff is None:
            self._diff = await diff_packages(self._index_orig, self._index_new)
        return self._diff

    async def get_added_packages(self) -> Iterable[PkgTing]:

        diff = await self.get_diff()
        return diff.get("added", [])

    async def get_added_package_names(self) -> Iterable[str]:

        pkgs = await self.get_added_packages()
        return [p.name for p in pkgs]

    async def get_removed_package_names(self) -> Iterable[str]:

        pkgs = await self.get_removed_packages()
        return [p.name for p in pkgs]

    async def get_removed_packages(self) -> Iterable[PkgTing]:

        diff = await self.get_diff()
        return diff.get("removed", [])

    async def get_updated_packages(self) -> Iterable[PkgTing]:

        diff = await self.get_diff()

        return diff.get("versions_added", {}).keys()

    async def get_updated_package_names(self) -> Iterable[str]:

        pkgs = await self.get_updated_packages()
        return [p.name for p in pkgs]

    async def get_inconsistent_packages(self) -> Set[PkgTing]:

        if self._inconsistent_packages is not None:
            return self._inconsistent_packages

        diff = await self.get_diff()

        pkgs_removed = diff.get("removed", None)
        versions_removed = diff.get("versions_removed", None)

        pkgs: Set[PkgTing] = set()
        if pkgs_removed:
            pkgs.update(pkgs_removed.keys())
        if versions_removed:
            pkgs.update(versions_removed.keys())

        self._inconsistent_packages = pkgs
        return self._inconsistent_packages

    async def get_inconsistent_package_names(self) -> Iterable[str]:

        inconsistent_packages = await self.get_inconsistent_packages()
        pkg_names = [p.name for p in inconsistent_packages]
        return pkg_names

    async def validate_update(self, raise_exception: bool = True) -> Set[PkgTing]:

        pkg_names = await self.get_inconsistent_package_names()

        if pkg_names:
            if raise_exception:
                raise FrklException(
                    msg="Can't update index.",
                    reason=f"Missing/inconsistent packages: {pkg_names}",
                )

        return await self.get_inconsistent_packages()

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:

        if self._diff is None:
            wrap_async_task(self.get_diff)

        if self._diff is None:
            raise Exception("Can't print index diff, this is a bug.")

        added = self._diff.get("added", None)
        removed = self._diff.get("removed", None)
        added_versions = self._diff.get("versions_added", None)
        removed_versions = self._diff.get("versions_removed", None)

        if added:
            if len(added) == 1:
                _ps = "package"
            else:
                _ps = "packages"
            yield f"- [title]added {_ps}:[/title]"
            for a in sorted([a.name for a in added]):
                yield f"  - {a}"
        else:
            yield "- [title]no added packages[/title]"
        yield ""

        if added_versions:
            if len(added_versions) == 1:
                _ps = "package"
            else:
                _ps = "packages"
            yield f"- [title]added versions in {_ps}:[/title]"
            versions_set = set()

            for pkg, versions in sorted(added_versions.items()):
                yield f"    [key2]{pkg.name}[/key2]:"
                for v in versions:
                    _v = v.get("version", "n/a")
                    versions_set.add(_v)
                for v in sorted(versions_set):
                    yield f"      - {v}"
        else:
            yield "- [title]no versions added to any packages[/title]"

        yield ""

        if removed:
            if len(removed) == 1:
                _ps = "package"
            else:
                _ps = "packages"
            yield f"- [title][red]removed {_ps}:[/red][/title]"
            for r in sorted(removed):
                yield f"  - {r.name}"
        else:
            yield "- [title]no removed packages[/title]"
        yield ""

        if removed_versions:
            if len(removed_versions) == 1:
                _ps = "package"
            else:
                _ps = "packages"
            yield f"- [bold red]removed versions in {_ps}:[/bold red]"
            versions_set = set()
            for pkg, versions in sorted(removed_versions.items()):

                yield f"    [key2]{pkg.name}[/key2]:"
                for v in versions:
                    _v = v.get("version", "n/a")
                    versions_set.add(_v)
                for v in sorted(versions_set):
                    yield f"      - {v}"


async def diff_packages(
    index_orig: BringIndexTing, index_new: BringIndexTing
) -> Mapping[str, Any]:
    """Diffs the packages of two indexes.

    This does not update any of the indexes, if that is the desired behaviour, do that beforehand.
    """

    pkgs_orig = await index_orig.get_pkgs()
    pkgs_new = await index_new.get_pkgs()

    pkgs_missing: List[PkgTing] = []
    pkgs_added: List[PkgTing] = []
    pkgs_diff: MutableMapping[PkgTing, Mapping[str, Any]] = {}

    versions_added: MutableMapping[PkgTing, Iterable[Mapping[str, Any]]] = {}
    versions_removed: MutableMapping[PkgTing, Iterable[Mapping[str, Any]]] = {}

    for pkg_name, pkg in pkgs_orig.items():

        pkg_new = pkgs_new.get(pkg_name, None)
        if pkg_new is None:
            pkgs_missing.append(pkg)
            continue

        v_orig = await pkg.get_versions()
        v_new = await pkg_new.get_versions()

        v_diff = diff_version_lists(v_orig, v_new)
        if v_diff:
            pkgs_diff[pkg] = v_diff
            if v_diff.get("added", None):
                versions_added[pkg] = v_diff["added"]
            if v_diff.get("removed", None):
                versions_removed[pkg] = v_diff["removed"]

    for pkg_name, pkg in pkgs_new.items():

        pkg_orig = pkgs_orig.get(pkg_name, None)
        if pkg_orig is None:
            pkgs_added.append(pkg)

    result: Dict[str, Any] = {}
    if pkgs_missing:
        result["removed"] = pkgs_missing
    if pkgs_added:
        result["added"] = pkgs_added
    if pkgs_diff:
        result["changed"] = pkgs_diff
    if versions_added:
        result["versions_added"] = versions_added
    if versions_removed:
        result["versions_removed"] = versions_removed
    return result


def diff_version_lists(
    versions_orig: Iterable[Mapping[str, Any]],
    versions_new: Iterable[Mapping[str, Any]],
) -> Mapping[str, Iterable[Mapping[str, Any]]]:

    versions_missing = []
    versions_added = []

    for version in versions_orig:
        if version not in versions_new:
            versions_missing.append(version)

    for version in versions_new:
        if version not in versions_orig:
            versions_added.append(version)

    result = {}
    if versions_added:
        result["added"] = versions_added
    if versions_missing:
        result["removed"] = versions_missing

    return result


async def ensure_index_file_is_local(index_url: str) -> str:

    if os.path.exists(index_url):
        return index_url

    cache_path = await download_cached_binary_file_async(
        url=index_url, cache_base=BRING_INDEX_FILES_CACHE, return_content=False
    )

    return cache_path  # type: ignore


async def retrieve_index_file_content(
    index_url: str, update: bool = False
) -> Mapping[str, Any]:

    if os.path.exists(index_url):
        async with await aopen(index_url, "rb") as f:
            content = await f.read()
    else:

        content = await download_cached_binary_file_async(
            url=index_url,
            update=update,
            cache_base=BRING_INDEX_FILES_CACHE,
            return_content=True,
        )

    json_string = zlib.decompress(content, 16 + zlib.MAX_WBITS)  # type: ignore

    data = json.loads(json_string)
    return data
