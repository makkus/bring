# -*- coding: utf-8 -*-
import json
import os
from abc import ABCMeta, abstractmethod
from typing import List, Union, Dict, Any

import arrow
from anyio import aopen

from bring.defaults import BRING_PKG_CACHE
from frtls.files import ensure_folder, generate_valid_filename
from frtls.strings import from_camel_case


class PkgResolver(metaclass=ABCMeta):
    @abstractmethod
    def get_supported_source_types(self) -> List[str]:
        pass

    @abstractmethod
    async def get_versions(self, source_details: Union[str, Dict]) -> Dict[str, Any]:
        pass

    def get_resolver_name(self):
        return from_camel_case(self.__class__.__name__, sep="-")


class SimplePkgResolver(PkgResolver):
    def __init__(self):

        self._cache_dir = os.path.join(
            BRING_PKG_CACHE, from_camel_case(self.__class__.__name__)
        )
        ensure_folder(self._cache_dir, mode=0o700)

        self._data_max_age_sec = 3600

    @abstractmethod
    async def _retrieve_versions(
        self, source_details: Dict, update=True
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _get_unique_id(self, source_details: Dict) -> str:
        pass

    async def get_versions(self, source_details: Union[str, Dict]) -> Dict[str, Any]:

        id = self._get_unique_id(source_details)
        id = generate_valid_filename(id, sep="_")
        metadata_file = os.path.join(self._cache_dir, f"{id}.json")

        if isinstance(source_details, str):
            source_details = {"url": source_details}

        metadata = await self.get_metadata(metadata_file)
        if "versions" in metadata.keys() and metadata["versions"]:

            last_access = metadata.get("last_access", None)
            if last_access is None:
                last_access = arrow.Arrow(1970, 1, 1)
            else:
                last_access = arrow.get(last_access)
            now = arrow.now()
            delta = now - last_access
            secs = delta.total_seconds()

            if secs < self._data_max_age_sec:
                return metadata["versions"]

        versions = await self._retrieve_versions(source_details=source_details)
        metadata["versions"] = versions
        metadata["last_access"] = str(arrow.Arrow.now())

        await self.write_metadata(metadata_file, metadata)

        return versions

    async def get_metadata(self, metadata_file: str):

        if not os.path.exists(metadata_file):
            return {}

        async with await aopen(metadata_file) as f:
            content = await f.read()
            metadata = json.loads(content)

        return metadata

    async def write_metadata(self, metadata_file: str, metadata: Dict):

        async with await aopen(metadata_file, "w") as f:
            await f.write(json.dumps(metadata))
