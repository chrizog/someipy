import asyncio
from typing import Coroutine, Dict


class TaskManager:
    def __init__(self):
        self._tasks: Dict[int, asyncio.Task] = {}

    def add_task(self, coro: Coroutine) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks[task.id] = task
        return task

    async def cancel_task(self, task: asyncio.Task):
        try:
            if task.id in self._tasks:
                self._tasks.pop(task.id)
                task.cancel()
                await task
        except asyncio.CancelledError:
            pass

    def get_task(self, task_id: int):
        return self._tasks.get(task_id)

    def get_all_tasks(self):
        return list(self._tasks.values())

    async def wait_for_all_tasks(self):
        return await asyncio.gather(*self._tasks.values())

    async def cancel_all_tasks(self):
        for task in self._tasks.values():
            await self.cancel_task(task)
