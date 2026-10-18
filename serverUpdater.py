from GIA_class import GIA
from X_Files import token, gist_id
from ArkMap_class import *
from trackPIDwrite import startArkServer
import subprocess
import time
import a2s

import threading


import comtypes
from comtypes import GUID
from comtypes.client import CreateObject
import time
from datetime import datetime


from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

KNOWN_IDS_FILE = BASE_DIR / "knownIDs.txt"




class IProgressDialog(comtypes.IUnknown):
    _iid_ = GUID("{EBBC7C04-315E-11D2-B62F-006097DF5BD4}")

    _methods_ = [
        comtypes.STDMETHOD(None, "StartProgressDialog",
            [comtypes.c_void_p, comtypes.c_void_p, comtypes.c_ulong, comtypes.c_void_p]),
        comtypes.STDMETHOD(None, "StopProgressDialog", []),
        comtypes.STDMETHOD(None, "SetTitle", [comtypes.c_wchar_p]),
        comtypes.STDMETHOD(None, "SetAnimation",
            [comtypes.c_void_p, comtypes.c_uint]),
        comtypes.STDMETHOD(comtypes.c_int, "HasUserCancelled", []),
        comtypes.STDMETHOD(None, "SetProgress",
            [comtypes.c_ulong, comtypes.c_ulong]),
        comtypes.STDMETHOD(None, "SetProgress64",
            [comtypes.c_ulonglong, comtypes.c_ulonglong]),
        comtypes.STDMETHOD(None, "SetLine",
            [comtypes.c_uint, comtypes.c_wchar_p, comtypes.c_int, comtypes.c_void_p]),
    ]

def progress_timer(seconds):
    comtypes.CoInitialize()

    try:
        progress = CreateObject(
            "{F8383852-FCD3-11D1-A6B9-006097DF5BD4}",
            interface=IProgressDialog
        )

        progress.SetTitle("Timer Running...")
        progress.StartProgressDialog(None, None, 0, None)

        start = time.time()

        try:
            while (elapsed := time.time() - start) < seconds:
                if progress.HasUserCancelled():
                    return False

                percent = int((elapsed / seconds) * 100)
                remaining = int(seconds - elapsed)

                progress.SetLine(1, f"Remaining: {remaining}s", 0, None)
                progress.SetProgress(percent, 100)

                time.sleep(0.1)

            return True

        finally:
            progress.StopProgressDialog()

    finally:
        comtypes.CoUninitialize()




HOST = "127.0.0.1"

def checkStatusQuery():
    while serverActive:
        for currM in allMaps:

            if currM.process is None:
                continue

            # Process died
            if currM.process.poll() is not None:
                print(f"{currM.displayName} exited "f"with code {currM.process.returncode}")

                currM.process = None
                currM.pid = None
                currM.status = ArkMap.INACTIVE
                currM.playerCount = 0
                currM.lastTimeRunning = None
                currM.lastUsed = None

                continue

            try:
                address = (HOST, currM.queryPort)
                info = a2s.info(address)

                currM.playerCount = info.player_count

                if currM.lastTimeRunning is None:
                    currM.lastTimeRunning = time.monotonic()
                    currM.lastUsed = currM.lastTimeRunning

                if currM.playerCount > 0:
                    currM.lastUsed = time.monotonic()

            except Exception:
                continue

        time.sleep(2)




def start(map):
    currMap = ArkMap.getMap(map)

    if currMap is None:
        print(f"Unknown map: {map}")
        return

    running = sum(m.process is not None for m in allMaps)

    if running >= ArkMap.MAX_SERVERS:
        print("Maximum server limit reached")
        return

    if currMap.process is not None:
        print(f"{map} is already running/starting")
        return


    currMap.lastTimeRunning = None
    currMap.lastUsed = None
    currMap.playerCount = 0
    currMap.status = ArkMap.STARTING

    try:
        startArkServer(currMap)

    except Exception as e:
        print(f"Failed to start {map}: {e}")

        currMap.process = None
        currMap.pid = None
        currMap.status = ArkMap.INACTIVE
        currMap.playerCount = 0
        currMap.lastTimeRunning = None
        currMap.lastUsed = None
        raise




def stop(map):
    currMap = ArkMap.getMap(map)

    if currMap is None:
        print(f"Unknown map: {map}")
        return

    if currMap.process is None:
        currMap.status = ArkMap.INACTIVE
        return

    currMap.status = ArkMap.STOPPING
    currMap.process.terminate()

    try:
        currMap.process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        currMap.process.kill()
        currMap.process.wait()


    currMap.process = None
    currMap.pid = None
    currMap.status = ArkMap.INACTIVE
    currMap.playerCount = 0
    currMap.lastTimeRunning = None
    currMap.lastUsed = None


