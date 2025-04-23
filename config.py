# config.py
"""
Shared configuration constants for the QKD-FH Simulation (Alice & Bob only).
"""

HOST = 'localhost'        # Network host
PORT_QKD = 12346          # Port for QKD (quantum + public channel simulation)
PORT_FH = 12347           # Port for Frequency Hopping data transmission

# Default values (can be overridden by command line args)
DEFAULT_KEY_LENGTH = 16
DEFAULT_PHOTON_FACTOR = 10 # Photons per desired key bit (adjust based on expected loss/sifting/qber)
DEFAULT_LOSS_RATE = 0.10   # Default 10% photon loss probability
DEFAULT_MESSAGE = "QKD-FH SECURE CHANNEL ESTABLISHED!"
DEFAULT_QBER_THRESHOLD = 0.15 # Default 15% QBER tolerance

FREQUENCIES = [88.1, 90.5, 92.3, 94.7, 96.9, 99.1, 101.3, 104.5, 107.9,
               110.2, 112.7, 115.3, 118.0, 121.5, 124.8, 127.1, 130.6,
               133.9, 136.4, 140.1, 142.5, 145.8, 148.2, 151.9, 155.0]

SOCKET_TIMEOUT = 45.0     # Timeout for socket operations (seconds)