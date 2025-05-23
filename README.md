# Secure Communication Simulation: QKD-Seeded Frequency Hopping (Alice & Bob)

## 1. Project Overview

This project demonstrates a secure communication system combining Quantum Key Distribution (QKD) and Frequency Hopping (FH), implemented as separate sender (Alice) and receiver (Bob) applications communicating over simulated network sockets.

**Key Features:**

- **Simulated QKD (BB84):** Establishes a shared secret key (seed) using a simulation of the BB84 protocol.
- **Simulated Photon Loss:** Models realistic quantum channel imperfections, impacting key rate.
- **Frequency Hopping (FH):** Uses the QKD-derived seed to generate a synchronized pseudo-random frequency hopping pattern for transmitting data, enhancing resilience.
- **Command-Line Configuration:** Uses `argparse` to configure key parameters (key length, photons, loss rate, QBER threshold).
- **(Optional) Colorized Output:** Uses `colorama` for better log readability.

This version focuses on the direct communication between Alice and Bob.

## 2. Conceptual Background

### Simulated Quantum Key Distribution (BB84)

QKD protocols allow two parties (Alice and Bob) to produce a shared, random secret key known only to them, using principles of quantum mechanics to detect potential eavesdropping.

This simulation mimics the core steps of the BB84 protocol:

1.  **Photon Transmission (Simulated):** Alice generates random bits and randomly chooses encoding bases (Rectilinear '+' or Diagonal 'x'). She sends simulated photons over a quantum channel, with some probability of photon loss.
2.  **Photon Measurement (Simulated):** Bob receives the surviving photons. For each, he randomly chooses a measurement basis. If his basis matches Alice's encoding basis, he measures the correct bit; otherwise, the result is random.
3.  **Basis Reconciliation (Public Channel):** Alice and Bob communicate over a public channel to determine which photons were successfully transmitted and measured with matching bases. This version uses a protocol resilient to photon loss:
    - Alice sends photons and a sync signal.
    - Bob sends back the bases he used for the photons he received.
    - Alice compares Bob's bases with hers for the _successfully sent_ photons and identifies which _relative_ positions (in Bob's received sequence) had matching bases.
    - Alice sends these _relative matching indices_ to Bob.
4.  **Key Sifting:** Both Alice and Bob use the agreed-upon relative matching indices to construct their initial _sifted keys_ from their respective bit sequences (Alice's sent bits, Bob's measured bits). These keys should now be correlated.
5.  **Parameter Estimation (QBER Check):** Alice and Bob publicly compare a random subset of their sifted key bits (revealing the bits at specific relative indices). They calculate the Quantum Bit Error Rate (QBER). A high QBER would indicate eavesdropping (or excessive channel noise).
6.  **Final Key Generation:** If the QBER is below a set threshold, they discard the bits revealed during the check. The remaining correlated bits form their shared secret key, which is then converted into a numerical seed for FH. If QBER is too high, they abort.

_(Note: Error correction and privacy amplification are omitted for simplicity.)_

### Frequency Hopping (FH)

Once Alice and Bob possess the identical secret seed from QKD:

1.  **Pattern Generation:** Both use the seed as input to the _same_ pseudo-random number generator algorithm (via `random.Random(seed)`), producing an identical, deterministic sequence of frequencies (the hopping pattern).
2.  **Synchronized Communication:** Alice transmits her message character by character, changing the transmission frequency according to the pattern. Bob tunes his receiver to the expected frequency at each step.

## 3. Simulation Architecture

- **`config.py`**: Stores shared configuration (ports, default parameters, frequencies).
- **`channels.py`**: Defines simulated `QuantumChannel`, `PublicChannel`, network helpers, and color constants.
- **`utils.py`**: Contains shared utility functions (key derivation, FH pattern, visualization).
- **`qkd_sender.py` (Alice):**
  - Acts as the server, listening for Bob's QKD and FH connections.
  - Simulates photon loss during transmission.
  - Performs QKD steps (Corrected Protocol v2).
  - Calculates final key and seed if successful.
  - Performs FH transmission to Bob.
  - Reports summary statistics and optionally plots the FH pattern.
- **`qkd_receiver.py` (Bob):**
  - Acts as the client, connecting to Alice's QKD and FH ports.
  - Performs QKD steps (Corrected Protocol v2), handling photon loss.
  - Calculates final key and seed if successful.
  - Performs FH reception.
  - Reports summary statistics and message reconstruction success.

## 4. Implementation Details

- **Language:** Python 3.x
- **Libraries:** `socket`, `random`, `time`, `hashlib`, `traceback`, `sys`, `argparse`
- **Optional:** `matplotlib` (for visualization), `colorama` (for colored output)

## 5. How to Run the Project

1.  **Prerequisites:**

    - Python 3.x installed.
    - Ensure all files (`config.py`, `channels.py`, `utils.py`, `qkd_sender.py`, `qkd_receiver.py`) are in the same directory.

2.  **Setup Virtual Environment & Dependencies (Recommended):**

    ```bash
    python -m venv .venv
    # Activate: .\.venv\Scripts\Activate.ps1 (PowerShell) or source .venv/bin/activate (Linux/macOS)
    # Install optional libs:
    pip install matplotlib colorama
    ```

    _(Simulation runs without optional libs, but plotting/colors will be disabled)_

3.  **Run the Simulation:**

    - **Open TWO separate terminals or command prompts** in the project directory.
    - **Terminal 1 (Start Sender FIRST):** Customize parameters as needed.

      ```bash
      # Example: Default settings
      python qkd_sender.py

      # Example: Custom settings (e.g., more photons, higher loss)
      python qkd_sender.py --key-length 24 --photon-factor 20 --loss-rate 0.3 --qber-threshold 0.20
      ```

      - The sender will start listening and wait for Bob.

    - **Terminal 2 (Start Receiver):** Use parameters matching the sender's expected key length and message.

      ```bash
      # Example: Default settings
      python qkd_receiver.py

      # Example: Custom settings (must match sender's key length)
      python qkd_receiver.py --key-length 24
      ```

      - The receiver will attempt to connect to the sender.

    - Observe the output in both terminals.
    - If successful and matplotlib is installed, the sender terminal will show a plot window after communication finishes (close the plot window to let the sender script fully terminate).

4.  **Deactivate Virtual Environment (Optional):**
    - Type `deactivate` in each terminal when finished.

## 6. Expected Results and Discussion

- **Terminal Output:** Both terminals show logs of QKD and FH steps.
- **Successful Key:** Sender and receiver should derive the same seed if QBER is below threshold. Note that photon loss significantly reduces the number of bits available for the key (requiring a higher initial `photon-factor`).
- **QBER:** Without eavesdropping, the QBER should be very low (near 0%). If QBER exceeds the threshold (due to simulated noise or high loss impacting the small sample size), the protocol correctly aborts.
- **Successful Transmission:** If QKD succeeds, the receiver should report successful reconstruction of the message.
- **Visualization:** The sender (if matplotlib installed) displays the frequency hops.

This simulation demonstrates the core principles of QKD key establishment, the impact of channel loss, the QBER check for security, and the subsequent use of the secure key for classical Frequency Hopping communication.
