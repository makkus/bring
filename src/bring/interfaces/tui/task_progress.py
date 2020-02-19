# -*- coding: utf-8 -*-
import asyncio

from blessings import Terminal
from frtls.tasks import RunWatch, Task, Tasks
from prompt_toolkit.application import Application
from prompt_toolkit.layout import FormattedTextControl
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.layout import Layout
from sortedcontainers import SortedDict


# Create one text buffer for the main content.


_pager_py_path = __file__


text = """
asdfas
asfasdf

asfasdfsf

asfasdfsdf

asfasdfasd
"""


class TuiRunWatch(RunWatch):
    def __init__(self):
        self._tasks = SortedDict()
        self._text_area = FormattedTextControl(text="", show_cursor=False)
        self._root_container = Window(content=self._text_area)
        self._application = Application(
            layout=Layout(self._root_container, focused_element=None),
            enable_page_navigation_bindings=True,
            mouse_support=False,
            # style=style,
            full_screen=False,
        )
        # @bindings.add("c-c")
        # @bindings.add("q")
        # def _(event):
        #     " Quit. "
        #     event.app.exit()

    async def run_tasks(self, tasks: Tasks):

        await self.start()
        await tasks.run_async(self)

        self._application.exit()

    async def start(self):

        asyncio.create_task(self._application.run_async())

    def update_text(self):
        text = "\n".join(self._tasks.values())
        self._text_area.text = "\n" + text
        self._application.invalidate()

    def task_started(self, task: Task):
        self._tasks[task.desc.name] = f"{task.desc.name}: running"
        self.update_text()

    def task_finished(self, task: Task):
        self._tasks[task.desc.name] = f"{task.desc.name}: finished"
        self.update_text()

    def task_failed(self, task: Task, exception: Exception):

        self._tasks[task.desc.name] = f"{task.desc.name}: failed ({exception})"
        self.update_text()


class TerminalRunWatch(RunWatch):
    def __init__(self):
        self._tasks = SortedDict()
        self._old_height = 0
        self._terminal: Terminal = Terminal()

    async def run_tasks(self, tasks: Tasks):

        self._terminal.stream.write(self._terminal.hide_cursor)
        try:
            await tasks.run_async(self)
        finally:
            print(self._terminal.normal_cursor)

    def update_text(self):

        t = self._terminal

        # text = '\n'.join(self._tasks.values())
        move_up = []
        for _ in range(self._old_height):
            move_up.append(t.move_up)
        self._terminal.stream.write("".join(move_up))

        max_left = 20
        lines = []
        for task, text in self._tasks.items():

            if task.parent:
                name = f"{task.parent.desc.name}:{task.desc.name}"
            else:
                name = task.desc.name

            length = len(name)
            if length > max_left:
                max_left = length
            diff = 20 - length

            if text == "finished":
                msg = f"{t.green}{text}{t.normal}"
            elif "failed" in text:
                msg = f"{t.red}{text}{t.normal}"
            else:
                msg = f"{t.yellow}{text}{t.normal}"
            lines.append((name, diff, msg))

        if max_left > 20:
            add = max_left - 20
        else:
            add = 1

        for line in lines:
            name = line[0]
            diff = (line[1] + add + 2) * " "
            msg = line[2]
            print(t.clear_eol + f" {name}{diff}\u279c {msg}")

        self._old_height = len(self._tasks)

    def task_started(self, task: Task):
        self._tasks[task] = "running"
        self.update_text()

    def task_finished(self, task: Task):
        self._tasks[task] = "finished"
        self.update_text()

    def task_failed(self, task: Task, exception: Exception):

        self._tasks[task] = f"failed ({exception})"
        self.update_text()
