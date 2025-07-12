import subprocess
import time
import fcntl
import os
import signal
import threading
import queue
import select
from abc import abstractmethod


class TestBase:
    def __init__(self):
        self.ld_library_path = None
        self.vsomeip_app = None
        self.vsomeip_config = None
        self.someipy_app = None
        self.someipydaemon_app = "someipyd"

        self.output_daemon = None
        self.output_someipy_app = None
        self.output_vsomeip_app = None

    @abstractmethod
    def evaluate(self) -> bool:
        pass

    def run(self, duration=5):
        env = dict(os.environ, VSOMEIP_CONFIGURATION=self.vsomeip_config)
        if self.ld_library_path is not None:
            env["LD_LIBRARY_PATH"] = self.ld_library_path

        thread_daemon, output_queue_daemon = self.run_in_thread(
            self.someipydaemon_app, duration + 1.0, env
        )

        thread_vsomeip, output_queue_vsomeip = self.run_in_thread(
            self.vsomeip_app, duration, env
        )

        thread_python, output_queue_python = self.run_in_thread(
            self.someipy_app, duration, env
        )

        thread_daemon.start()
        thread_vsomeip.start()
        thread_python.start()

        thread_vsomeip.join()
        thread_python.join()
        thread_daemon.join()

        self.output_vsomeip_app = list(output_queue_vsomeip.queue)
        self.output_someipy_app = list(output_queue_python.queue)
        self.output_daemon = list(output_queue_daemon.queue)

    def start_process(self, command, output_queue, env, timeout=5):
        """Starts a subprocess and puts its stdout lines in a queue."""
        process = subprocess.Popen(
            command, shell=False, stdout=subprocess.PIPE, env=env
        )

        # Set non-blocking mode for stdout
        fcntl.fcntl(process.stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)

        # Collect output for timeout seconds
        start_time = time.time()
        while time.time() - start_time < timeout:
            readable, _, _ = select.select(
                [process.stdout], [], [], 0.1
            )  # Non-blocking read with timeout
            if readable:
                line = process.stdout.readline().decode().strip()
                if line:
                    output_queue.put(line)

        process.send_signal(signal.SIGINT)

        # Collect output for 1 seconds after sending the sigint
        start_time = time.time()
        while time.time() - start_time < 1:
            readable, _, _ = select.select(
                [process.stdout], [], [], 0.1
            )  # Non-blocking read with timeout
            if readable:
                line = process.stdout.readline().decode().strip()
                if line:
                    output_queue.put(line)
                else:
                    break  # No more output available

        process.wait()

    def run_in_thread(self, command, duration, env):
        output_queue = queue.Queue()
        thread = threading.Thread(
            target=TestBase.start_process,
            args=(self, command, output_queue, env, duration),
        )
        return thread, output_queue

    def print_outputs(self):
        print("-------- Output from someipy app --------")
        for l in self.output_someipy_app:
            print(l)

        print("-------- Output from vsomeip app --------")
        for l in self.output_vsomeip_app:
            print(l)

        print("-------- Output from someipy daemon --------")
        for l in self.output_daemon:
            print(l)
