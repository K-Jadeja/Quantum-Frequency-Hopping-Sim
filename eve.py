# eve.py
"""
Eavesdropper (Eve) script for QKD Man-in-the-Middle attack simulation.
Listens for Alice, connects to Bob, intercepts and measures quantum channel.
Relays public channel messages transparently (simple MitM).

CORRECTED: Accepts Bob's connection first to avoid race condition.
"""

import socket
import time
import random
import traceback
import argparse
import threading

# Import configuration and utilities
import config
from channels import QuantumChannel, PublicChannel, setup_server_listener, accept_connection, setup_client
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
    COLOR_ERROR = COLOR_WARNING = COLOR_SUCCESS = COLOR_INFO = COLOR_RESET = ""

EVE_MEASUREMENT_BASIS_STRATEGY = "Random" # Could be "FixedRectilinear", "FixedDiagonal"

# Global flag to signal relay thread to stop
stop_event = threading.Event()

def relay_messages(source_sock, dest_sock, source_name, dest_name, direction):
    """Generic function to relay messages between two sockets."""
    source_sock.settimeout(1.0) # Use short timeout for relay check
    relay_count = 0
    print(f"{COLOR_INFO}[Relay {direction}] Starting relay from {source_name} to {dest_name}.{COLOR_RESET}")
    while not stop_event.is_set():
        try:
            data = source_sock.recv(4096)
            if not data:
                print(f"{COLOR_WARNING}[Relay {direction}] {source_name} closed connection. Stopping relay.{COLOR_RESET}")
                break
            dest_sock.sendall(data)
            relay_count += len(data)
            # print(f"DEBUG [Relay {direction}] Relayed {len(data)} bytes") # Very verbose
        except socket.timeout:
            continue # No data received, check stop_event again
        except socket.error as e:
            # Check for specific errors indicating closed connection on either end
            if e.errno in [10053, 10054, 32]: # WinError 10053/10054 (closed), errno 32 (Broken pipe)
                 print(f"{COLOR_WARNING}[Relay {direction}] Connection closed ({e.strerror}). Stopping relay.{COLOR_RESET}")
            else:
                 print(f"{COLOR_ERROR}[Relay {direction}] Socket error relaying from {source_name} to {dest_name}: {e}{COLOR_RESET}")
            break
        except Exception as e:
            print(f"{COLOR_ERROR}[Relay {direction}] Unexpected error relaying from {source_name} to {dest_name}: {e}{COLOR_RESET}")
            traceback.print_exc()
            break
    print(f"{COLOR_INFO}[Relay {direction}] Relay thread finished. Relayed approx {relay_count} bytes.{COLOR_RESET}")
    stop_event.set() # Signal other relay thread to stop too


