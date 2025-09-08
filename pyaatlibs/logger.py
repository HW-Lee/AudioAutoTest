import threading
import datetime
import os
import enum

from pyaatlibs import ROOT_DIR, SEP

try:
    import queue
    import io as sio
except ImportError:
    import Queue as queue
    import StringIO as sio


class LoggerThread(threading.Thread):
    MAX_SIZE = 100000
    BUF_SIZE = 10
    LOG_DIR = ROOT_DIR + "{}{}{}".format(SEP, "{}log", SEP)

    def __init__(
        self, prefix="", logfolder_prefix="", max_size=MAX_SIZE, buf_size=BUF_SIZE, log_dir=LOG_DIR
    ):
        super(LoggerThread, self).__init__()
        self.daemon = True
        self.msg_q = queue.Queue()
        self.stoprequest = threading.Event()
        self.msg_stream = sio.StringIO()
        self.prefix = prefix
        self.max_size = max_size
        self.buf_size = buf_size
        self.current_size = 0
        self.log_dir = log_dir.format(
            "{}-".format(logfolder_prefix) if len(logfolder_prefix) > 0 else logfolder_prefix
        )
        self._to_stdout = False
        self._to_file = False

        if len(self.log_dir) > 0 and self.log_dir[-1] != SEP:
            self.log_dir += SEP

        self._update_timestamp()

    def to_file(self):
        self._to_file = True

    def to_stdout(self):
        self._to_stdout = True

    def _update_timestamp(self):
        t = datetime.datetime.now()
        prefix = "{}-".format(self.prefix) if len(self.prefix) > 0 else ""
        self.filename = "{}{}{:02d}{:02d}_{:02d}{:02d}{:02d}.log.txt".format(
            prefix, t.year, t.month, t.day, t.hour, t.minute, t.second
        )
        self.log_timestamp = t

    def _dump(self):
        if not self._to_file:
            return

        with open(self.log_dir + self.filename, "a") as f:
            f.write(self.msg_stream.getvalue())

        self.msg_stream.truncate(0)
        self.msg_stream.seek(0)

    def wait_for_queue_empty(self):
        while not self.msg_q.empty():
            import time

            time.sleep(0.5)

    def push(self, msg):
        self.msg_q.put(msg)

    def join(self, timeout=None):
        self.stoprequest.set()
        super(LoggerThread, self).join(timeout)

    def run(self):
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        while not self.stoprequest.isSet():
            interval = 0.5
            timeout = 10
            count = 0
            got_msg = False
            while count < timeout / interval and not self.stoprequest.isSet():
                try:
                    msg = self.msg_q.get(True, interval)
                    got_msg = True
                    break
                except queue.Empty:
                    count += 1

            force_dump = count >= timeout / interval
            if got_msg:
                logtext = "[{}] {}\n".format(datetime.datetime.now(), msg)
                self.msg_stream.write(logtext)

                if self._to_stdout:
                    import sys

                    sys.stdout.write(logtext)
                    sys.stdout.flush()

                self.current_size += 1

            if self.current_size > 0 and (self.current_size % self.buf_size == 0 or force_dump):
                self._dump()

            if self.current_size >= self.max_size:
                self._dump()
                self.current_size = 0
                self._update_timestamp()

        if self.current_size > 0:
            self._dump()
            self.current_size = 0


class Logger(object):
    WORK_THREAD = None
    HAS_BEEN_INIT = False

    class Verbosity(enum.IntEnum):
        NONE = enum.auto()
        ERROR = enum.auto()
        WARN = enum.auto()
        INFO = enum.auto()
        DEBUG = enum.auto()

    VERBOSITY_LEVEL = Verbosity.NONE

    class Mode(object):
        STDOUT = 1
        FILE = 2
        BOTH_FILE_AND_STDOUT = STDOUT | FILE

    @staticmethod
    def init(
        mode=Mode.BOTH_FILE_AND_STDOUT, prefix="", logfolder_prefix="", log_dir=LoggerThread.LOG_DIR
    ):
        if Logger.HAS_BEEN_INIT:
            return

        Logger.WORK_THREAD = LoggerThread(
            prefix=prefix, logfolder_prefix=logfolder_prefix, log_dir=log_dir
        )

        if mode & Logger.Mode.STDOUT > 0:
            Logger.WORK_THREAD.to_stdout()
        if mode & Logger.Mode.FILE > 0:
            Logger.WORK_THREAD.to_file()

        Logger.WORK_THREAD.start()
        Logger.HAS_BEEN_INIT = True

    @staticmethod
    def get_log_path():
        return SEP.join([Logger.WORK_THREAD.log_dir, Logger.WORK_THREAD.filename])

    @staticmethod
    def finalize():
        if not Logger.HAS_BEEN_INIT:
            return

        Logger.WORK_THREAD.wait_for_queue_empty()

        Logger.WORK_THREAD.join()
        Logger.HAS_BEEN_INIT = False

    @staticmethod
    def log(tag=None, msg=None, level=Verbosity.NONE):
        if not tag or not msg:
            raise (ValueError("no tag or msg argument for Logger.log"))

        if Logger.VERBOSITY_LEVEL != Logger.Verbosity.NONE and level > Logger.VERBOSITY_LEVEL:
            return

        if level != Logger.Verbosity.NONE:
            tag = "{}/{}".format(level.name[0], tag)

        if not Logger.HAS_BEEN_INIT:
            print("[{}] {}: {}".format(datetime.datetime.now(), tag, msg))
            return

        Logger.WORK_THREAD.push("{}: {}".format(tag, msg))
