# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
from datetime import datetime, timezone
from typing import List, Union, Dict, Any

from frtls.strings import from_camel_case


class PkgResolver(metaclass=ABCMeta):
    @abstractmethod
    def get_supported_source_types(self) -> List[str]:
        pass

    async def get_versions(self, source_details: Union[str, Dict]) -> Dict[str, Any]:

        now = datetime.now(timezone.utc)

        result = await self._get_versions(source_details=source_details)

        result.setdefault("_meta", {})["timestamp"] = str(now)
        return result

    @abstractmethod
    def _get_versions(self, source_details: Union[str, Dict]) -> Dict[str, Any]:
        pass

    def get_resolver_name(self):
        return from_camel_case(self.__class__.__name__, sep="-")
