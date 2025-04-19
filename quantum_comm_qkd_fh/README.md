# Secure Communication Simulation: QKD-Seeded Frequency Hopping

## 1. Project Overview

This project demonstrates an advanced secure communication system that combines two powerful concepts:

1.  **Simulated Quantum Key Distribution (QKD):** Uses a simulation of the BB84 protocol to securely establish a shared secret key (seed) between a sender (Alice) and a receiver (Bob). The simulation leverages core quantum principles like random basis selection and measurement disturbance to detect potential eavesdropping.
2.  **Frequency Hopping (FH):** Employs the secret key generated via QKD as a seed for a pseudo-random number generator. This generator creates a synchronized frequency hopping pattern that both Alice and Bob follow to transmit the actual data message, enhancing resilience against jamming and interception.

By first establishing a key using quantum principles (simulated) and then using that key for classical frequency hopping, this project offers a compelling demonstration of layered security inspired by modern cryptographic techniques.

## 2. Conceptual Background

### Simulated Quantum Key Distribution (BB84)

QKD protocols allow two parties (Alice and Bob) to produce a shared, random secret key known only to them, using principles of quantum mechanics to detect the presence of an eavesdropper (Eve).

This simulation mimics the core steps of the BB84 protocol:

1.  **Photon Transmission (Simulated):** Alice generates a sequence of random bits. For each bit, she randomly chooses one of two *bases* (e.g., Rectilinear '+' or Diagonal 'x') to *encode* the bit onto a simulated photon. She sends these photons to Bob over a *quantum channel* (simulated via a socket).
2.  **Photon Measurement (Simulated):** Bob doesn't know which basis Alice used for each photon. For each incoming photon, he randomly chooses one of the two bases to *measure* it. Quantum mechanics dictates that if Bob chooses the *same* basis as Alice, he measures the correct bit Alice sent. If he chooses the *wrong* basis, his measurement result is random (50% chance of 0 or 1).
3.  **Basis Reconciliation (Public Channel):** After the transmission, Bob tells Alice *which basis he used* for each measurement (but not the results) over a *public classical channel* (simulated via another socket). Alice compares this to the bases she used.
4.  **Key Sifting:** Alice and Bob discard all measurements where they used different bases. The remaining sequence of bits, where their bases matched, forms their initial *sifted key*. In an ideal, noise-free, eavesdropper-free scenario, their sifted keys should be identical.
5.  **Eavesdropping Check (Parameter Estimation):** Alice and Bob publicly compare a randomly chosen subset of their sifted key bits. If an eavesdropper (Eve) had tried to measure the photons in transit, she would inevitably introduce errors (disturb the quantum states) due to the uncertainty principle. This results in a higher *Quantum Bit Error Rate (QBER)* when Alice and Bob compare their subset of bits. If the QBER exceeds a certain threshold, they assume eavesdropping occurred and discard the key.
6.  **Final Key Generation:** If the QBER is acceptable, they remove the publicly revealed check bits. The remaining correlated bits form their shared secret key. This key is then converted into a numerical seed.

*(Note: This simulation omits advanced QKD steps like error correction and privacy amplification for simplicity but captures the core protocol flow and security concept.)*

### Frequency Hopping (FH)

Once Alice and Bob possess the identical secret seed from QKD:

1.  **Pattern Generation:** Both use the seed as input to the *same* pseudo-random number generator algorithm. This produces an identical, deterministic sequence of frequencies (the hopping pattern).
2.  **Synchronized Communication:** Alice transmits her message character by character, changing the transmission frequency for each character according to the generated pattern. Bob, knowing the pattern (because he has the seed), tunes his receiver to the expected frequency at each time step to receive the message.

This makes it difficult for an interceptor who doesn't know the seed/pattern to follow the communication across the frequency spectrum.

## 3. Simulation Architecture

