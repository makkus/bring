# -*- coding: utf-8 -*-

"""Main module."""
import os
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Type, Union

from anyio import Lock, create_lock, create_task_group
from bring.config.bring_config import BringConfig
from bring.defaults import BRINGISTRY_INIT, BRING_WORKSPACE_FOLDER
from bring.mogrify import Transmogritory
from bring.pkg_index import BringIndexTing
from bring.pkg_index.index_config import BringIndexConfig
from bring.pkg_index.pkg import PkgTing
from bring.utils import BringTaskDesc
from frtls.args.hive import ArgHive
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.tasks import SerialTasksAsync
from tings.ting import SimpleTing, TingMeta
from tings.tingistry import Tingistry


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
        if self._bring_config is not None:
            self._bring_config.set_bring(self)

        self._indexes: Dict[str, BringIndexTing] = {}
        self._all_indexes_created: bool = False

    async def _get_index_lock(self) -> Lock:

        if self._index_lock is None:
            self._index_lock = create_lock()
        return self._index_lock

    @property
    def config(self) -> BringConfig:

        if self._bring_config is None:
            self._bring_config = BringConfig(tingistry=self._tingistry_obj)
            self._bring_config.set_bring(self)

        return self._bring_config

    def _invalidate(self):

        self._indexes = {}
        self._all_indexes_created = False

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

    async def _create_all_indexes(self):

        async with await self._get_index_lock():

            if self._all_indexes_created:
                return

            async def create_index(_index_config: BringIndexConfig):
                ctx = await _index_config.get_index()
                self._indexes[ctx.name] = ctx

            async with create_task_group() as tg:
                all_index_configs = await self.config.get_all_index_configs()
                for index_name, index_config in all_index_configs.items():
                    if index_name not in self._indexes.keys():
                        await tg.spawn(create_index, index_config)

            self._all_indexes_created = True

    @property
    async def indexes(self) -> Mapping[str, BringIndexTing]:

        await self._create_all_indexes()
        return self._indexes

    @property
    async def index_names(self) -> Iterable[str]:

        all_index_configs = await self.config.get_all_index_configs()
        return all_index_configs.keys()

    async def get_index(
        self, index_name: Optional[str] = None, raise_exception=True
    ) -> Optional[BringIndexTing]:

        if index_name is None:
            index_name = await self.config.get_default_index_name()

        # indexes = await self.indexes
        # idx = indexes.get(index_name)
        async with await self._get_index_lock():
            idx = self._indexes.get(index_name, None)

            if idx is not None:
                return idx

            index_config: BringIndexConfig = await self.config.get_index_config(  # type: ignore
                index_name=index_name, raise_exception=raise_exception
            )

            if index_config is None:

                if raise_exception:
                    raise FrklException(
                        msg=f"Can't access bring index '{index_name}'.",
                        reason="No index with that name.",
                        solution=f"Create index, or choose one of the existing ones: {', '.join(await self.index_names)}",
                    )
                else:
                    return None

            idx = await index_config.get_index()
            self._indexes[index_name] = idx

        return idx

    async def update(self, index_names: Optional[Iterable[str]] = None):

        if index_names is None:
            index_names = await self.index_names

        td = BringTaskDesc(
            name="update metadata", msg="updating metadata for all indexes"
        )
        # tasks = ParallelTasksAsync(task_desc=td)
        tasks = SerialTasksAsync(task_desc=td)
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

        await tasks.run_async()

    async def get_pkg_map(
        self, indexes: Optional[Iterable[str]] = None
    ) -> Mapping[str, Mapping[str, PkgTing]]:
        """Get all pkgs, per available (or requested) indexes."""

        if indexes is None:
            ctxs: Iterable[BringIndexTing] = (await self.indexes).values()
        else:
            ctxs = []
            for c in indexes:
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
                pkg_map[_index.name][pkg.name] = pkg

        for index in ctxs:

            if index.name in pkg_map.keys():
                raise FrklException(
                    msg=f"Can't assemble packages for index '{index.name}'",
                    reason="Duplicate index name.",
                )
            pkg_map[index.name] = {}

        async with create_task_group() as tg:

            for index in ctxs:
                await tg.spawn(get_pkgs, index)

        return pkg_map

    async def get_alias_pkg_map(
        self,
        indexes: Optional[Iterable[str]] = None,
        add_default_index_pkg_names: bool = False,
    ) -> Mapping[str, PkgTing]:

        pkg_map = await self.get_pkg_map(indexes=indexes)

        result: Dict[str, PkgTing] = {}
        if add_default_index_pkg_names:

            default_index_name = await self.config.get_default_index_name()
            pkgs = pkg_map.get(default_index_name, {})

            for pkg_name in sorted(pkgs.keys()):
                if pkg_name not in result.keys():
                    result[pkg_name] = pkgs[pkg_name]

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

        alias_pkg_map = await self.get_alias_pkg_map(indexes=indexes)

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

    async def get_all_pkgs(
        self, indexes: Optional[Iterable[str]] = None
    ) -> Iterable[PkgTing]:

        pkg_map = await self.get_pkg_map(indexes=indexes)

        result = []
        for index_map in pkg_map.values():
            for pkg in index_map.values():
                result.append(pkg)

        return result

    # def create_pkg_plugin(self, plugin: str, pkg: PkgTing, pkg_include: Optional[Iterable[str]]=None, **pkg_vars: Any) -> BringPlugin:
    #
    #     if pkg_vars is None:
    #         pkg_vars = {}
    #
    #     _plugin = TemplatePlugin(bring=self, pkg=pkg, pkg_include=pkg_include, **pkg_vars)
    #
    #     return _plugin

    async def get_pkg(
        self, name: str, index: Optional[str] = None, raise_exception: bool = False
    ) -> Optional[PkgTing]:

        if index and "." in name:
            raise ValueError(
                f"Can't get pkg '{name}' for index '{index}': either specify index name, or use namespaced pkg name, not both."
            )

        elif "." in name:
            tokens = name.split(".")
            if len(tokens) != 2:
                raise ValueError(
                    f"Invalid pkg name: {name}, needs to be format '[index_name.]pkg_name'"
                )
            _index_name: Optional[str] = tokens[0]
            _pkg_name = name
        else:
            _index_name = index
            if _index_name:
                _pkg_name = f"{_index_name}.{name}"
            else:
                _pkg_name = name

        if _index_name:
            pkgs = await self.get_alias_pkg_map(
                indexes=[_index_name], add_default_index_pkg_names=True
            )
        else:
            pkgs = await self.get_alias_pkg_map(add_default_index_pkg_names=True)

        pkg = pkgs.get(_pkg_name, None)

        # vals = await pkg.get_values()

        if pkg is None and raise_exception:
            raise FrklException(msg=f"Can't retrieve pkg '{name}': no such package")

        return pkg

    async def pkg_exists(self, pkg_name: str, pkg_index: Optional[str] = None):

        pkg = await self.get_pkg(name=pkg_name, index=pkg_index, raise_exception=False)

        return pkg is not None

    # async def find_pkg(
    #     self, pkg_name: str, indexes: Optional[Iterable[str]] = None
    # ) -> PkgTing:
    #     """Finds one pkg with the specified name in all the available/specified indexes.
    #
    #     If more than one package is found, and if 'indexes' are provided, those are looked up in the order provided
    #     to find the first match. If not indexes are provided, first the default indexes are searched, then the
    #     extra ones. In this case, the result is not 100% predictable, as the order of those indexes might vary
    #     from invocation to invocation.
    #
    #     Args:
    #         - *pkg_name*: the package name
    #         - *indexes*: the indexes to look in (or all available ones, if set to 'None')
    #
    #     """
    #
    #     pkgs = await self.find_pkgs(pkg_name=pkg_name, indexes=indexes)
    #
    #     if len(pkgs) == 1:
    #         return pkgs[0]
    #
    #     if indexes is None:
    #         _indexes: List[BringIndexTing] = []
    #         for cc in await self.get_index_configs():
    #             n = cc["name"]
    #             ctx = await self.get_index(n)
    #             _indexes.append(ctx)
    #     else:
    #         _indexes = []
    #         # TODO: make this parallel
    #         for c in indexes:
    #             ctx_2 = await self.get_index(c)
    #             if ctx_2 is None:
    #                 raise FrklException(
    #                     msg=f"Can't search for pkg '{pkg_name}'.",
    #                     reason=f"Requested index '{c}' not available.",
    #                 )
    #             _indexes.append(ctx_2)
    #
    #     for ctx in _indexes:
    #
    #         for pkg in pkgs:
    #             if pkg.bring_index == ctx:
    #                 return pkg
    #
    #     raise FrklException(
    #         msg=f"Can't find pkg '{pkg_name}' in the available/specified indexes."
    #     )
    #
    # async def find_pkgs(
    #     self, pkg_name: str, indexes: Optional[Iterable[str]] = None
    # ) -> List[PkgTing]:
    #
    #     pkgs: List[PkgTing] = []
    #
    #     async def find_pkg(_index: BringIndexTing, _pkg_name: str):
    #
    #         _pkgs = await _index.get_pkgs()
    #         _pkg = _pkgs.get(_pkg_name, None)
    #         if _pkg is not None:
    #             pkgs.append(_pkg)
    #
    #     async with create_task_group() as tg:
    #         if indexes is None:
    #             ctxs: Iterable[BringIndexTing] = (await self.indexes).values()
    #         else:
    #             ctxs = []
    #             for c in indexes:
    #                 ctx = await self.get_index(c)
    #                 if ctx is None:
    #                     raise FrklException(
    #                         msg=f"Can't find pkgs with name '{pkg_name}'.",
    #                         reason=f"Requested index '{c}' not available.",
    #                     )
    #                 ctxs.append(ctx)
    #
    #         for index in ctxs:
    #             await tg.spawn(find_pkg, index, pkg_name)
    #
    #     return pkgs

    async def get_defaults(self) -> Mapping[str, Any]:

        config = await self.config.get_config_dict()

        return config["defaults"]

    async def get_default_vars(self) -> Mapping[str, Any]:

        config = await self.get_defaults()

        return config["vars"]
