from pathlib import Path
import subprocess

from ArkMap_class import *
from X_Files import admPw

import a2s
import time



def ConsoleLog(m):
    print(m)





def terminate_process(proc, timeout=15):
    if proc is None:
        return

    if proc.poll() is not None:
        return

    proc.terminate()

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"Process {proc.pid} did not terminate. Killing it.")
        proc.kill()
        proc.wait()


HOST = "127.0.0.1"

def checkStatusQuery(mainM: ArkMap):

    address = (HOST, mainM.queryPort)
    
    ConsoleLog(f"- address: {address}")
    try:
        print("checkin a2s...")
        info = a2s.info(address)
        print("done")

        expected_name = f"The Final Ascension - {mainM.displayName} - (v361.7)"
        ConsoleLog(f"- expected: {expected_name}, got: {info.server_name}")
        if info.server_name != expected_name:
            ConsoleLog(f"- Wrong server answered {mainM.queryPort}: "f"- {info.server_name}")
            return False
        ConsoleLog("worked!")
        ConsoleLog("iterating maps...")
        for m in allMaps:
            if m.queryPort == mainM.queryPort:
                m.playerCount = info.player_count
                m.lastTimeRunning = time.monotonic()
                ConsoleLog("found correct")
                ConsoleLog(f"- expected map: {mainM.displayName}, got: {m.displayName}")
                ConsoleLog(f"- playerCount: {info.player_count}\n")

        return True

    except Exception as e:
        time.sleep(2)
        ConsoleLog(f"failed in checkStatusQuery : {e}")
        return False


def startArkServer(m):

    # Folder containing ShooterGameServer.exe
    server_dir = Path(
        r"C:\servers\ARK\the_final_ascension\ShooterGame\Binaries\Win64"
    )

    exe = server_dir / "ShooterGameServer.exe"

    if not exe.exists():
        raise FileNotFoundError(f"Could not find:\n{exe}")

    ServerAdminPassword = admPw
    ServerPassword = "1984"
    MaxPlayers = str(ArkMap.MAX_PLAYERS)
    difficulty = "5.0"
    difficultyOffset = "1.0"
    activeEvent = "none"
    clusterID = "tree12345"

    displayArk = m.displayName
    internalArk = m.internalName
    saveDirName = displayArk
    SessionName = f"The Final Ascension - {displayArk}"
    Port = m.Port
    QueryPort = m.queryPort
    RconPort = m.rconPort

    map_arg = (
        f"{internalArk}"
        f"?SessionName={SessionName}"
        f"?MaxPlayers={MaxPlayers}"
        f"?OverrideOfficialDifficulty={difficulty}"
        f"?DifficultyOffset={difficultyOffset}"
        f"?AltSaveDirectoryName={saveDirName}"
        f"?ServerPassword={ServerPassword}"
        f"?ServerAdminPassword={ServerAdminPassword}"
        f"?Port={Port}"
        f"?QueryPort={QueryPort}"
        f"?RCONEnabled=True"
        f"?RCONPort={RconPort}"
        f"?listen"
    )

    cmd = [
        str(exe),
        map_arg,
        "-NoBattleEye",
        "-NoTransferFromFiltering",
        f"-clusterid={clusterID}",
        f"-activeevent={activeEvent}",
        "-noundermeshkilling",
    ]

    print("\nLaunching:\n")
    print(" ".join(cmd))
    print()

    proc = subprocess.Popen(
        cmd,
        cwd=server_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )

    try:
        timeout = 180
        start_time = time.monotonic()

        while time.monotonic() - start_time < timeout:

            if proc.poll() is not None:
                raise RuntimeError(f"{m.displayName} exited during startup " f"with code {proc.returncode}")

            ConsoleLog(f"checking Query at {round(time.monotonic() - start_time)}")
            if checkStatusQuery(m):
                ConsoleLog("-> success")
                m.process = proc
                m.pid = proc.pid
                ConsoleLog(f"setting status from {m.status} to {ArkMap.RUNNING}")
                m.status = ArkMap.RUNNING
                return

            time.sleep(2)

        raise TimeoutError(f"{m.displayName} failed to start within {timeout}s")

    except Exception:
        terminate_process(proc)

        m.process = None
        m.pid = None
        m.status = ArkMap.INACTIVE
        m.playerCount = 0
        m.lastTimeRunning = None
        m.lastUsed = None

        raise


if __name__ == "__main__":
    startArkServer(TheCenter)