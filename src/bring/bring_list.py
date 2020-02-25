# -*- coding: utf-8 -*-
from typing import Any, Iterable, Mapping, Union


class BringItem(object):
    @classmethod
    def create(cls, item: Union[str, Mapping]) -> "BringItem":

        if isinstance(item, str):
            result = {"name": item}
        elif isinstance(item, Mapping):
            result = item
        else:
            raise TypeError(
                f"Can't create bring item, invalid input type '{type(item)}': {item}"
            )

        try:
            bring_item = BringItem(**result)
            return bring_item
        except Exception as e:
            raise ValueError(f"Can't create bring item with input '{item}': {e}")

    def __init__(self, name: str, context):

        self._name: str = name
        self._context: str = context


class BringList(object):
    @classmethod
    def create(
        cls,
        data: Union[Mapping[str, Any], Iterable[Mapping[str, Any]]],
        item_defaults: Mapping[str, Any] = None,
    ) -> "BringList":

        if data is not Mapping:
            _data: Mapping[str, Any] = {"items": data}
        else:
            _data: Mapping[str, Any] = data

        items = []
        for item in _data.get("items", []):
            bi = BringItem.create(item)
            items.append(bi)

        return BringList(*items, item_defaults=item_defaults)

    def __init__(
        self, *items: BringItem, item_defaults: Mapping[str, Any] = None
    ) -> None:

        self._items = items
        self._item_defaults = item_defaults
