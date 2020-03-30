# -*- coding: utf-8 -*-

"""Main module."""
import os
import threading
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Type,
    Union,
)

from anyio import create_task_group
from bring.config import FolderConfigProfilesTing
from bring.context import (
    BringContextTing,
    BringDynamicContextTing,
    BringStaticContextTing,
)
from bring.defaults import (
    BRINGISTRY_CONFIG,
    BRING_CONTEXT_NAMESPACE,
    BRING_WORKSPACE_FOLDER,
)
from bring.mogrify import Transmogritory
from bring.pkg import PkgTing
from bring.utils import BringTaskDesc
from bring.utils.contexts import validate_context_name
from frtls.args.hive import ArgHive
from frtls.async_helpers import wrap_async_task
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.formats.input_formats import INPUT_FILE_TYPE, determine_input_file_type
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

        prototings: Iterable[Mapping] = BRINGISTRY_CONFIG["prototings"]  # type: ignore
        tings: Iterable[Mapping] = BRINGISTRY_CONFIG["tings"]  # type: ignore
        modules: Iterable[str] = BRINGISTRY_CONFIG["modules"]  # type: ignore
        classes: Iterable[Union[Type, str]] = BRINGISTRY_CONFIG[  # type: ignore
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
        self._init_lock = threading.Lock()

        self._config_profiles: FolderConfigProfilesTing = self._tingistry_obj.get_ting(  # type: ignore
            "bring.config_profiles"
        )
        # self._dynamic_context_maker: Optional[TextFileTingMaker] = None

        # config & other mutable attributes
        self._config = "default"
        self._config_dict: Optional[Mapping[str, Any]] = None

        self._context_configs: Optional[List[Mapping[str, Any]]] = None
        self._extra_context_configs: List[Mapping[str, Any]] = []
        self._contexts: Dict[str, BringContextTing] = {}
        self._default_context: Optional[str] = None

        # self._default_contexts: Dict[str, BringStaticContextTing] = {}
        # self._extra_contexts: Dict[str, BringContextTing] = {}
        self._all_contexts_created: bool = False

    def set_config(self, config_profile: str):

        self._config = config_profile
        self._contexts = {}
        self._config_dict = None
        self.invalidate()

    async def add_extra_context(self, name: str, **config: Any):

        cc = await self._get_context_config(name)
        if cc is not None:
            raise FrklException(
                msg=f"Can't create context '{name}'.", reason="Name already registered"
            )

        c = dict(config)
        c["name"] = name
        self._extra_context_configs.append(c)

    async def get_config_dict(self) -> Mapping[str, Any]:

        if self._config_dict is not None:
            return self._config_dict

        self._config_profiles.input.set_values(profile_name=self._config)
        self._config_dict = await self._config_profiles.get_value(  # type: ignore
            "config"
        )

        return self._config_dict

    async def get_context_configs(self) -> Iterable[Mapping[str, Any]]:

        if self._context_configs is not None:
            return self._context_configs + self._extra_context_configs

        config = await self.get_config_dict()
        self._context_configs = config["contexts"]
        self._default_context = config.get("default_context", None)
        if self._default_context is None:
            self._default_context = self._context_configs[0]["name"]

        return self._context_configs + self._extra_context_configs

    @property
    def default_context_name(self) -> str:

        if self._default_context is None:
            wrap_async_task(self.get_context_configs)  # noqa

        return self._default_context  # type: ignore

    @property
    def typistry(self):

        return self._tingistry_obj.typistry

    @property
    def arg_hive(self) -> ArgHive:

        return self._tingistry_obj.arg_hive

    # @property
    # def dynamic_context_maker(self) -> TextFileTingMaker:
    #
    #     if self._dynamic_context_maker is not None:
    #         return self._dynamic_context_maker
    #
    #     self._dynamic_context_maker = self._tingistry_obj.create_ting(  # type: ignore
    #         "bring.types.config_file_context_maker", "bring.context_maker"
    #     )
    #     self._dynamic_context_maker.add_base_paths(  # type: ignore
    #         BRING_CONTEXTS_FOLDER
    #     )  # type: ignore
    #     return self._dynamic_context_maker  # type: ignore

    def provides(self) -> Mapping[str, str]:

        return {}

    def requires(self) -> Mapping[str, str]:

        return {}

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        return {}

    def _create_all_contexts_sync(self):
        if self._all_contexts_created:
            return

        wrap_async_task(self._create_all_contexts, _raise_exception=True)

    async def _create_all_contexts(self):

        with self._init_lock:
            if self._all_contexts_created:
                return

            async def create_context(config: Mapping[str, Any]):
                ctx = await self.create_context(**config)
                self._contexts[config["name"]] = ctx

            async with create_task_group() as tg:
                for c in await self.get_context_configs():

                    if c["name"] not in self._contexts.keys():
                        await tg.spawn(create_context, c)

            self._all_contexts_created = True

    async def create_context(self, name: str, **config: Any) -> BringContextTing:

        context_type = config.pop("type", "auto")

        if context_type == "auto":
            raise NotImplementedError()

        if context_type == "folder":
            folder = config.get("folder", None)
            if folder is None:
                raise FrklException(
                    msg=f"Can't create bring context '{name}' from folder.",
                    reason="'folder' config value missing.",
                )

            ctx: BringContextTing = await self.create_context_from_folder(
                context_name=name, folder=folder
            )

        elif context_type == "index":

            index_file = config.get("index_file", None)
            if index_file is None:
                raise FrklException(
                    msg=f"Can't create bring context '{name}' from index.",
                    reason="'index_file' config value missing.",
                )

            ctx = await self.create_context_from_index(
                context_name=name, index_file=index_file
            )

        else:
            raise FrklException(
                msg=f"Can't create bring context '{name}'.",
                reason=f"Context type '{context_type}' not supported.",
            )

        return ctx

    async def create_context_from_index(
        self, context_name: str, index_file: Union[str, Path]
    ) -> BringStaticContextTing:

        if self._contexts.get(context_name, None) is not None:
            raise FrklException(
                msg=f"Can't add context '{context_name}'.",
                reason="Default context with that name already exists.",
            )

        ctx: BringStaticContextTing = self._tingistry_obj.create_ting(  # type: ignore
            "bring.types.contexts.default_context",
            f"{BRING_CONTEXT_NAMESPACE}.{context_name}",
        )

        ctx.input.set_values(ting_dict={"indexes": [index_file]})
        await ctx.get_values("config")

        return ctx

    async def create_context_from_folder(
        self, context_name: str, folder: Union[str, Path]
    ) -> BringDynamicContextTing:

        if self._contexts.get(context_name, None) is not None:
            raise FrklException(
                msg=f"Can't add context '{context_name}'.",
                reason="Default context with that name already exists.",
            )

        input_type = determine_input_file_type(folder)

        # if input_type == INPUT_FILE_TYPE.git_repo:
        #     git_url = expand_git_url(path, DEFAULT_URL_ABBREVIATIONS_GIT_REPO)
        #     _path = await ensure_repo_cloned(git_url)
        if input_type == INPUT_FILE_TYPE.local_dir:
            if isinstance(folder, Path):
                _path: str = os.path.realpath(folder.resolve().as_posix())
            else:
                _path = os.path.realpath(os.path.expanduser(folder))
        else:
            raise FrklException(
                msg=f"Can't add context for: {folder}.",
                reason=f"Invalid input file type {input_type}.",
            )

        validate_context_name(context_name)

        ctx: BringDynamicContextTing = self._tingistry_obj.create_ting(  # type: ignore
            "bring_dynamic_context_ting", f"{BRING_CONTEXT_NAMESPACE}.{context_name}"
        )
        indexes = [_path]
        ctx.input.set_values(  # type: ignore
            ting_dict={"indexes": indexes}
        )

        await ctx.get_values("config")

        return ctx

    @property
    def contexts(self) -> Mapping[str, BringContextTing]:

        self._create_all_contexts_sync()
        return self._contexts

    async def _get_context_config(
        self, context_name: str
    ) -> Optional[Mapping[str, Any]]:

        cc = await self.get_context_configs()
        for c in cc:
            if c["name"] == context_name:
                return c

        for c in self._extra_context_configs:
            if c["name"] == context_name:
                return c

        return None

    def get_context(
        self, context_name: Optional[str] = None, raise_exception=True
    ) -> Optional[BringContextTing]:

        if context_name is None:
            context_name = self.default_context_name

        ctx = self._contexts.get(context_name, None)

        if ctx is not None:
            return ctx

        context_config = wrap_async_task(self._get_context_config, context_name)

        if context_config is None:

            if raise_exception:
                raise FrklException(
                    msg=f"Can't access bring context '{context_name}'.",
                    reason=f"No context with that name.",
                    solution=f"Create context, or choose one of the existing ones: {', '.join(self.contexts.keys())}",
                )
            else:
                return None

        ctx = wrap_async_task(self.create_context, **context_config)
        self._contexts[context_name] = ctx

        return ctx

    async def update(self, context_names: Optional[Iterable[str]] = None):

        if context_names is None:
            context_names = self.contexts.keys()

        td = BringTaskDesc(
            name="update metadata", msg="updating metadata for all contexts"
        )
        # tasks = ParallelTasksAsync(task_desc=td)
        tasks = SerialTasksAsync(task_desc=td)
        for context_name in context_names:
            context = self.get_context(context_name)
            if context is None:
                raise FrklException(
                    msg=f"Can't update context '{context_name}'.",
                    reason="No context with that name registered.",
                )
            tsk = await context._create_update_tasks()

            if tsk:
                tasks.add_task(tsk)

        await tasks.run_async()

    async def get_all_pkgs(
        self, contexts: Optional[Iterable[str]] = None
    ) -> Iterable[PkgTing]:

        if contexts is None:
            ctxs: Iterable[BringContextTing] = self.contexts.values()
        else:
            ctxs = []
            for c in contexts:
                ctx = self.get_context(c)
                if ctx is None:
                    raise FrklException(
                        msg=f"Can't get packages for context '{c}.",
                        reason="No such context found.",
                    )
                ctxs.append(ctx)

        result = []

        async def get_pkgs(_context: BringContextTing):

            pkgs = await _context.get_pkgs()
            for pkg in pkgs.values():
                result.append(pkg)

        async with create_task_group() as tg:

            for context in ctxs:
                await tg.spawn(get_pkgs, context)

            return result

    async def find_pkg(
        self, pkg_name: str, contexts: Optional[Iterable[str]] = None
    ) -> PkgTing:
        """Finds one pkg with the specified name in all the available/specified contexts.

        If more than one package is found, and if 'contexts' are provided, those are looked up in the order provided
        to find the first match. If not contexts are provided, first the default contexts are searched, then the
        extra ones. In this case, the result is not 100% predictable, as the order of those contexts might vary
        from invocation to invocation.

        Args:
            - *pkg_name*: the package name
            - *contexts*: the contexts to look in (or all available ones, if set to 'None')

        """

        pkgs = await self.find_pkgs(pkg_name=pkg_name, contexts=contexts)

        if len(pkgs) == 1:
            return pkgs[0]

        if contexts is None:
            _contexts: List[BringContextTing] = []
            for cc in await self.get_context_configs():
                n = cc["name"]
                ctx = self.contexts[n]
                _contexts.append(ctx)
        else:
            _contexts = []
            # TODO: make this parallel
            for c in contexts:
                ctx_2 = self.get_context(c)
                if ctx_2 is None:
                    raise FrklException(
                        msg=f"Can't search for pkg '{pkg_name}'.",
                        reason=f"Requested context '{c}' not available.",
                    )
                _contexts.append(ctx_2)

        for ctx in _contexts:

            for pkg in pkgs:
                if pkg.bring_context == ctx:
                    return pkg

        raise FrklException(
            msg=f"Can't find pkg '{pkg_name}' in the available/specified contexts."
        )

    async def find_pkgs(
        self, pkg_name: str, contexts: Optional[Iterable[str]] = None
    ) -> List[PkgTing]:

        pkgs: List[PkgTing] = []

        async def find_pkg(_context: BringContextTing, _pkg_name: str):

            _pkgs = await _context.get_pkgs()
            _pkg = _pkgs.get(_pkg_name, None)
            if _pkg is not None:
                pkgs.append(_pkg)

        async with create_task_group() as tg:
            if contexts is None:
                ctxs: Iterable[BringContextTing] = self.contexts.values()
            else:
                ctxs = []
                for c in contexts:
                    ctx = self.get_context(c)
                    if ctx is None:
                        raise FrklException(
                            msg=f"Can't find pkgs with name '{pkg_name}'.",
                            reason=f"Requested context '{c}' not available.",
                        )
                    ctxs.append(ctx)

            for context in ctxs:
                await tg.spawn(find_pkg, context, pkg_name)

        return pkgs

    def install(self, pkgs):
        pass

    # async def get_all_pkgs(self) -> Dict[str, PkgTing]:
    #
    #     result = {}
    #     for context_name, context in self.contexts.items():
    #         pkgs = await context.get_pkgs()
    #         for pkg_name, pkg in pkgs.pkgs.items():
    #             result[f"{context_name}:{pkg_name}"] = pkg
    #
    #     return result
