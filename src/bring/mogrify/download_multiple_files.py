# -*- coding: utf-8 -*-
import logging
import os
import shutil
from typing import Any, Dict, List, Mapping

import anyio
import httpx
from anyio import aopen
from bring.defaults import BRING_DOWNLOAD_CACHE
from bring.mogrify import MogrifierException, SimpleMogrifier
from frkl.common.downloads.cache import calculate_cache_path
from frkl.common.filesystem import ensure_folder
from frkl.common.strings import generate_valid_identifier


log = logging.getLogger("bring")


class DownloadMultipleFilesMogrifier(SimpleMogrifier):

    _plugin_name = "download_multiple_files"
    _requires = {"urls": "list", "retries": "int?"}
    _provides = {"folder_path": "string"}

    def get_msg(self) -> str:

        result = "downloading multiple files"

        # url = self.get_user_input("url")
        # if url:
        #     result = result + f": {url}"

        return result

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        urls: List[Mapping[str, str]] = requirements["urls"]
        retries = requirements.get("retries", None)
        if retries is None:
            retries = 3

        if retries < 2:
            retries = 1

        retry_wait = 1

        target_folder = self.create_temp_dir("download_multi_")

        new_urls: Dict[str, str] = {}

        for data in urls:
            url = data["url"]
            target = data["target"]
            if os.path.isabs(target):
                raise MogrifierException(
                    self,
                    msg="Can't download files.",
                    reason=f"Invalid configuration, 'target'-path can't be absolute: {target}",
                )

            if target in new_urls.keys():
                raise MogrifierException(
                    self,
                    msg="Can't download files.",
                    reason=f"Duplicate target: {target}",
                )
            new_urls[target] = url

        client = httpx.AsyncClient()

        downloaded_files: Dict[str, str] = {}

        async def download_file(_url, _target):

            _cache_path = calculate_cache_path(base_path=BRING_DOWNLOAD_CACHE, url=_url)

            if os.path.exists(_cache_path):
                downloaded_files[_target] = _cache_path
                return

            log.debug(f"downloading '{_url}' to: {_cache_path}")
            ensure_folder(os.path.dirname(_cache_path))

            # download to a temp location, in case another process downloads the same url
            temp_name = f"{_cache_path}_{generate_valid_identifier()}"

            try_nr = 1
            success = False
            while try_nr <= retries and not success:

                try_nr = try_nr + 1
                log.debug(f"Downloading url: {_url}")
                try:
                    async with await aopen(temp_name, "wb") as f:
                        async with client.stream("GET", _url) as response:
                            async for chunk in response.aiter_bytes():
                                await f.write(chunk)
                    success = True
                except Exception as e:
                    log.debug(f"Failed to download '{_url}': {e}", exc_info=True)
                    if try_nr <= retries:
                        await anyio.sleep(retry_wait)

            if not success:
                raise MogrifierException(self, msg=f"Error downloading '{_url}'")

            if os.path.exists(_cache_path):
                os.unlink(temp_name)
            else:
                shutil.move(temp_name, _cache_path)

            downloaded_files[_target] = _cache_path

        try:
            for t, u in new_urls.items():
                await download_file(_url=u, _target=t)
        finally:
            await client.aclose()

        for _target_path, _source_path in downloaded_files.items():
            _full_target = os.path.join(target_folder, _target_path)
            ensure_folder(os.path.dirname(_full_target))
            shutil.copy2(_source_path, _full_target)

        return {"folder_path": target_folder}
