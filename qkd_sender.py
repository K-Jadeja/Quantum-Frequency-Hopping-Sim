# qkd_sender.py
"""
QKD-FH Sender (Alice) script.
Listens for Bob, performs QKD with loss simulation (Corrected Protocol v2),
derives seed, and transmits message via FH.
"""

import socket
import time
import random
import traceback
import argparse

# Import configuration and utilities
import config
from channels import QuantumChannel, PublicChannel, setup_server_listener, accept_connection
from utils import derive_seed_from_key, generate_hopping_pattern, visualize_hopping

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


def prepare_qubits(count):
    """Sender: Generate random bits and bases."""
    bits = [random.randint(0, 1) for _ in range(count)]
    bases = [random.randint(0, 1) for _ in range(count)] # 0: Rectilinear (+), 1: Diagonal (x)
    print(f"{COLOR_INFO}[QKD Sender] Prepared {count} initial random bits and bases.{COLOR_RESET}")
    return bits, bases

# Corrected QKD Sender Role (v2 - matches corrected Bob)
def perform_qkd_sender_role(qkd_conn, args, stats):
    """Handles the QKD protocol steps for the sender (Corrected Protocol v2)."""
    qkd_seed = None
    sifted_sender_key_final = None
    peer_name = "Bob" # Only communicating with Bob now
    quantum_ch = QuantumChannel(qkd_conn, peer_name)
    public_ch = PublicChannel(qkd_conn, peer_name)
    photons_to_attempt = args.photon_count

    try:
        print(f"\n{COLOR_INFO}--- Starting QKD Phase (Sender) ---{COLOR_RESET}")
        # a. Prepare qubits
        sender_bits_all, sender_bases_all = prepare_qubits(photons_to_attempt)
        stats['photons_prepared'] = photons_to_attempt

        # b. Send photons with loss simulation AND keep track of sent ones
        photons_sent_indices = [] # Store original indices of photons successfully sent
        sender_bits_sent = {}     # Store bits for sent photons, keyed by original index
        sender_bases_sent = {}    # Store bases for sent photons, keyed by original index
        print(f"[QKD Sender] Attempting to send {photons_to_attempt} photons (Loss Rate: {args.loss_rate:.1%})...")
        for i in range(photons_to_attempt):
            if random.random() >= args.loss_rate: # Photon NOT lost
                quantum_ch.send_photon(sender_bases_all[i], sender_bits_all[i])
                photons_sent_indices.append(i) # Store original index
                # Store info only for sent photons, keyed by the original index
                sender_bits_sent[i] = sender_bits_all[i]
                sender_bases_sent[i] = sender_bases_all[i]

        photons_sent_count = len(photons_sent_indices)
        stats['photons_sent'] = photons_sent_count
        print(f"[QKD Sender] Successfully sent {photons_sent_count} / {photons_to_attempt} photons.")

        # c. Send SYNC signal (indicate number sent)
        public_ch.send("SYNC", f"PHOTONS_SENT:{photons_sent_count}")

        # d. Receive BOB'S BASES (sequential, for photons he received)
        print(f"[QKD Sender] Waiting for {peer_name}'s bases ('BOB_BASES')...")
        data_type, bob_bases_str = public_ch.receive()
        if not data_type: raise ConnectionAbortedError(f"{peer_name} disconnected (bob bases)")
        if data_type == "ABORT": raise ValueError(f"{peer_name} aborted: {bob_bases_str}")
        if data_type != "BOB_BASES": raise TypeError(f"Expected BOB_BASES from {peer_name}, got {data_type}")
        bob_bases_list = [int(b) for b in bob_bases_str]
        stats['receiver_bases_count'] = len(bob_bases_list) # How many bases Bob sent
        print(f"[QKD Sender] Received {len(bob_bases_list)} bases from {peer_name}.")

        # e. Sift Locally and Find Matching Indices (Relative to Bob's List)
        match_indices_relative_to_bob = [] # Indices into Bob's list where bases matched
        comparison_count = min(len(bob_bases_list), photons_sent_count)
        if len(bob_bases_list) > photons_sent_count:
             print(f"{COLOR_WARNING}[QKD Sender Warning] Received more bases ({len(bob_bases_list)}) than photons sent ({photons_sent_count}). Comparing only first {photons_sent_count}.{COLOR_RESET}")

        for j in range(comparison_count):
             original_index = photons_sent_indices[j]
             if original_index in sender_bases_sent:
                 alice_basis = sender_bases_sent[original_index]
                 bob_basis = bob_bases_list[j]
                 if alice_basis == bob_basis:
                      match_indices_relative_to_bob.append(j)
             else:
                  print(f"{COLOR_ERROR}[QKD Sender Internal Error] Index {original_index} from photons_sent_indices not found in sender_bases_sent.{COLOR_RESET}")

        stats['sifted_key_length'] = len(match_indices_relative_to_bob)
        print(f"[QKD Sender] Found {len(match_indices_relative_to_bob)} matching bases.")

        # f. Send MATCHING INDICES (Relative to Bob's List) back to Bob
        match_indices_relative_str = ",".join(map(str, match_indices_relative_to_bob))
        public_ch.send("MATCH_INDICES_REL", match_indices_relative_str)
        print(f"[QKD Sender] Sent {len(match_indices_relative_to_bob)} relative matching indices to {peer_name}.")

        # g. Construct Alice's Sifted Key
        sifted_sender_key = []
        for rel_idx in match_indices_relative_to_bob:
             if rel_idx < len(photons_sent_indices):
                 original_index = photons_sent_indices[rel_idx]
                 if original_index in sender_bits_sent:
                     sifted_sender_key.append(sender_bits_sent[original_index])
                 else:
                      print(f"{COLOR_ERROR}[QKD Sender Internal Error] Original index {original_index} for relative index {rel_idx} not found in sender_bits_sent.{COLOR_RESET}")
             else:
                 print(f"{COLOR_ERROR}[QKD Sender Internal Error] Relative match index {rel_idx} out of bounds for photons_sent_indices ({len(photons_sent_indices)}).{COLOR_RESET}")

        print(f"[QKD Sender] Constructed sifted key of length: {len(sifted_sender_key)}")
        stats['sifted_key_length'] = len(sifted_sender_key) # Update stat

        if len(sifted_sender_key) < args.key_length:
             print(f"{COLOR_WARNING}[QKD Sender] Sifted key length ({len(sifted_sender_key)}) may be insufficient for desired key length {args.key_length} after QBER check.{COLOR_RESET}")

        # h. QBER Check (based on the sifted key derived from relative matches)
        if not sifted_sender_key:
            raise ValueError("No matching bases found after sifting. Cannot perform QBER check.")

        check_len = max(1, min(len(sifted_sender_key) // 4, args.key_length * 2))
        if len(sifted_sender_key) <= check_len: check_len = max(1, len(sifted_sender_key) // 2)
        if len(sifted_sender_key) <= check_len: raise ValueError(f"Insufficient sifted bits ({len(sifted_sender_key)}) for QBER check.")

        check_indices_relative_sifted = sorted(random.sample(range(len(sifted_sender_key)), check_len))
        indices_to_check_for_bob_str = ",".join(map(str, check_indices_relative_sifted))
        stats['qber_check_bits'] = check_len
        print(f"[QKD Sender] Proposing {len(check_indices_relative_sifted)} indices (relative to sifted key) for QBER check.")
        public_ch.send("CHECK_INDICES_REL_SIFT", indices_to_check_for_bob_str)

        # i. Receive Receiver's Check Bits
        print(f"[QKD Sender] Waiting for {peer_name}'s check bits...")
        data_type, receiver_check_bits_str = public_ch.receive()
        if not data_type: raise ConnectionAbortedError(f"{peer_name} disconnected (check bits)")
        if data_type == "ABORT": raise ValueError(f"{peer_name} aborted: {receiver_check_bits_str}")
        if data_type != "CHECK_BITS": raise TypeError(f"Expected CHECK_BITS from {peer_name}, got {data_type}")
        if len(receiver_check_bits_str) != len(check_indices_relative_sifted):
            raise ValueError(f"Check bits length mismatch (Got {len(receiver_check_bits_str)} from {peer_name}, Expected {len(check_indices_relative_sifted)})")

        # j. Calculate QBER
        mismatches = 0
        for i, rel_sift_idx in enumerate(check_indices_relative_sifted):
            if rel_sift_idx < len(sifted_sender_key):
                 alice_bit_at_check = sifted_sender_key[rel_sift_idx]
                 try:
                     bob_bit_at_check = int(receiver_check_bits_str[i])
                     if alice_bit_at_check != bob_bit_at_check:
                         mismatches += 1
                 except (ValueError, IndexError):
                      print(f"{COLOR_ERROR}[QKD Sender Error] Invalid character or index in received check bits: '{receiver_check_bits_str}' at pos {i}. Assuming mismatch.{COLOR_RESET}")
                      mismatches += 1
            else:
                 print(f"{COLOR_ERROR}[QKD Sender Internal Error] Relative sifted index {rel_sift_idx} out of bounds for sifted key ({len(sifted_sender_key)}). Assuming mismatch.{COLOR_RESET}")
                 mismatches += 1

        qber = mismatches / len(check_indices_relative_sifted) if check_indices_relative_sifted else 0
        stats['qber_mismatches'] = mismatches
        stats['qber_estimate'] = qber
        print(f"[QKD Sender] QBER Check: {mismatches}/{len(check_indices_relative_sifted)} mismatches. QBER = {COLOR_WARNING if qber > args.qber_threshold else (COLOR_SUCCESS if qber > 0 else COLOR_SUCCESS)}{qber:.2%}{COLOR_RESET}")

        # k. Decide based on QBER
        if qber > args.qber_threshold:
            print(f"{COLOR_ERROR}[QKD Sender] QBER ({qber:.2%}) exceeds threshold ({args.qber_threshold:.1%}). Aborting.{COLOR_RESET}")
            public_ch.send("ABORT", "QBER_HIGH")
            stats['status'] = 'QBER Fail'
            return None, None
        else:
            print(f"{COLOR_SUCCESS}[QKD Sender] QBER acceptable. Confirming key.{COLOR_RESET}")
            public_ch.send("CONFIRM_KEY", "OK")

            # l. Generate Final Key
            final_key_bits = [sifted_sender_key[i] for i in range(len(sifted_sender_key)) if i not in check_indices_relative_sifted]
            stats['key_after_qber'] = len(final_key_bits)
            print(f"[QKD Sender] Key length after QBER check: {len(final_key_bits)}")

            if len(final_key_bits) < args.key_length:
                print(f"{COLOR_ERROR}[QKD Sender Error] Final key too short ({len(final_key_bits)} < {args.key_length}).{COLOR_RESET}")
                stats['status'] = 'Key Too Short'
                return None, None
            else:
                sifted_sender_key_final = final_key_bits[:args.key_length]
                stats['final_key_length'] = len(sifted_sender_key_final)
                print(f"{COLOR_SUCCESS}[QKD Sender] Final {args.key_length}-bit key generated.{COLOR_RESET}")
                qkd_seed = derive_seed_from_key(sifted_sender_key_final)
                stats['status'] = 'Success'
                print(f"{COLOR_SUCCESS}--- QKD Phase (Sender) Successful ---{COLOR_RESET}")
                return qkd_seed, sifted_sender_key_final

    except (socket.error, socket.timeout, ConnectionAbortedError, TypeError, ValueError, IndexError) as e:
        print(f"{COLOR_ERROR}[QKD Sender Error] QKD phase failed: {e}{COLOR_RESET}")
        stats['status'] = f'Error: {e}'
        if 'public_ch' in locals() and public_ch and hasattr(public_ch, 'sock') and public_ch.sock.fileno() != -1:
             try: public_ch.send("ABORT", f"Sender Error: {e}")
             except socket.error: pass
        return None, None
    except Exception as e:
        print(f"{COLOR_ERROR}[QKD Sender Error] Unexpected error in QKD phase: {e}{COLOR_RESET}")
        traceback.print_exc()
        stats['status'] = f'Unexpected Error: {e}'
        return None, None

def perform_fh_sender_role(fh_conn, seed, args, stats):
    """Handles the Frequency Hopping transmission for the sender."""
    print(f"\n{COLOR_INFO}--- Starting Frequency Hopping Phase (Sender) ---{COLOR_RESET}")
    final_hopping_pattern = []
    try:
        hopping_pattern = generate_hopping_pattern(seed, len(args.message), config.FREQUENCIES)
        if not hopping_pattern:
             stats['fh_status'] = 'Pattern Generation Fail'
             return []
        final_hopping_pattern = hopping_pattern

        fh_conn.settimeout(config.SOCKET_TIMEOUT)
        print("[FH SENDER] Sending FH_READY signal.")
        fh_conn.sendall("FH_READY".encode('utf-8'))

        print("[FH SENDER] Waiting for FH_ACK...")
        ack = fh_conn.recv(1024).decode('utf-8')
        if ack != "FH_ACK":
            raise ValueError(f"Did not receive FH_ACK (Got: {ack}). Aborting FH.")

        print(f"[FH SENDER] Synchronization successful. Transmitting message ({len(args.message)} chars)...")
        for i, char in enumerate(args.message):
            freq = hopping_pattern[i]
            message_part = f"{char},{freq:.1f}"
            fh_conn.sendall(message_part.encode('utf-8'))
            time.sleep(random.uniform(0.05, 0.10))

        print(f"[FH SENDER] Finished sending. Sending FH_END.")
        fh_conn.sendall("FH_END".encode('utf-8'))
        print(f"{COLOR_SUCCESS}[FH SENDER] FH phase finished successfully.{COLOR_RESET}")
        stats['fh_status'] = 'Success'

    except (socket.error, socket.timeout, ValueError, UnicodeDecodeError, ConnectionAbortedError) as e:
        print(f"{COLOR_ERROR}[FH SENDER Error] FH phase failed: {e}{COLOR_RESET}")
        stats['fh_status'] = f'Error: {e}'
    except Exception as e:
        print(f"{COLOR_ERROR}[FH SENDER Error] Unexpected error in FH phase: {e}{COLOR_RESET}")
        traceback.print_exc()
        stats['fh_status'] = f'Unexpected Error: {e}'

    return final_hopping_pattern


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QKD-FH Sender (Alice)")
    parser.add_argument('-k', '--key-length', type=int, default=config.DEFAULT_KEY_LENGTH, help=f"Desired final key length (default: {config.DEFAULT_KEY_LENGTH})")
    parser.add_argument('-p', '--photon-factor', type=int, default=config.DEFAULT_PHOTON_FACTOR, help=f"Photon count factor (photons per key bit) (default: {config.DEFAULT_PHOTON_FACTOR})")
    parser.add_argument('-l', '--loss-rate', type=float, default=config.DEFAULT_LOSS_RATE, help=f"Simulated photon loss rate (0.0 to 1.0) (default: {config.DEFAULT_LOSS_RATE})")
    parser.add_argument('-q', '--qber-threshold', type=float, default=config.DEFAULT_QBER_THRESHOLD, help=f"Max acceptable QBER (default: {config.DEFAULT_QBER_THRESHOLD})")
    parser.add_argument('-m', '--message', type=str, default=config.DEFAULT_MESSAGE, help="Message to send via FH")
    # Removed --eve argument
    args = parser.parse_args()

    args.photon_count = args.key_length * args.photon_factor
    if not (0.0 <= args.loss_rate <= 1.0): parser.error("Loss rate must be between 0.0 and 1.0")
    if not (0.0 <= args.qber_threshold <= 1.0): parser.error("QBER threshold must be between 0.0 and 1.0")

    print(f"{COLOR_INFO}--- QKD-Seeded Frequency Hopping Sender (Alice) ---{COLOR_RESET}")
    print(f"Configuration: KeyLen={args.key_length}, PhotonFactor={args.photon_factor} ({args.photon_count} photons), Loss={args.loss_rate:.1%}, QBER_Max={args.qber_threshold:.1%}")

    qkd_server_sock = None
    fh_server_sock = None
    qkd_conn = None
    fh_conn = None
    final_pattern = []
    qkd_seed = None
    stats = {
        'photons_prepared': 0, 'photons_sent': 0, 'receiver_bases_count': 0,
        'sifted_key_length': 0, 'qber_check_bits': 0, 'qber_mismatches': 0,
        'qber_estimate': -1, 'key_after_qber': 0, 'final_key_length': 0,
        'status': 'Not Started', 'fh_status': 'Not Started'
    }

    try:
        # 1. Setup listener sockets
        qkd_server_sock = setup_server_listener(config.HOST, config.PORT_QKD)
        fh_server_sock = setup_server_listener(config.HOST, config.PORT_FH)

        # 2. Accept connections (Always from Bob now)
        qkd_conn, qkd_addr = accept_connection(qkd_server_sock, client_name="Bob (QKD)")
        fh_conn, fh_addr = accept_connection(fh_server_sock, client_name="Bob (FH)")

        # 3. Perform QKD
        qkd_seed, final_key = perform_qkd_sender_role(qkd_conn, args, stats)

        # 4. Perform FH if QKD succeeded
        if qkd_seed is not None:
            final_pattern = perform_fh_sender_role(fh_conn, qkd_seed, args, stats)
        else:
            print(f"\n{COLOR_WARNING}[SYSTEM] QKD failed, skipping Frequency Hopping.{COLOR_RESET}")
            stats['fh_status'] = 'Skipped (QKD Fail)'

    except (socket.error, socket.timeout, ConnectionAbortedError) as e:
        print(f"\n{COLOR_ERROR}[SENDER MAIN Error] Network error during setup or execution: {e}{COLOR_RESET}")
        stats['status'] = f'Network Error: {e}'
    except KeyboardInterrupt:
        print(f"\n{COLOR_WARNING}[SENDER MAIN] Interrupted by user.{COLOR_RESET}")
        stats['status'] = 'Interrupted'
    except Exception as e:
        print(f"\n{COLOR_ERROR}[SENDER MAIN Error] An unexpected error occurred: {e}{COLOR_RESET}")
        stats['status'] = f'Unexpected Main Error: {e}'
        traceback.print_exc()
    finally:
        # 5. Print Summary
        print("\n--- Sender Simulation Summary ---")
        print(f" QKD Status:         {stats.get('status', 'Unknown')}")
        print(f" Photons Prepared:   {stats.get('photons_prepared', 0)}")
        print(f" Photons Sent:       {stats.get('photons_sent', 0)} ({stats.get('photons_prepared', 0)-stats.get('photons_sent',0)} lost)")
        print(f" Bob Bases Rcvd:     {stats.get('receiver_bases_count', 0)}")
        print(f" Matches Found:      {stats.get('sifted_key_length', 0)}") # This is now count of matches
        if stats.get('qber_estimate', -1) != -1:
             qber_val = stats.get('qber_estimate', 0)
             qber_color = COLOR_ERROR if qber_val > args.qber_threshold else (COLOR_SUCCESS if qber_val > 0 else COLOR_SUCCESS)
             print(f" QBER Check:         {stats.get('qber_mismatches', 0)} / {stats.get('qber_check_bits', 0)} mismatches ({qber_color}{qber_val:.2%}{COLOR_RESET})")
        else:
             print(f" QBER Check:         Not Performed")
        print(f" Key Len Post-QBER:  {stats.get('key_after_qber', 0)}")
        print(f" Final Key Length:   {stats.get('final_key_length', 0)} / {args.key_length} (desired)")
        print(f" FH Status:          {stats.get('fh_status', 'Unknown')}")
        print("---------------------------------")

        # 6. Cleanup
        print("\n[SENDER MAIN] Cleaning up connections and listeners...")
        if qkd_conn: qkd_conn.close()
        if fh_conn: fh_conn.close()
        if qkd_server_sock: qkd_server_sock.close()
        if fh_server_sock: fh_server_sock.close()

        # Visualize if QKD succeeded
        if qkd_seed is not None:
            visualize_hopping(final_pattern, config.FREQUENCIES)

        print("[SENDER MAIN] Sender finished.")