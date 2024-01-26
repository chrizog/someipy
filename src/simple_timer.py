import asyncio

class SimplePeriodicTimer():
    def __init__(self, period, callback):
        self._period = period
        self._callback = callback
        self.task = None

    async def _job(self):
        while True:
            try:
                await asyncio.sleep(self._period)
                self._callback()
            except asyncio.CancelledError as e:
                # print(f"SimplePeriodicTimer error: {e}")
                pass

    def start(self):
        if self.task is None:
            self.task = asyncio.create_task(self._job())

    def stop(self):
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