# -*- coding: utf-8 -*-

"""Main module."""
import logging
import os
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Type, Union

from anyio import Lock, create_lock, create_task_group
from bring.bring_target import BringTarget
from bring.config.bring_config import BringConfig
from bring.defaults import BRINGISTRY_INIT, BRING_WORKSPACE_FOLDER
from bring.interfaces.cli import console
from bring.mogrify import Transmogritory
from bring.pkg_index.config import IndexConfig
from bring.pkg_index.factory import IndexFactory
from bring.pkg_index.index import BringIndexTing
from bring.pkg_index.pkg import PkgTing
from bring.utils import BringTaskDesc
from bring.utils.defaults import calculate_defaults
from frtls.args.hive import ArgHive
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.introspection.pkg_env import AppEnvironment
from frtls.tasks import ParallelTasksAsync, Tasks
from frtls.tasks.task_watcher import TaskWatchManager
from frtls.tasks.watchers.rich import RichTaskWatcher
from frtls.types.utils import is_instance_or_subclass
from tings.ting import SimpleTing, TingMeta
from tings.tingistry import Tingistry


log = logging.getLogger("bring")


DEFAULT_TRANSFORM_PROFILES = {
    "executable": [
        {"type": "file_filter", "exclude": ["*~", "~*"]},
        {"type": "set_mode", "config": {"set_executable": True, "set_readable": True}},
    ]
}


