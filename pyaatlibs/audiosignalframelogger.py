import datetime
import subprocess
import threading
import struct
import json
import numpy as np

from pyaatlibs import SEP


class AudioSignalFrameLogger(object):
    INFO_FILE = "info.json"
    BIN_FILE = "stream.bin"

    def __init__(self):
        self.info = []
        self.databuf = []
        self.lock = threading.Lock()

    def push(self, name, fs, values):
        self.lock.acquire()
        self.info.append({
            "name": name,
            "fs": fs,
            "datasize-in-double": values.shape[0],
            "createAt": "{} (UTF+8)".format(str(datetime.datetime.now())[:-3]),
        })
        self.databuf.append(np.array(values, dtype=np.float64))
        self.lock.release()

    def dump(self, path):
        if path.endswith(SEP):
            path = path[:-1]
        self.lock.acquire()
        out, _ = subprocess.Popen(
            ["mkdir", "-p", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ).communicate()

        with open("{}{}{}".format(path, SEP, AudioSignalFrameLogger.INFO_FILE), "w") as f:
            f.write(json.dumps(self.info, indent=4) + "\n")

        with open("{}{}{}".format(path, SEP, AudioSignalFrameLogger.BIN_FILE), "wb") as f:
            for data in self.databuf:
                f.write(struct.pack(">{}d".format(data.shape[0]), *data))

        del self.info[:]
        del self.databuf[:]
        self.lock.release()
