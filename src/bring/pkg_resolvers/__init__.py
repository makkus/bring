# -*- coding: utf-8 -*-
import copy
import json
import logging
import os
from abc import ABCMeta, abstractmethod
from collections import Sequence
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

import arrow
import httpx
from anyio import aopen
from bring.defaults import BRING_PKG_CACHE, PKG_RESOLVER_DEFAULTS
from frtls.dicts import get_seeded_dict
from frtls.files import ensure_folder, generate_valid_filename
from frtls.strings import from_camel_case


log = logging.getLogger("bring")


class PkgResolver(metaclass=ABCMeta):

    metadata_cache = {}

    @abstractmethod
    def _supports(self) -> List[str]:
        pass

    @abstractmethod
    def get_resolver_config(self) -> Mapping[str, Any]:
        pass

    @abstractmethod
    def get_unique_source_id(self, source_details: Dict) -> str:
        pass

    @abstractmethod
    def get_artefact_defaults(self, source_details: Dict) -> Dict[str, Any]:
        pass

    def check_pkg_metadata_valid(
        self,
        metadata: Optional[Mapping[str, Any]],
        source_details: Mapping[str, Any],
        config: Optional[Mapping[str, Any]] = None,
    ) -> bool:

        if not metadata:
            return False

        if not metadata["metadata"].get("versions", None):
            return False

        if dict(metadata["source"]) != dict(source_details):
            return False

        if config is None:
            config = self.get_resolver_config()

        if config["metadata_max_age"] < 0:
            return True

        last_access = metadata["metadata"].get("metadata_check", None)
        if last_access is None:
            last_access = arrow.Arrow(1970, 1, 1)
        else:
            last_access = arrow.get(last_access)
        now = arrow.now()
        delta = now - last_access
        secs = delta.total_seconds()

        if secs < config["metadata_max_age"]:
            return True

        return False

    async def _get_cached_metadata(
        self,
        source_details: Mapping[str, Any],
        config: Optional[Mapping[str, Any]] = None,
    ):

        id = self.get_unique_source_id(source_details)

        metadata = PkgResolver.metadata_cache.setdefault(self.__class__, {}).get(
            id, None
        )

        # check whether we have the metadata in the global cache
        if self.check_pkg_metadata_valid(metadata, source_details, config=config):
            return metadata["metadata"]

        # check whether the metadata is cached within the PkgResolver
        metadata = await self._get_pkg_metadata(
            source_details, config, cached_only=True
        )
        if metadata is not None:
            PkgResolver.metadata_cache[self.__class__][id] = {
                "metadata": metadata,
                "source": source_details,
            }
            return metadata

        return None

    async def get_metadata_timestamp(
        self, source_details: Union[str, Dict[str, Any]]
    ) -> Optional[arrow.Arrow]:

        if isinstance(source_details, str):
            _source_details = {"url": source_details}
        else:
            _source_details = source_details

        metadata = await self._get_cached_metadata(
            source_details=_source_details, config={"metadata_max_age": -1}
        )
        if metadata is None:
            return None

        last_access = metadata.get("metadata_check", None)
        if last_access is None:
            return None
        return arrow.get(last_access)

    async def get_pkg_metadata(
        self,
        source_details: Union[str, Dict[str, Any]],
        override_config: Optional[Mapping[str, Any]] = None,
    ) -> List[Dict[str, str]]:

        if isinstance(source_details, str):
            _source_details = {"url": source_details}
        else:
            _source_details = source_details

        config = get_seeded_dict(self.get_resolver_config(), override_config)

        metadata = await self._get_cached_metadata(
            source_details=_source_details, config=config
        )
        if metadata:
            return metadata

        # retrieve the metadata
        metadata = await self._get_pkg_metadata(
            _source_details, config, cached_only=True
        )
        if metadata is not None:
            PkgResolver.metadata_cache[self.__class__][id] = {
                "metadata": metadata,
                "source": source_details,
            }
            return metadata

        metadata = await self._get_pkg_metadata(
            _source_details, config, cached_only=False
        )
        PkgResolver.metadata_cache[self.__class__][id] = {
            "metadata": metadata,
            "source": source_details,
        }

        return metadata

    @abstractmethod
    async def _get_pkg_metadata(
        self,
        source_details: Mapping[str, Any],
        config: Mapping[str, Any],
        cached_only=False,
    ) -> List[Dict[str, str]]:
        pass

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
        aliases: Dict[str, Dict[str, str]],
        versions: List[Dict[str, str]],
        source_details: Dict[str, Any],
    ):

        if not aliases:
            vars_alias = vars
        else:
            vars_alias = {}

            for k, v in vars.items():
                alias_dict = aliases.get(k, None)
                if alias_dict is None:
                    vars_alias[k] = v
                    continue
                if v in alias_dict.keys():
                    vars_alias[k] = alias_dict[v]
                else:
                    vars_alias[k] = v

        vars_final = copy.copy(defaults)
        if "var_map" in source_details.keys():
            var_map = source_details["var_map"]
            for k, v in vars_alias.items():
                v_list = []
                if v in var_map.values():
                    for k1, v1 in var_map.items():
                        if v1 == v:
                            v_list.append(k1)

                    vars_final[k] = v_list
                else:
                    vars_final[k] = v
        else:
            vars_final.update(vars_alias)

        matches = []
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
                matches.append(version)

        if not matches:
            return None

        if len(matches) == 1:
            return matches[0]

        # find the first 'exactest" match
        max_match = matches[0]
        for m in matches[1:]:
            if len(m) > len(max_match):
                max_match = m

        return max_match


