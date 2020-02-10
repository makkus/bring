# -*- coding: utf-8 -*-
import copy
import json
import logging
import os
from abc import ABCMeta, abstractmethod
from collections import Sequence
from typing import List, Union, Dict, Any

import arrow
import httpx
from anyio import aopen

from bring.defaults import BRING_PKG_CACHE
from frtls.files import ensure_folder, generate_valid_filename
from frtls.strings import from_camel_case

log = logging.getLogger("bring")


class PkgResolver(metaclass=ABCMeta):
    @abstractmethod
    def get_supported_source_types(self) -> List[str]:
        pass

    @abstractmethod
    async def get_pkg_metadata(
        self, source_details: Union[str, Dict]
    ) -> List[Dict[str, str]]:
        pass

    def get_resolver_name(self):
        return from_camel_case(self.__class__.__name__, sep="-")

    @abstractmethod
    async def get_artefact_path(
        self, version: Dict[str, str], source_details: Dict[str, Any]
    ):

        pass

    def calculate_unique_version_id(
        self, version: Dict[str, str], source_details: Dict[str, Any]
    ) -> str:

        id = self.get_unique_source_id(source_details=source_details)
        for k in sorted(version):
            if k != "_meta":
                id = id + "_" + version[k]
        id = id + ".download"

        return id

    def find_version(
        self,
        vars: Dict[str, str],
        defaults: Dict[str, str],
        versions: List[Dict[str, str]],
        source_details: Dict[str, Any],
    ):

        vars_final = copy.copy(defaults)
        if "var_map" in source_details.keys():
            var_map = source_details["var_map"]
            for k, v in vars.items():
                v_list = []
                if v in var_map.values():
                    for k1, v1 in var_map.items():
                        if v1 == v:
                            v_list.append(k1)

                    vars_final[k] = v_list
                else:
                    vars_final[k] = v
        else:
            vars_final.update(vars)

        for version in versions:
            match = True
            for k, v in version.items():
                if k == "_meta":
                    continue

                comp_v = vars_final.get(k, None)
                if not isinstance(comp_v, str) and isinstance(comp_v, Sequence):
                    temp_match = False
                    for c in comp_v:
                        if c == v:
                            temp_match = True
                            break
                    if not temp_match:
                        match = False
                        break
                else:

                    if comp_v != v:
                        match = False
                        break

            if match:
                return version

        return None


class SimplePkgResolver(PkgResolver):
    def __init__(self):

        self._cache_dir = os.path.join(
            BRING_PKG_CACHE, "resolvers", from_camel_case(self.__class__.__name__)
        )
        ensure_folder(self._cache_dir, mode=0o700)

        self._data_max_age_sec = 3600

    @abstractmethod
    async def _retrieve_versions(
        self, source_details: Dict, update=True
    ) -> List[Dict[str, str]]:
        pass

    @abstractmethod
    async def get_unique_source_id(self, source_details: Dict) -> str:
        pass

    async def get_pkg_metadata(
        self, source_details: Union[str, Dict]
    ) -> List[Dict[str, str]]:

        id = self.get_unique_source_id(source_details)
        id = generate_valid_filename(id, sep="_")
        metadata_file = os.path.join(self._cache_dir, f"{id}.json")

        if isinstance(source_details, str):
            source_details = {"url": source_details}

        metadata = await self.get_metadata(metadata_file)
        if "versions" in metadata.keys() and metadata["versions"]:

            last_access = metadata.get("metadata_check", None)
            if last_access is None:
                last_access = arrow.Arrow(1970, 1, 1)
            else:
                last_access = arrow.get(last_access)
            now = arrow.now()
            delta = now - last_access
            secs = delta.total_seconds()

            if secs < self._data_max_age_sec:
                return metadata

        if "var_map" in source_details.keys():
            var_map = source_details["var_map"]
        else:
            var_map = {}

        try:
            versions = await self._retrieve_versions(source_details=source_details)
        except (Exception) as e:
            log.error(f"Can't retrieve versions for pkg: {e}")
            log.debug(
                f"Error retrieving versions in resolver '{self.__class__.__name__}': {e}",
                exc_info=1,
            )
            raise e
        metadata["versions"] = versions

        defaults = copy.copy(source_details.get("defaults", {}))
        if versions:
            for k, v in versions[0].items():

                if v in var_map.values():
                    trans_val = []
                    for k1, v1 in var_map.items():
                        if v1 == v:
                            trans_val.append(k1)
                    if len(trans_val) != 1:
                        raise Exception(
                            f"More than one reverse match for var_map value'{v}': {var_map}"
                        )
                    v = trans_val[0]

                if k != "_meta" and k not in defaults.keys():
                    defaults[k] = v

        metadata["defaults"] = defaults
        metadata["metadata_check"] = str(arrow.Arrow.now())

        await self.write_metadata(metadata_file, metadata)

        return metadata

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


class HttpDownloadPkgResolver(SimplePkgResolver):
    def __init__(self):

        super().__init__()
        self._download_dir = os.path.join(self._cache_dir, "_downloads")
        ensure_folder(self._download_dir)

    async def get_artefact_path(
        self, version: Dict[str, str], source_details: Dict[str, Any]
    ):

        download_path = await self.download_artefact(
            version=version, source_details=source_details
        )

        return download_path

    async def download_artefact(
        self, version: Dict[str, str], source_details: Dict[str, Any]
    ):

        download_url = self.get_download_url(version)
        log.debug(f"downloading: {download_url}")

        # filename = self.calculate_unique_version_id(version=version, source_details=source_details)
        filename = version["_meta"]["asset_name"]
        target_path = os.path.join(self._download_dir, filename)

        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            log.debug(f"Cached file present, not downloading url: {download_url}")
            return target_path

        log.debug(f"Downloading url: {download_url}")

        try:
            client = httpx.AsyncClient()
            with open(target_path, "wb") as f:
                async with client.stream("GET", download_url) as response:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)
        finally:
            await client.aclose()

        return target_path
