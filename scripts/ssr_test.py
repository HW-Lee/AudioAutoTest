from com.dtmilano.android.viewclient import ViewClient
import os
import subprocess
import time
import datetime

import sys
sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../")

from libs import ROOT_DIR
from libs.audiofunction import AudioFunction
from libs.logger import Logger
from libs.logcatlistener import LogcatListener, LogcatEvent

INTENT_PREFIX = "am broadcast -a"
HTC_INTENT_PREFIX = "audio.htc.com.intent."
DEVICE_MUSIC_DIR = "sdcard/Music/"
OUT_FREQ = 440

FILE_NAMES = [
    "440Hz.wav",
    "440Hz.mp3"
]

def push_files_if_needed(serialno):
    out, _ = subprocess.Popen(["adb", "-s", serialno, "shell", "ls", DEVICE_MUSIC_DIR], stdout=subprocess.PIPE).communicate()

    # The command "adb shell ls" might return several lines of strings where each line lists multiple file names
    # Then the result should be handled line by line:
    #           map function for split with spaces and reduce function for concatenate the results of each line
    files = reduce(lambda x, y: x+y, map(lambda s: s.split(), out.splitlines())) if out else []

    for file_to_pushed in FILE_NAMES:
        if file_to_pushed in files:
            continue
        out, _ = subprocess.Popen(["find", ROOT_DIR, "-name", file_to_pushed], stdout=subprocess.PIPE).communicate()
        file_path = out.splitlines()[0] if out else None
        if file_path:
            os.system("adb -s {} push {} {} > /dev/null".format(serialno, file_path, DEVICE_MUSIC_DIR))
        else:
            raise ValueError("Cannot find the file \"{}\", please place it under the project tree.".format(file_to_pushed))

def trigger_ssr(device):
    device.shell("asound -crashdsp")

def dev_playback_nonoffload(device):
    cmd = " ".join([INTENT_PREFIX, HTC_INTENT_PREFIX + "playback.nonoffload", "--es", "file", "440Hz.wav"])
    device.shell(cmd)

def dev_playback_offload(device):
    cmd = " ".join([INTENT_PREFIX, HTC_INTENT_PREFIX + "playback.offload", "--es", "file", "440Hz.mp3"])
    device.shell(cmd)

def dev_playback_stop(device):
    cmd = " ".join([INTENT_PREFIX, HTC_INTENT_PREFIX + "playback.stop"])
    device.shell(cmd)

def dev_record_start(device):
    cmd = " ".join([INTENT_PREFIX, HTC_INTENT_PREFIX + "record.start", "--ei", "spt_xmax", "1000"])
    device.shell(cmd)

def dev_record_stop(device):
    cmd = " ".join([INTENT_PREFIX, HTC_INTENT_PREFIX + "record.stop"])
    device.shell(cmd)

def dev_print_detected_tone(device):
    cmd = " ".join([INTENT_PREFIX, HTC_INTENT_PREFIX + "print.properties"])
    device.shell(cmd)

class ToneDetectedDecision(object):
    def __init__(self, thresh_blocks=3):
        self.counter = 0
        self.thresh_blocks = thresh_blocks

    @staticmethod
    def freq_cb(pattern, msg):
        freq, amp_db = msg.split()[-1].split(",")
        print freq
        print amp_db

def run():
    AudioFunction.init()
    Logger.init()
    os.system("adb start-server > /dev/null")

    package = "com.htc.audiofunctionsdemo"
    activity = ".activities.MainActivity"
    component = package + "/" + activity

    device, serialno = ViewClient.connectToDeviceOrExit()
    vc = ViewClient(device, serialno, autodump=False)

    LogcatListener.init(serialno)

    # push_files_if_needed(serialno)

    if not device.isScreenOn():
        device.wake()
        vc.dump()

        import StringIO as sio
        so = sio.StringIO()
        vc.traverse(stream=so)
        if "lockscreen" in so.getvalue():
            device.unlock()

    # keymap reference:
    #   https://github.com/dtmilano/AndroidViewClient/blob/master/src/com/dtmilano/android/adb/androidkeymap.py
    device.press("HOME")
    time.sleep(1)
    device.startActivity(component=component)
    time.sleep(1)

    dev_record_start(device)
    logcat_event = LogcatEvent(pattern="AudioFunctionsDemo::properties", cb=ToneDetectedDecision.freq_cb)
    LogcatListener.register_event(serialno=serialno, logcat_event=logcat_event)
    AudioFunction.play_sound(out_freq=OUT_FREQ)
    time.sleep(2)
    dev_print_detected_tone(device)
    time.sleep(3)
    AudioFunction.stop_audio()
    dev_record_stop(device)

    AudioFunction.finalize()
    Logger.finalize()
    LogcatListener.finalize()

if __name__ == "__main__":
    run()
