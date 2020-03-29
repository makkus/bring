# -*- coding: utf-8 -*-
import json
import zlib
from abc import abstractmethod
from typing import Any, Dict, Iterable, List, Mapping, Optional

from anyio import create_task_group
from bring.defaults import BRING_CONTEXT_FILES_CACHE
from bring.pkg import PkgTing
from bring.pkgs import Pkgs
from bring.utils import BringTaskDesc
from frtls.dicts import dict_merge
from frtls.downloads import download_cached_binary_file_async
from frtls.exceptions import FrklException
from frtls.tasks import ParallelTasksAsync, SingleTaskAsync, Task
from tings.makers import TingMaker
from tings.ting import SimpleTing
from tings.ting.inheriting import InheriTing


class BringContextTing(InheriTing, SimpleTing):
    def __init__(
        self,
        name: str,
        parent_key: str = "parent",
        meta: Optional[Mapping[str, Any]] = None,
    ):

        self._parent_key: str = parent_key
        self._initialized: bool = False
        super().__init__(name=name, meta=meta)

    def provides(self) -> Dict[str, str]:

        return {
            self._parent_key: "string?",
            "info": "dict",
            "pkgs": "dict",
            "config": "dict",
        }

    def requires(self) -> Dict[str, str]:

        return {"ting_dict": "dict"}

    async def retrieve(self, *value_names: str, **requirements) -> Dict[str, Any]:

        result = {}

        data = requirements["ting_dict"]
        parent = data.get(self._parent_key, None)

        result[self._parent_key] = parent

        if "config" in requirements.keys():
            # still valid cache
            config = requirements["config"]
        else:
            config = await self._get_config(data)

        if not self._initialized:
            await self.init(config)
            self._initialized = True

        if "config" in value_names:
            result["config"] = config

        if "info" in value_names:
            result["info"] = config.get("info", {})

        if "pkgs" in value_names:
            # await self._ensure_pkgs(config)
            result["pkgs"] = await self.get_pkgs()

        return result

    async def get_config(self) -> Mapping[str, Any]:

        return await self.get_values("config", resolve=True)  # type: ignore

    async def _get_config(self, raw_config) -> Dict[str, Any]:

        parent = raw_config.get(self._parent_key, None)
        if not parent:
            return raw_config
        else:
            parent_vals = await self._get_values_from_ting(
                f"{self.namespace}.{parent}", "config"
            )
            config = parent_vals["config"]
            dict_merge(config, raw_config, copy_dct=False)
            return config

    async def get_info(self) -> Dict[str, Any]:

        vals: Mapping[str, Any] = await self.get_values(resolve=True)  # type: ignore

        config = vals["config"]
        parent = vals[self._parent_key]
        if parent is None:
            parent = "(no parent)"

        slug = config.get("info", {}).get("slug", "no description available")
        return {"name": self.name, "parent": parent, "slug": slug}

    @abstractmethod
    async def get_pkgs(self) -> Mapping[str, PkgTing]:

        pass

    @abstractmethod
    async def init(self, config: Mapping[str, Any]):

        pass

    async def get_pkg(self, name: str) -> PkgTing:

        pkgs = await self.get_pkgs()
        pkg = pkgs.get(name, None)

        if pkg is None:
            pkg_names = await self.pkg_names
            raise FrklException(
                msg=f"Can't retrieve package '{name}' from context '{self.name}'.",
                reason="No package with that name available.",
                solution=f"Make sure the package name is correct, available packages: {', '.join(pkg_names)}.",
            )

        return pkg

    @property
    async def pkg_names(self) -> Iterable[str]:

        pkgs = await self.get_pkgs()
        return pkgs.keys()

    @abstractmethod
    async def _create_update_tasks(self) -> Optional[Task]:
        raise NotImplementedError()

    async def update(self, in_background: bool = False) -> None:
        """Updates pkg metadata."""

        if in_background:
            raise NotImplementedError()

        tasks = await self._create_update_tasks()
        if tasks is not None:
            await tasks.run_async()

    async def get_all_pkg_values(self, *value_names) -> Dict[str, Dict]:

        result = {}

        async def get_value(pkg, vn):
            vals = await pkg.get_values(*vn)
            result[pkg.name] = vals

        async with create_task_group() as tg:
            pkgs = await self.get_pkgs()
            for pkg in pkgs.values():
                await tg.spawn(get_value, pkg, value_names)
                # break

        return result

    async def export_context(self) -> Mapping[str, Any]:

        all_values = await self.get_all_pkg_values(
            "source", "metadata", "aliases", "info", "labels", "tags"
        )

        return all_values


