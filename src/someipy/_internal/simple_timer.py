import asyncio
import time

class SimplePeriodicTimer():
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