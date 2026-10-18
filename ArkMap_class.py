from GIA_class import GIA
from X_Files import token, gist_id

import threading
import uuid

chars = [
    'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j',
    'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't',
    'u', 'v', 'w', 'x', 'y', 'z',
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',
    'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T',
    'U', 'V', 'W', 'X', 'Y', 'Z',
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9'
]

giaLock = threading.Lock()
mapLock = threading.Lock()
bufferLock = threading.Lock()

class ArkMap:

    STARTING = 0
    STOPPING = 1
    INACTIVE = 2
    RUNNING = 3

    MAX_SERVERS = 3
    MAX_PLAYERS = 3
    SHUTDOWN_COOLDOWN = 1

    CURR_USER = "N/A"
    CURR_GIA:GIA = None

    BUFFER = []

    def __init__(self, internalName, port, displayName=None):
        self.internalName = internalName
        if displayName is None:
            self.displayName = self.internalName
        else:
            self.displayName = displayName

        self.Port = port
        self.queryPort = 27055 + (port-7777)//2
        self.rconPort= 27015 + (port-7777)//2

        self.pid = None
        self.process = None
        self.lastTimeRunning = None

        self.lastUsed = None

        self.keepOnPerm = 1
        self.keepOnTemp = 0

        self.playerCount = 0

        self.status = ArkMap.INACTIVE


    @staticmethod
    def addCommand(command):
        if command in [c["command"] for c in ArkMap.BUFFER]:
            return
        
        commandid = ArkMap.generateUUID()

        commandData = {"id": commandid, "command": command}

        # with bufferLock:
        ArkMap.BUFFER.append(commandData)

        # ArkMap.startSending()
        #start sending is commented out because otherwise its not checked if previous command has done or is part of curr buffer 
        # --> just waitr for bufferCTLR to handle the command


    @staticmethod
    def startSending():
        threading.Thread(target=ArkMap._sendNextCommand,daemon=True).start()


    @staticmethod
    def _sendNextCommand():
        with bufferLock:
            if not ArkMap.BUFFER:
                return

            commandData = ArkMap.BUFFER[0]

        command = f"{commandData['id']}|{commandData['command']}|Pending"

        with giaLock:
            if ArkMap.CURR_GIA is None:
                ArkMap.CURR_GIA = GIA(ArkMap.CURR_USER, token, gist_id)

            ArkMap.CURR_GIA.writeGist(command, file="cmdFile1.txt")


    @staticmethod
    def bufferCTLR():
        with giaLock:
            if ArkMap.CURR_GIA is None:
                ArkMap.CURR_GIA = GIA(ArkMap.CURR_USER, token, gist_id)

            response = ArkMap.CURR_GIA.readGist(file="cmdFile1.txt")
            
        with bufferLock:
            if not ArkMap.BUFFER:
                return

            response_id = response.split("|", 1)[0]
            current = ArkMap.BUFFER[0]

            # if (response_id != current["id"]) and not response.endswith("|Done"):
            #     return
            
            if response.endswith("|Done") or "|Failed:" in response:
                if response_id == current["id"]:
                    ArkMap.BUFFER.pop(0)

                if not ArkMap.BUFFER:
                    return

                ArkMap.startSending()


    @staticmethod
    def getBuffer():
        with bufferLock:
            return ArkMap.BUFFER.copy()


    @staticmethod
    def getBufferSize():
        with bufferLock:
            return len(ArkMap.BUFFER)




    def startS(self):
        ArkMap.addCommand(f"start {self.displayName}")

    def stopS(self):
        ArkMap.addCommand(f"stop {self.displayName}")

    def setKeepOnPerm(self, n):
        ArkMap.addCommand(f"set2 {self.displayName} keepOnPerm {n}")

    def setKeepOnTemp(self, n):
        ArkMap.addCommand(f"set2 {self.displayName} keepOnTemp {n}")

    @staticmethod
    def setKeepOnServer(n):
        ArkMap.addCommand(f"set1 maxShutdownCooldown {n}")

    @staticmethod
    def setMaxServers(n):
        n = int(float(n))
        ArkMap.addCommand(f"set1 maxServers {n}")

    @staticmethod
    def setMaxPlayers(n):
        n = int(float(n))
        ArkMap.addCommand(f"set1 maxPlayers {n}")





    @staticmethod
    def updateFromRemote():
            
        with giaLock:
            if ArkMap.CURR_GIA is None:
                ArkMap.CURR_GIA = GIA(ArkMap.CURR_USER, token, gist_id)

            response = ArkMap.CURR_GIA.readGist(file="serverStatusFile2.txt")


        for line in response.splitlines():
            if line.strip() == "":
                continue
            prefix, data = line.split("|", 1)
            prefix = prefix.strip()
            data = data.strip()


            if prefix == "PERMAP":
                values = {}

                for item in data.split():
                    key, value = item.split(":", 1)
                    values[key] = value

                currMap = ArkMap.getMap(values["MapName"])

                if currMap is None:
                    continue

                status = values["Status"]

                if status == "starting":
                    currMap.status = ArkMap.STARTING
                elif status == "online":
                    currMap.status = ArkMap.RUNNING
                elif status == "stopping":
                    currMap.status = ArkMap.STOPPING
                elif status == "offline":
                    currMap.status = ArkMap.INACTIVE

                currMap.playerCount = int(values["PlayerCount"])
                currMap.keepOnTemp = float(values["KeepOnTemp"])
                currMap.keepOnPerm = float(values["KeepOnPerm"])



            elif prefix == "GLOBAL":
                parts = data.split(":", 1)

                key, value = parts

                if "MAX_SERVERS"== key:
                    ArkMap.MAX_SERVERS = int(value)
                elif "MAX_PLAYERS"== key:
                    ArkMap.MAX_PLAYERS = int(value)
                elif "SHUTDOWN_COOLDOWN"== key:
                    ArkMap.SHUTDOWN_COOLDOWN = float(value)

    @staticmethod
    def generateUUID():
        return str(uuid.uuid4())


    @staticmethod
    def setCurrUser(user):
        ArkMap.CURR_USER = user
        ArkMap.CURR_GIA = GIA(ArkMap.CURR_USER, token, gist_id)

    @staticmethod
    def getMap(string):
        for m in allMaps:
            if m.displayName == string:
                return m

    @staticmethod
    def getAllRunnings():
        with mapLock:
            res = []
            for m in allMaps:
                if m.status == ArkMap.RUNNING:
                    res.append(m)
            return res

    @staticmethod
    def getAllStartings():
        with mapLock:
            res = []
            for m in allMaps:
                if m.status == ArkMap.STARTING:
                    res.append(m)
            return res

    def getPlayerCount(self):
        "fix with playerCount"
        return self.playerCount

    @staticmethod
    def getMaxServers():
        return ArkMap.MAX_SERVERS


    def __str__(self):
        return self.displayName





