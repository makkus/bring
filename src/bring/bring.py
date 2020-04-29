# -*- coding: utf-8 -*-

"""Main module."""
import os
import threading
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Type, Union

from anyio import create_task_group
from bring.config.bring_config import BringConfig, BringContextConfig
from bring.context import BringContextTing
from bring.defaults import BRINGISTRY_INIT, BRING_WORKSPACE_FOLDER
from bring.mogrify import Transmogritory
from bring.pkg import PkgTing
from bring.utils import BringTaskDesc
from frtls.args.hive import ArgHive
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.tasks import SerialTasksAsync
from tings.ting import SimpleTing
from tings.tingistry import Tingistry


DEFAULT_TRANSFORM_PROFILES = {
    "executable": [
        {"type": "file_filter", "exclude": ["*~", "~*"]},
        {"type": "set_mode", "config": {"set_executable": True, "set_readable": True}},
    ]
}


class Bring(SimpleTing):
    def __init__(self, name: str = None, meta: Optional[Mapping[str, Any]] = None):

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

        self._tingistry_obj: Tingistry = meta["tingistry"]

        self._tingistry_obj.add_module_paths(*modules)
        self._tingistry_obj.add_classes(*classes)

        if prototings:
            for pt in prototings:
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
        self.typistry.get_plugin_manager("pkg_resolver", plugin_config=env_conf)

        self._transmogritory = Transmogritory(self._tingistry_obj)
        self._context_lock = threading.Lock()

        self._bring_config: BringConfig = BringConfig(tingistry=self._tingistry_obj)
        self._bring_config.set_bring(self)

        self._contexts: Dict[str, BringContextTing] = {}
        self._all_contexts_created: bool = False

    @property
    def config(self):

        return self._bring_config

    def _invalidate(self):

        self._contexts = {}
        self._all_contexts_created = False

    @property
    def typistry(self):

        return self._tingistry_obj.typistry

    @property
    def arg_hive(self) -> ArgHive:

        return self._tingistry_obj.arg_hive

    def provides(self) -> Mapping[str, str]:

        return {}

    def requires(self) -> Mapping[str, str]:

        return {}

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        return {}

    async def _create_all_contexts(self):

        with self._context_lock:

            if self._all_contexts_created:
                return

            async def create_context(_context_config: BringContextConfig):
                ctx = await _context_config.get_context()
                self._contexts[ctx.name] = ctx

            async with create_task_group() as tg:
                all_context_configs = await self._bring_config.get_all_context_configs()
                for context_name, context_config in all_context_configs.items():

                    if context_name not in self._contexts.keys():
                        await tg.spawn(create_context, context_config)

            self._all_contexts_created = True

    @property
    async def contexts(self) -> Mapping[str, BringContextTing]:

        await self._create_all_contexts()
        return self._contexts

    @property
    async def context_names(self) -> Iterable[str]:

        all_context_configs = await self._bring_config.get_all_context_configs()
        return all_context_configs.keys()

    async def get_context(
        self, context_name: Optional[str] = None, raise_exception=True
    ) -> Optional[BringContextTing]:

        if context_name is None:
            context_name = await self._bring_config.get_default_context_name()

        with self._context_lock:
            ctx = self._contexts.get(context_name, None)

            if ctx is not None:
                return ctx

            context_config: BringContextConfig = await self._bring_config.get_context_config(  # type: ignore
                context_name=context_name, raise_exception=raise_exception
            )

            if context_config is None:

                if raise_exception:
                    raise FrklException(
                        msg=f"Can't access bring context '{context_name}'.",
                        reason="No context with that name.",
                        solution=f"Create context, or choose one of the existing ones: {', '.join(await self.context_names)}",
                    )
                else:
                    return None

            ctx = await context_config.get_context()
            self._contexts[context_name] = ctx

            return ctx

    async def update(self, context_names: Optional[Iterable[str]] = None):

        if context_names is None:
            context_names = await self.context_names

        td = BringTaskDesc(
            name="update metadata", msg="updating metadata for all contexts"
        )
        # tasks = ParallelTasksAsync(task_desc=td)
        tasks = SerialTasksAsync(task_desc=td)
        for context_name in context_names:
            context = await self.get_context(context_name)
            if context is None:
                raise FrklException(
                    msg=f"Can't update context '{context_name}'.",
                    reason="No context with that name registered.",
                )
            tsk = await context._create_update_tasks()

            if tsk:
                tasks.add_task(tsk)

        await tasks.run_async()

    async def get_pkg_map(
        self, contexts: Optional[Iterable[str]] = None
    ) -> Mapping[str, Mapping[str, PkgTing]]:
        """Get all pkgs, per available (or requested) contexts."""

        if contexts is None:
            ctxs: Iterable[BringContextTing] = (await self.contexts).values()
        else:
            ctxs = []
            for c in contexts:
                ctx = await self.get_context(c)
                if ctx is None:
                    raise FrklException(
                        msg=f"Can't get packages for context '{c}.",
                        reason="No such context found.",
                    )
                ctxs.append(ctx)

        pkg_map: Dict[str, Dict[str, PkgTing]] = {}

        async def get_pkgs(_context: BringContextTing):

            pkgs = await _context.get_pkgs()
            for pkg in pkgs.values():
                pkg_map[_context.name][pkg.name] = pkg

        for context in ctxs:

            if context.name in pkg_map.keys():
                raise FrklException(
                    msg=f"Can't assemble packages for context '{context.name}'",
                    reason="Duplicate context name.",
                )
            pkg_map[context.name] = {}

        async with create_task_group() as tg:

            for context in ctxs:
                await tg.spawn(get_pkgs, context)

        return pkg_map

    async def get_alias_pkg_map(
        self,
        contexts: Optional[Iterable[str]] = None,
        add_default_context_pkg_names: bool = False,
    ) -> Mapping[str, PkgTing]:

        pkg_map = await self.get_pkg_map(contexts=contexts)

        result: Dict[str, PkgTing] = {}
        if add_default_context_pkg_names:

            default_context_name = await self.config.get_default_context_name()
            pkgs = pkg_map.get(default_context_name, {})

            for pkg_name in sorted(pkgs.keys()):
                if pkg_name not in result.keys():
                    result[pkg_name] = pkgs[pkg_name]

        for context_name in sorted(pkg_map.keys()):

            context_map = pkg_map[context_name]
            for pkg_name in sorted(context_map.keys()):
                result[f"{context_name}.{pkg_name}"] = context_map[pkg_name]

        return result

    async def get_pkg_property_map(
        self,
        *value_names: str,
        contexts: Optional[Iterable[str]] = None,
        pkg_filter: Union[str, Iterable[str]] = None,
    ):

        alias_pkg_map = await self.get_alias_pkg_map(contexts=contexts)

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
        self, contexts: Optional[Iterable[str]] = None
    ) -> Iterable[PkgTing]:

        pkg_map = await self.get_pkg_map(contexts=contexts)

        result = []
        for context_map in pkg_map.values():
            for pkg in context_map.values():
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
        self, name: str, context: Optional[str] = None, raise_exception: bool = False
    ) -> Optional[PkgTing]:

        if context and "." in name:
            raise ValueError(
                f"Can't get pkg '{name}' for context '{context}': either specify context name, or use namespaced pkg name, not both."
            )

        elif "." in name:
            tokens = name.split(".")
            if len(tokens) != 2:
                raise ValueError(
                    f"Invalid pkg name: {name}, needs to be format '[context_name.]pkg_name'"
                )
            _context_name: Optional[str] = tokens[0]
            _pkg_name = name
        else:
            _context_name = context
            if _context_name:
                _pkg_name = f"{_context_name}.{name}"
            else:
                _pkg_name = name

        if _context_name:
            pkgs = await self.get_alias_pkg_map(
                contexts=[_context_name], add_default_context_pkg_names=True
            )
        else:
            pkgs = await self.get_alias_pkg_map(add_default_context_pkg_names=True)

        pkg = pkgs.get(_pkg_name, None)
        if pkg is None and raise_exception:
            raise FrklException(msg=f"Can't retrieve pkg '{name}': no such package")

        return pkg

    async def pkg_exists(self, pkg_name: str, pkg_context: Optional[str] = None):

        pkg = await self.get_pkg(
            name=pkg_name, context=pkg_context, raise_exception=False
        )

        return pkg is not None

    # async def find_pkg(
    #     self, pkg_name: str, contexts: Optional[Iterable[str]] = None
    # ) -> PkgTing:
    #     """Finds one pkg with the specified name in all the available/specified contexts.
    #
    #     If more than one package is found, and if 'contexts' are provided, those are looked up in the order provided
    #     to find the first match. If not contexts are provided, first the default contexts are searched, then the
    #     extra ones. In this case, the result is not 100% predictable, as the order of those contexts might vary
    #     from invocation to invocation.
    #
    #     Args:
    #         - *pkg_name*: the package name
    #         - *contexts*: the contexts to look in (or all available ones, if set to 'None')
    #
    #     """
    #
    #     pkgs = await self.find_pkgs(pkg_name=pkg_name, contexts=contexts)
    #
    #     if len(pkgs) == 1:
    #         return pkgs[0]
    #
    #     if contexts is None:
    #         _contexts: List[BringContextTing] = []
    #         for cc in await self.get_context_configs():
    #             n = cc["name"]
    #             ctx = await self.get_context(n)
    #             _contexts.append(ctx)
    #     else:
    #         _contexts = []
    #         # TODO: make this parallel
    #         for c in contexts:
    #             ctx_2 = await self.get_context(c)
    #             if ctx_2 is None:
    #                 raise FrklException(
    #                     msg=f"Can't search for pkg '{pkg_name}'.",
    #                     reason=f"Requested context '{c}' not available.",
    #                 )
    #             _contexts.append(ctx_2)
    #
    #     for ctx in _contexts:
    #
    #         for pkg in pkgs:
    #             if pkg.bring_context == ctx:
    #                 return pkg
    #
    #     raise FrklException(
    #         msg=f"Can't find pkg '{pkg_name}' in the available/specified contexts."
    #     )
    #
    # async def find_pkgs(
    #     self, pkg_name: str, contexts: Optional[Iterable[str]] = None
    # ) -> List[PkgTing]:
    #
    #     pkgs: List[PkgTing] = []
    #
    #     async def find_pkg(_context: BringContextTing, _pkg_name: str):
    #
    #         _pkgs = await _context.get_pkgs()
    #         _pkg = _pkgs.get(_pkg_name, None)
    #         if _pkg is not None:
    #             pkgs.append(_pkg)
    #
    #     async with create_task_group() as tg:
    #         if contexts is None:
    #             ctxs: Iterable[BringContextTing] = (await self.contexts).values()
    #         else:
    #             ctxs = []
    #             for c in contexts:
    #                 ctx = await self.get_context(c)
    #                 if ctx is None:
    #                     raise FrklException(
    #                         msg=f"Can't find pkgs with name '{pkg_name}'.",
    #                         reason=f"Requested context '{c}' not available.",
    #                     )
    #                 ctxs.append(ctx)
    #
    #         for context in ctxs:
    #             await tg.spawn(find_pkg, context, pkg_name)
    #
    #     return pkgs

    async def get_defaults(self) -> Mapping[str, Any]:

        config = await self.config.get_config_dict()

        return config["defaults"]

    async def get_default_vars(self) -> Mapping[str, Any]:

        config = await self.get_defaults()

        return config["vars"]
