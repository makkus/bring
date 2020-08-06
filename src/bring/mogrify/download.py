# -*- coding: utf-8 -*-
import logging
import os
import shutil
from typing import Any, Mapping

import httpx
from anyio import aopen
from bring.defaults import BRING_DOWNLOAD_CACHE
from bring.mogrify import SimpleMogrifier
from frkl.common.downloads.cache import calculate_cache_path
from frkl.common.filesystem import ensure_folder
from frkl.common.strings import generate_valid_identifier


log = logging.getLogger("bring")


class DownloadMogrifier(SimpleMogrifier):

    _plugin_name = "download"
    _requires = {"url": "string", "target_file_name": "string"}
    _provides = {"file_path": "string"}

    def get_msg(self) -> str:

        result = "downloading file"

        url = self.get_user_input("url")
        if url:
            result = result + f": {url}"

        return result

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

        # download to a temp location, in case another process downloads the same url
        temp_name = f"{target_path}_{generate_valid_identifier()}"

        log.debug(f"Downloading url: {download_url}")
        try:
            client = httpx.AsyncClient()
            async with await aopen(temp_name, "wb") as f:
                async with client.stream("GET", download_url) as response:
                    async for chunk in response.aiter_bytes():
                        await f.write(chunk)
        finally:
            await client.aclose()

        if os.path.exists(target_path):
            os.unlink(temp_name)
        else:
            shutil.move(temp_name, target_path)

        return {"file_path": target_path}
