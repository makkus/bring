# -*- coding: utf-8 -*-
import logging
from abc import ABCMeta
from typing import Any, Iterable, Mapping, Optional


log = logging.getLogger("bring")


class IndexConfig(metaclass=ABCMeta):
    def __init__(
        self,
        id: str,
        type: str,
        uri: str,
        info: Optional[Mapping[str, Any]] = None,
        labels: Optional[Mapping[str, str]] = None,
        tags: Optional[Iterable[str]] = None,
        **metadata: Any
    ):

        self._id = id
        self._index_type: str = type
        self._uri: str = uri
        if info is None:
            info = {}
        self._info: Mapping[str, Any] = info
        if labels is None:
            labels = {}
        self._labels: Mapping[str, str] = labels
        if tags is None:
            tags = []
        self._tags: Iterable[str] = tags

        self._metadata: Mapping[str, Any] = metadata

    @property
    def id(self) -> str:
        return self._id

    @property
    def uri(self) -> str:
        return self._uri

    @property
    def index_type(self) -> str:
        return self._index_type

    @property
    def info(self) -> Mapping[str, Any]:
        return self._info

    @property
    def labels(self) -> Mapping[str, str]:
        return self._labels

    @property
    def tags(self) -> Iterable[str]:
        return self._tags

    def to_dict(self) -> Mapping[str, Any]:

        return {
            "id": self.id,
            "uri": self.uri,
            "info": self.info,
            "tags": self.tags,
            "labels": self._labels,
            "index_type": self.index_type,
        }
