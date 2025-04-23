# channels.py
"""
Defines simulated communication channels (Quantum, Public) and network setup utilities.
Includes optional color output via colorama.
"""

import socket
import time
import traceback
from config import SOCKET_TIMEOUT

# Optional Colorama Import
try:
    import colorama
    colorama.init(autoreset=True)
    COLOR_ERROR = colorama.Fore.RED
    COLOR_WARNING = colorama.Fore.YELLOW
    COLOR_SUCCESS = colorama.Fore.GREEN
    COLOR_INFO = colorama.Fore.CYAN
    COLOR_RESET = colorama.Style.RESET_ALL
except ImportError:
    print("[Channels] colorama not found, using plain output.")
    COLOR_ERROR = COLOR_WARNING = COLOR_SUCCESS = COLOR_INFO = COLOR_RESET = ""

# --- Simulated Channel Classes ---

class QuantumChannel:
    """Simulates the insecure quantum channel (photon transmission)."""
    def __init__(self, sock, peer_name="Peer"): # peer_name is less critical now
        self.sock = sock
        self.sock.settimeout(SOCKET_TIMEOUT)
        self.peer_name = peer_name # For logging clarity

    def send_photon(self, basis, bit):
        message = f"P:{basis},{bit}"
        try:
            self.sock.sendall(message.encode('utf-8'))
            time.sleep(0.005)
        except socket.error as e:
            print(f"{COLOR_ERROR}[Quantum Channel Error] Failed to send photon to {self.peer_name}: {e}{COLOR_RESET}")
            raise

    def receive_photon(self):
        try:
            data = self.sock.recv(1024)
            if not data:
                print(f"{COLOR_WARNING}[Quantum Channel Warning] Connection closed by {self.peer_name} while receiving photon.{COLOR_RESET}")
                return None, None
            decoded_data = data.decode('utf-8')
            if decoded_data.startswith("P:"):
                parts = decoded_data[2:].split(',')
                if len(parts) == 2:
                    basis, bit = map(int, parts)
                    return basis, bit
                else:
                    print(f"{COLOR_ERROR}[Quantum Channel Error] Received malformed photon data from {self.peer_name}: {decoded_data}{COLOR_RESET}")
                    return None, None
            else:
                # Pass non-photon data up for handling by PublicChannel logic if sharing socket
                return "OTHER", decoded_data
        except socket.timeout:
            print(f"{COLOR_WARNING}[Quantum Channel Warning] Timeout receiving photon from {self.peer_name}.{COLOR_RESET}")
            return None, None
        except (socket.error, ValueError, UnicodeDecodeError) as e:
            print(f"{COLOR_ERROR}[Quantum Channel Error] Error receiving photon from {self.peer_name}: {e}{COLOR_RESET}")
            return None, None

class PublicChannel:
    """Simulates the authenticated public classical channel."""
    def __init__(self, sock, peer_name="Peer"): # peer_name is less critical now
        self.sock = sock
        self.sock.settimeout(SOCKET_TIMEOUT)
        self.peer_name = peer_name

    def send(self, data_type, data):
        message = f"{data_type}:{data}"
        try:
            self.sock.sendall(message.encode('utf-8'))
        except socket.error as e:
            print(f"{COLOR_ERROR}[Public Channel Error] Failed to send {data_type} to {self.peer_name}: {e}{COLOR_RESET}")
            raise

    def receive(self):
        try:
            data = self.sock.recv(4096)
            if not data:
                print(f"{COLOR_WARNING}[Public Channel Warning] Connection closed by {self.peer_name} while receiving data.{COLOR_RESET}")
                return None, None
            decoded_data = data.decode('utf-8')
            if ':' in decoded_data:
                data_type, content = decoded_data.split(':', 1)
                return data_type, content
            else:
                if decoded_data.startswith("P:"):
                    print(f"{COLOR_WARNING}[Public Channel Warning] Received photon data on public channel from {self.peer_name}. Likely sync issue.{COLOR_RESET}")
                    return "PHOTON_ON_PUBLIC", decoded_data
                print(f"{COLOR_ERROR}[Public Channel Error] Received malformed data (no type) from {self.peer_name}: {decoded_data}{COLOR_RESET}")
                return None, None
        except socket.timeout:
            print(f"{COLOR_WARNING}[Public Channel Warning] Timeout receiving public data from {self.peer_name}.{COLOR_RESET}")
            return None, None
        except (socket.error, ValueError, UnicodeDecodeError) as e:
            print(f"{COLOR_ERROR}[Public Channel Error] Error receiving public data from {self.peer_name}: {e}{COLOR_RESET}")
            return None, None

# --- Network Setup Utilities ---

def setup_server_listener(host, port):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_sock.bind((host, port))
        server_sock.listen(1)
        print(f"{COLOR_INFO}[Network Setup] Server listening on {host}:{port}...{COLOR_RESET}")
        return server_sock
    except socket.error as e:
        print(f"{COLOR_ERROR}[Network Setup Error] Failed to bind/listen on {host}:{port}: {e}{COLOR_RESET}")
        traceback.print_exc()
        if server_sock: server_sock.close()
        raise

def accept_connection(server_sock, client_name="Client"):
    try:
        print(f"{COLOR_INFO}[Network Setup] Waiting to accept connection from {client_name} on {server_sock.getsockname()}...{COLOR_RESET}")
        conn, addr = server_sock.accept()
        conn.settimeout(SOCKET_TIMEOUT)
        print(f"{COLOR_SUCCESS}[Network Setup] Accepted connection from {client_name} at {addr}{COLOR_RESET}")
        return conn, addr
    except socket.timeout:
        print(f"{COLOR_ERROR}[Network Setup Error] Timeout waiting for {client_name} on {server_sock.getsockname()}.{COLOR_RESET}")
        raise
    except socket.error as e:
        print(f"{COLOR_ERROR}[Network Setup Error] Failed to accept connection from {client_name}: {e}{COLOR_RESET}")
        traceback.print_exc()
        raise

def setup_client(host, port, server_name="Server"):
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_sock.settimeout(SOCKET_TIMEOUT)
    try:
        print(f"{COLOR_INFO}[Network Setup] Attempting to connect client to {server_name} at {host}:{port}...{COLOR_RESET}")
        client_sock.connect((host, port))
        print(f"{COLOR_SUCCESS}[Network Setup] Client connected successfully to {server_name} at {host}:{port}.{COLOR_RESET}")
        return client_sock
    except socket.timeout:
        print(f"{COLOR_ERROR}[Network Setup Error] Timeout connecting client to {server_name} at {host}:{port}.{COLOR_RESET}")
        if client_sock: client_sock.close()
        raise
    except socket.error as e:
        print(f"{COLOR_ERROR}[Network Setup Error] Failed to connect client to {server_name} at {host}:{port}: {e}{COLOR_RESET}")
        traceback.print_exc()
        if client_sock: client_sock.close()
        raise