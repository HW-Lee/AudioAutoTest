from pyaatlibs.adbutils import Adb
from pyaatlibs.logger import Logger


class AppInterface(object):

    @classmethod
    def log(child, msg):
        Logger.log(child.TAG, msg)

    @staticmethod
    def get_apk_version():
        raise (NotImplementedError("not implemented"))

    @staticmethod
    def get_apk_path():
        raise (NotImplementedError("not implemented"))

    @staticmethod
    def get_launch_component():
        raise (NotImplementedError("not implemented"))

    @staticmethod
    def get_package():
        raise (NotImplementedError("not implemented"))

    @classmethod
    def clear_data(child, serialno=None, tolog=True):
        Adb.execute(["shell", "pm clear {}".format(child.PACKAGE)], serialno=serialno, tolog=tolog)

    @classmethod
    def installed(child, serialno=None, tolog=True):
        out, _ = Adb.execute(["shell", "pm list packages"], serialno=serialno, tolog=tolog)
        packages = [
            line.split(":")[-1].strip() for line in out.splitlines() if line.startswith("package:")
        ]
        return child.get_package() in packages

    @classmethod
    def install(child, grant=False, serialno=None, tolog=True):
        params = ["-r", "-d"]
        if grant:
            params.append("-g")
        params.append(child.get_apk_path())
        Adb.execute(["install"] + params, serialno=serialno, tolog=tolog)

    @classmethod
    def uninstall(child, serialno=None, tolog=True):
        Adb.execute(["uninstall", child.get_package()], serialno=serialno, tolog=tolog)

    @classmethod
    def get_permissions(child, serialno=None, tolog=True):
        if not child.installed(serialno=serialno, tolog=tolog):
            child.log("{} should be installed on the device.".format(child.TAG))
            return None

        out, _ = Adb.execute(
            ["shell", "dumpsys package {}".format(child.get_package())],
            serialno=serialno,
            tolog=tolog,
        )
        lines = out.splitlines()
        requested_perm_idx = [
            idx for idx, line in enumerate(lines) if "requested permissions:" == line.strip()
        ][0]
        install_perm_idx = [
            idx for idx, line in enumerate(lines) if "install permissions:" == line.strip()
        ][0]
        install_perm_idx_end = (
            [
                idx
                for idx, line in enumerate(lines[install_perm_idx + 1 :])
                if not "android.permission." in line
            ][0]
            + install_perm_idx
            + 1
        )

        runtime_perm_idx = [
            idx for idx, line in enumerate(lines) if "runtime permissions:" == line.strip()
        ][0]

        try:
            runtime_perm_idx_end = (
                [
                    idx
                    for idx, line in enumerate(lines[runtime_perm_idx + 1 :])
                    if not "android.permission." in line
                ][0]
                + runtime_perm_idx
                + 1
            )
        except IndexError:
            runtime_perm_idx_end = len(lines)

        requested_perms = [
            line.strip() for line in lines[requested_perm_idx + 1 : install_perm_idx]
        ]
        install_perms = [
            line.strip() for line in lines[install_perm_idx + 1 : install_perm_idx_end]
        ]
        runtime_perms = [
            line.strip() for line in lines[runtime_perm_idx + 1 : runtime_perm_idx_end]
        ]

        perms = {}
        for perm in requested_perms:
            perms[perm.split(":")[0]] = False
        for perm in install_perms:
            if not "granted=" in perm:
                continue
            perms[perm.split(":")[0]] = perm.split("granted=")[-1].lower() == "true"
        for perm in runtime_perms:
            if not "granted=" in perm:
                continue
            perms[perm.split(":")[0]] = (
                perm.split(":")[-1].split(",")[0].split("granted=")[-1].lower() == "true"
            )

        return perms

    @classmethod
    def grant_permissions(child, serialno=None, tolog=True, warning=True):
        for perm, granted in child.get_permissions(serialno=serialno, tolog=tolog).items():
            if granted or not perm.startswith("android.permission."):
                continue
            cmd = "pm grant {} {}".format(child.get_package(), perm)
            out, err = Adb.execute(["shell", cmd], serialno=serialno, tolog=tolog)
            if warning and len(err) > 0:
                child.log("grant permission failed: {}".format(err.strip()))

    @classmethod
    def launch_app(child, device=None, serialno=None):
        Adb.execute(
            ["shell", "am start -n {}".format(child.get_launch_component())], serialno=serialno
        )

    @classmethod
    def stop_app(child, device=None, serialno=None):
        Adb.execute(["shell", "am force-stop {}".format(child.get_package())], serialno=serialno)
