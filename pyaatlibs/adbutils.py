import subprocess
import threading
import signal
import re
import time
from pyaatlibs.logger import Logger

class AdbScreenRecordingThread(threading.Thread):
    def __init__(self, serialno):
        super(AdbScreenRecordingThread, self).__init__()
        self.serialno = serialno
        self.daemon = True
        self.proc = None

    def terminate(self):
        self.proc.stdin.close()
        self.proc.terminate()
        self.proc.wait(timeout=1)
        super(AdbScreenRecordingThread, self).join(timeout=1)

    def run(self):
        # shell_cmd = "screenrecord --bit-rate 4000000 /sdcard/screenrecord.mp4"
        shell_cmd = "screenrecord /sdcard/screenrecord.mp4"
        cmd = ["adb", "-s", self.serialno, "shell", shell_cmd]
        Logger.log(
            "AdbScreenRecordingThread", "threadloop is running with the command '{}'".format(cmd))
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

class Adb(object):
    HAS_BEEN_INIT = False
    SCREEN_RECORDING_THREADS = {}
    SERIAL_TO_IP_INFO = {}

    TAG = "Adb"

    @staticmethod
    def init():
        Adb._execute("start-server")
        Adb.HAS_BEEN_INIT = True

    @staticmethod
    def _check_init():
        if not Adb.HAS_BEEN_INIT:
            Adb.init()

    @classmethod
    def _log(child, msg, tolog):
        if not tolog:
            return
        Logger.log(child.TAG, msg)

    @classmethod
    def execute(child, cmd, serialno=None, tolog=True, timeoutsec=None):
        child._check_init()

        if serialno and not serialno in child.get_devices(tolog=tolog) and \
            child.is_device_available(serialno=serialno, tolog=tolog):
            ip_info = Adb.SERIAL_TO_IP_INFO[serialno]
            ip_addr = "{}:{}".format(ip_info["addr"], ip_info["port"])
            child._log("use Wifi adb: addr[{}] of serialno '{}'".format(ip_addr, serialno), tolog)
            serialno = ip_addr

        return child._execute(cmd=cmd, serialno=serialno, tolog=tolog, timeoutsec=timeoutsec)

    @classmethod
    def _execute(child, cmd, serialno=None, tolog=True, timeoutsec=None):
        if not isinstance(cmd, list):
            cmd = [cmd]

        cmd_prefix = ["adb"]
        if serialno:
            cmd_prefix += ["-s", serialno]

        cmd = cmd_prefix + cmd
        child._log("exec: {}".format(cmd), tolog)
        out, err =  subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) \
                .communicate(timeout=timeoutsec)

        return out, err

    @classmethod
    def get_devices(child, **kwargs):
        retry = 60
        lines = []
        while retry > 0:
            out, _ = child.execute(["devices"], **kwargs)
            lines = [l for l in map(lambda x: x.strip(), out.splitlines()) if len(l) > 0]

            if len(lines) > 0 and lines[0] == "List of devices attached":
                break

            retry -= 1
            time.sleep(1)

        if retry == 0:
            raise(RuntimeError("\"adb device\" might have some problems."))

        devices = [l.split()[0] for l in lines if l.split()[1] == "device"]
        return devices

    @classmethod
    def is_device_available(child, serialno, tolog=True, **kwargs):
        devices = child.get_devices(tolog=tolog, **kwargs)

        # establish unknown ip
        for device in devices:
            m = re.match("(?P<addr>(\\d+\\.?)+)(:(?P<port>\\d+))?$", device)
            if not m:
                continue

            ip_info = m.groupdict()
            if ip_info in Adb.SERIAL_TO_IP_INFO.values():
                continue

            out, err = child.execute(
                ["shell", "getprop ro.serialno"], serialno=device, tolog=tolog, **kwargs)
            if len(err) > 0:
                continue

            Adb.SERIAL_TO_IP_INFO[out.strip()] = ip_info
            child._log("update wifi adb device: {}, {}".format(out.strip(), ip_info), tolog)

        if serialno in devices:
            return True

        if serialno in Adb.SERIAL_TO_IP_INFO and "port" in Adb.SERIAL_TO_IP_INFO[serialno]:
            ip_info = Adb.SERIAL_TO_IP_INFO[serialno]
            ip_addr = "{}:{}".format(ip_info["addr"], ip_info["port"])
            if ip_addr in devices:
                return True

        return False

    @classmethod
    def get_wifi_status(child, serialno, tolog=True, **kwargs):
        out, err = child.execute(
            ["shell", "cmd wifi status"], serialno=serialno, tolog=tolog, **kwargs)
        if len(err) > 0:
            child._log("got error: {}".format(err.strip()), tolog)
            return None

        out = out.strip()
        child._log("get_wifi_status: ret:\n{}".format(out), tolog)

        if not out.startswith("Wifi is "):
            child._log("get_wifi_status: not starts with \"Wifi is\".", tolog)
            return None

        lines = out.splitlines()
        info = {}

        if len(lines) < 1:
            return info

        m = re.match("Wifi is (?P<state>\\w+)", lines[0].strip())
        if m is None:
            return info

        info["wifi_enabled"] = "true" if m.groupdict()["state"] == "enabled" else "false"

        m = re.search("WifiInfo: .*", out)
        if m is None:
            return info
        detail_str = m.group()

        key_strings = detail_str[len("WifiInfo: "):].split(", ")
        matches = [re.match("(?P<key>[\\d\\w\\s\\-]+): (?P<value>.*)", s) for s in key_strings]
        info.update(
            {d["key"]: d["value"] for d in [m.groupdict() for m in matches if m is not None]})

        for k, v in info.items():
            try:
                float(v)
                info[k] = float(v)
                continue
            except:
                pass
            if v.lower() == "true":
                info[k] = True
                continue
            if v.lower() == "false":
                info[k] = False
                continue
            if v.lower() == "<none>":
                info[k] = None
                continue

        return info

    @classmethod
    def is_wifi_adb_supported(child, serialno, tolog=True, **kwargs):
        devices = child.get_devices(tolog=tolog, **kwargs)
        if not serialno in devices:
            child._log("device '{}' not found".format(serialno), tolog)
            return False

        wifi_status = child.get_wifi_status(serialno=serialno, tolog=tolog, **kwargs)
        if wifi_status is None:
            child._log("failed to get wifi_status.")
            return False

        if "IP" in wifi_status:
            m = re.match("/(?P<addr>(\\d+\\.?)+)", wifi_status["IP"])
            if m is not None:
                Adb.SERIAL_TO_IP_INFO[serialno] = dict(m.groupdict())
                return True

        if serialno in Adb.SERIAL_TO_IP_INFO:
            del Adb.SERIAL_TO_IP_INFO[serialno]
        return False

    @classmethod
    def enable_wifi_adb(child, serialno, port=5555, tolog=True, **kwargs):
        child._check_init()

        if not serialno in Adb.SERIAL_TO_IP_INFO \
            and not child.is_wifi_adb_supported(serialno=serialno, tolog=tolog, **kwargs):
            child._log("Wifi adb is not supported on device '{}'".format(serialno), tolog)
            return False

        _, err = child.execute(["tcpip", str(port)], serialno=serialno, tolog=tolog, **kwargs)
        if len(err) > 0:
            child._log("got error: {}".format(err.strip()), tolog)
            return False

        time.sleep(1)

        ip_info = Adb.SERIAL_TO_IP_INFO[serialno]
        ip_addr = "{}:{}".format(ip_info["addr"], port)
        out, err = child.execute(["connect", ip_addr], tolog=tolog, **kwargs)
        if len(err) > 0:
            child._log("got error: {}".format(err.strip()), tolog)
            return False

        if not re.match("(already )?connected to {}".format(ip_addr), out.strip()):
            child._log("unexpected output: {}".format(out.strip()), tolog)
            return False

        ip_info["port"] = str(port)
        return True

    @classmethod
    def disable_wifi_adb(child, serialno, tolog=True, **kwargs):
        if not serialno in Adb.SERIAL_TO_IP_INFO:
            child._log("Wifi adb is not constructed on device '{}'".format(serialno), tolog)
            return False

        ip_info = Adb.SERIAL_TO_IP_INFO[serialno]

        if not "port" in ip_info:
            child._log(
                ("Wifi adb might not be connected on device '{}', "
                "the port cannot be found.").format(serialno), tolog)
            return False

        ip_addr = "{}:{}".format(ip_info["addr"], ip_info["port"])

        out, err = child.execute(["disconnect", ip_addr], tolog=tolog, **kwargs)
        if len(err) > 0:
            child._log("got error: {}".format(err.strip()), tolog)
            return False

        if not re.match("disconnected {}".format(ip_addr), out.strip()):
            child._log("unexpected output: {}".format(out.strip()), tolog)
            return False

        del Adb.SERIAL_TO_IP_INFO[serialno]
        return True

    @classmethod
    def get_wifi_adb_ip_addr(child, serialno, tolog=True, **kwargs):
        if not serialno in Adb.SERIAL_TO_IP_INFO \
            and not child.is_wifi_adb_supported(serialno=serialno, tolog=tolog, **kwargs):
            child._log("Wifi adb is not supported on device '{}'".format(serialno), tolog)
            return None

        ip_info = Adb.SERIAL_TO_IP_INFO[serialno]
        child._log("get_wifi_adb_ip_addr: ip_info: {}".format(ip_info), tolog)
        if not "addr" in ip_info or not "port" in ip_info:
            return None

        ip_addr = "{}:{}".format(ip_info["addr"], ip_info["port"])
        child._log(
            "get_wifi_adb_ip_addr: addr[{}] of serialno '{}'".format(ip_addr, serialno), tolog)

        out, err = child.execute(
            ["shell", "getprop ro.serialno"], serialno=ip_addr, tolog=tolog, **kwargs)
        out = out.strip()
        if len(err):
            child._log("get_wifi_adb_ip_addr: get error: {}".format(err), tolog)
            return None

        if out != serialno:
            child._log("get_wifi_adb_ip_addr: the serialno does not match: " \
                "detected[{}], expected[{}]".format(serialno, out), tolog)
            return None

        return ip_addr

    @classmethod
    def wait_for_device(child, serialno, timeoutsec, tolog=True):
        while not child.is_device_available(serialno=serialno, tolog=tolog) and timeoutsec > 0:
            time.sleep(1)
            timeoutsec -= 1

    @classmethod
    def device_fingerprint(child, serialno=None, **kwargs):
        return child.execute(
            ["shell", "getprop", "ro.vendor.build.fingerprint"], serialno=serialno, **kwargs)

    @classmethod
    def device_stayon(child, serialno=None, on=None, **kwargs):
        if on == None or type(on) is not bool:
            return
        return child.execute(
            ["shell", "svc", "power", "stayon", str(on).lower()], serialno=serialno, **kwargs)

    @classmethod
    def device_keyevent(child, serialno=None, keyevent=None, **kwargs):
        if not keyevent:
            return
        return child.execute(
            ["shell", "input", "keyevent", str(keyevent)], serialno=serialno, **kwargs)

    @classmethod
    def device_keyevent_menu(child, serialno=None, **kwargs):
        return child.device_keyevent(serialno=serialno, keyevent="KEYCODE_MENU", **kwargs)

    @classmethod
    def device_keyevent_power(child, serialno=None, **kwargs):
        return child.device_keyevent(serialno=serialno, keyevent="KEYCODE_POWER", **kwargs)

    @classmethod
    def device_lock(child, serialno=None, tolog=True, **kwargs):
        child._log("lock the screen", tolog)
        child.device_stayon(serialno=serialno, tolog=tolog, on=True, **kwargs)
        child.device_keyevent_power(serialno=serialno, tolog=tolog, **kwargs)
        child.device_stayon(serialno=serialno, tolog=tolog, on=False, **kwargs)

    @classmethod
    def device_unlock(child, serialno=None, tolog=True, **kwargs):
        child._log("unlock the screen", tolog)
        child.device_stayon(serialno=serialno, tolog=tolog, on=True, **kwargs)
        child.device_keyevent_menu(serialno=serialno, tolog=tolog, **kwargs)

    @staticmethod
    def screen_recording_start(serialno=None, tolog=True):
        if not serialno:
            devices = Adb.get_devices(tolog=tolog)
            if len(devices) == 0:
                return False
            serialno = devices[0]

        if serialno in Adb.SCREEN_RECORDING_THREADS:
            return False

        th = AdbScreenRecordingThread(serialno)
        th.start()
        Adb.SCREEN_RECORDING_THREADS[serialno] = th
        return True

    @staticmethod
    def screen_recording_stop(pullto, serialno=None, tolog=True):
        if not serialno:
            devices = Adb.get_devices(tolog=tolog)
            if len(devices) == 0:
                return False
            serialno = devices[0]

        if not serialno in Adb.SCREEN_RECORDING_THREADS:
            return False

        th = Adb.SCREEN_RECORDING_THREADS[serialno]
        th.terminate()
        del Adb.SCREEN_RECORDING_THREADS[serialno]

        time.sleep(1)
        if pullto:
            Adb.execute(
                ["pull", "/sdcard/screenrecord.mp4", pullto], serialno=serialno, tolog=tolog)
        return True