class Bring(SimpleTing):
    def __init__(
        self, meta: TingMeta, name: str = None, bring_config: BringConfig = None
    ):

        prototings: Iterable[Mapping] = BRINGISTRY_INIT["prototings"]  # type: ignore
        tings: Iterable[Mapping] = BRINGISTRY_INIT["tings"]  # type: ignore
        modules: Iterable[str] = BRINGISTRY_INIT["modules"]  # type: ignore
        classes: Iterable[Union[Type, str]] = BRINGISTRY_INIT[  # type: ignore
            "classes"
        ]

        if name is None:
            name = "bring"

        ensure_folder(BRING_WORKSPACE_FOLDER)

        if meta is None:
            raise Exception(
                "Can't create 'bring' object: 'meta' argument not provided, this is a bug"
            )

        self._tingistry_obj: Tingistry = meta.tingistry

        self._defaults: Optional[Mapping[str, Any]] = None

        self._tingistry_obj.add_module_paths(*modules)
        self._tingistry_obj.add_classes(*classes)

        if prototings:
            for pt in prototings:
                pt_name = pt["prototing_name"]
                existing = self._tingistry_obj.get_ting(pt_name)
                if existing is None:
                    self._tingistry_obj.register_prototing(**pt)

        if tings:
            for t in tings:
                self._tingistry_obj.create_ting(**t)

        super().__init__(name=name, meta=meta)

        env_conf: MutableMapping[str, Any] = {}
        for k, v in os.environ.items():
            k = k.lower()
            if not k.startswith("bring_"):
                continue
            env_conf[k[6:]] = v

        env_conf["bringistry"] = self
        self.typistry.get_plugin_manager("pkg_type", plugin_config=env_conf)

        # self._transmogritory = Transmogritory(self._tingistry_obj)
        self._transmogritory = self._tingistry_obj.get_ting(
            "bring.transmogritory", raise_exception=False
        )
        if self._transmogritory is None:
            self._transmogritory = self._tingistry_obj.create_singleting(
                "bring.transmogritory", Transmogritory
            )

        self._index_lock: Optional[Lock] = None

        self._bring_config: Optional[BringConfig] = bring_config
        self._index_factory = IndexFactory(
            tingistry=self._tingistry_obj, bring_config=self._bring_config
        )

        if self._bring_config is not None:
            self._bring_config.set_bring(self)

        self._indexes: Dict[str, Optional[BringIndexTing]] = {}

    async def _get_index_lock(self) -> Lock:

        if self._index_lock is None:
            self._index_lock = create_lock()
        return self._index_lock

    @property
    def config(self) -> BringConfig:

        if self._bring_config is None:
            self._bring_config = BringConfig(tingistry=self._tingistry_obj)
            self._bring_config.set_bring(self)
            self._index_factory.bring_config = self._bring_config

        return self._bring_config

    def _invalidate(self) -> None:

        self._indexes = {}
        self._defaults = None
        self._index_factory.invalidate()

        # if self._bring_config is not None:
        #     indexes = self.config.get_config_value("indexes")
        #     if not indexes:
        #         return
        #     else:
        #         for idx in indexes:
        #             if isinstance(idx, str):
        #                 idx_id = idx
        #             elif isinstance(idx, collections.Mapping):
        #                 idx_id = idx.get("id", None)
        #                 if idx_id is None:
        #                     raise FrklException(
        #                         f"Can't add index config: {idx}",
        #                         reason="No 'id' value provided.",
        #                     )
        #
        #             self._indexes[idx_id] = None

    @property
    def typistry(self):

        return self._tingistry_obj.typistry

    @property
    def arg_hive(self) -> ArgHive:

        return self._tingistry_obj.arg_hive

    def provides(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        return {}

    def requires(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        return {}

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        return {}

    async def get_indexes(self) -> Mapping[str, BringIndexTing]:

        missing = []
        for k, v in self._indexes.items():
            if v is None:
                missing.append(k)

        if missing:
            await self.add_indexes(*missing, allow_existing=True)

        return self._indexes  # type: ignore

    @property
    def index_ids(self) -> Iterable[str]:

        return self._indexes.keys()

    async def add_indexes(
        self,
        *index_items: Union[str, Mapping[str, Any], IndexConfig],
        allow_existing: bool = False,
    ) -> Mapping[str, BringIndexTing]:

        if not index_items:
            return {}

        added = {}

        async def add(_ii, _ae):
            _idx = await self.create_index(_ii, _ae)
            added[_ii] = _idx

        async with create_task_group() as tg:

            for ii in index_items:
                await tg.spawn(add, ii, allow_existing)

        # make sure we preserve the order of the items
        result = {}
        for ii in index_items:
            _idx = added[ii]
            await self.add_index(_idx, allow_existing=allow_existing)
            result[_idx.id] = _idx

        return result

    async def add_all_config_indexes(self) -> Mapping[str, BringIndexTing]:

        indexes = await self._index_factory.get_indexes_in_config()

        result = await self.add_indexes(*indexes, allow_existing=True)
        return result

    async def create_index(
        self,
        index_data: Union[str, Mapping[str, Any], IndexConfig],
        allow_existing: bool = False,
    ) -> BringIndexTing:

        index = await self._index_factory.create_index(
            index_data=index_data, allow_existing=allow_existing
        )

        return index

    async def add_index(
        self,
        index_data: Union[str, Mapping[str, Any], IndexConfig, BringIndexTing],
        allow_existing: bool = False,
    ) -> BringIndexTing:

        if is_instance_or_subclass(index_data, BringIndexTing):
            index: BringIndexTing = index_data  # type: ignore
        else:
            index = await self.create_index(
                index_data=index_data, allow_existing=allow_existing  # type: ignore
            )

        if index.id in self.index_ids and not allow_existing:
            raise FrklException(
                f"Can't add index '{index.id}'.",
                reason="Index with this id already added.",
            )

        if (
            index.id in self.index_ids
            and self._indexes.get(index.id, None) is not None
            and index != self._indexes.get(index.id)
        ):
            raise FrklException(
                f"Can't add index '{index.id}'.",
                reason="Different index with same id already exists.",
            )

        self._indexes[index.id] = index

        return index

    async def get_defaults(self) -> Mapping[str, Any]:

        if self._defaults is not None:
            return self._defaults

        defaults: Mapping[str, Any] = await self.config.get_config_value_async(
            "defaults"
        )
        if defaults is None:
            defaults = {}

        if defaults:
            self._defaults = calculate_defaults(
                typistry=self._tingistry_obj.typistry, data=defaults
            )
        else:
            self._defaults = {}

        return self._defaults

    async def get_default_index(self) -> str:

        index_name = await self.config.get_default_index()

        if not index_name:
            indexes = await self._index_factory.get_indexes_in_config()
            if not indexes:
                raise FrklException(
                    "Can't calculate default index.",
                    reason="No 'default_index' value in config, and no indexes configured/registered (yet).",
                )

            index_name = list(indexes)[0]

        return index_name

    async def get_index(self, index_name: Optional[str] = None) -> BringIndexTing:

        if index_name is None:
            index_name = await self.get_default_index()

        if index_name not in self._indexes.keys():
            idx = await self.add_index(index_data=index_name, allow_existing=True)
            index_name = idx.id

        return self._indexes[index_name]  # type: ignore

    async def update(self, index_names: Optional[Iterable[str]] = None):

        if index_names is None:
            index_names = self.index_ids

        td = BringTaskDesc(
            name="update metadata", msg="updating metadata for all indexes"
        )
        tasks = ParallelTasksAsync(task_desc=td)
        # tasks = SerialTasksAsync(task_desc=td)
        for index_name in index_names:
            index = await self.get_index(index_name)
            if index is None:
                raise FrklException(
                    msg=f"Can't update index '{index_name}'.",
                    reason="No index with that name registered.",
                )
            tsk = await index._create_update_tasks()

            if tsk:
                tasks.add_task(tsk)

        await self.run_async_tasks(tasks, subtopic="update_indexes")

        # await tasks.run_async()

    async def run_async_tasks(self, tasks: Tasks, subtopic: Optional[str] = None):

        twm: TaskWatchManager = AppEnvironment().get_global("task_watcher")
        # twm = TaskWatchManager(typistry=self._bring._tingistry_obj.typistry)
        tlc = {
            "type": "rich",
            "base_topics": [tasks.task_desc.topic],
            "console": console,
            "tasks": tasks,
        }

        if subtopic:

            if isinstance(tasks.task_desc, BringTaskDesc):
                tasks.task_desc.subtopic = subtopic

            for index, child in enumerate(tasks.children.values()):
                child.task_desc.subtopic = f"{subtopic}.{index}"

        wid = twm.add_watcher(tlc)
        tw: RichTaskWatcher = twm.get_watcher(wid)  # type: ignore

        progress = tw.progress

        with progress:
            await tasks.run_async()

        twm.remove_watcher(wid)

    async def get_pkg_map(self, *indexes) -> Mapping[str, Mapping[str, PkgTing]]:
        """Get all pkgs, per available (or requested) indexes."""

        if not indexes:
            idxs: Iterable[str] = self.index_ids
        else:
            idxs = list(indexes)

        ctxs = []
        for c in idxs:
            ctx = await self.get_index(c)
            if ctx is None:
                raise FrklException(
                    msg=f"Can't get packages for index '{c}.",
                    reason="No such index found.",
                )
            ctxs.append(ctx)

        pkg_map: Dict[str, Dict[str, PkgTing]] = {}

        async def get_pkgs(_index: BringIndexTing):

            pkgs = await _index.get_pkgs()
            for pkg in pkgs.values():
                pkg_map[_index.id][pkg.name] = pkg

        for index in ctxs:

            if index.name in pkg_map.keys():
                raise FrklException(
                    msg=f"Can't assemble packages for index '{index.name}'",
                    reason="Duplicate index name.",
                )
            pkg_map[index.id] = {}

        async with create_task_group() as tg:

            for index in ctxs:
                await tg.spawn(get_pkgs, index)

        return pkg_map

    async def get_alias_pkg_map(self, *indexes: str) -> Mapping[str, PkgTing]:

        pkg_map = await self.get_pkg_map(*indexes)

        result: Dict[str, PkgTing] = {}

        for index_name in sorted(pkg_map.keys()):

            index_map = pkg_map[index_name]
            for pkg_name in sorted(index_map.keys()):
                result[f"{index_name}.{pkg_name}"] = index_map[pkg_name]

        return result

    async def get_pkg_property_map(
        self,
        *value_names: str,
        indexes: Optional[Iterable[str]] = None,
        pkg_filter: Union[str, Iterable[str]] = None,
    ):

        if not indexes:
            indexes = self.index_ids

        alias_pkg_map = await self.get_alias_pkg_map(*indexes)

        if isinstance(pkg_filter, str):
            pkg_filter = [pkg_filter]

        if pkg_filter:
            raise NotImplementedError()

        result = {}

        async def add_pkg(_pkg_name: str, _pkg: PkgTing):

            values = await _pkg.get_values(*value_names)
            result[_pkg_name] = values

        async with create_task_group() as tg:
            for pkg_name, pkg in alias_pkg_map.items():

                await tg.spawn(add_pkg, pkg_name, pkg)

        return result

    async def get_pkg(
        self, name: str, index: Optional[str] = None, raise_exception: bool = False
    ) -> Optional[PkgTing]:

        if index and "." in name:
            raise ValueError(
                f"Can't get pkg '{name}' for index '{index}': either specify index name, or use namespaced pkg name, not both."
            )

        elif "." in name:
            tokens = name.rsplit(".", maxsplit=1)
            _index_name: Optional[str] = tokens[0]
            _pkg_name = tokens[1]
            # _full_name = f"{_index_name}.{_pkg_name}"
        else:
            _pkg_name = name

            _index_name = index
            if index is None:
                _index_name = await self.get_default_index()

            if _index_name is None:
                for id_n in self.index_ids:
                    idx = await self.get_index(id_n)
                    pkg_names = await idx.pkg_names
                    if _pkg_name in pkg_names:
                        _index_name = idx.id
                        break

            if _index_name is None:
                if raise_exception:
                    raise FrklException(
                        f"No index provided, and none of the registered ones contains a pkg named '{_pkg_name}'."
                    )
                else:
                    return None

            if isinstance(not _index_name, str):
                raise NotImplementedError()

            # _full_name = f"{_index_name}.{name}"

        result_index: BringIndexTing = await self.get_index(_index_name)

        pkg = await result_index.get_pkg(_pkg_name, raise_exception=raise_exception)

        if pkg is None and raise_exception:
            raise FrklException(msg=f"Can't retrieve pkg '{name}': no such package")

        return pkg

    async def pkg_exists(self, pkg_name: str, pkg_index: Optional[str] = None):

        pkg = await self.get_pkg(name=pkg_name, index=pkg_index, raise_exception=False)

        return pkg is not None

    # def create_processor(self, processor_type: str) -> BringProcessor:
    #
    #     pm = self._tingistry_obj.get_plugin_manager(BringProcessor)
    #
    #     plugin_class = pm.get_plugin(processor_type, raise_exception=True)
    #     proc = plugin_class(self)
    #     return proc

    # async def process(self, processor_type: str, **input_vars) -> Mapping[str, Any]:
    #
    #     proc = self.create_processor(processor_type)
    #     proc.set_user_input(**input_vars)
    #
    #     result = await proc.process()
    #     return result

    async def create_target(self, target_type: str, **input_vars: Any) -> BringTarget:

        pm = self._tingistry_obj.get_plugin_manager(BringTarget)

        plugin_class = pm.get_plugin(target_type, raise_exception=True)
        target = plugin_class(self, **input_vars)

        return target
