import socket
import ssl
import json
from datetime import datetime

import threading



class GIA:

    HOST = "api.github.com"
    PORT = 443

    def __init__(self, user, gitHubToken, gistID):


        self.user = user
        self.token = gitHubToken
        self.gistID = gistID
        self.currEtagAndBody = None
        self._ssl_context = ssl.create_default_context()
        self._lock = threading.RLock()



    def _sendRequest(self, request, printing=False):
        try:
            with socket.create_connection((self.HOST, self.PORT)) as sock:
                if printing: print("TCP Connection successful")
                with self._ssl_context.wrap_socket(sock, server_hostname=self.HOST) as ssock:
                    if printing: print("HTTP to HTTPS successful"); print("TLS handshake done")
                    ssock.sendall(request.encode("utf-8"))
                    response = bytearray()
                    while True:
                        data = ssock.recv(4096)
                        if not data: break
                        response.extend(data)

            response = response.decode("utf-8")
            if printing:
                print("Response received")
                print(response)

            try:
                header, body = response.split("\r\n\r\n", 1)
                headers = {}

                for line in header.split("\r\n")[1:]:
                    if ":" in line:
                        key, value = line.split(":", 1)
                        headers[key.strip().lower()] = value.strip()

            except ValueError:
                raise Exception("Invalid HTTP response:\n" + response)

            status = int(header.split()[1])
            if printing: print(f"GitHub returned status code {status}")

            try:
                body = json.loads(body) if body else {}
            except json.JSONDecodeError:
                pass

            if status not in (200, 201, 204, 304):
                raise Exception(f"GitHub API error\nStatus: {status}\nResponse: {json.dumps(body, indent=2)}")
            
            if status == 304:
                if self.currEtagAndBody is None:
                    raise Exception("Received 304 but no cached response exists")
                return self.currEtagAndBody[1]

            if self.currEtagAndBody == None:
                self.currEtagAndBody = (headers["etag"], body)


            return body

        except socket.gaierror as e:
            raise Exception(f"DNS lookup failed: {e}")
        except socket.timeout as e:
            raise Exception(f"Connection timeout: {e}")
        except ConnectionError as e:
            raise Exception(f"Connection error: {e}")
        except ssl.SSLError as e:
            raise Exception(f"SSL/TLS error: {e}")
        except Exception:
            raise

    def log(self, text, file, printing=False):
        # print("START LOGGING")
        try:
            currLog = self.readGist(file="logFile0.txt")
            timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

            self.writeGist(text=f'{currLog}\n{self.user} - {timestamp} - "{text}" in {file}', file="logFile0.txt", log=False, printing=printing)
            if printing:
                print("Log update complete")

        except Exception as e:
            print(f"Logging failed: {e}")
        # print("FINISHED LOGGING")


    def readGist(self, file="cmdFile1.txt", printing=False):
        with self._lock:
            request = (
                f"GET /gists/{self.gistID} HTTP/1.1\r\n"
                f"Host: {self.HOST}\r\n"
                f"Authorization: Bearer {self.token}\r\n"
                "User-Agent: python-socket-client\r\n"
                "Accept: application/vnd.github+json\r\n"
                "Connection: close\r\n"
                "\r\n"
            )

            if printing:
                print("Request built")

            try:
                response = self._sendRequest(request, printing=printing)
            except Exception as e:
                print(f"Gist read failed: {e}")
                raise
                # return False

            files = response.get("files", {})

            if file not in files:
                raise FileNotFoundError(f"{file} not found in gist")

            return files[file]["content"]



    def writeGist(self, text, file="cmdFile1.txt", log=True, printing=False):
        with self._lock:
            update = {
                "files": {
                    file: {
                        "content": text
                    }
                }
            }

            body = json.dumps(update, separators=(",", ":"))

            request = (
                f"PATCH /gists/{self.gistID} HTTP/1.1\r\n"
                f"Host: {self.HOST}\r\n"
                f"Authorization: Bearer {self.token}\r\n"
                "User-Agent: python-socket-client\r\n"
                "Accept: application/vnd.github+json\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body.encode('utf-8'))}\r\n"
                "Connection: close\r\n"
                "\r\n"
                + body
            )
            if printing:
                print("Request built")

            try:
                self._sendRequest(request, printing=printing)
                if log:
                    self.log(text, file)
                return True

            except Exception as e:
                print(f"Gist write failed: {e}")
                return False
        





# https://ark.fandom.com/wiki/Dedicated_server_setup#Windows
# https://ark.wiki.gg/wiki/Server_configuration#Command_line_options
# https://www.youtube.com/watch?v=o1dcWkSzGd4