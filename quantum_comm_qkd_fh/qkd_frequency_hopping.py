#!/usr/bin/env python
# -*- coding: utf-8 -*-

import random
import time
import socket
import threading
import sys
import math

# --- Configuration ---
HOST = 'localhost'
PORT_QKD = 12346       # Port for QKD communication
PORT_FH = 12347        # Port for Frequency Hopping data
KEY_LENGTH = 16        # Desired length of the shared secret key (seed)
PHOTON_COUNT = KEY_LENGTH * 4 # Send more photons than needed for the key
MESSAGE = "QKD ESTABLISHED SECURE FH CHANNEL"

# Define available frequencies (in MHz)
FREQUENCIES = [88.1, 90.5, 92.3, 94.7, 96.9, 99.1, 101.3, 104.5, 107.9,
               110.2, 112.7, 115.3, 118.0, 121.5, 124.8, 127.1, 130.6,
               133.9, 136.4, 140.1]

# Try to import matplotlib, but allow failure
matplotlib_present = False
try:
    import matplotlib.pyplot as plt
    matplotlib_present = True
except ImportError:
    print("\n[WARNING] matplotlib not found. Visualization will be skipped.")
    print("          Please install it ('pip install matplotlib') if you wish to see the plot.\n")

# --- Simulated Quantum Objects ---
class QuantumChannel:
    """Simulates the insecure quantum channel where photons are transmitted."""
    def __init__(self, sock):
        self.sock = sock

    def send_photon(self, basis, bit):
        # Simulate sending a photon state (basis, bit)
        # In reality, this involves manipulating single photons.
        message = f"P:{basis},{bit}"
        self.sock.sendall(message.encode())
        # print(f"Sent Photon: Basis={basis}, Bit={bit}") # Debug
        time.sleep(0.01) # Simulate transmission time

    def receive_photon(self):
        # Simulate receiving a photon state
        try:
            data = self.sock.recv(1024).decode()
            if data.startswith("P:"):
                basis, bit = map(int, data[2:].split(','))
                # print(f"Received Photon: Basis={basis}, Bit={bit}") # Debug
                return basis, bit
            else:
                print(f"[Quantum Channel] Received unexpected data: {data}")
                return None, None
        except Exception as e:
            print(f"[Quantum Channel] Error receiving photon: {e}")
            return None, None

class PublicChannel:
    """Simulates the authenticated public classical channel."""
    def __init__(self, sock):
        self.sock = sock

    def send(self, data_type, data):
        message = f"{data_type}:{data}"
        self.sock.sendall(message.encode())

    def receive(self):
        try:
            data = self.sock.recv(1024).decode()
            if ':' in data:
                data_type, content = data.split(':', 1)
                return data_type, content
            else:
                print(f"[Public Channel] Received malformed data: {data}")
                return None, None
        except Exception as e:
            print(f"[Public Channel] Error receiving data: {e}")
            return None, None

# --- QKD (BB84 Simulation) Functions ---
def prepare_qubits(count):
    """Sender: Generate random bits and bases for the qubits."""
    bits = [random.randint(0, 1) for _ in range(count)]
    bases = [random.randint(0, 1) for _ in range(count)] # 0: Rectilinear (+), 1: Diagonal (x)
    print(f"[QKD Sender] Prepared {count} random bits and bases.")
    return bits, bases

def measure_qubits(receiver_bases, sender_bases, sender_bits):
    """Receiver: Simulate measuring qubits based on chosen bases."""
    measured_bits = []
    for i in range(len(receiver_bases)):
        if receiver_bases[i] == sender_bases[i]: # Bases match
            measured_bits.append(sender_bits[i])
        else: # Bases mismatch - outcome is random
            measured_bits.append(random.randint(0, 1))
    print(f"[QKD Receiver] Measured {len(measured_bits)} bits (some may be random due to basis mismatch)." )
    return measured_bits

