# -*- coding: utf-8 -*-
import logging
import os
from typing import Any, Mapping, Optional

import httpx
from anyio import aopen
from bring.defaults import BRING_DOWNLOAD_CACHE
from bring.mogrify import SimpleMogrifier
from frtls.downloads import calculate_cache_path
from frtls.files import ensure_folder


log = logging.getLogger("bring")


class DownloadMogrifier(SimpleMogrifier):

    _plugin_name = "download"

    def __init__(self, name: str, meta: Optional[Mapping[str, Any]] = None) -> None:

        super().__init__(name=name, meta=meta)

    def get_msg(self) -> str:

        return "downloading file"

    def requires(self) -> Mapping[str, str]:

        return {"url": "string", "target_file_name": "string"}

    def provides(self) -> Mapping[str, str]:

        return {"file_path": "string"}

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        download_url = requirements["url"]
        target_file_name = requirements["target_file_name"]

        cache_path = calculate_cache_path(
            base_path=BRING_DOWNLOAD_CACHE, url=download_url
        )

        target_path = os.path.join(cache_path, target_file_name)

        if os.path.exists(target_path):
            return {"file_path": target_path}

        ensure_folder(cache_path)

        log.debug(f"Downloading url: {download_url}")
        try:
            client = httpx.AsyncClient()
            async with await aopen(target_path, "wb") as f:
                async with client.stream("GET", download_url) as response:
                    async for chunk in response.aiter_bytes():
                        await f.write(chunk)
        finally:
            await client.aclose()

        return {"file_path": target_path}
