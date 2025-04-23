# qkd_receiver.py
"""
QKD-FH Receiver (Bob) script.
Connects to Alice, performs QKD (Corrected Protocol v2), derives seed,
and receives message via FH.
"""

import socket
import time
import random
import traceback
import argparse

# Import configuration and utilities
import config
from channels import QuantumChannel, PublicChannel, setup_client
from utils import derive_seed_from_key, generate_hopping_pattern

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

# Corrected QKD Receiver Role (v2 - matches corrected Sender)
def perform_qkd_receiver_role(qkd_sock, args, stats):
    """Handles the QKD protocol steps for the receiver (Corrected Protocol v2)."""
    qkd_seed = None
    sifted_receiver_key_final = None
    peer_name = "Alice" # Only communicating with Alice now
    quantum_ch = QuantumChannel(qkd_sock, peer_name)
    public_ch = PublicChannel(qkd_sock, peer_name)
    photons_expected_from_sync = -1

    # Store received photon info sequentially: List of {'bob_basis': b, 'measured_bit': m}
    received_photon_info = []

    try:
        print(f"\n{COLOR_INFO}--- Starting QKD Phase (Receiver) ---{COLOR_RESET}")

        # a. Receive photons until SYNC signal
        print(f"[QKD Receiver] Preparing to receive photons from {peer_name}...")
        while True: # Loop until SYNC or error
            result = quantum_ch.receive_photon()

            if result == (None, None):
                 print(f"{COLOR_WARNING}[QKD Receiver Warning] Photon stream ended prematurely after {len(received_photon_info)} stored photons (error/timeout).{COLOR_RESET}")
                 break

            elif result[0] == "OTHER": # Got non-photon data
                 non_photon_data = result[1]
                 if ':' in non_photon_data:
                     data_type, content = non_photon_data.split(':', 1)
                     if data_type == "SYNC" and content.startswith("PHOTONS_SENT"):
                         try:
                             photons_expected_from_sync = int(content.split(':')[1])
                             stats['photons_sender_sent'] = photons_expected_from_sync
                             print(f"[QKD Receiver] Received SYNC signal. {peer_name} sent {photons_expected_from_sync} photons.")
                         except (ValueError, IndexError): raise ValueError(f"Malformed SYNC data received: {content}")
                         break # Exit photon receiving loop
                     elif data_type == "ABORT": raise ValueError(f"{peer_name} aborted: {content}")
                     else: print(f"{COLOR_WARNING}[QKD Receiver Warning] Received unexpected public message '{data_type}' during photon phase.{COLOR_RESET}")
                 else: print(f"{COLOR_WARNING}[QKD Receiver Warning] Received undecipherable non-photon data: {non_photon_data}{COLOR_RESET}")
                 break

            else: # Valid photon received
                 s_basis, s_bit = result
                 bob_basis = random.randint(0, 1)
                 if bob_basis == s_basis: measured_bit = s_bit
                 else: measured_bit = random.randint(0, 1)
                 received_photon_info.append({'bob_basis': bob_basis, 'measured_bit': measured_bit})

        photons_received_count = len(received_photon_info)
        stats['photons_received'] = photons_received_count
        print(f"[QKD Receiver] Finished receiving phase. Stored info for {photons_received_count} received photons.")
        if photons_received_count == 0: raise ValueError("No photons were successfully received.")

        # b. Wait for SYNC signal properly if not received above
        if photons_expected_from_sync == -1:
            print(f"[QKD Receiver] Waiting for PHOTONS_SENT sync signal from {peer_name}...")
            data_type, content = public_ch.receive()
            if not data_type: raise ConnectionAbortedError(f"{peer_name} disconnected (sync)")
            if data_type == "ABORT": raise ValueError(f"{peer_name} aborted: {content}")
            if data_type != "SYNC" or not content.startswith("PHOTONS_SENT"):
                raise TypeError(f"Expected SYNC:PHOTONS_SENT:count, got {data_type}:{content}")
            try:
                photons_expected_from_sync = int(content.split(':')[1])
                stats['photons_sender_sent'] = photons_expected_from_sync
                print(f"[QKD Receiver] Received SYNC signal. {peer_name} sent {photons_expected_from_sync} photons.")
            except (ValueError, IndexError): raise ValueError(f"Malformed SYNC data received: {content}")


        # c. Send Bob's Bases (only for photons received)
        bob_bases_sent = [info['bob_basis'] for info in received_photon_info]
        public_ch.send("BOB_BASES", "".join(map(str, bob_bases_sent)))
        print(f"[QKD Receiver] Sent {len(bob_bases_sent)} bases to {peer_name}.")

        # d. Wait for relative matching indices from Alice
        print(f"[QKD Receiver] Waiting for {peer_name} to send relative matching indices ('MATCH_INDICES_REL')...")
        data_type, match_indices_relative_str = public_ch.receive()
        if not data_type: raise ConnectionAbortedError(f"{peer_name} disconnected (relative match indices)")
        if data_type == "ABORT": raise ValueError(f"{peer_name} aborted: {match_indices_relative_str}")
        if data_type != "MATCH_INDICES_REL": raise TypeError(f"Expected MATCH_INDICES_REL from {peer_name}, got {data_type}")

        match_indices_relative_to_bob = []
        if match_indices_relative_str:
             try: match_indices_relative_to_bob = [int(i) for i in match_indices_relative_str.split(',')]
             except ValueError: raise ValueError(f"Received malformed relative match indices: '{match_indices_relative_str}'")

        stats['sifted_key_length'] = len(match_indices_relative_to_bob)
        print(f"[QKD Receiver] Received {len(match_indices_relative_to_bob)} relative matching indices from {peer_name}.")

        # e. Construct Sifted Key using relative indices
        sifted_receiver_key = []
        for rel_idx in match_indices_relative_to_bob:
             if rel_idx < len(received_photon_info):
                  sifted_receiver_key.append(received_photon_info[rel_idx]['measured_bit'])
             else:
                  raise IndexError(f"Received relative match index {rel_idx} out of bounds for received photons ({len(received_photon_info)}).")

        print(f"[QKD Receiver] Constructed sifted key of length: {len(sifted_receiver_key)}")
        stats['sifted_key_length'] = len(sifted_receiver_key) # Update stat

        if len(sifted_receiver_key) < args.key_length:
             print(f"{COLOR_WARNING}[QKD Receiver] Sifted key length ({len(sifted_receiver_key)}) may be insufficient for desired key length {args.key_length} after QBER check.{COLOR_RESET}")

        # f. QBER Check (Wait for indices relative to the sifted key)
        if not sifted_receiver_key:
            raise ValueError("No matching bases found after sifting. Cannot perform QBER check.")

        print(f"[QKD Receiver] Waiting for check indices (relative to sifted key) from {peer_name} ('CHECK_INDICES_REL_SIFT')...")
        data_type, indices_rel_sifted_str = public_ch.receive()
        if not data_type: raise ConnectionAbortedError(f"{peer_name} disconnected (check indices rel sifted)")
        if data_type == "ABORT": raise ValueError(f"{peer_name} aborted: {indices_rel_sifted_str}")
        if data_type != "CHECK_INDICES_REL_SIFT": raise TypeError(f"Expected CHECK_INDICES_REL_SIFT from {peer_name}, got {data_type}")

        indices_to_check_relative_sifted = []
        if indices_rel_sifted_str:
            try: indices_to_check_relative_sifted = [int(i) for i in indices_rel_sifted_str.split(',')]
            except ValueError: raise ValueError(f"Malformed relative-sifted check indices received: '{indices_rel_sifted_str}'.")
        stats['qber_check_bits'] = len(indices_to_check_relative_sifted)
        print(f"[QKD Receiver] Received {len(indices_to_check_relative_sifted)} indices for QBER check (relative to sifted key).")

        # g. Validate Indices and Send Check Bits
        bits_to_send_str = ""
        if indices_to_check_relative_sifted:
            if any(i < 0 or i >= len(sifted_receiver_key) for i in indices_to_check_relative_sifted):
                raise IndexError(f"Invalid check indices received (out of bounds for sifted key length {len(sifted_receiver_key)}).")
            bits_to_send_str = "".join([str(sifted_receiver_key[i]) for i in indices_to_check_relative_sifted])
        print(f"[QKD Receiver] Sending {len(bits_to_send_str)} check bits to {peer_name}.")
        public_ch.send("CHECK_BITS", bits_to_send_str)

        # h. Wait for Confirmation or Abort from Sender
        print(f"[QKD Receiver] Waiting for key confirmation from {peer_name}...")
        data_type, content = public_ch.receive()
        if not data_type: raise ConnectionAbortedError(f"{peer_name} disconnected (confirmation)")

        if data_type == "ABORT":
            print(f"{COLOR_ERROR}[QKD Receiver] Received ABORT signal from {peer_name}: {content}. QKD failed.{COLOR_RESET}")
            stats['status'] = f'Aborted by {peer_name}: {content}'
            return None, None
        elif data_type == "CONFIRM_KEY":
            print(f"{COLOR_SUCCESS}[QKD Receiver] Key confirmation received from {peer_name}.{COLOR_RESET}")
            # i. Generate Final Key
            final_key_bits = [sifted_receiver_key[i] for i in range(len(sifted_receiver_key)) if i not in indices_to_check_relative_sifted]
            stats['key_after_qber'] = len(final_key_bits)
            print(f"[QKD Receiver] Key length after QBER check: {len(final_key_bits)}")

            if len(final_key_bits) < args.key_length:
                print(f"{COLOR_ERROR}[QKD Receiver Error] Final key too short ({len(final_key_bits)} < {args.key_length}). Key invalid.{COLOR_RESET}")
                stats['status'] = 'Key Too Short'
                return None, None
            else:
                sifted_receiver_key_final = final_key_bits[:args.key_length]
                stats['final_key_length'] = len(sifted_receiver_key_final)
                print(f"{COLOR_SUCCESS}[QKD Receiver] Final {args.key_length}-bit key generated.{COLOR_RESET}")
                qkd_seed = derive_seed_from_key(sifted_receiver_key_final)
                stats['status'] = 'Success'
                print(f"{COLOR_SUCCESS}--- QKD Phase (Receiver) Successful ---{COLOR_RESET}")
                return qkd_seed, sifted_receiver_key_final
        else:
            raise TypeError(f"Expected CONFIRM_KEY or ABORT from {peer_name}, got {data_type}:{content}.")

    except (socket.error, socket.timeout, ConnectionAbortedError, TypeError, ValueError, IndexError) as e:
        print(f"{COLOR_ERROR}[QKD Receiver Error] QKD phase failed: {e}{COLOR_RESET}")
        stats['status'] = f'Error: {e}'
        if 'public_ch' in locals() and public_ch and hasattr(public_ch, 'sock') and public_ch.sock.fileno() != -1 and ('data_type' not in locals() or data_type != "ABORT"):
             try: public_ch.send("ABORT", f"Receiver Error: {e}")
             except socket.error: pass
        return None, None
    except Exception as e:
        print(f"{COLOR_ERROR}[QKD Receiver Error] Unexpected error in QKD phase: {e}{COLOR_RESET}")
        traceback.print_exc()
        stats['status'] = f'Unexpected Error: {e}'
        return None, None

