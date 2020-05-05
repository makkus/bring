# -*- coding: utf-8 -*-
import collections
import tempfile
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Union,
)

from anyio import create_task_group
from bring.defaults import (
    BRING_AUTO_ARG,
    BRING_RESULTS_FOLDER,
    BRING_TEMP_FOLDER_MARKER,
)
from bring.pkg_index.pkg import PkgTing
from bring.utils.merging import FolderMerge, MergeStrategy
from frtls.dicts import get_seeded_dict
from frtls.doc import Doc
from frtls.exceptions import FrklException
from frtls.formats.input_formats import SmartInput
from frtls.templating import (
    create_var_regex,
    find_var_names_in_obj,
    replace_var_names_in_obj,
)


if TYPE_CHECKING:
    from bring.bring import Bring

BRING_IN_DEFAULT_DELIMITER = create_var_regex()


class BringIn(object):
    @classmethod
    def create(cls, item: Union[str, Mapping[str, Any]]) -> "BringIn":

        if isinstance(item, str):
            result: Mapping[str, Any] = {"name": item}
        elif isinstance(item, Mapping):
            result = item
        else:
            raise TypeError(
                f"Can't create bring item, invalid input type '{type(item)}': {item}"
            )

        try:
            bring_item = BringIn(**result)
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

        self._var_names: Optional[Set[str]] = None

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

    def process_vars(self, repl_dict: Mapping[str, Any]):

        repl = replace_var_names_in_obj(
            self._vars, repl_dict=repl_dict, delimiter=BRING_IN_DEFAULT_DELIMITER
        )
        return repl

    def process_mogrify(self, repl_dict: Mapping[str, Any]):

        repl = replace_var_names_in_obj(
            self._mogrify, repl_dict=repl_dict, delimiter=BRING_IN_DEFAULT_DELIMITER
        )
        return repl

    @property
    def mogrify(self) -> Iterable[Mapping[str, Any]]:

        return self._mogrify

    def get_var_names(self) -> Set[str]:

        if self._var_names is not None:
            return self._var_names

        obj: Dict[str, Any] = {}
        if self._vars:
            obj["vars"] = self._vars
        if self._mogrify:
            obj["mogrify"] = self._mogrify

        self._var_names = find_var_names_in_obj(
            obj, delimiter=BRING_IN_DEFAULT_DELIMITER
        )
        return self._var_names


class BringIns(object):
    @classmethod
    async def from_file(cls, path: Union[str, Path]) -> "BringIns":

        si = SmartInput(path)

        content = await si.content_async()

        if not isinstance(content, collections.Mapping):
            content = {"pkgs": content}

        return cls.create(data=content["pkgs"])

    @classmethod
    def create(
        cls,
        data: Union[Mapping[str, Any], Iterable[Mapping[str, Any]]],
        defaults: Mapping[str, Any] = None,
    ) -> "BringIns":

        if not isinstance(data, collections.abc.Mapping):
            _data: Mapping[str, Any] = {"items": data}
        else:
            _data = data

        items = []
        for item in _data.get("items", []):
            bi = BringIn.create(item)
            items.append(bi)

        return BringIns(*items, defaults=defaults)

    def __init__(
        self,
        *items: BringIn,
        defaults: Optional[Mapping[str, Any]] = None,
        args: Optional[Mapping[str, Any]] = None,
        doc: Optional[Union[str, Mapping[str, Any]]] = None,
    ) -> None:

        self._items = items
        self._defaults = defaults

        self._doc = Doc(doc)
        self._var_names: Optional[Set[str]] = None
        if args is None:
            args = {}
        self._provided_args: Mapping[str, Any] = args
        self._auto_args: Optional[Mapping[str, Any]] = None
        self._args: Optional[Mapping[str, Any]] = None

    @property
    def doc(self) -> Doc:

        return self._doc

    @property
    def args(self) -> Mapping[str, Any]:

        if self._args is not None:
            return self._args

        self._args = get_seeded_dict(
            self.auto_args, self._provided_args, merge_strategy="update"
        )
        return self._args

    @property
    def auto_args(self) -> Mapping[str, Any]:

        if self._auto_args is not None:
            return self._auto_args

        self._auto_args = {}
        for vn in self.get_var_names():
            if vn in self._provided_args.keys():
                continue

            self._auto_args[vn] = dict(BRING_AUTO_ARG)

        return self._auto_args

    def get_var_names(self) -> Set[str]:

        if self._var_names is not None:
            return self._var_names

        self._var_names = set()
        for item in self._items:

            var_names = item.get_var_names()
            self._var_names.update(var_names)

        return self._var_names

    async def install(
        self,
        bring: "Bring",
        vars: Optional[Mapping[str, Any]] = None,
        target: Union[str, Path] = None,
        strategy: Optional[Union[str, Mapping[str, Any], MergeStrategy]] = None,
        flatten: bool = False,
    ) -> str:

        item_list = []

        async def retrieve_pkg(_item: BringIn, _vars: Mapping[str, Any]):

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
                target=BRING_TEMP_FOLDER_MARKER,
                vars=_item.process_vars(repl_dict=_vars),
                extra_mogrifiers=_item.process_mogrify(repl_dict=_vars),
            )
            data["target"] = t
            item_list.append(data)

        if vars is None:
            vars = {}

        async with create_task_group() as tg:
            for i in self._items:
                await tg.spawn(retrieve_pkg, i, vars)

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
