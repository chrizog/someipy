# Copyright (C) 2024 Christian H.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import time


class SimplePeriodicTimer:
    def __init__(self, period, callback):
        self._period = period
        self._callback = callback
        self._task = None
        self._running = False

    async def _job(self):
        try:
            while True:
                start = time.time()
                self._callback()
                elapsed = time.time() - start
                to_sleep = self._period - elapsed
                if elapsed > self._period:
                    to_sleep = 0
                await asyncio.sleep(to_sleep)
        except asyncio.CancelledError:
            self._running = False

    def start(self):
        if not self._running:
            self._running = True
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._job())

    def stop(self):
        if self._running and self._task is not None:
            self._task.cancel()
            self._running = False

    @property
    def task(self):
        return self._task
