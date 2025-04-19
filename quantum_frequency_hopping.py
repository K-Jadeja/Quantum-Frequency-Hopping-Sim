import random
import time
import matplotlib.pyplot as plt
import socket
import threading
import sys

# Define available frequencies (in MHz) - Larger set for more variability
FREQUENCIES = [88.1, 90.5, 92.3, 94.7, 96.9, 99.1, 101.3, 104.5, 107.9,
               110.2, 112.7, 115.3, 118.0, 121.5, 124.8, 127.1, 130.6,
               133.9, 136.4, 140.1]

# Message to be transmitted
MESSAGE = "SECURE COMMS VIA QUANTUM INSPIRED HOPPING"
HOST = 'localhost'
PORT = 12345
SEED_RANGE_MIN = 1000
SEED_RANGE_MAX = 9999

def quantum_random_seed(min_val=SEED_RANGE_MIN, max_val=SEED_RANGE_MAX):
    """
    Simulates the generation of a random seed based on quantum randomness inspiration.
    In a real quantum system, this would involve measuring quantum states.
    Here, we use a standard pseudo-random number generator for simulation.
    """
    seed = random.randint(min_val, max_val)
    print(f"[SYSTEM] Generated Quantum-Inspired Seed: {seed}")
    return seed

def generate_hopping_pattern(seed, length):
    """
    Generates a deterministic sequence of frequencies from a shared seed.
    Ensures both sender and receiver produce the identical pattern.
    """
    # Create a local random generator instance seeded with the shared seed
    local_random = random.Random(seed)
    pattern = [local_random.choice(FREQUENCIES) for _ in range(length)]
    print(f"[SYSTEM] Generated Hopping Pattern (Seed: {seed}): {pattern}")
    return pattern

def sender(sock, seed):
    """Simulates a sender transmitting data over hopping frequencies determined by the shared seed."""
    hopping_pattern = generate_hopping_pattern(seed, len(MESSAGE))

    print("[SENDER] Starting transmission...")
    # Send the seed first (as a string)
    try:
        sock.sendall(str(seed).encode())
        # Wait for acknowledgment (optional, but good practice)
        ack = sock.recv(1024)
        if ack.decode() != 'SEED_ACK':
             print("[SENDER] Error: Did not receive seed acknowledgment.")
             return hopping_pattern # Return pattern for visualization even on error

        print("[SENDER] Seed acknowledged by receiver.")

        # Now send the message character by character on the hopping frequencies
        for i, char in enumerate(MESSAGE):
            freq = hopping_pattern[i]
            message_part = f"{char},{freq}"
            print(f"[SENDER] Step {i+1}: Transmitting '{char}' on {freq:.1f} MHz")
            sock.sendall(message_part.encode())
            time.sleep(0.2) # Simulate transmission delay

        # Send end-of-transmission signal
        sock.sendall("END".encode())
        print("[SENDER] Transmission complete.")

    except socket.error as e:
        print(f"[SENDER] Socket Error: {e}")
    except Exception as e:
        print(f"[SENDER] Error during sending: {e}")

    return hopping_pattern # Return for visualization

def receiver(sock):
    """Simulates a receiver listening according to the hopping pattern derived from the received seed."""
    received_message = ""
    hopping_pattern = []

    try:
        # Receive the seed first
        seed_str = sock.recv(1024).decode()
        if not seed_str.isdigit():
            print("[RECEIVER] Error: Invalid seed received.")
            return
        seed = int(seed_str)
        print(f"[RECEIVER] Received Quantum-Inspired Seed: {seed}")

        # Acknowledge seed receipt
        sock.sendall("SEED_ACK".encode())

        # Generate the expected hopping pattern using the received seed
        hopping_pattern = generate_hopping_pattern(seed, len(MESSAGE))
        print("[RECEIVER] Synchronized hopping pattern. Listening...")

        # Listen for message parts according to the pattern
        for i, expected_freq in enumerate(hopping_pattern):
            data = sock.recv(1024).decode()

            if data == "END":
                print("[RECEIVER] End of transmission signal received.")
                break

            try:
                char, received_freq_str = data.split(',')
                received_freq = float(received_freq_str)
            except ValueError:
                print(f"[RECEIVER] Error: Received malformed data '{data}'")
                received_message += "?"
                continue # Skip to next expected frequency

            print(f"[RECEIVER] Step {i+1}: Received '{char}' on {received_freq:.1f} MHz. Expecting {expected_freq:.1f} MHz.")

            # Simple check if the frequency matches (allowing for slight float inaccuracies if needed)
            # In a real system, the receiver would *tune* to expected_freq
            if abs(received_freq - expected_freq) < 0.01:
                # print(f"[RECEIVER] Frequency Match ✅")
                received_message += char
            else:
                print(f"[RECEIVER] Frequency Mismatch! Expected {expected_freq:.1f} MHz, got {received_freq:.1f} MHz ❌")
                received_message += "?" # Indicate error/missed character

            time.sleep(0.1) # Simulate processing delay

        if len(received_message) != len(MESSAGE):
             print(f"[RECEIVER] Warning: Received message length ({len(received_message)}) differs from expected ({len(MESSAGE)}).")


    except socket.timeout:
        print("[RECEIVER] Socket timed out.")
    except socket.error as e:
        print(f"[RECEIVER] Socket Error: {e}")
    except Exception as e:
        print(f"[RECEIVER] Error during receiving: {e}")


    print(f"[RECEIVER] Final reconstructed message: {received_message}")
    print(f"[RECEIVER] Original message was:        {MESSAGE}")
    if received_message == MESSAGE:
        print("[RECEIVER] Message successfully reconstructed! ✅")
    else:
        print("[RECEIVER] Message reconstruction failed or had errors. ❌")


