# -*- coding: utf-8 -*-

"""Main module."""
import json
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

from anyio import aopen, create_task_group
from bring.config import FolderConfigProfilesTing
from bring.context import BringContextTing, BringStaticContextTing
from bring.defaults import (
    BRINGISTRY_CONFIG,
    BRING_CONTEXTS_FOLDER,
    BRING_DEFAULT_CONTEXTS_FOLDER,
    BRING_WORKSPACE_FOLDER,
    DYNAMIC_CONTEXT_SUBSCRIPTION_NAMESPACE,
)
from bring.mogrify import Transmogritory
from bring.pkg import PkgTing
from bring.utils import BringTaskDesc
from frtls.args.hive import ArgHive
from frtls.async_helpers import wrap_async_task
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.formats.input_formats import INPUT_FILE_TYPE, determine_input_file_type
from frtls.tasks import FlattenParallelTasksAsync
from tings.makers.file import TextFileTingMaker
from tings.ting import SimpleTing
from tings.ting.tings import SubscripTings
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
        self._dynamic_context_maker: Optional[TextFileTingMaker] = None

        # config & other mutable attributes
        self._config = "test"

        self._context_configs: List[Mapping[str, Any]] = []
        self._contexts: Dict[str, BringContextTing] = {}

        self._default_contexts: Dict[str, BringStaticContextTing] = {}
        self._extra_contexts: Dict[str, BringContextTing] = {}
        self._initialized = False

    def set_config(self, config_profile: str):

        self._config = config_profile
        self.invalidate()

    def _invalidate(self):

        self._contexts = None
        self._default_contexts: Dict[str, BringStaticContextTing] = {}
        self._extra_contexts: Dict[str, BringContextTing] = {}
        self._initialized = False

    async def get_config_dict(self) -> Mapping[str, Any]:

        self._config_profiles.input.set_values(profile_name=self._config)
        config: Mapping[str, Any] = await self._config_profiles.get_value("config")
        return config

    @property
    def typistry(self):

        return self._tingistry_obj.typistry

    @property
    def arg_hive(self) -> ArgHive:

        return self._tingistry_obj.arg_hive

    @property
    def dynamic_context_maker(self) -> TextFileTingMaker:

        if self._dynamic_context_maker is not None:
            return self._dynamic_context_maker

        self._dynamic_context_maker = self._tingistry_obj.create_ting(  # type: ignore
            "bring.types.config_file_context_maker", "bring.context_maker"
        )
        self._dynamic_context_maker.add_base_paths(  # type: ignore
            BRING_CONTEXTS_FOLDER
        )  # type: ignore
        return self._dynamic_context_maker  # type: ignore

    def _init_sync(self):
        if self._initialized:
            return

        wrap_async_task(self._init, _raise_exception=True)

    def provides(self) -> Mapping[str, str]:

        return {}

    def requires(self) -> Mapping[str, str]:

        return {}

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        return {}

    async def _init(self):

        with self._init_lock:
            if self._initialized:
                return

            self._transmogritory.plugin_manager

            await self.dynamic_context_maker.sync()

            async def add_default_context(_file_name: str):

                path = os.path.join(BRING_DEFAULT_CONTEXTS_FOLDER, _file_name)
                async with await aopen(path) as f:
                    content = await f.read()

                context_name = _file_name.split(".")[0]
                if context_name in self._default_contexts:
                    raise FrklException(
                        msg=f"Can't add context '{context_name}'.",
                        reason="Default context with that name already exists.",
                    )

                json_content: Mapping[str, Any] = json.loads(content)
                ctx: BringStaticContextTing = self._tingistry_obj.create_ting(  # type: ignore
                    "bring.types.contexts.default_context",
                    f"bring.contexts.default.{context_name}",
                )
                ctx.input.set_values(ting_dict=json_content)
                self._default_contexts[context_name] = ctx

                await ctx.get_values("config")

            contexts: SubscripTings = self._tingistry_obj.get_ting(  # type: ignore
                DYNAMIC_CONTEXT_SUBSCRIPTION_NAMESPACE
            )
            dynamic: Dict[str, BringContextTing] = {  # type: ignore
                x.split(".")[-1]: ctx
                for x, ctx in contexts.childs.items()  # type: ignore
            }

            async with create_task_group() as tg:
                for file_name in os.listdir(BRING_DEFAULT_CONTEXTS_FOLDER):
                    if not file_name.endswith(".context"):
                        continue
                    await tg.spawn(add_default_context, file_name)

                for context in dynamic.values():
                    await tg.spawn(context.get_values, "config")

            self._initialized = True

    def add_context(self, context_name: str, context: BringContextTing):

        self._extra_contexts[context_name] = context

    def add_context_from_folder(
        self, path: Union[Path, str], alias: str = None
    ) -> BringContextTing:

        input_type = determine_input_file_type(path)

        # if input_type == INPUT_FILE_TYPE.git_repo:
        #     git_url = expand_git_url(path, DEFAULT_URL_ABBREVIATIONS_GIT_REPO)
        #     _path = await ensure_repo_cloned(git_url)
        if input_type == INPUT_FILE_TYPE.local_dir:
            if isinstance(path, Path):
                _path: str = os.path.realpath(path.resolve().as_posix())
            else:
                _path = os.path.realpath(os.path.expanduser(path))
        else:
            raise FrklException(
                msg=f"Can't add context for: {path}.",
                reason=f"Invalid input file type {input_type}.",
            )

        if alias is None:
            _alias: str = _path
        else:
            _alias = alias

        ting_rel_name = _alias.replace(os.path.sep, ".")[1:]
        ting_rel_name = ting_rel_name.replace("..", ".")

        ctx: BringContextTing = self._tingistry_obj.create_ting(  # type: ignore
            "bring_dynamic_context_ting", f"bring.context.extra.{ting_rel_name}"
        )
        indexes = [path]
        ctx.input.set_values(  # type: ignore
            ting_dict={"indexes": indexes}
        )

        # await ctx.get_values("config")
        wrap_async_task(ctx.get_values, "config")
        self.add_context(_alias, ctx)

        return ctx

    @property
    def contexts(self) -> Mapping[str, BringContextTing]:

        self._init_sync()

        contexts: SubscripTings = self._tingistry_obj.get_ting(  # type: ignore
            DYNAMIC_CONTEXT_SUBSCRIPTION_NAMESPACE
        )
        result: Dict[str, BringContextTing] = {  # type: ignore
            x.split(".")[-1]: ctx for x, ctx in contexts.childs.items()  # type: ignore
        }

        result.update(self._extra_contexts)

        result.update(self._default_contexts)

        return result

    def get_context(self, context_name: str) -> BringContextTing:

        ctx = self.contexts.get(context_name, None)
        if ctx is None:
            raise FrklException(
                msg=f"Can't access bring context '{context_name}'.",
                reason=f"No context with that name.",
                solution=f"Create context, or choose one of the existing ones: {', '.join(self.contexts.keys())}",
            )

        return ctx

    async def update(self):

        await self._init()

        td = BringTaskDesc(
            name="update metadata", msg="updating metadata for all contexts"
        )
        tasks = FlattenParallelTasksAsync(desc=td)
        for context in self.contexts.values():
            t = await context._create_update_tasks()
            tasks.add_task(t)

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
            _contexts.extend(self._default_contexts.values())
            _contexts.extend(self._extra_contexts.values())
        else:
            _contexts = []
            for c in contexts:
                _contexts.append(self.get_context(c))

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