def sift_keys(sender_bases, receiver_bases, sender_bits, receiver_bits):
    """Both: Compare bases over public channel and keep bits where bases matched."""
    sifted_sender_key = []
    sifted_receiver_key = []
    match_indices = []
    for i in range(len(sender_bases)):
        if sender_bases[i] == receiver_bases[i]:
            sifted_sender_key.append(sender_bits[i])
            sifted_receiver_key.append(receiver_bits[i])
            match_indices.append(i)

    print(f"[QKD System] Bases matched for {len(match_indices)} qubits out of {len(sender_bases)}.")
    # print(f"[QKD System] Match indices: {match_indices}") # Debug
    return sifted_sender_key, sifted_receiver_key

def check_key_agreement(key1, key2, check_length):
    """Both: Sacrifice a portion of the key to check for eavesdropping."""
    if not key1 or not key2 or len(key1) < check_length or len(key2) < check_length:
        print("[QKD System] Error: Not enough key bits to perform check.")
        return False, [], []

    indices_to_check = random.sample(range(len(key1)), min(check_length, len(key1)))
    indices_to_check.sort()

    mismatches = 0
    bits_compared = []
    for i in indices_to_check:
        bits_compared.append((key1[i], key2[i]))
        if key1[i] != key2[i]:
            mismatches += 1

    print(f"[QKD System] Comparing {len(indices_to_check)} bits to check for eavesdropping.")
    # print(f"[QKD System] Compared bits (Sender, Receiver): {bits_compared}") # Debug
    qber = mismatches / len(indices_to_check) # Quantum Bit Error Rate
    print(f"[QKD System] Found {mismatches} mismatches. Estimated QBER: {qber:.2%}")

    final_sender_key = [key1[i] for i in range(len(key1)) if i not in indices_to_check]
    final_receiver_key = [key2[i] for i in range(len(key2)) if i not in indices_to_check]

    # Define an arbitrary QBER threshold
    QBER_THRESHOLD = 0.10
    if qber > QBER_THRESHOLD:
        print(f"[QKD System] QBER ({qber:.2%}) exceeds threshold ({QBER_THRESHOLD:.0%}). Eavesdropping suspected! Aborting.")
        return False, [], []
    else:
        print(f"[QKD System] QBER is acceptable. Potential shared key established.")
        print(f"[QKD System] Final key length after check: {len(final_sender_key)}")
        return True, final_sender_key, final_receiver_key

def derive_seed_from_key(key):
    """Derive a numerical seed from the binary key."""
    if not key:
        print("[SYSTEM] Error: Cannot derive seed from empty key. Using default.")
        return 42 # Default fallback seed
    # Simple method: treat binary key as a base-2 number
    seed_str = "".join(map(str, key))
    seed = int(seed_str, 2)
     # Ensure seed isn't excessively large (optional constraint)
    max_seed_value = (1 << 32) -1 # Example constraint
    seed = seed % max_seed_value
    print(f"[SYSTEM] Derived numerical seed from key: {seed}")
    return seed

# --- Frequency Hopping Functions ---
def generate_hopping_pattern(seed, length):
    """Generates a deterministic sequence of frequencies from a shared seed."""
    local_random = random.Random(seed)
    pattern = [local_random.choice(FREQUENCIES) for _ in range(length)]
    print(f"[FH System] Generated Hopping Pattern (Seed: {seed}, Length: {length}): {pattern}")
    return pattern

def fh_sender(sock, seed):
    """Sender logic for Frequency Hopping phase."""
    hopping_pattern = generate_hopping_pattern(seed, len(MESSAGE))
    print("\n[FH SENDER] Starting data transmission...")
    try:
        # Optional: Send a READY signal to sync receiver
        sock.sendall("FH_READY".encode())
        ack = sock.recv(1024).decode()
        if ack != "FH_ACK":
            print("[FH SENDER] Did not receive FH ACK. Aborting.")
            return hopping_pattern # Still return for visualization

        for i, char in enumerate(MESSAGE):
            freq = hopping_pattern[i]
            message_part = f"{char},{freq}"
            print(f"[FH SENDER] Step {i+1}: Transmitting '{char}' on {freq:.1f} MHz")
            sock.sendall(message_part.encode())
            time.sleep(0.15) # Simulate transmission delay

        sock.sendall("FH_END".encode())
        print("[FH SENDER] Data transmission complete.")
    except socket.error as e:
        print(f"[FH SENDER] Socket Error: {e}")
    except Exception as e:
        print(f"[FH SENDER] Error: {e}")
    return hopping_pattern

