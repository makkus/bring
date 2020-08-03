# -*- coding: utf-8 -*-
import logging
from abc import abstractmethod
from typing import Any, Dict, Iterable, Mapping, Optional

import arrow
from anyio import create_task_group
from bring.defaults import BRING_NO_METADATA_TIMESTAMP_MARKER
from bring.pkg_index.config import IndexConfig
from bring.pkg_index.pkg import PkgTing
from bring.utils.defaults import calculate_defaults
from frkl.common.async_utils import wrap_async_task
from frkl.common.exceptions import FrklException
from frkl.common.types import isinstance_or_subclass
from frkl.tasks.task import Task
from tings.exceptions import TingValueError
from tings.ting import SimpleTing, TingMeta
from tings.ting.inheriting import InheriTing


log = logging.getLogger("bring")


class BringIndexTing(InheriTing, SimpleTing):
    def __init__(self, name: str, meta: TingMeta):

        # self._parent_key: str = parent_key
        self._initialized: bool = False

        self._id: Optional[str] = None

        super().__init__(name=name, meta=meta)

    def _invalidate(self) -> None:

        pass

    def provides(self) -> Dict[str, str]:

        return {
            "id": "string",
            "uri": "string",
            "index_type_config": "dict",
            "index_type": "string",
            "index_file": "string?",
            "info": "dict",
            "config": "dict",
            "pkgs": "dict",
            "tags": "list",
            "labels": "dict",
            "defaults": "dict",
            "metadata_timestamp": "string",
        }

    def requires(self) -> Dict[str, str]:

        return {"config": "any"}

    @property
    def id(self) -> str:

        if self._id is None:
            self._id = wrap_async_task(self.get_value, "id")
        return self._id

    async def retrieve(self, *value_names: str, **requirements) -> Dict[str, Any]:

        result: Dict[str, Any] = {}

        config: IndexConfig = requirements["config"]
        if not isinstance_or_subclass(config, IndexConfig):
            raise FrklException(
                f"Can't process index {self.name}",
                reason=f"Invalid index config type: {type(config)}",
            )

        self._id = config.id

        if not self._initialized:
            await self.init(config)
            self._initialized = True

        if "config" in value_names:
            result["config"] = config.to_dict()

        if "id" in value_names:
            result["id"] = self._id

        if "index_type" in value_names:
            result["index_type"] = config.index_type

        if "index_file" in value_names:
            result["index_file"] = config.index_file

        if "uri" in value_names:
            result["uri"] = await self.get_uri()

        if "index_type_config" in value_names:
            result["index_type_config"] = config.index_type_config

        if "defaults" in value_names:

            _defaults = calculate_defaults(
                typistry=self._tingistry_obj.typistry, data=config.defaults
            )
            result["defaults"] = _defaults

        if "info" in value_names:
            result["info"] = config.info

        if "labels" in value_names:
            result["labels"] = config.labels

        if "tags" in value_names:
            result["tags"] = config.tags

        if "pkgs" in value_names:
            # await self._ensure_pkgs(config)
            try:
                result["pkgs"] = await self._get_pkgs()
            except Exception as e:
                log.debug(
                    f"Error retrieving packages for index '{self.full_name}'.",
                    exc_info=True,
                )
                result["pkgs"] = TingValueError(
                    e, msg=f"Can't retrieve packages for index '{self.id}'."
                )

        if "metadata_timestamp" in value_names:
            result["metadata_timestamp"] = await self.get_metadata_timestamp()

        return result

    async def get_index_defaults(self):

        return await self.get_value("defaults")

    async def get_info(self) -> Dict[str, Any]:

        vals: Mapping[str, Any] = await self.get_values(resolve=True)  # type: ignore

        slug = vals["info"].get("slug", "no description available")
        return {"name": self.name, "slug": slug}

    async def get_pkgs(
        self, update: bool = False, raise_exception: bool = True
    ) -> Mapping[str, PkgTing]:

        if update:
            await self.update()

        pkgs = await self.get_value("pkgs")

        if raise_exception and isinstance_or_subclass(pkgs, Exception):
            raise pkgs
        return pkgs

    @abstractmethod
    async def _get_pkgs(self) -> Mapping[str, PkgTing]:
        pass

    @abstractmethod
    async def get_uri(self) -> str:
        pass

    @abstractmethod
    async def init(self, config: IndexConfig):

        pass

    @abstractmethod
    async def _create_update_tasks(self) -> Optional[Task]:
        raise NotImplementedError()

    async def get_metadata_timestamp(self, return_format: str = "default") -> str:

        mts = await self._get_metadata_timestamp()
        if not mts:
            if return_format == "default":
                return BRING_NO_METADATA_TIMESTAMP_MARKER
            elif return_format == "human":
                return "unknown"
        else:
            if return_format == "default":
                return mts
            elif return_format == "human":
                age = arrow.get(mts)
                return age.humanize()

        raise Exception(
            f"Invalid return format '{return_format}', this is a bug. Allowed: {', '.join(['default', 'human'])}"
        )

    async def _get_metadata_timestamp(self) -> Optional[str]:

        return None

    async def get_pkg(
        self, name: str, raise_exception: bool = True
    ) -> Optional[PkgTing]:
        pkgs = await self.get_pkgs()

        pkg = pkgs.get(name, None)

        if pkg is None and raise_exception:
            pkg_names = await self.pkg_names
            if "." not in name:
                _t = " default"
                solution = f"Specify an index name and/or make sure the package name is correct, available packages: {', '.join(pkg_names)}."
            else:
                solution = f"Make sure the package name is correct, available packages: {', '.join(pkg_names)}."
            raise FrklException(
                msg=f"Can't retrieve package '{name}' from{_t} index '{self.name}'.",
                reason="No package with that name available.",
                solution=solution,
            )
        elif isinstance_or_subclass(pkg, Exception) and raise_exception:
            raise pkg  # type: ignore
        elif isinstance_or_subclass(pkg, Exception):
            return None

        return pkg

    @property
    async def pkg_names(self) -> Iterable[str]:

        pkgs = await self.get_pkgs()
        return pkgs.keys()

    async def update(self, in_background: bool = False) -> None:
        """Updates pkg metadata."""

        if in_background:
            raise NotImplementedError()

        tasks = await self._create_update_tasks()
        if tasks is not None:
            await tasks.run_async()
        else:
            log.info(f"Index '{self.name}' does not support updates, doing nothing")

    async def get_all_pkg_values(self, *value_names) -> Dict[str, Dict]:

        result = {}

        async def get_value(_pkg, _vn):
            _vals = await _pkg.get_values(*_vn)
            result[_pkg.name] = _vals

        async with create_task_group() as tg:
            pkgs = await self.get_pkgs()
            for pkg in pkgs.values():
                await tg.spawn(get_value, pkg, value_names)

        return result

    async def export_index(self, update: bool = True) -> Mapping[str, Any]:

        if update:
            await self.update()

        timestamp = await self.get_metadata_timestamp()

        all_values = await self.get_all_pkg_values(
            "source", "metadata", "aliases", "info", "labels", "tags"
        )

        _all_values: Dict[str, Any] = dict(all_values)
        # config = await self.get_values()
        # config_dict = await self.get_value("config")
        # config.pop("auto_id", None)
        # config.pop("id", None)
        # config.pop("index_type", None)
        # config.pop("index_config", None)
        # _all_values["_bring_index_config"] = config_dict

        _all_values["_bring_metadata_timestamp"] = timestamp

        return _all_values