def set1(var, n):
    n = float(n)
    match var:
        case "maxServers":
            ArkMap.MAX_SERVERS=int(n)
        case "maxPlayers":
            ArkMap.MAX_PLAYERS=int(n)
        case "maxShutdownCooldown":            
            ArkMap.SHUTDOWN_COOLDOWN=n

def set2(map, var, n):
    n = float(n)
    m = ArkMap.getMap(map)
    match var:
        case "keepOnPerm":
            m.keepOnPerm = n
        case "keepOnTemp":
            m.keepOnTemp = n

cmdDict = {"start": start,
           "stop": stop,
           "set1": set1,
           "set2": set2}



def runCMD():
    while serverActive:
        cmdString = "<unread>"
        try:
            cmdString = gia.readGist(file="cmdFile1.txt").strip()

            if not cmdString:
                time.sleep(2)
                continue

            command_id, command_text = cmdString.split("|")[0], cmdString.split("|")[1]

            with open(KNOWN_IDS_FILE, "r") as file:
                known_ids = {line.strip() for line in file}

            if command_id in known_ids:
                did = gia.writeGist(f"{cmdString}|Done", file="cmdFile1.txt", log=False)
                time.sleep(2)
                continue

            parts = command_text.split()
            cmd = parts[0]
            args = parts[1:]

            func = cmdDict.get(cmd)

            if func is None:
                raise ValueError(f"Unknown command: {cmd}")

            func(*args)

            if not did:
                raise RuntimeError("Failed to send command completion to GitHub")


            with open(KNOWN_IDS_FILE, "a") as file:
                file.write(f"{command_id}\n")

            

        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Command failed: {cmdString!r}: {e}")
            gia.writeGist(f"{('|'.join(cmdString.split('|')[:2]))}|Failed: for error check log file", file="cmdFile1.txt", log=False)
            
        time.sleep(5)


def UpdateTheRemote():
    last = ""
    while serverActive:
        res = ""
        for m in allMaps:
            match m.status:
                case ArkMap.INACTIVE:
                    mode = "offline"
                case ArkMap.RUNNING:
                    mode = "online"
                case ArkMap.STARTING:
                    mode = "starting"
                case ArkMap.STOPPING:
                    mode = "stopping"
            res += f"PERMAP| MapName:{m.displayName} Status:{mode} PlayerCount:{m.playerCount} KeepOnTemp:{m.keepOnTemp} KeepOnPerm:{m.keepOnPerm}\n"
        res += "\n"
        res += f"GLOBAL| MAX_SERVERS:{ArkMap.MAX_SERVERS}\n"
        res += f"GLOBAL| MAX_PLAYERS:{ArkMap.MAX_PLAYERS}\n"
        res += f"GLOBAL| SHUTDOWN_COOLDOWN:{ArkMap.SHUTDOWN_COOLDOWN}"


        if res != last:
            if gia.writeGist(text=res, file="serverStatusFile2.txt", log=False):
                last = res
        time.sleep(5)



def shutDown():
    global serverActive
    gia.writeGist(text="offline", file="serverStatusFile3.txt", log=True)
    serverActive = False
    subprocess.run(["shutdown", "/s", "/t", "60"], check=True)

def checkForShutdown():
    global serverActive
    dontAskAgain = False

    while serverActive:
        allInactive = True
        hadRunningServer = False
        now = time.monotonic()


        for m in allMaps:
            if m.lastUsed is None:
                continue

            hadRunningServer = True

            if (now - m.lastUsed) / 60 < ArkMap.SHUTDOWN_COOLDOWN:
                allInactive = False

        if hadRunningServer and allInactive:
            if not dontAskAgain and progress_timer(30):
                shutDown()
            else:
                dontAskAgain = True

        time.sleep(3)


def checkForStopS():
     while serverActive:
        for m in allMaps:
            if m.lastUsed is None:
                continue
            if m.keepOnTemp:
                currKeepOn = max(m.keepOnPerm, m.keepOnTemp)
                if (time.monotonic() - m.lastUsed)/60 >= currKeepOn:
                    stop(m.displayName)
            else:
                if (time.monotonic() - m.lastUsed)/60 >= m.keepOnPerm:
                    stop(m.displayName)
        time.sleep(3)

serverActive = True

gia = GIA(user="_server", gitHubToken=token, gistID=gist_id)
gia.writeGist(text="online", file="serverStatusFile3.txt", log=True)

threading.Thread(target=runCMD, daemon=True).start()
threading.Thread(target=UpdateTheRemote, daemon=True).start()
threading.Thread(target=checkForStopS, daemon=True).start()
threading.Thread(target=checkForShutdown, daemon=True).start()
threading.Thread(target=checkStatusQuery, daemon=True).start()





while serverActive:
    time.sleep(1)