def fh_receiver(sock, seed):
    """Receiver logic for Frequency Hopping phase."""
    hopping_pattern = generate_hopping_pattern(seed, len(MESSAGE))
    received_message = ""
    print("\n[FH RECEIVER] Waiting for data transmission...")
    try:
        # Wait for READY signal
        ready_sig = sock.recv(1024).decode()
        if ready_sig != "FH_READY":
            print("[FH RECEIVER] Did not receive FH_READY. Aborting.")
            return
        sock.sendall("FH_ACK".encode()) # Acknowledge readiness
        print("[FH RECEIVER] Synchronized. Listening for data...")

        for i, expected_freq in enumerate(hopping_pattern):
            data = sock.recv(1024).decode()
            if data == "FH_END":
                print("[FH RECEIVER] End of transmission signal received.")
                break
            try:
                char, received_freq_str = data.split(',')
                received_freq = float(received_freq_str)
            except ValueError:
                print(f"[FH RECEIVER] Error: Received malformed data '{data}'")
                received_message += "?"
                continue

            print(f"[FH RECEIVER] Step {i+1}: Received '{char}' on {received_freq:.1f} MHz. Expecting {expected_freq:.1f} MHz.")
            if abs(received_freq - expected_freq) < 0.01:
                received_message += char
            else:
                print(f"[FH RECEIVER] Frequency Mismatch! ❌")
                received_message += "?"
            time.sleep(0.05) # Simulate processing

    except socket.timeout:
        print("[FH RECEIVER] Socket timed out.")
    except socket.error as e:
        print(f"[FH RECEIVER] Socket Error: {e}")
    except Exception as e:
        print(f"[FH RECEIVER] Error: {e}")

    print(f"\n[FH RECEIVER] Final reconstructed message: {received_message}")
    print(f"[FH RECEIVER] Original message was:        {MESSAGE}")
    if received_message == MESSAGE:
        print("[FH RECEIVER] Message successfully reconstructed! ✅")
    else:
        print("[FH RECEIVER] Message reconstruction failed or had errors. ❌")

# --- Visualization --- (Optional, depends on matplotlib)
def visualize_hopping(hopping_pattern):
    """Visualizes the frequency hopping pattern over time."""
    if not matplotlib_present:
        print("[VISUALIZATION] Skipping plot as matplotlib is not available.")
        return
    if not hopping_pattern:
        print("[VISUALIZATION] No hopping pattern data to visualize.")
        return

    try:
        plt.figure(figsize=(12, 6))
        time_steps = range(1, len(hopping_pattern) + 1)
        plt.plot(time_steps, hopping_pattern, marker='o', linestyle='-', color='b', label='Frequency Hop')
        plt.step(time_steps, hopping_pattern, where='mid', color='r', linestyle='--', alpha=0.7, label='Hopping Path')

        plt.xlabel('Time Step (Message Character Index + 1)')
        plt.ylabel('Frequency (MHz)')
        plt.title('Frequency Hopping Pattern (Seed from Simulated QKD)')
        plt.xticks(time_steps)
        plt.yticks(FREQUENCIES)
        plt.ylim(min(FREQUENCIES) - 1, max(FREQUENCIES) + 1)
        plt.grid(True, which='both', linestyle='--', linewidth=0.5)
        plt.legend()
        plt.tight_layout()
        print("\n[VISUALIZATION] Displaying hopping pattern plot...")
        plt.show()
    except Exception as e:
        print(f"[VISUALIZATION] Error plotting graph: {e}")