class BringStaticContextTing(BringContextTing):
    def __init__(
        self,
        name: str,
        parent_key: str = "parent",
        meta: Optional[Mapping[str, Any]] = None,
    ):
        self._urls: List[str] = []
        self._pkgs: Optional[Dict[str, PkgTing]] = None
        self._config: Optional[Mapping[str, Any]] = None
        super().__init__(name=name, parent_key=parent_key, meta=meta)

    def add_urls(self, *urls: str):

        self._urls.extend(urls)
        self.invalidate()

    async def _load_pkgs(self):

        self._pkgs.clear()

        async def add_index(index_url: str):

            update = False
            content = await download_cached_binary_file_async(
                url=index_url,
                update=update,
                cache_base=BRING_CONTEXT_FILES_CACHE,
                return_content=True,
            )

            json_string = zlib.decompress(content, 16 + zlib.MAX_WBITS)  # type: ignore

            data = json.loads(json_string)

            if self._pkgs is None:
                raise Exception("_pkgs variable not initialized yet, this is a bug")

            for pkg_name, pkg_data in data.items():

                if pkg_name in self._pkgs.keys():
                    raise FrklException(
                        msg=f"Can't add pkg '{pkg_name}'.",
                        reason=f"Package with that name already exists in context '{self.name}'.",
                    )

                ting: PkgTing = self._tingistry_obj.create_ting(  # type: ignore
                    "bring.types.static_pkg",
                    f"{self.full_name}.pkgs.{pkg_name}",  # type: ignore
                )
                ting.bring_context = self

                ting.input.set_values(**pkg_data)
                # ting._set_result(data)
                self._pkgs[pkg_name] = ting

        async with create_task_group() as tg:
            for url in self._urls:
                await tg.spawn(add_index, url)

    async def get_pkgs(self) -> Mapping[str, PkgTing]:

        if self._pkgs is None:
            self._pkgs = {}
            await self._load_pkgs()

        return self._pkgs

    async def _create_update_tasks(self) -> Optional[Task]:

        return None

    async def init(self, config: Mapping[str, Any]) -> None:

        self._config = config
        self.add_urls(*config["indexes"])


class BringDynamicContextTing(BringContextTing):
    def __init__(
        self,
        name: str,
        parent_key: str = "parent",
        meta: Optional[Mapping[str, Any]] = None,
    ):

        super().__init__(name=name, parent_key=parent_key, meta=meta)

        self._pkg_namespace = f"bring.contexts.{self.name}.pkgs"
        self._pkg_list: Pkgs = self._tingistry_obj.create_singleting(  # type: ignore
            name=self._pkg_namespace,
            ting_class="pkgs",
            subscription_namespace=self._pkg_namespace,
            bring_context=self,
        )
        self._maker_config: Optional[Mapping[str, Any]] = None
        self._maker: Optional[TingMaker] = None

    async def init(self, config: Mapping[str, Any]) -> None:

        maker = await self.get_maker(config)
        await maker.sync()

    async def get_pkgs(self) -> Mapping[str, PkgTing]:

        return self._pkg_list.pkgs

    async def _create_update_tasks(self) -> Optional[Task]:

        task_desc = BringTaskDesc(
            name=f"metadata update {self.name}",
            msg=f"updating metadata for context '{self.name}'",
        )
        tasks = ParallelTasksAsync(task_desc=task_desc)
        pkgs = await self.get_pkgs()
        for pkg_name, pkg in pkgs.items():
            td = BringTaskDesc(
                name=f"{pkg_name}",
                msg=f"updating metadata for pkg '{pkg_name}' (context: {self.name})",
            )
            t = SingleTaskAsync(pkg.update_metadata, task_desc=td, parent_task=tasks)
            tasks.add_task(t)

        return tasks

    async def get_maker(self, config) -> TingMaker:

        # TODO: revisit typing here
        if self._maker is not None:
            if config != self._maker_config:
                raise Exception("Maker config changed, this is not supported yet...")
            return self._maker  # type: ignore

        maker_name = f"bring.pkg_maker.{self.name}"
        self._maker_config = config
        self._maker = self._tingistry_obj.create_singleting(  # type: ignore
            name=maker_name,
            ting_class="text_file_ting_maker",
            prototing="bring.types.dynamic_pkg",
            ting_name_strategy="basename_no_ext",
            ting_target_namespace=self._pkg_namespace,
            file_matchers=[{"type": "extension", "regex": ".*\\.bring$"}],
        )

        indexes = config.get("indexes", [])
        for index in indexes:
            self._maker.add_base_paths(index)  # type: ignore

        return self._maker  # type: ignore