class SimplePkgResolver(PkgResolver):
    def __init__(self, config: Optional[Dict[str, Any]] = None):

        self._cache_dir = os.path.join(
            BRING_PKG_CACHE, "resolvers", from_camel_case(self.__class__.__name__)
        )
        ensure_folder(self._cache_dir, mode=0o700)

        self._config: Mapping[str, Any] = get_seeded_dict(PKG_RESOLVER_DEFAULTS, config)

    def get_resolver_config(self) -> Mapping[str, Any]:

        return self._config

    @abstractmethod
    async def _retrieve_versions(
        self, source_details: Dict, update=True
    ) -> Union[Tuple[List, Dict], List]:
        pass

    def get_artefact_defaults(self, source_details: Dict) -> Dict[str, Any]:
        return {}

    async def _get_pkg_metadata(
        self,
        source_details: Mapping[str, Any],
        config: Mapping[str, Any],
        cached_only=False,
    ) -> Optional[List[Dict[str, Any]]]:

        id = self.get_unique_source_id(source_details)
        id = generate_valid_filename(id, sep="_")
        metadata_file = os.path.join(self._cache_dir, f"{id}.json")

        metadata = await self.get_metadata(metadata_file)
        if self.check_pkg_metadata_valid(metadata, source_details, config=config):
            return metadata["metadata"]

        if cached_only:
            return None

        if "var_map" in source_details.keys():
            var_map = source_details["var_map"]
        else:
            var_map = {}

        try:
            versions = await self._retrieve_versions(source_details=source_details)
            if isinstance(versions, tuple):
                aliases: Dict[str, str] = versions[1]
                versions: List[Dict[str, Any]] = versions[0]
            else:
                aliases = {}
        except (Exception) as e:
            log.debug(f"Can't retrieve versions for pkg: {e}")
            log.debug(
                f"Error retrieving versions in resolver '{self.__class__.__name__}': {e}",
                exc_info=1,
            )
            raise e

        metadata["versions"] = versions
        metadata["aliases"] = aliases

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

        await self.write_metadata(metadata_file, metadata, source_details)

        return metadata

    async def get_metadata(self, metadata_file: str):

        if not os.path.exists(metadata_file):
            return {}

        async with await aopen(metadata_file) as f:
            content = await f.read()
            metadata = json.loads(content)

        return metadata

    async def write_metadata(
        self, metadata_file: str, metadata: Mapping[str, Any], source: Mapping[str, Any]
    ):

        data = {"metadata": metadata, "source": source}
        async with await aopen(metadata_file, "w") as f:
            await f.write(json.dumps(data))


class HttpDownloadPkgResolver(SimplePkgResolver):
    def __init__(self, config: Optional[Mapping[str, Any]] = None):

        super().__init__(config=config)
        self._download_dir = os.path.join(self._cache_dir, "_downloads")
        ensure_folder(self._download_dir)

    async def get_artefact_path(
        self, version: Dict[str, str], source_details: Dict[str, Any]
    ):

        download_path = await self.download_artefact(
            version=version, source_details=source_details
        )

        return download_path

    @abstractmethod
    def get_download_url(self, version: Dict[str, str], source_details: Dict[str, Any]):

        pass

    async def download_artefact(
        self, version: Dict[str, str], source_details: Dict[str, Any]
    ):

        download_url = self.get_download_url(version, source_details)
        log.debug(f"downloading: {download_url}")

        # filename = self.calculate_unique_version_id(version=version, source_details=source_details)
        filename = version.get("_meta", {}).get("asset_name", None)
        if filename is None:
            filename = os.path.basename(download_url)

        target_path = os.path.join(self._download_dir, filename)

        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            log.debug(f"Cached file present, not downloading url: {download_url}")
            return target_path

        log.debug(f"Downloading url: {download_url}")

        try:
            client = httpx.AsyncClient()
            async with await aopen(target_path, "wb") as f:
                async with client.stream("GET", download_url) as response:
                    async for chunk in response.aiter_bytes():
                        await f.write(chunk)
        finally:
            await client.aclose()

        return target_path
