# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
from typing import Any, Mapping

from blessings import Terminal
from bring.defaults import BRING_TASKS_BASE_TOPIC
from frtls.tasks import TaskDesc
from pubsub import pub
from treelib import Tree


class BringTaskWatcher(metaclass=ABCMeta):
    def __init__(self, base_topic=BRING_TASKS_BASE_TOPIC):

        self._base_topic = base_topic

        pub.subscribe(self.task_handler, self._base_topic)

    def task_handler(
        self, event_name: str, source: Any, event_details: Mapping[str, Any]
    ):

        if event_name == "task_started":
            self._task_started(source, event_details)
        elif event_name == "task_finished":
            self._task_finished(source, event_details)
        elif event_name == "task_failed":
            self._task_failed(source, event_details)

    @abstractmethod
    def _task_started(self, source: TaskDesc, event_details: Mapping[str, Any]):

        pass

    @abstractmethod
    def _task_finished(self, source: TaskDesc, event_details: Mapping[str, Any]):

        pass

    @abstractmethod
    def _task_failed(self, source: TaskDesc, event_details: Mapping[str, Any]):

        pass


class TerminalRunWatcher(BringTaskWatcher):
    def __init__(
        self,
        base_topic=BRING_TASKS_BASE_TOPIC,
        sort_task_names: bool = True,
        terminal: Terminal = None,
    ):

        if terminal is None:
            terminal = Terminal()

        self._terminal = terminal
        self._old_height = 0
        self._sort_task_names = sort_task_names

        self._tasks = Tree()
        self._root_tasks = self._tasks.create_node(
            tag="tasks", identifier="root", data=None
        )

        self._running_tasks = {}
        self._finished_tasks = {}

        super().__init__(base_topic=base_topic)

    def _task_started(self, source: TaskDesc, event_details: Mapping[str, Any]):

        if source.parent:
            parent_id = source.parent.id
        else:
            parent_id = None

        if self._tasks.get_node(source.id):
            raise Exception(f"Task with id '{source.id}' already registered.")

        if source.id in self._running_tasks.keys():
            raise Exception(f"Task with id '{source.id}' already registered.")

        if not source.parent:
            parent_id: str = "root"
        else:
            parent_id: str = source.parent.id

        self._tasks.create_node(
            tag=f"{source.name} (running)",
            identifier=source.id,
            parent=parent_id,
            data=source,
        )
        self._running_tasks[source.id] = source

        self.update_text()

    def _task_finished(self, source: TaskDesc, event_details: Mapping[str, Any]):

        if source.id not in self._running_tasks.keys():
            raise Exception(f"Task with id '{source.id}' not registered as started.")

        t = self._tasks.get_node(source.id)
        t.tag = f"{source.name} (finished)"

        self._running_tasks.pop(source.id)
        self._finished_tasks[source.id] = source

        self.update_text()

    def _task_failed(self, source: TaskDesc, event_details: Mapping[str, Any]):

        if source.id not in self._running_tasks.keys():
            raise Exception(f"Task with id '{source.id}' not registered as started.")

        t = self._tasks.get_node(source.id)
        t.tag = f"{source.name} (failed)"

        self._running_tasks.pop(source.id)
        self._finished_tasks[source.id] = source

        self.update_text()

    def update_text(self):

        t = self._terminal

        # go to top of generated output
        move_up = []

        for _ in range(self._old_height):
            move_up.append(t.move_up)
            move_up.append(t.clear_eol)
        self._terminal.stream.write("".join(move_up))

        self._tasks.show(key=lambda node: node.data._start_time)

        self._old_height = self._tasks.size() + 1