# --- Main Execution Logic ---
def start_qkd_sender(qkd_conn, fh_conn):
    """Manages the sender side for both QKD and FH phases."""
    qkd_seed = None
    final_hopping_pattern = []
    try:
        print("--- Starting QKD Phase (Sender) ---")
        quantum_ch = QuantumChannel(qkd_conn)
        public_ch = PublicChannel(qkd_conn)

        # 1. Prepare and send qubits
        sender_bits, sender_bases = prepare_qubits(PHOTON_COUNT)
        print(f"[QKD Sender] Sending {PHOTON_COUNT} simulated photons...")
        for i in range(PHOTON_COUNT):
            quantum_ch.send_photon(sender_bases[i], sender_bits[i])
        print("[QKD Sender] Photon transmission complete.")
        public_ch.send("SYNC", "PHOTONS_SENT") # Synchronization signal

        # 2. Receive receiver's bases
        print("[QKD Sender] Waiting for receiver to send bases...")
        data_type, receiver_bases_str = public_ch.receive()
        if data_type != "BASES":
            raise ValueError("Did not receive bases from receiver")
        receiver_bases = [int(b) for b in receiver_bases_str]
        print(f"[QKD Sender] Received {len(receiver_bases)} bases from receiver.")

        # 3. Send sender's bases
        sender_bases_str = "".join(map(str, sender_bases))
        public_ch.send("BASES", sender_bases_str)
        print("[QKD Sender] Sent own bases to receiver.")

        # 4. Sift keys (locally)
        sifted_sender_key, _ = sift_keys(sender_bases, receiver_bases, sender_bits, []) # Sender doesn't need receiver bits here

        # 5. Agree on indices to check and compare bits
        check_len = max(1, len(sifted_sender_key) // 4) # Check ~25% of the bits
        indices_to_check = sorted(random.sample(range(len(sifted_sender_key)), min(check_len, len(sifted_sender_key))))
        indices_str = ",".join(map(str, indices_to_check))
        bits_to_compare_str = "".join([str(sifted_sender_key[i]) for i in indices_to_check])

        print(f"[QKD Sender] Proposing indices to check: {indices_str}")
        public_ch.send("CHECK_INDICES", indices_str)

        data_type, receiver_bits_str = public_ch.receive() # Wait for receiver's bits at check indices
        if data_type != "CHECK_BITS":
            raise ValueError("Did not receive check bits from receiver")

        print("[QKD Sender] Received receiver's bits for comparison.")
        mismatches = 0
        for i, index in enumerate(indices_to_check):
            if str(sifted_sender_key[index]) != receiver_bits_str[i]:
                mismatches += 1

        qber = mismatches / len(indices_to_check) if indices_to_check else 0
        print(f"[QKD Sender] Comparison complete. Mismatches: {mismatches}. QBER: {qber:.2%}")

        QBER_THRESHOLD = 0.10
        if qber > QBER_THRESHOLD:
            print("[QKD Sender] QBER too high! Eavesdropping likely. Aborting.")
            public_ch.send("ABORT", "QBER_HIGH")
            return None

        print("[QKD Sender] QBER acceptable. Proceeding.")
        public_ch.send("CONFIRM_KEY", "OK")

        # 6. Create final key
        final_sender_key = [sifted_sender_key[i] for i in range(len(sifted_sender_key)) if i not in indices_to_check]
        print(f"[QKD Sender] Generated final key (length {len(final_sender_key)}): {''.join(map(str, final_sender_key))}")

        if len(final_sender_key) < KEY_LENGTH:
            print(f"[QKD Sender] Error: Final key length {len(final_sender_key)} is less than desired {KEY_LENGTH}. Aborting.")
            # Might need to restart QKD with more photons in a real system
            public_ch.send("ABORT", "KEY_TOO_SHORT")
            return None

        # Trim key if too long
        final_sender_key = final_sender_key[:KEY_LENGTH]
        qkd_seed = derive_seed_from_key(final_sender_key)
        print("--- QKD Phase (Sender) Successful ---")

    except Exception as e:
        print(f"[QKD Sender] Error during QKD: {e}")
        # Try sending an abort signal
        try: public_ch.send("ABORT", str(e))
        except: pass
        return None # Indicate QKD failure

    # --- Start FH Phase --- (Only if QKD succeeded)
    if qkd_seed is not None:
        print("\n--- Starting Frequency Hopping Phase (Sender) ---")
        try:
            final_hopping_pattern = fh_sender(fh_conn, qkd_seed)
        except Exception as e:
            print(f"[FH Sender] Error during Frequency Hopping: {e}")
        finally:
            visualize_hopping(final_hopping_pattern)
    else:
        print("[SYSTEM] QKD failed, skipping Frequency Hopping.")

    return qkd_seed # Or None if failed

def start_qkd_receiver(qkd_conn, fh_conn):
    """Manages the receiver side for both QKD and FH phases."""
    qkd_seed = None
    try:
        print("--- Starting QKD Phase (Receiver) ---")
        quantum_ch = QuantumChannel(qkd_conn)
        public_ch = PublicChannel(qkd_conn)

        # 1. Receive photons and measure
        receiver_bases = [random.randint(0, 1) for _ in range(PHOTON_COUNT)]
        measured_bits = []
        sender_bases_sim = [] # Need to reconstruct sender's basis/bit from message
        sender_bits_sim = []
        print(f"[QKD Receiver] Preparing to receive {PHOTON_COUNT} photons...")
        for i in range(PHOTON_COUNT):
            s_basis, s_bit = quantum_ch.receive_photon()
            if s_basis is None:
                raise ConnectionAbortedError("Photon channel disrupted")
            sender_bases_sim.append(s_basis)
            sender_bits_sim.append(s_bit)

            # Measure based on receiver's random basis
            if receiver_bases[i] == s_basis:
                measured_bits.append(s_bit)
            else:
                measured_bits.append(random.randint(0, 1))
        print(f"[QKD Receiver] Received and measured {len(measured_bits)} photons.")

        # Wait for sync signal
        data_type, content = public_ch.receive()
        if data_type != "SYNC" or content != "PHOTONS_SENT":
             raise ValueError("Did not receive PHOTONS_SENT sync")

        # 2. Send receiver's bases
        receiver_bases_str = "".join(map(str, receiver_bases))
        public_ch.send("BASES", receiver_bases_str)
        print("[QKD Receiver] Sent own bases to sender.")

        # 3. Receive sender's bases
        print("[QKD Receiver] Waiting for sender's bases...")
        data_type, sender_bases_str = public_ch.receive()
        if data_type != "BASES":
            raise ValueError("Did not receive bases from sender")
        sender_bases = [int(b) for b in sender_bases_str]
        print(f"[QKD Receiver] Received {len(sender_bases)} bases from sender.")

        # 4. Sift keys (locally)
        _, sifted_receiver_key = sift_keys(sender_bases, receiver_bases, [], measured_bits)

        # 5. Receive indices to check, send corresponding bits
        print("[QKD Receiver] Waiting for check indices...")
        data_type, indices_str = public_ch.receive()
        if data_type == "ABORT":
             print(f"[QKD Receiver] Received ABORT signal from sender: {indices_str}. Aborting.")
             return None
        if data_type != "CHECK_INDICES":
            raise ValueError("Did not receive check indices")

        indices_to_check = [int(i) for i in indices_str.split(',')] if indices_str else []
        print(f"[QKD Receiver] Received indices to check: {indices_str}")

        bits_to_send = ""
        valid_indices = True
        if indices_to_check:
            try:
                bits_to_send = "".join([str(sifted_receiver_key[i]) for i in indices_to_check])
            except IndexError:
                print("[QKD Receiver] Error: Invalid check indices received from sender.")
                valid_indices = False
                # Send error signal? For now, send empty string.

        if valid_indices:
            public_ch.send("CHECK_BITS", bits_to_send)
            print("[QKD Receiver] Sent own bits for comparison.")
        else:
            # Consider sending an error, but for now rely on sender detecting mismatch/abort
            public_ch.send("CHECK_BITS", "ERROR_INVALID_INDICES") # Send error indication
            raise ValueError("Invalid indices received during check")

        # 6. Wait for confirmation or abort
        print("[QKD Receiver] Waiting for key confirmation...")
        data_type, content = public_ch.receive()
        if data_type == "ABORT":
            print(f"[QKD Receiver] Received ABORT signal from sender: {content}. Aborting.")
            return None
        if data_type != "CONFIRM_KEY":
            print(f"[QKD Receiver] Did not receive key confirmation. Aborting. ({data_type}:{content})")
            return None

        print("[QKD Receiver] Key confirmation received.")

        # 7. Create final key
        final_receiver_key = [sifted_receiver_key[i] for i in range(len(sifted_receiver_key)) if i not in indices_to_check]
        print(f"[QKD Receiver] Generated final key (length {len(final_receiver_key)}): {''.join(map(str, final_receiver_key))}")

        if len(final_receiver_key) < KEY_LENGTH:
             print(f"[QKD Receiver] Error: Final key length {len(final_receiver_key)} is less than desired {KEY_LENGTH}. Aborting.")
             return None

        # Trim key if too long
        final_receiver_key = final_receiver_key[:KEY_LENGTH]
        qkd_seed = derive_seed_from_key(final_receiver_key)
        print("--- QKD Phase (Receiver) Successful ---")

    except Exception as e:
        print(f"[QKD Receiver] Error during QKD: {e}")
        return None # Indicate QKD failure

    # --- Start FH Phase --- (Only if QKD succeeded)
    if qkd_seed is not None:
        print("\n--- Starting Frequency Hopping Phase (Receiver) ---")
        try:
            fh_receiver(fh_conn, qkd_seed)
        except Exception as e:
            print(f"[FH Receiver] Error during Frequency Hopping: {e}")
    else:
         print("[SYSTEM] QKD failed, skipping Frequency Hopping.")

    return qkd_seed # Or None if failed

def setup_server(host, port):
    """Sets up a server socket and waits for a connection."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(1)
    print(f"[Server Setup] Listening on {host}:{port}...")
    conn, addr = server_sock.accept()
    print(f"[Server Setup] Connection accepted from {addr} on port {port}.")
    return server_sock, conn

def setup_client(host, port):
    """Sets up a client socket and connects to the server."""
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_sock.settimeout(20) # Timeout for connection attempt
    print(f"[Client Setup] Attempting to connect to {host}:{port}...")
    client_sock.connect((host, port))
    print(f"[Client Setup] Connected to server on port {port}.")
    return client_sock

if __name__ == "__main__":
    print("--- QKD-Seeded Frequency Hopping Simulation ---")

    # Need two connections: one for QKD, one for FH
    sender_qkd_server = None
    sender_fh_server = None
    sender_qkd_conn = None
    sender_fh_conn = None
    receiver_qkd_sock = None
    receiver_fh_sock = None

    try:
        # Setup server sockets first
        sender_qkd_server, sender_qkd_conn = setup_server(HOST, PORT_QKD)
        sender_fh_server, sender_fh_conn = setup_server(HOST, PORT_FH)

        # Setup client sockets
        # Add slight delay before client connection attempts
        time.sleep(0.5)
        receiver_qkd_sock = setup_client(HOST, PORT_QKD)
        receiver_fh_sock = setup_client(HOST, PORT_FH)

        # Create threads for sender and receiver main logic
        # Pass the established connections to the threads
        sender_thread = threading.Thread(target=start_qkd_sender, args=(sender_qkd_conn, sender_fh_conn), name="SenderThread")
        receiver_thread = threading.Thread(target=start_qkd_receiver, args=(receiver_qkd_sock, receiver_fh_sock), name="ReceiverThread")

        # Start threads
        sender_thread.start()
        receiver_thread.start()

        # Wait for threads to complete
        sender_thread.join()
        receiver_thread.join()

    except socket.timeout:
        print("\n[SYSTEM ERROR] Socket timed out during connection setup.")
    except socket.error as e:
        print(f"\n[SYSTEM ERROR] Socket error during setup or execution: {e}")
    except Exception as e:
        print(f"\n[SYSTEM ERROR] An unexpected error occurred: {e}")
    finally:
        # Cleanup sockets
        print("\n--- Cleaning up connections ---")
        if sender_qkd_conn: sender_qkd_conn.close()
        if sender_fh_conn: sender_fh_conn.close()
        if sender_qkd_server: sender_qkd_server.close()
        if sender_fh_server: sender_fh_server.close()
        if receiver_qkd_sock: receiver_qkd_sock.close()
        if receiver_fh_sock: receiver_fh_sock.close()
        print("[SYSTEM] All sockets closed.")

    print("\n--- Simulation Finished ---") 