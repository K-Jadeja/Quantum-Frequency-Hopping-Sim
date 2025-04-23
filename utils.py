# utils.py
"""
Shared utility functions for QKD-FH simulation (key derivation, FH pattern, visualization).
Handles optional colorama import.
"""
import random
import hashlib
import sys
import time
import traceback
# No direct config import here, pass params

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


# Try to import matplotlib
matplotlib_present = False
plt = None
try:
    import matplotlib.pyplot as plt
    matplotlib_present = True
except ImportError:
    print(f"{COLOR_WARNING}\n[Utils] Warning: matplotlib not found. Visualization disabled.{COLOR_RESET}")


def derive_seed_from_key(key):
    """Derive a numerical seed from the final binary key using SHA-256."""
    if not key or len(key) < 8:
        print(f"{COLOR_ERROR}[Utils Error] Cannot derive seed from short/empty key. Using random fallback.{COLOR_RESET}")
        return random.randint(0, (1 << 32) - 1)

    key_str = "".join(map(str, key))
    seed_bytes = hashlib.sha256(key_str.encode()).digest()
    seed = int.from_bytes(seed_bytes[:4], 'big') # Use first 32 bits of hash
    # print(f"{COLOR_INFO}[Utils] Derived numerical seed from {len(key)}-bit key: {seed}{COLOR_RESET}") # Silent unless debugging
    return seed

def generate_hopping_pattern(seed, length, frequencies):
    """Generates a deterministic sequence of frequencies from the shared seed."""
    if not frequencies:
        print(f"{COLOR_ERROR}[Utils Error] No frequencies provided!{COLOR_RESET}")
        return []
    if length <= 0:
        print(f"{COLOR_ERROR}[Utils Error] Cannot generate pattern of length <= 0.{COLOR_RESET}")
        return []
    local_random = random.Random(seed)
    pattern = [local_random.choice(frequencies) for _ in range(length)]
    print(f"{COLOR_INFO}[Utils] Generated Hopping Pattern (Seed: {seed}, Length: {length}){COLOR_RESET}")
    return pattern

def visualize_hopping(hopping_pattern, frequencies):
    """Visualizes the frequency hopping pattern if matplotlib is available."""
    if not matplotlib_present or plt is None:
        return
    if not hopping_pattern:
        return

    print(f"\n{COLOR_INFO}[Visualization] Preparing frequency hopping plot...{COLOR_RESET}")
    try:
        plt.figure(figsize=(12, 7))
        time_steps = range(1, len(hopping_pattern) + 1)

        plt.plot(time_steps, hopping_pattern, marker='o', linestyle='None', color='blue', markersize=6, label='Hop Frequency')
        plt.step(time_steps, hopping_pattern, where='post', color='red', linestyle='--', alpha=0.7, label='Hopping Path')

        plt.xlabel('Time Step (Message Character Index + 1)')
        plt.ylabel('Frequency (MHz)')
        plt.title(f'Frequency Hopping Pattern (Seed Derived from QKD Key)')
        plt.xticks(time_steps[::max(1, len(time_steps)//20)])
        plt.yticks(frequencies)
        plt.ylim(min(frequencies) - 1, max(frequencies) + 1)
        plt.grid(True, which='major', axis='x', linestyle=':', linewidth=0.7)
        plt.grid(True, which='major', axis='y', linestyle='--', linewidth=0.5)
        plt.legend()
        plt.tight_layout()
        print(f"{COLOR_INFO}[Visualization] Displaying plot window (close window to continue)...{COLOR_RESET}")
        plt.show()
    except Exception as e:
        print(f"{COLOR_ERROR}[Visualization Error] Failed to plot graph: {e}{COLOR_RESET}")
        traceback.print_exc()


def sift_key_indices(own_bases, other_bases):
    """Compares bases and returns indices where they matched. (Not used in corrected protocol)."""
    match_indices = []
    count = min(len(own_bases), len(other_bases))
    for i in range(count):
        if own_bases[i] == other_bases[i]:
            match_indices.append(i)
    return match_indices