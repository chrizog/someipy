import asyncio
import time


class SimplePeriodicTimer():
    def __init__(self, period, callback):
        self._period = period
        self._callback = callback
        self.task = None
        self._running = False

    async def _job(self):
        try:
            while True:
                start = time.time()
                self._callback()
                elapsed = time.time() - start
                to_sleep = self._period - elapsed
                if (elapsed > self._period):
                    # TODO: print warning
                    pass
                    to_sleep = self._period
                await asyncio.sleep(to_sleep)
        except asyncio.CancelledError as e:
            self._running = False
            pass

  
    def start(self):
        if not self._running:
            self._running = True
            self.task = asyncio.create_task(self._job())

    def stop(self):
        if self._running and self.task is not None:
            self.task.cancel()


class SimpleTimer():

    def __init__(self, timeout, callback):
        self._timeout = timeout
        self._callback = callback
        self.task = asyncio.create_task(self._job())

        self._stopped = False
        self._reset_triggered = False

    async def _job(self):
        try:
            await asyncio.sleep(self._timeout)
            self._callback()
        except asyncio.CancelledError:
            if self._reset_triggered:
                self._reset_triggered = False
                self.task = asyncio.create_task(self._job())
            else:
                pass

    def stop(self):
        self._stopped = True
        self.task.cancel()

    def reset(self):
        self._reset_triggered = True
        self.task.cancel()