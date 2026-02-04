# Solana Verifiable Lottery 

A **trust-minimized** lottery draw system designed for Solana token holders. This tool ensures fairness by leveraging on-chain entropy and deterministic selection logic.

---

## How It Works

The system uses a **Commit-Reveal scheme** to prevent manipulation by developers or participants.

* **Commitment:** A future block number is publicly announced before it is produced by the network.
* **Randomness:** The winning seed is derived from the **Blockhash** of that specific finalized slot. Since blockhashes are unpredictable until the moment they are produced, the result is tamper-proof.
* **Audit:** Every draw generates an `audit.json` file. This allows any third party to re-run the logic and verify the winner independently.

---

## Features

* **Slot Prediction:** Estimate the specific slot number for a target time based on real-time network performance.
* **Dual Program Support:** Automatically aggregates balances from both **SPL Token** and **Token-2022** accounts.
* **Deterministic Selection:** Entrants are sorted by public key before tickets are assigned, ensuring that the same inputs always yield the same winner.
* **Audit Logging:** Comprehensive JSON exports for full community transparency.

---

## 🛠 Usage

### 1. Installation

Set up your environment and install the package:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

```

### 2. The Draw Process

**Step A: Predict and Announce**
Calculate a slot for a future time (e.g., 10:00 PM) and announce it to your community to "lock in" the target.

```bash
solana-lottery predict --time 22:00

```

**Step B: Execute the Draw**
Once the target slot has passed and reached **finalized** commitment, run the draw command:

```bash
solana-lottery draw --slot <TARGET_SLOT>

```

### 3. Verification

Anyone can verify an existing audit file to confirm the result:

```bash
solana-lottery verify --audit audit.json

```

---

## ⚙️ Technical Details

| Component | Logic |
| --- | --- |
| **Seed** | Blockhash from a finalized slot (or provided block feed). |
| **Entrants** | Snapshot of holders from classic SPL and Token-2022 programs. |
| **Winner Calculation** | `$SHA\text{-}256(\text{seed}) \pmod{\text{total\_tickets}}$` |
| **Skipped Slots** | Automatically fetches the next available blockhash if the target is skipped. |
| **Finality** | Requires `finalized` status to protect against chain reorganizations. |

---

## ⚠️ Disclaimer

*This software is provided for experimental and entertainment purposes. Users are responsible for ensuring compliance with local laws and regulations regarding giveaways or lotteries.*

---
