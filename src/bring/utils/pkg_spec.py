# -*- coding: utf-8 -*-
import collections
import copy
import logging
import os
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

from frtls.types.utils import is_instance_or_subclass


log = logging.getLogger("bring")

PKG_SPEC_DEFAULTS = {"flatten": False, "single_file": False}

PATH_KEY = "path"
FROM_KEY = "from"


class PkgSpec(object):
    @classmethod
    def create(cls, pkg_spec: Any) -> "PkgSpec":

        if is_instance_or_subclass(pkg_spec, PkgSpec):
            return pkg_spec

        if not pkg_spec:
            pkg_spec = {}
        elif isinstance(pkg_spec, str):
            pkg_spec = {"items": [{PATH_KEY: pkg_spec}]}

        elif not isinstance(pkg_spec, collections.abc.Mapping):
            raise TypeError(f"Invalid type '{type(pkg_spec)}' for pkg spec: {pkg_spec}")

        pkg_spec_obj = PkgSpec(**pkg_spec)
        return pkg_spec_obj

    def __init__(
        self,
        items: Optional[Iterable[str]] = None,
        flatten: bool = PKG_SPEC_DEFAULTS["flatten"],
        single_file: bool = PKG_SPEC_DEFAULTS["single_file"],
    ):

        self._flatten: bool = flatten
        self._single_file_pkg: bool = single_file

        self._items: Dict[str, Mapping[str, Any]] = {}

        if isinstance(items, collections.abc.Mapping):

            _files_dict: Mapping[str, Any] = copy.deepcopy(items)
            for path_key, details in _files_dict.items():

                if isinstance(details, str):
                    details = {PATH_KEY: details}

                if PATH_KEY in details.keys():
                    if path_key != details[PATH_KEY]:
                        raise ValueError(
                            f"Invalid 'items' value: item_id != '{PATH_KEY}' value: {path_key} - {details[PATH_KEY]}"
                        )
                else:
                    details[PATH_KEY] = path_key

                if PATH_KEY not in details.keys():
                    details[PATH_KEY] = path_key

                self._items[path_key] = details
        else:

            if items is None:
                _files: List[Union[str, Mapping[str, Any]]] = []
            else:
                _files = list(items)

            for _f in _files:
                if isinstance(_f, str):
                    f: Mapping[str, Any] = {PATH_KEY: _f, FROM_KEY: _f}
                else:
                    f = _f  # type: ignore

                if (
                    len(f) == 1
                    and PATH_KEY not in f.keys()
                    and FROM_KEY not in f.keys()
                ):
                    key = next(iter(f.keys()))
                    value = f[key]
                    if PATH_KEY not in value.keys():
                        value[PATH_KEY] = key
                        f = value

                if PATH_KEY in f.keys():
                    path_key = f[PATH_KEY]
                    details = f
                    if FROM_KEY not in f.keys():
                        if self._flatten:
                            path = os.path.basename(f[PATH_KEY])
                        else:
                            path = f[PATH_KEY]
                        details[FROM_KEY] = path
                elif FROM_KEY in f.keys():
                    path_key = f[FROM_KEY]
                    details = f
                    details[PATH_KEY] = path_key
                else:
                    raise ValueError(
                        f"No '{PATH_KEY}' or '{FROM_KEY}' key in item details: {f}"
                    )
                self._items[path_key] = details

        # import pp
        # pp(self._items)

    @property
    def pkg_items(self) -> Mapping[str, Mapping[str, Any]]:
        return self._items

    @property
    def flatten(self) -> bool:
        return self._flatten

    @property
    def single_file(self) -> bool:
        return self._single_file_pkg

    def get_item_details(self, item: str) -> Optional[Mapping[str, Any]]:

        details: Optional[Mapping[str, Any]] = self._items.get(item, None)

        if details is None:
            if not self._items:
                details = {PATH_KEY: item, FROM_KEY: item}
        return details