def perform_eve_mitm(alice_conn, bob_conn, args):
    """Handles Eve's interception and relay logic."""
    alice_qc = QuantumChannel(alice_conn, "Alice")
    alice_pc = PublicChannel(alice_conn, "Alice") # Uses same socket
    bob_qc = QuantumChannel(bob_conn, "Bob")
    bob_pc = PublicChannel(bob_conn, "Bob") # Uses same socket

    intercepted_count = 0
    stop_event.clear() # Reset stop event for this run

    # Start relay threads for the public channel messages (run in background)
    relay_thread_alice_to_bob = threading.Thread(target=relay_messages, args=(alice_conn, bob_conn, "Alice", "Bob", "A->B Pub"), daemon=True)
    relay_thread_bob_to_alice = threading.Thread(target=relay_messages, args=(bob_conn, alice_conn, "Bob", "Alice", "B->A Pub"), daemon=True)

    print(f"{COLOR_INFO}[Eve] Starting public channel relay threads...{COLOR_RESET}")
    relay_thread_alice_to_bob.start()
    relay_thread_bob_to_alice.start()

    print(f"{COLOR_WARNING}[Eve] Starting Quantum Channel Interception (Strategy: {EVE_MEASUREMENT_BASIS_STRATEGY})...{COLOR_RESET}")

    # Main loop focuses on intercepting Quantum Channel from Alice to Bob
    try:
        while not stop_event.is_set():
             # 1. Receive from Alice (Quantum Channel primarily)
             try:
                 # Use a short timeout on recv to allow checking stop_event
                 # Important: Use the connection socket directly here, not the PublicChannel wrapper
                 # as we need to distinguish photon messages from relayed public ones.
                 alice_conn.settimeout(0.5)
                 data_from_alice = alice_conn.recv(1024)
                 if not data_from_alice:
                     print(f"{COLOR_WARNING}[Eve Intercept] Alice closed connection. Stopping interception.{COLOR_RESET}")
                     stop_event.set()
                     break
             except socket.timeout:
                 continue # Check stop_event again
             except socket.error as e:
                 # Ignore errors likely caused by relay thread closing connection
                 if e.errno in [10053, 10054, 32, 9]: # Add Bad file descriptor (9)
                      if not stop_event.is_set(): # Only print if not already stopping
                           print(f"{COLOR_WARNING}[Eve Intercept] Socket error receiving from Alice (likely closed by relay): {e}. Stopping.{COLOR_RESET}")
                 else:
                      print(f"{COLOR_ERROR}[Eve Intercept] Socket error receiving from Alice: {e}. Stopping.{COLOR_RESET}")
                 stop_event.set()
                 break

             decoded_data = data_from_alice.decode('utf-8', errors='ignore')

             # 2. Check if it's a Photon message ('P:...')
             if decoded_data.startswith("P:"):
                 intercepted_count += 1
                 try:
                     _, basis_bit_str = decoded_data.split(':', 1)
                     original_basis, original_bit = map(int, basis_bit_str.split(','))

                     # 3. Eve Measures (disturbing the state)
                     if EVE_MEASUREMENT_BASIS_STRATEGY == "Random": eve_basis = random.randint(0, 1)
                     elif EVE_MEASUREMENT_BASIS_STRATEGY == "FixedRectilinear": eve_basis = 0
                     else: eve_basis = 1 # FixedDiagonal

                     if eve_basis == original_basis: eve_measured_bit = original_bit
                     else: eve_measured_bit = random.randint(0, 1) # Random outcome

                     # 4. Eve Resends Photon based on *her* measurement to Bob
                     # print(f"DEBUG Eve: Intercepted ({original_basis},{original_bit}), Measured ({eve_basis},{eve_measured_bit}), Resending...") # Verbose
                     # Use Bob's Quantum Channel wrapper to send
                     bob_qc.send_photon(eve_basis, eve_measured_bit)

                 except (ValueError, IndexError, socket.error) as e:
                     print(f"{COLOR_ERROR}[Eve Error] Error processing/resending photon: {e}. Data: '{decoded_data}'{COLOR_RESET}")
                     continue # Skip to next message from Alice
                 except Exception as e_inner:
                      print(f"{COLOR_ERROR}[Eve Error] Unexpected error handling photon: {e_inner}{COLOR_RESET}")
                      traceback.print_exc()
                      continue

             # 5. Else: It's a public channel message. The relay threads handle these.
             # This loop should ideally only see photons if timing works out,
             # but public messages might slip through recv(). We just ignore them here.
             else:
                  # print(f"DEBUG Eve: Intercept loop saw non-photon data (ignored): {decoded_data[:50]}...")
                  pass

    except KeyboardInterrupt:
        print(f"\n{COLOR_WARNING}[Eve] Interrupted by user.{COLOR_RESET}")
        stop_event.set()
    except Exception as e:
        print(f"{COLOR_ERROR}[Eve Error] Unexpected error in main interception loop: {e}{COLOR_RESET}")
        traceback.print_exc()
        stop_event.set()
    finally:
        print(f"{COLOR_INFO}[Eve] Stopping relay threads...{COLOR_RESET}")
        stop_event.set() # Ensure threads stop
        # Give threads a moment to stop based on the event
        time.sleep(1.5)
        if relay_thread_alice_to_bob.is_alive():
            print(f"{COLOR_WARNING}[Eve] Alice->Bob relay thread still alive, attempting join...{COLOR_RESET}")
            relay_thread_alice_to_bob.join(timeout=1)
        if relay_thread_bob_to_alice.is_alive():
            print(f"{COLOR_WARNING}[Eve] Bob->Alice relay thread still alive, attempting join...{COLOR_RESET}")
            relay_thread_bob_to_alice.join(timeout=1)

        print("\n--- Eve Interception Summary ---")
        print(f" Photons Intercepted: {intercepted_count}")
        print("------------------------------")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QKD Eavesdropper (Eve) - MitM")
    args = parser.parse_args()

    print(f"{COLOR_WARNING}--- QKD Eavesdropper (Eve) Starting ---{COLOR_RESET}")
    print(f" Eve listens for Alice on {config.HOST}:{config.PORT_QKD_BASE}")
    print(f" Eve listens for Bob on   {config.HOST}:{config.PORT_EVE_LISTEN}")
    print(f" Public channel messages will be relayed.")

    alice_listen_sock = None
    bob_listen_sock = None
    alice_conn = None
    bob_conn = None

    try:
        # 1. Setup listener sockets
        alice_listen_sock = setup_server_listener(config.HOST, config.PORT_QKD_BASE)
        bob_listen_sock = setup_server_listener(config.HOST, config.PORT_EVE_LISTEN)

        # --- ACCEPT BOB FIRST ---
        # 2. Accept connection from Bob (on Eve's dedicated port)
        bob_conn, bob_addr = accept_connection(bob_listen_sock, client_name="Bob")

        # --- THEN ACCEPT ALICE ---
        # 3. Accept connection from Alice (on Alice's normal QKD port)
        alice_conn, alice_addr = accept_connection(alice_listen_sock, client_name="Alice")

        # 4. Start the Man-in-the-Middle process
        perform_eve_mitm(alice_conn, bob_conn, args)

    except (socket.error, socket.timeout) as e:
        print(f"\n{COLOR_ERROR}[Eve MAIN Error] Network error during setup or execution: {e}{COLOR_RESET}")
        # traceback.print_exc()
    except KeyboardInterrupt:
        print(f"\n{COLOR_WARNING}[Eve MAIN] Interrupted by user.{COLOR_RESET}")
    except Exception as e:
        print(f"\n{COLOR_ERROR}[Eve MAIN Error] An unexpected error occurred: {e}{COLOR_RESET}")
        traceback.print_exc()
    finally:
        # 5. Cleanup
        print("\n[Eve MAIN] Cleaning up connections and listeners...")
        stop_event.set() # Ensure threads are signaled
        if alice_conn: alice_conn.close()
        if bob_conn: bob_conn.close()
        if alice_listen_sock: alice_listen_sock.close()
        if bob_listen_sock: bob_listen_sock.close()
        print("[Eve MAIN] Eve finished.")