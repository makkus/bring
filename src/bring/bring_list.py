# -*- coding: utf-8 -*-
import collections
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, List, Mapping, Optional, Union

from anyio import create_task_group
from bring.defaults import BRING_RESULTS_FOLDER
from bring.merging import FolderMerge, MergeStrategy
from bring.pkg import PkgTing
from frtls.exceptions import FrklException
from frtls.formats.input_formats import SmartInput


if TYPE_CHECKING:
    from bring.bring import Bring


class BringItem(object):
    @classmethod
    def create(cls, item: Union[str, Mapping[str, Any]]) -> "BringItem":

        if isinstance(item, str):
            result: Mapping[str, Any] = {"name": item}
        elif isinstance(item, Mapping):
            result = item
        else:
            raise TypeError(
                f"Can't create bring item, invalid input type '{type(item)}': {item}"
            )

        try:
            bring_item = BringItem(**result)
            return bring_item
        except Exception as e:
            raise ValueError(f"Can't create bring item with input '{item}': {e}")

    def __init__(
        self,
        name: str,
        index: Optional[str] = None,
        vars: Mapping[str, Any] = None,
        mogrify: Iterable[Union[str, Mapping[str, Any]]] = None,
    ) -> None:

        if "." in name and index:
            raise FrklException(
                msg=f"Can't create item '{name}'.",
                reason="Index provided, but name uses dotted notation.",
                solution="Use either or.",
            )

        _index: Optional[str]
        _name: str
        if "." in name:
            _index, _name = name.split(".", maxsplit=1)
        else:
            _index = index
            _name = name

        self._name: str = _name
        self._index: Optional[str] = _index

        if vars is None:
            vars = {}
        self._vars: Mapping[str, Any] = vars

        if mogrify is None:
            mogrify = []
        self._mogrify: List[Mapping[str, Any]] = []
        for m in mogrify:
            if isinstance(m, str):
                _m: Mapping[str, Any] = {"type": m}
            else:
                _m = m
            self._mogrify.append(_m)

    def to_dict(self) -> Mapping[str, Any]:

        return {
            "name": self.name,
            "index": self.index,
            "vars": self.vars,
            "mogrifiers": self.mogrify,
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def index(self) -> Optional[str]:
        return self._index

    @property
    def vars(self) -> Mapping[str, Any]:
        return self._vars

    @property
    def mogrify(self) -> Iterable[Mapping[str, Any]]:

        return self._mogrify


class BringList(object):
    @classmethod
    async def from_file(cls, path: Union[str, Path]) -> "BringList":

        si = SmartInput(path)

        content = await si.content_async()

        return cls.create(data=content["pkgs"])

    @classmethod
    def create(
        cls,
        data: Union[Mapping[str, Any], Iterable[Mapping[str, Any]]],
        item_defaults: Mapping[str, Any] = None,
    ) -> "BringList":

        if not isinstance(data, collections.abc.Mapping):
            _data: Mapping[str, Any] = {"items": data}
        else:
            _data = data

        items = []
        for item in _data.get("items", []):
            bi = BringItem.create(item)
            items.append(bi)

        return BringList(*items, item_defaults=item_defaults)

    def __init__(
        self, *items: BringItem, item_defaults: Mapping[str, Any] = None
    ) -> None:

        self._items = items
        self._item_defaults = item_defaults

    async def install(
        self,
        bring: "Bring",
        target: Union[str, Path] = None,
        strategy: Optional[Union[str, Mapping[str, Any], MergeStrategy]] = None,
        flatten: bool = False,
    ) -> str:

        item_list = []

        async def retrieve_pkg(_item: BringItem):

            pkg: Optional[PkgTing] = await bring.get_pkg(
                name=_item.name, index=_item.index
            )

            if pkg is None:
                if _item.index:
                    _msg = f" from index ({_item.index})"
                else:
                    _msg = ""
                raise FrklException(msg=f"Can't retrieve pkg '{_item.name}'{_msg}.")

            data = {"pkg": pkg, "item": _item}

            t = await pkg.create_version_folder(
                target=None, vars=_item.vars, extra_mogrifiers=_item.mogrify
            )
            data["target"] = t
            item_list.append(data)

        async with create_task_group() as tg:
            for i in self._items:
                await tg.spawn(retrieve_pkg, i)

        if target is None:
            target = tempfile.mkdtemp(prefix="install_", dir=BRING_RESULTS_FOLDER)

        merge_obj = FolderMerge(
            typistry=bring.typistry,
            target=target,
            merge_strategy=strategy,
            flatten=flatten,
        )
        sources = []
        for pkg in item_list:
            source: str = pkg["target"]  # type: ignore
            sources.append(source)

        merge_obj.merge_folders(*sources)

        if isinstance(target, Path):
            target = target.resolve().as_posix()
        return target