TheIsland = ArkMap(displayName="TheIsland", internalName="TheIsland", port=7777)
ScorchedEarth = ArkMap(displayName="ScorchedEarth", internalName="ScorchedEarth_P", port=7779)
Aberration = ArkMap(displayName="Aberration", internalName="Aberration_P", port=7781)
Extinction = ArkMap(displayName="Extinction", internalName="Extinction", port=7783)
Genesis1 = ArkMap(displayName="Genesis1", internalName="Genesis", port=7785)
Genesis2 = ArkMap(displayName="Genesis2", internalName="Gen2", port=7787)

TheCenter = ArkMap(displayName="TheCenter", internalName="TheCenter", port=7789)
Ragnarok = ArkMap(displayName="Ragnarok", internalName="Ragnarok", port=7791)
Valguero = ArkMap(displayName="Valguero", internalName="Valguero_P", port=7793)
CrystalIsles = ArkMap(displayName="CrystalIsles", internalName="CrystalIsles", port=7795)
LostIsland = ArkMap(displayName="LostIsland", internalName="LostIsland", port=7797)
Fjordur = ArkMap(displayName="Fjordur", internalName="Fjordur", port=7799)


allCanonMaps = [
    TheIsland,
    ScorchedEarth,
    Aberration,
    Extinction,
    Genesis1,
    Genesis2
]

allModMaps = [
    TheCenter,
    Ragnarok,
    Valguero,
    CrystalIsles,
    LostIsland,
    Fjordur
]

allMaps = allCanonMaps + allModMaps