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
        index_file: Optional[str] = None,
        auto_id: Optional[str] = None,
        info: Optional[Mapping[str, Any]] = None,
        labels: Optional[Mapping[str, str]] = None,
        tags: Optional[Iterable[str]] = None,
        defaults: Optional[Mapping[str, Any]] = None,
        **type_config: Any
    ):

        self._id: str = id
        self._auto_id: Optional[str] = auto_id

        self._index_file: Optional[str] = index_file

        self._index_type: str = type

        if info is None:
            info = {}
        self._info: Mapping[str, Any] = info
        if labels is None:
            labels = {}
        self._labels: Mapping[str, str] = labels
        if tags is None:
            tags = []
        self._tags: Iterable[str] = tags

        if defaults is None:
            defaults = {}
        self._defaults = defaults

        self._type_config: Mapping[str, Any] = type_config

    @property
    def id(self) -> str:
        return self._id

    @property
    def auto_id(self) -> Optional[str]:
        return self._auto_id

    @property
    def index_file(self) -> Optional[str]:
        return self._index_file

    @property
    def index_type(self) -> str:
        return self._index_type

    @property
    def info(self) -> Mapping[str, Any]:
        return self._info

    @property
    def index_type_config(self) -> Mapping[str, Any]:
        return self._type_config

    @property
    def labels(self) -> Mapping[str, str]:
        return self._labels

    @property
    def tags(self) -> Iterable[str]:
        return self._tags

    @property
    def defaults(self) -> Mapping[str, Any]:

        return self._defaults

    def to_dict(self) -> Mapping[str, Any]:

        result = {
            "id": self.id,
            "auto_id": self._auto_id,
            "info": self.info,
            "tags": self.tags,
            "labels": self._labels,
            "index_type": self.index_type,
            "defaults": self.defaults,
            "index_config": self.index_type_config,
        }
        if self._auto_id:
            result["auto_id"] = self._auto_id
        return result
