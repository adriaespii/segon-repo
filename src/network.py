import socket
import pickle
import struct
import pygame
import threading # Use threads for connection handling

PORT = 5555

class Network:
    def __init__(self):
        self.socket = None
        self.is_host = False
        self.connection_status = "IDLE" # IDLE, HOSTING, CONNECTING, CONNECTED, FAILED
        self.host_thread = None

    def get_local_interfaces(self):
        # Returns list of (Name, IP)
        interfaces = []
        try:
             # Get hostname
             hostname = socket.gethostname()
             # Get all IPs
             # This is tricky in Python cross-platform without external libs like netifaces.
             # We will try getaddrinfo.
             
             infos = socket.getaddrinfo(hostname, None)
             seen = set()
             for info in infos:
                 ip = info[4][0]
                 if ":" not in ip and ip not in seen: # IPv4 only
                     seen.add(ip)
                     interfaces.append(("Local IP", ip))
             
             # Always add localhost
             if "127.0.0.1" not in seen:
                 interfaces.append(("Localhost", "127.0.0.1"))
                 
        except:
             interfaces.append(("Localhost", "127.0.0.1"))
             
        return interfaces

    def start_host_nonblocking(self, bind_ip="0.0.0.0"):
        self.connection_status = "HOSTING"
        self.host_thread = threading.Thread(target=self._host_thread_func, args=(bind_ip,))
        self.host_thread.daemon = True # Daemon thread dies with main
        self.host_thread.start()
        
    def _host_thread_func(self, bind_ip):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Allow reuse address
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((bind_ip, PORT))
            self.server_socket.listen(1)
            print(f"[HOST] Listening on {bind_ip}:{PORT}...")
            
            # This blocks, but it's in a thread now!
            conn, addr = self.server_socket.accept()
            print(f"[HOST] Connected to {addr}")
            
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            conn.settimeout(0.005) 
            
            self.socket = conn
            self.is_host = True
            self.connection_status = "CONNECTED"
        except Exception as e:
            print(f"[HOST] Error: {e}")
            self.connection_status = "FAILED"

    def connect_to_host(self, ip):
        self.connection_status = "CONNECTING"
        # We can do this in a thread too if we want a "Connecting..." screen
        # But connect usually fails fast or succeeds fast on LAN.
        # Let's use a thread anyway for better UX.
        t = threading.Thread(target=self._client_connect_func, args=(ip,))
        t.daemon = True
        t.start()
        
    def _client_connect_func(self, ip):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((ip, PORT))
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.settimeout(0.005)
            self.is_host = False
            self.connection_status = "CONNECTED"
        except Exception as e:
             print(f"[CLIENT] Connection failed: {e}")
             self.connection_status = "FAILED"

    def send(self, data):
        if not self.socket or self.connection_status != "CONNECTED": return
        try:
            serialized = pickle.dumps(data)
            length = struct.pack('!I', len(serialized))
            self.socket.sendall(length + serialized)
        except Exception as e:
            # print(f"[NET] Send Error: {e}")
            pass

    def receive(self):
        if not self.socket or self.connection_status != "CONNECTED": return None
        try:
            length_data = self._recv_all(4)
            if not length_data: return None
            length = struct.unpack('!I', length_data)[0]
            payload = self._recv_all(length)
            if not payload: return None
            return pickle.loads(payload)
        except socket.timeout:
            return None
        except Exception as e:
            # print(f"[NET] Receive Error: {e}")
            return None

    def _recv_all(self, n):
        data = bytearray()
        while len(data) < n:
            try:
                packet = self.socket.recv(n - len(data))
                if not packet: return None
                data.extend(packet)
            except socket.timeout:
                # If we timeout in the MIDDLE of a packet, that's bad.
                # But for now, just return None and drop packet.
                # Ideally we should buffer.
                return None 
            except:
                return None
        return data

    def close(self):
        if self.socket:
            try: self.socket.close() 
            except: pass
        if getattr(self, 'server_socket', None):
             try: self.server_socket.close()
             except: pass
