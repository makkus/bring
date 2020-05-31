# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Set

from bring.pkg_index.index import BringIndexTing
from bring.pkg_index.pkg import PkgTing
from frtls.exceptions import FrklException


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
                    msg=f"Can't update index.",
                    reason=f"Missing/inconsistent packages: {pkg_names}",
                )

        return await self.get_inconsistent_packages()


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