def perform_fh_receiver_role(fh_sock, seed, args, stats):
    """Handles the Frequency Hopping reception for the receiver."""
    print(f"\n{COLOR_INFO}--- Starting Frequency Hopping Phase (Receiver) ---{COLOR_RESET}")
    received_message = ""
    chars_received = 0
    freq_mismatches = 0
    malformed_packets = 0
    fh_status = 'Not Started'

    try:
        hopping_pattern = generate_hopping_pattern(seed, len(args.message), config.FREQUENCIES)
        if not hopping_pattern:
             fh_status = 'Pattern Generation Fail'
             stats['fh_status'] = fh_status
             return

        fh_sock.settimeout(config.SOCKET_TIMEOUT + 10.0)

        print("[FH RECEIVER] Waiting for FH_READY signal from Alice...")
        ready_sig = fh_sock.recv(1024).decode('utf-8')
        if not ready_sig: raise ConnectionAbortedError("Alice disconnected before FH_READY")
        if ready_sig != "FH_READY":
            raise ValueError(f"Did not receive FH_READY (Got: {ready_sig}). Aborting FH.")
        print("[FH RECEIVER] Received FH_READY. Sending FH_ACK.")
        fh_sock.sendall("FH_ACK".encode('utf-8'))

        print("[FH RECEIVER] Synchronization successful. Listening for message...")
        for i, expected_freq in enumerate(hopping_pattern):
            data = fh_sock.recv(1024).decode('utf-8')
            if not data:
                 print(f"{COLOR_WARNING}[FH RECEIVER Warning] Connection closed by Alice during FH reception after {i} steps.{COLOR_RESET}")
                 fh_status = 'Connection Closed Mid-FH'
                 break

            if data == "FH_END":
                print("[FH RECEIVER] Received FH_END signal.")
                fh_status = 'Success (FH_END Received)'
                break

            try:
                char, received_freq_str = data.split(',')
                received_freq = float(received_freq_str)
                chars_received += 1

                if abs(received_freq - expected_freq) < 0.01:
                    received_message += char
                else:
                    print(f"{COLOR_WARNING}[FH RECEIVER] Frequency Mismatch! Step {i+1}: Expected {expected_freq:.1f} MHz, Got {received_freq:.1f}. Storing '?'.{COLOR_RESET}")
                    received_message += "?"
                    freq_mismatches += 1
            except ValueError:
                print(f"{COLOR_ERROR}[FH RECEIVER Error] Received malformed data packet: '{data}'{COLOR_RESET}")
                received_message += "?"
                malformed_packets += 1

        if fh_status == 'Not Started':
             print(f"{COLOR_WARNING}[FH RECEIVER Warning] Data stream ended before FH_END received.{COLOR_RESET}")
             fh_status = 'Ended without FH_END'

        stats['fh_status'] = fh_status
        stats['fh_chars_received'] = chars_received
        stats['fh_freq_mismatches'] = freq_mismatches
        stats['fh_malformed_packets'] = malformed_packets

        print("\n--- FH Reception Summary ---")
        print(f" Status:            {fh_status}")
        print(f" Expected Message:  '{args.message}' ({len(args.message)} chars)")
        print(f" Reconstructed msg: '{received_message}' ({len(received_message)} chars)")
        print(f" Chars Received OK: {chars_received - freq_mismatches - malformed_packets}")
        print(f" Freq Mismatches:   {freq_mismatches}")
        print(f" Malformed Packets: {malformed_packets}")
        if received_message == args.message:
            print(f"{COLOR_SUCCESS} Message successfully reconstructed! ✅{COLOR_RESET}")
            stats['fh_match'] = True
        else:
            print(f"{COLOR_ERROR} Message reconstruction failed! ❌{COLOR_RESET}")
            stats['fh_match'] = False

    except (socket.error, socket.timeout, ValueError, UnicodeDecodeError, ConnectionAbortedError) as e:
        print(f"{COLOR_ERROR}[FH RECEIVER Error] FH phase failed: {e}{COLOR_RESET}")
        stats['fh_status'] = f'Error: {e}'
    except Exception as e:
        print(f"{COLOR_ERROR}[FH RECEIVER Error] Unexpected error in FH phase: {e}{COLOR_RESET}")
        traceback.print_exc()
        stats['fh_status'] = f'Unexpected Error: {e}'


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QKD-FH Receiver (Bob)")
    parser.add_argument('-k', '--key-length', type=int, default=config.DEFAULT_KEY_LENGTH, help="Expected final key length (should match sender's desired length)")
    # Removed photon factor from Bob's args as it's not strictly needed
    parser.add_argument('-m', '--message', type=str, default=config.DEFAULT_MESSAGE, help="Expected message (must match sender)")
    # Removed --eve argument
    args = parser.parse_args()

    print(f"{COLOR_INFO}--- QKD-Seeded Frequency Hopping Receiver (Bob) ---{COLOR_RESET}")
    print(f"Configuration: Expected KeyLen={args.key_length}")

    qkd_sock = None
    fh_sock = None
    qkd_seed = None
    stats = {
        'photons_sender_sent': -1, 'photons_received': 0,
        'sifted_key_length': 0, 'qber_check_bits': 0, 'key_after_qber': 0,
        'final_key_length': 0, 'status': 'Not Started',
        'fh_status': 'Not Started', 'fh_match': None, 'fh_chars_received': 0,
        'fh_freq_mismatches': 0, 'fh_malformed_packets': 0
    }

    try:
        # 1. Connect to servers (Always connect directly to Alice now)
        print("Waiting briefly before connecting...")
        time.sleep(1.0)

        qkd_sock = setup_client(config.HOST, config.PORT_QKD, server_name="Alice (QKD)")
        fh_sock = setup_client(config.HOST, config.PORT_FH, server_name="Alice (FH)")

        # 2. Perform QKD
        qkd_seed, final_key = perform_qkd_receiver_role(qkd_sock, args, stats)

        # 3. Perform FH if QKD succeeded
        if qkd_seed is not None:
            perform_fh_receiver_role(fh_sock, qkd_seed, args, stats)
        else:
            print(f"\n{COLOR_WARNING}[SYSTEM] QKD failed, skipping Frequency Hopping.{COLOR_RESET}")
            stats['fh_status'] = 'Skipped (QKD Fail)'

    except (socket.error, socket.timeout, ConnectionAbortedError) as e:
        print(f"\n{COLOR_ERROR}[RECEIVER MAIN Error] Network error during setup or execution: {e}{COLOR_RESET}")
        stats['status'] = f'Network Error: {e}'
    except KeyboardInterrupt:
        print(f"\n{COLOR_WARNING}[RECEIVER MAIN] Interrupted by user.{COLOR_RESET}")
        stats['status'] = 'Interrupted'
    except Exception as e:
        print(f"\n{COLOR_ERROR}[RECEIVER MAIN Error] An unexpected error occurred: {e}{COLOR_RESET}")
        stats['status'] = f'Unexpected Main Error: {e}'
        traceback.print_exc()
    finally:
        # 4. Print Summary
        print("\n--- Receiver Simulation Summary ---")
        print(f" QKD Status:         {stats.get('status', 'Unknown')}")
        if stats.get('photons_sender_sent', -1) != -1:
             print(f" Photons Sender Sent:{stats.get('photons_sender_sent', 'N/A')}")
        print(f" Photons Received:   {stats.get('photons_received', 0)}")
        print(f" Matches Found:      {stats.get('sifted_key_length', 0)}")
        print(f" QBER Check Bits:    {stats.get('qber_check_bits', 0)}")
        print(f" Key Len Post-QBER:  {stats.get('key_after_qber', 'N/A')}")
        print(f" Final Key Length:   {stats.get('final_key_length', 0)} / {args.key_length} (desired)")
        print(f" FH Status:          {stats.get('fh_status', 'Unknown')}")
        if stats.get('fh_match', None) is not None:
             match_color = COLOR_SUCCESS if stats['fh_match'] else COLOR_ERROR
             print(f" FH Message Match:   {match_color}{stats['fh_match']}{COLOR_RESET}")
             print(f"   (Chars OK: {stats.get('fh_chars_received', 0) - stats.get('fh_freq_mismatches', 0) - stats.get('fh_malformed_packets', 0)}, Freq Err: {stats.get('fh_freq_mismatches', 0)}, Malformed: {stats.get('fh_malformed_packets', 0)})")
        print("-----------------------------------")

        # 5. Cleanup
        print("\n[RECEIVER MAIN] Cleaning up connections...")
        if qkd_sock: qkd_sock.close()
        if fh_sock: fh_sock.close()
        print("[RECEIVER MAIN] Receiver finished.")