import socket
import pickle
import struct
import pygame
import threading
import time

PORT = 5555
UDP_PORT = 5556

class UDPDiscovery:
    def __init__(self, username="Wizard"):
        self.username = username
        self.running = False
        self.peers = {} # {ip: {"name": name, "last_seen": time}}
        self.broadcast_sock = None
        self.listen_sock = None
        self.lock = threading.Lock()
        self.bind_ip = "0.0.0.0"

    def start(self, bind_ip="0.0.0.0"):
        self.running = True
        self.bind_ip = bind_ip
        
        # Broadcast Socket
        self.broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Listen Socket
        self.listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.listen_sock.bind((self.bind_ip, UDP_PORT))
        except:
            print("UDP Bind Failed")
            
        threading.Thread(target=self._broadcast_loop, daemon=True).start()
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _broadcast_loop(self):
        while self.running:
            msg = f"WIZARD_DISCOVERY:{self.username}".encode()
            try:
                self.broadcast_sock.sendto(msg, ('<broadcast>', UDP_PORT))
            except: pass
            time.sleep(2)

    def _listen_loop(self):
        while self.running:
            try:
                data, addr = self.listen_sock.recvfrom(1024)
                msg = data.decode()
                if msg.startswith("WIZARD_DISCOVERY:"):
                    name = msg.split(":")[1]
                    ip = addr[0]
                    # Don't discover self ideally, but local testing needs it maybe?
                    # if ip != socket.gethostbyname(socket.gethostname()):
                    with self.lock:
                        self.peers[ip] = {"name": name, "last_seen": time.time()}
            except: pass

    def get_peers(self):
        # Clean old peers
        now = time.time()
        with self.lock:
            to_remove = [ip for ip, data in self.peers.items() if now - data["last_seen"] > 5]
            for ip in to_remove: del self.peers[ip]
            return self.peers.copy()

    def stop(self):
        self.running = False
        if self.broadcast_sock: self.broadcast_sock.close()
        if self.listen_sock: self.listen_sock.close()


class Network:
    def __init__(self):
        self.socket = None
        self.is_host = False
        self.connection_status = "IDLE" 
        self.discovery = UDPDiscovery()
        self.server_socket = None
        
        # Invite System
        self.incoming_invite = None # {ip: ..., name: ...}
        self.lock = threading.Lock()
        self.bind_ip = "0.0.0.0"
    
    def get_local_interfaces(self):
        """Returns a list of local IP addresses."""
        try:
            hostname = socket.gethostname()
            ips = socket.gethostbyname_ex(hostname)[2]
            if not ips: return ["127.0.0.1"]
            return ips
        except:
            return ["127.0.0.1"]

    def start_discovery(self, bind_ip="0.0.0.0"):
        self.bind_ip = bind_ip
        self.discovery.start(bind_ip)
        # Also start listening for TCP Setup
        self._start_tcp_listener()
        
    def stop(self):
        self.discovery.stop()
        if self.socket: self.socket.close()
        if self.server_socket: self.server_socket.close()

    def _start_tcp_listener(self):
        # Listen for Incoming Invites / Connections
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.bind_ip, PORT))
            self.server_socket.listen(5)
            threading.Thread(target=self._accept_loop, daemon=True).start()
        except Exception as e:
            print(f"TCP Bind Error: {e}")

    def _accept_loop(self):
        while True:
            try:
                conn, addr = self.server_socket.accept()
                # Handle new connection
                # We expect a handshake
                threading.Thread(target=self._handle_incoming, args=(conn, addr), daemon=True).start()
            except: break

    def _handle_incoming(self, conn, addr):
        try:
            conn.settimeout(5)
            # Read first packet
            length_data = conn.recv(4)
            length = struct.unpack('!I', length_data)[0]
            data = pickle.loads(conn.recv(length))
            
            if data.get("cmd") == "INVITE":
                # Received Invitation
                self.incoming_invite = {"ip": addr[0], "name": data.get("name", "Unknown"), "mode": data.get("mode", "COOP"), "conn": conn}
            elif data.get("cmd") == "ACCEPT_INVITE":
                # They accepted our invite!
                # We generated the invite connection, so we are Client side physically, 
                # but game-logic wise we are the Inviter (Host).
                self.socket = conn
                self.connection_status = "CONNECTED"
                self.is_host = True
                conn.settimeout(0.005) # Switch to non-blocking gameplay
            elif data.get("cmd") == "GAME_START":
                 # We accepted, and they started game
                 self.socket = conn
                 self.connection_status = "CONNECTED"
                 self.is_host = False
                 conn.settimeout(0.005)
        except:
            conn.close()

    def send_invite(self, ip, my_name, game_mode="COOP"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((ip, PORT))
            
            # Send Invite Packet
            msg = {"cmd": "INVITE", "name": my_name, "mode": game_mode}
            serialized = pickle.dumps(msg)
            s.sendall(struct.pack('!I', len(serialized)) + serialized)
            
            self.socket = s # Keep this socket open waiting for Accept
            self.connection_status = "INVITING"
            
            # Start thread to wait for Accept response
            threading.Thread(target=self._wait_for_accept, daemon=True).start()
        except:
             self.connection_status = "FAILED"

    def _wait_for_accept(self):
        try:
            self.socket.settimeout(10)
            length_data = self.socket.recv(4)
            length = struct.unpack('!I', length_data)[0]
            data = pickle.loads(self.socket.recv(length))
            
            if data.get("cmd") == "ACCEPT":
                 self.connection_status = "CONNECTED"
                 self.is_host = True # Inviter is Host
                 self.socket.settimeout(0.005)
        except:
             self.connection_status = "FAILED"
             self.socket.close()

    def accept_invite(self):
        # We confirm to the inviter
        if self.incoming_invite:
            conn = self.incoming_invite["conn"]
            try:
                msg = {"cmd": "ACCEPT"}
                serialized = pickle.dumps(msg)
                conn.sendall(struct.pack('!I', len(serialized)) + serialized)
                
                self.socket = conn
                self.connection_status = "CONNECTED"
                self.is_host = False # Invitee is Client
                conn.settimeout(0.005)
                self.incoming_invite = None
            except:
                pass
    
    def decline_invite(self):
        if self.incoming_invite:
            try: self.incoming_invite["conn"].close()
            except: pass
            self.incoming_invite = None

    def send(self, data):
        if not self.socket or self.connection_status != "CONNECTED": return
        try:
            serialized = pickle.dumps(data)
            length = struct.pack('!I', len(serialized))
            self.socket.sendall(length + serialized)
        except: pass

    def receive(self):
        if not self.socket or self.connection_status != "CONNECTED": return None
        try:
            length_data = self._recv_all(4)
            if not length_data: return None
            length = struct.unpack('!I', length_data)[0]
            payload = self._recv_all(length)
            if not payload: return None
            return pickle.loads(payload)
        except socket.timeout: return None
        except: return None

    def _recv_all(self, n):
        data = bytearray()
        while len(data) < n:
            try:
                packet = self.socket.recv(n - len(data))
                if not packet: return None
                data.extend(packet)
            except socket.timeout: return None
            except: return None
        return data
