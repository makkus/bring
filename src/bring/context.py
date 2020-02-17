# -*- coding: utf-8 -*-
from typing import Any, Dict

from bring.pkgs import Pkgs
from bring.transform import TransformProfile
from frtls.dicts import dict_merge
from tings.makers import TingMaker
from tings.makers.file import TextFileTingMaker
from tings.ting import SimpleTing
from tings.ting.inheriting import InheriTing


class BringContextTing(InheriTing, SimpleTing):
    def __init__(
        self, name: str, parent_key: str = "parent", meta: Dict[str, Any] = None
    ):

        self._parent_key = parent_key
        super().__init__(name=name, meta=meta)

        ting_type_name = f"bring.types.pkgs.{self.name}"
        self._pkg_namespace = f"bring.pkgs.{self.name}"
        self.tingistry.register_ting_type(
            ting_type_name=ting_type_name,
            ting_class="pkgs",
            subscription_namespace=self._pkg_namespace,
        )
        self._pkg_list = self.tingistry.create_ting(
            ting_type=ting_type_name, ting_name=self._pkg_namespace
        )

    def provides(self) -> Dict[str, str]:

        return {
            self._parent_key: "string?",
            "pkgs": "ting",
            "config": "dict",
            "indexes": "list",
            "transformer": "ting",
            "maker": "ting",
        }

    def requires(self) -> Dict[str, str]:

        return {"dict": "dict"}

    async def retrieve(self, *value_names: str, **requirements) -> Dict[str, Any]:

        result = {}

        data = requirements["dict"]
        parent = data.get(self._parent_key, None)

        result[self._parent_key] = parent

        if "config" in requirements.keys():
            # still valid cache
            config = requirements["config"]
        else:
            config = await self._get_config(data)

        if "config" in value_names:
            result["config"] = config

        if "indexes" in value_names:
            result["indexes"] = config.get("indexes", [])

        if "transformer" in value_names:
            result["transformer"] = await self.get_transformer(config)

        if "maker" in value_names:
            result["maker"] = await self.get_maker(config)

        if "pkgs" in value_names:
            await self._ensure_pkgs(config)
            result["pkgs"] = self._pkg_list

        return result

    async def get_config(self) -> Dict[str, Any]:

        return await self.get_values("config")

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

        config = await self.get_values()
        parent = config[self._parent_key]
        if parent is None:
            parent = "(no parent)"
        return {"name": self.name, "parent": parent, "config": config["config"]}

    async def get_transformer(self, config) -> TransformProfile:

        transform_profile = self.tingistry.get_ting(f"bring.transform.{self.name}")
        if transform_profile is not None:
            return transform_profile

        transformers_conf = config.get(
            "transform", [{"type": "file_filter", "include": ["*", ".*"]}]
        )

        self.tingistry.register_ting_type(
            f"bring.types.transform.{self.name}",
            "transform_profile",
            transformers_config=transformers_conf,
        )
        transform_profile = self.tingistry.create_ting(
            ting_type=f"bring.types.transform.{self.name}",
            ting_name=f"bring.transform.{self.name}",
        )

        return transform_profile

    async def _ensure_pkgs(self, config: Dict[str, Any]) -> None:

        maker = await self.get_maker(config)
        await maker.sync()

    async def get_pkgs(self) -> Pkgs:

        vals = await self.get_values("pkgs")
        return vals["pkgs"]

    async def get_maker(self, config) -> TingMaker:

        maker = self.tingistry.get_ting(f"bring.pkg_maker.{self.name}")
        if maker is not None:
            return maker

        self.tingistry.register_ting_type(
            f"bring.types.pkg_maker.{self.name}",
            "text_file_ting_maker",
            ting_type="bring.types.pkg",
            ting_name_strategy="basename_no_ext",
            ting_target_namespace=self._pkg_namespace,
            file_matchers=[{"type": "extension", "regex": ".*\\.bring$"}],
        )

        maker: TextFileTingMaker = self.tingistry.create_ting(
            ting_type=f"bring.types.pkg_maker.{self.name}",
            ting_name=f"bring.pkg_maker.{self.name}",
        )

        indexes = config.get("indexes", [])
        for index in indexes:
            maker.add_base_paths(index)

        return maker