def visualize_hopping(hopping_pattern):
    """Visualizes the frequency hopping pattern over time."""
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
        plt.title('Quantum-Inspired Frequency Hopping Pattern')
        plt.xticks(time_steps)
        plt.yticks(FREQUENCIES) # Show all possible frequencies on y-axis
        plt.ylim(min(FREQUENCIES) - 1, max(FREQUENCIES) + 1)
        plt.grid(True, which='both', linestyle='--', linewidth=0.5)
        plt.legend()
        plt.tight_layout()
        print("[VISUALIZATION] Displaying hopping pattern plot...")
        plt.show()
    except Exception as e:
        print(f"[VISUALIZATION] Error plotting graph: {e}. Ensure matplotlib is installed and a display is available.")


def start_sender():
    """Starts the sender server, generates seed, and initiates communication."""
    generated_seed = quantum_random_seed() # Generate the seed here
    final_hopping_pattern = []

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow address reuse
    try:
        server_sock.bind((HOST, PORT))
        server_sock.listen(1)
        print(f"[SENDER] Server listening on {HOST}:{PORT}...")
        print("[SENDER] Waiting for receiver connection...")
        conn, addr = server_sock.accept()
        with conn:
            print(f"[SENDER] Receiver connected from {addr}")
            final_hopping_pattern = sender(conn, generated_seed) # Pass seed to sender function
    except socket.error as e:
         print(f"[SENDER] Server Socket Error: {e}")
    except Exception as e:
        print(f"[SENDER] Server Error: {e}")
    finally:
        server_sock.close()
        print("[SENDER] Server socket closed.")
        # Visualize the pattern used by the sender after transmission attempt
        visualize_hopping(final_hopping_pattern)


def start_receiver():
    """Starts the receiver client and connects to the sender."""
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_sock.settimeout(15) # Set a timeout for blocking operations
    try:
        print(f"[RECEIVER] Attempting to connect to {HOST}:{PORT}...")
        client_sock.connect((HOST, PORT))
        print("[RECEIVER] Connected to sender!")
        receiver(client_sock)
    except socket.timeout:
        print("[RECEIVER] Connection attempt timed out.")
    except socket.error as e:
        print(f"[RECEIVER] Client Socket Error: {e}")
    except Exception as e:
        print(f"[RECEIVER] Client Error: {e}")
    finally:
        client_sock.close()
        print("[RECEIVER] Client socket closed.")

if __name__ == "__main__":
    # Ensure matplotlib is installed
    try:
        import matplotlib
    except ImportError:
        print("Error: matplotlib is not installed. Please install it using:")
        print("pip install matplotlib")
        sys.exit(1)

    print("--- Quantum-Inspired Frequency Hopping Simulation ---")
    # Using threading to run sender and receiver concurrently
    sender_thread = threading.Thread(target=start_sender, name="SenderThread")
    receiver_thread = threading.Thread(target=start_receiver, name="ReceiverThread")

    sender_thread.start()
    time.sleep(1) # Give sender a moment to set up the server socket
    receiver_thread.start()

    sender_thread.join()
    receiver_thread.join()

    print("--- Simulation Finished ---") 