try:
    import functools
    reduce = functools.reduce
except:
    pass

import time

class AudioAdb(Adb):
    TAG = "AudioAdb"

    @staticmethod
    def get_stream_volumes(serialno=None, **kwargs):
        out, _ = AudioAdb.execute(["shell", "dumpsys audio"], serialno=serialno, **kwargs)
        lines = [line.strip() \
            if isinstance(line, str) \
            else line.decode("utf-8").strip() for line in out.splitlines()]
        idices = [idx for idx, line in enumerate(lines) if line.startswith("- STREAM")]
        if len(idices) < 2:
            return None
        nlines = idices[1] - idices[0]
        volumes = {}

        def parse_str_v(str_v):
            str_v = str_v.strip()
            if str_v.lower() in ["true", "false"]:
                return str_v.lower() == "true"

            if str_v.isdigit():
                return int(str_v)

            try:
                return float(str_v)
            except ValueError:
                return str_v

        for idx in idices:
            stream = lines[idx].split()[1][:-1]
            volumes[stream] = {}
            for line in lines[idx+1:idx+nlines]:
                result = [fragment.split(",") for fragment in line.split(":")]
                result = reduce(lambda x, y: x + y, result)
                if len(result) == 2:
                    k, v = result
                    volumes[stream][k.strip()] = parse_str_v(v)
                elif len(result) % 2 == 1:
                    k = result[0]
                    volumes[stream][k] = {}
                    for idx in range(1, len(result), 2):
                        subk, v = result[idx], result[idx+1]
                        volumes[stream][k][subk.strip()] = parse_str_v(v)

        return volumes

    @staticmethod
    def adj_volume(keycode, times, serialno=None, **kwargs):
        for x in range(times):
            AudioAdb.device_keyevent(serialno=serialno, keyevent=keycode, **kwargs)
            time.sleep(0.2)

    @staticmethod
    def inc_volume(serialno=None, volume_steps=1, **kwargs):
        AudioAdb.adj_volume(serialno=serialno, keycode=24, times=volume_steps+1, **kwargs)

    @staticmethod
    def dec_volume(serialno=None, volume_steps=1, **kwargs):
        AudioAdb.adj_volume(serialno=serialno, keycode=25, times=volume_steps+1, **kwargs)

