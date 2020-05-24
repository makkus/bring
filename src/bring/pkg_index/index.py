# -*- coding: utf-8 -*-
import json
import logging
import os
import zlib
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Iterable, Mapping, Optional

import arrow
from anyio import aopen, create_task_group
from bring.defaults import BRING_INDEX_FILES_CACHE, BRING_NO_METADATA_TIMESTAMP_MARKER
from bring.pkg_index.pkg import PkgTing
from bring.utils.system_info import get_current_system_info
from frtls.async_helpers import wrap_async_task
from frtls.downloads import download_cached_binary_file_async
from frtls.exceptions import FrklException
from frtls.tasks import Task
from frtls.types.utils import is_instance_or_subclass
from tings.ting import SimpleTing, TingMeta
from tings.ting.inheriting import InheriTing


if TYPE_CHECKING:
    pass

log = logging.getLogger("bring")


async def retrieve_index_content(
    index_url: str, update: bool = False
) -> Mapping[str, Any]:

    if os.path.exists(index_url):
        async with await aopen(index_url, "rb") as f:
            content = await f.read()
    else:

        content = await download_cached_binary_file_async(
            url=index_url,
            update=update,
            cache_base=BRING_INDEX_FILES_CACHE,
            return_content=True,
        )

    json_string = zlib.decompress(content, 16 + zlib.MAX_WBITS)  # type: ignore

    data = json.loads(json_string)
    return data


class BringIndexTing(InheriTing, SimpleTing):
    def __init__(self, name: str, meta: TingMeta):

        # self._parent_key: str = parent_key
        self._initialized: bool = False

        self._id: Optional[str] = None
        super().__init__(name=name, meta=meta)

    def provides(self) -> Dict[str, str]:

        return {
            "id": "string",
            "uri": "string",
            "info": "dict",
            "pkgs": "dict",
            "tags": "list",
            "labels": "dict",
            "defaults": "dict",
            "metadata_timestamp": "string",
        }

    def requires(self) -> Dict[str, str]:

        return {
            "id": "string",
            "uri": "string",
            "info": "dict?",
            "defaults": "dict?",
            "labels": "dict?",
            "tags": "list?",
        }

    @property
    def id(self) -> str:

        if self._id is None:
            self._id = wrap_async_task(self.get_value, "id")
        return self._id

    async def retrieve(self, *value_names: str, **requirements) -> Dict[str, Any]:

        result: Dict[str, Any] = {}

        self._id = requirements["id"]
        if "id" in value_names:
            result["id"] = self._id

        uri = requirements["uri"]

        # if "config" in requirements.keys():
        #     # still valid cache
        #     config = requirements["config"]
        # else:
        #     config = await self._get_config(data)

        if not self._initialized:
            await self.init(uri)
            self._initialized = True

        if "uri" in value_names:
            result["uri"] = uri

        if "defaults" in value_names:
            defaults = requirements.get("defaults", {})
            if defaults is None:
                defaults = {}
            result["defaults"] = defaults

        if "info" in value_names:
            result["info"] = requirements.get("info", {})

        if "labels" in value_names:
            result["labels"] = requirements.get("labels", {})

        if "tags" in value_names:
            result["tags"] = requirements.get("tags", [])

        if "metadata_timestamp" in value_names:
            result["metadata_timestamp"] = await self.get_metadata_timestamp()

        if "pkgs" in value_names:
            # await self._ensure_pkgs(config)
            result["pkgs"] = await self._get_pkgs()

        return result

    async def get_index_defaults(self):

        return await self.get_value("defaults")

    async def get_info(self) -> Dict[str, Any]:

        vals: Mapping[str, Any] = await self.get_values(resolve=True)  # type: ignore

        slug = vals["info"].get("slug", "no description available")
        return {"name": self.name, "slug": slug}

    async def get_pkgs(self, update: bool = False) -> Mapping[str, PkgTing]:

        if update:
            await self.update()

        return await self.get_value("pkgs")

    @abstractmethod
    async def _get_pkgs(self) -> Mapping[str, PkgTing]:

        pass

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

    @abstractmethod
    async def init(self, uri: str):

        pass

    async def get_pkg(
        self, name: str, raise_exception: bool = True
    ) -> Optional[PkgTing]:
        pkgs = await self.get_pkgs()

        pkg = pkgs.get(name, None)

        if pkg is None and raise_exception:
            pkg_names = await self.pkg_names
            raise FrklException(
                msg=f"Can't retrieve package '{name}' from index '{self.name}'.",
                reason="No package with that name available.",
                solution=f"Make sure the package name is correct, available packages: {', '.join(pkg_names)}.",
            )
        elif is_instance_or_subclass(pkg, Exception) and raise_exception:
            raise pkg  # type: ignore
        elif is_instance_or_subclass(pkg, Exception):
            return None

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

        all_values = await self.get_all_pkg_values(
            "source", "metadata", "aliases", "info", "labels", "tags"
        )

        _all_values: Dict[str, Any] = dict(all_values)

        config_dict = dict(await self.get_value("config"))
        config_dict.pop("_name_autogenerated", None)
        config_dict.pop("name", None)
        config_dict.pop("type", None)

        if config_dict.get("add_sysinfo_to_default_vars", False):
            default_vars = config_dict["defaults"]["vars"]
            for k, v in get_current_system_info().items():
                if default_vars.get(k, None) == v:
                    default_vars.pop(k, None)

        _all_values["_bring_config"] = config_dict

        _all_values["_bring_metadata_timestamp"] = str(arrow.now())

        return _all_values