*   **Sender (Alice):** Initiates QKD, generates/sends simulated photons, performs basis reconciliation and QBER check, derives the seed, generates the FH pattern, and transmits the message over hopping frequencies.
*   **Receiver (Bob):** Receives/measures simulated photons, performs basis reconciliation and QBER check, derives the seed, generates the FH pattern, and listens on the correct frequencies to reconstruct the message.
*   **Quantum Channel (Simulated):** A socket connection used for transmitting the simulated photon states (`basis`, `bit`). This channel is assumed to be vulnerable to eavesdropping in a real scenario.
*   **Public Channel (Simulated):** A separate socket connection used for classical communication (exchanging bases, check bits, synchronization signals). This channel is assumed to be authenticated but not necessarily confidential.
*   **Frequency Hopping Channel (Simulated):** The public channel socket is reused after QKD for transmitting the actual data message using the hopping pattern.
*   **Visualization Module:** Uses Matplotlib (if available) to plot the frequency hopping pattern derived from the QKD seed after the simulation completes.

## 4. Implementation Details

### Technologies and Libraries

*   **Programming Language:** Python 3.x
*   **Libraries:**
    *   `random`: For all randomness requirements (bits, bases, frequency choices).
    *   `socket`: For network communication simulation (QKD and FH channels).
    *   `threading`: To run sender and receiver concurrently.
    *   `sys`: For basic system interaction (checking imports).
    *   `math`: (Potentially, if needed for more complex operations - currently minimal use).
    *   `matplotlib` (Optional): For plotting the frequency hopping pattern.

### How to Run the Project

1.  **Prerequisites:**
    *   Python 3.x installed and accessible from the terminal (`python` or `py` command).
    *   `pip` (Python package installer) available.

2.  **Setup Virtual Environment (Recommended):**
    *   Open a terminal or command prompt in the `quantum_comm_qkd_fh` directory.
    *   Create a virtual environment:
        ```bash
        python -m venv .venv
        ```
    *   Activate the environment:
        *   Windows (PowerShell): `.venv\Scripts\Activate.ps1`
            *(If blocked by execution policy, run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force` first)*
        *   Windows (Command Prompt): `.venv\Scripts\activate.bat`
        *   macOS/Linux: `source .venv/bin/activate`
    *   You should see `(.venv)` at the beginning of your terminal prompt.

3.  **Install Dependencies:**
    *   While the virtual environment is active, install `matplotlib`:
        ```bash
        pip install -r requirements.txt
        # or manually: pip install matplotlib
        ```
    *   **Note:** If you encounter network errors preventing `pip` from installing `matplotlib` (as seen previously), the simulation can still run. The script will detect the missing library, print a warning, and skip the final visualization plot. The core QKD and FH communication logic will execute and print detailed steps to the console.

4.  **Run the Simulation:**
    *   Execute the main script:
        ```bash
        python qkd_frequency_hopping.py
        ```
    *   Observe the terminal output. It will show:
        *   Detailed steps of the simulated QKD phase (photon sending/receiving, basis comparison, QBER check, final key generation, seed derivation).
        *   Detailed steps of the Frequency Hopping phase (pattern generation, message transmission/reception on hopping frequencies).
        *   Final reconstructed message and comparison with the original.
    *   If `matplotlib` was installed successfully, a plot window will appear showing the frequency hopping pattern used.

5.  **Deactivate Virtual Environment (Optional):**
    *   When finished, simply type `deactivate` in the terminal.

## 5. Expected Results and Discussion

*   **Successful Key Exchange:** The terminal output should show Alice and Bob agreeing on a final secret key (binary string) with a low QBER (below the threshold).
*   **Seed Derivation:** A numerical seed should be derived from this binary key on both sides.
*   **Synchronized Hopping:** Both sender and receiver should generate the identical frequency hopping pattern based on the shared seed.
*   **Successful Data Transmission:** The receiver should successfully reconstruct the original message sent by the sender.
*   **Security Demonstration:** The QBER check step highlights how eavesdropping could be detected in a real QKD system. The subsequent frequency hopping demonstrates resilience against simpler forms of interception.

This simulation provides a strong conceptual illustration of how quantum communication principles can be combined with classical techniques to build robust secure communication systems. 