# -*- coding: utf-8 -*-
from typing import Any, Dict, Iterable, Mapping, Optional

from bring.pkg import PkgTing
from bring.pkgs import Pkgs
from frtls.dicts import dict_merge
from frtls.tasks import FlattenParallelTasksAsync, SingleTaskAsync, TaskDesc, Tasks
from tings.makers import TingMaker
from tings.ting import SimpleTing
from tings.ting.inheriting import InheriTing


class BringContextTing(InheriTing, SimpleTing):
    def __init__(
        self, name: str, parent_key: str = "parent", meta: Dict[str, Any] = None
    ):

        self._parent_key = parent_key
        super().__init__(name=name, meta=meta)

        self._pkg_namespace = f"bring.contexts.{self.name}.pkgs"
        self._pkg_list = self._tingistry_obj.create_singleting(
            name=self._pkg_namespace,
            ting_class="pkgs",
            subscription_namespace=self._pkg_namespace,
            bring_context=self,
        )
        self._maker_config: Optional[Mapping[str, Any]] = None
        self._maker: Optional[TingMaker] = None

    def provides(self) -> Dict[str, str]:

        return {
            self._parent_key: "string?",
            "info": "dict",
            "pkgs": "ting",
            "config": "dict",
            "indexes": "list",
            "maker": "ting",
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

        if "config" in value_names:
            result["config"] = config

        if "info" in value_names:
            result["info"] = config.get("info", {})

        if "indexes" in value_names:
            result["indexes"] = config.get("indexes", [])

        if "maker" in value_names:
            result["maker"] = await self.get_maker(config)

        if "pkgs" in value_names:
            await self._ensure_pkgs(config)
            result["pkgs"] = self._pkg_list

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

        config: Mapping[str, Any] = await self.get_values(resolve=True)  # type: ignore
        parent = config[self._parent_key]
        if parent is None:
            parent = "(no parent)"
        return {"name": self.name, "parent": parent, "config": config["config"]}

    async def _ensure_pkgs(self, config: Dict[str, Any]) -> None:

        maker = await self.get_maker(config)
        await maker.sync()

    @property
    async def pkgs(self) -> Pkgs:

        vals: Mapping[str, Any] = await self.get_values(
            "pkgs", resolve=True
        )  # type: ignore
        return vals["pkgs"]

    async def get_pkg(self, name: str) -> PkgTing:

        pkgs = await self.pkgs
        return pkgs.get_pkg(name)

    @property
    async def pkg_names(self) -> Iterable[str]:

        pkgs = await self.pkgs
        return pkgs.get_pkg_names()

    async def _create_update_tasks(self) -> Tasks:

        task_desc = TaskDesc(
            name=f"metadata update {self.name}",
            msg=f"updating metadata for context '{self.name}'",
        )
        tasks = FlattenParallelTasksAsync(desc=task_desc)
        pkgs = await self.pkgs
        for pkg_name, pkg in pkgs.pkgs.items():
            t = SingleTaskAsync(pkg.update_metadata)
            t.task_desc.name = pkg_name
            t.task_desc.msg = f"updating metadata for pkg '{pkg_name}'"
            tasks.add_task(t)

        return tasks

    async def update(self, in_background: bool = False) -> None:
        """Updates pkg metadata."""

        if in_background:
            raise NotImplementedError()

        tasks = await self._create_update_tasks()

        await tasks.run_async()

    async def get_maker(self, config) -> TingMaker:

        # TODO: revisit typing here
        if self._maker is not None:
            if config != self._maker_config:
                raise Exception("Maker config changed, this is not supported yet...")
            return self._maker  # type: ignore

        maker_name = f"bring.pkg_maker.{self.name}"
        self._maker_config = config
        self._maker = self._tingistry_obj.create_singleting(
            name=maker_name,
            ting_class="text_file_ting_maker",
            prototing="bring.types.pkg",
            ting_name_strategy="basename_no_ext",
            ting_target_namespace=self._pkg_namespace,
            file_matchers=[{"type": "extension", "regex": ".*\\.bring$"}],
        )  # type: ignore

        indexes = config.get("indexes", [])
        for index in indexes:
            self._maker.add_base_paths(index)  # type: ignore

        return self._maker  # type: ignore
