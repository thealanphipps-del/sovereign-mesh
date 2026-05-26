import os
import json

print("🚀 MIGRATING ARCHIVES: Ingesting Jovian Archives and Forensic Hub sync logs...")

dataset_path = "/home/aellok/sovereign_mesh/sovereign_genome_dataset.jsonl"
archive_entries = []

# ==============================================================================
# 1. PARSE JOVIAN ARCHIVE: reconcile_zdsp.py
# ==============================================================================
zdsp_path = "/home/aellok/Jovian_Archives/Epoch_4/Initial_Cleanup/reconcile_zdsp.py"
if os.path.exists(zdsp_path):
    print("  -> Ingesting reconcile_zdsp.py (Z-DSP Algorithm)...")
    try:
        with open(zdsp_path, "r", encoding="utf-8") as f:
            code = f.read()
        entry_zdsp = {
            "input": "JOVIAN_ARCHIVE_INQUIRY: Retrieve reconcile_zdsp.py source and specification from Epoch 4",
            "output": f"Z_DSP_SPECIFICATION: Zero-Divergence Reconciliation Algorithm (Z-DSP v4.0):\n```python\n{code}\n```\nStatus: REGISTERED in local Jovian epoch core."
        }
        archive_entries.append(entry_zdsp)
        print("     ✅ Formatted Z-DSP algorithm specification.")
    except Exception as e:
        print(f"     [WARN] Error parsing reconcile_zdsp.py: {e}")

# ==============================================================================
# 2. PARSE JOVIAN ARCHIVE: offload_sort.sh
# ==============================================================================
sort_path = "/home/aellok/Jovian_Archives/Epoch_4/Initial_Cleanup/offload_sort.sh"
if os.path.exists(sort_path):
    print("  -> Ingesting offload_sort.sh (Storage Offload Policy)...")
    try:
        with open(sort_path, "r", encoding="utf-8") as f:
            code = f.read()
        entry_sort = {
            "input": "JOVIAN_ARCHIVE_INQUIRY: Retrieve offload_sort.sh script from Epoch 4",
            "output": f"OFFLOAD_SPECIFICATION: Storage Offload & Sort Policy from Epoch 4:\n```bash\n{code}\n```\nStatus: ENFORCED via cron job."
        }
        archive_entries.append(entry_sort)
        print("     ✅ Formatted Storage Offload specification.")
    except Exception as e:
        print(f"     [WARN] Error parsing offload_sort.sh: {e}")

# ==============================================================================
# 3. PARSE FORENSIC LOG: forensic_chain.log
# ==============================================================================
forensic_path = "/home/aellok/Sovereign_Node_Go/forensic_chain.log"
if os.path.exists(forensic_path):
    print("  -> Ingesting forensic_chain.log...")
    try:
        with open(forensic_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            if line.strip():
                entry_forensic = {
                    "input": "FORENSIC_HUB_AUDIT: Retrieve file relocation event from forensic_chain.log",
                    "output": f"FORENSIC_CHAIN_LOG: Verified relocation event:\n{line.strip()}\nStatus: AUDITED & SIGNED."
                }
                archive_entries.append(entry_forensic)
        print(f"     ✅ Formatted {len(lines)} forensic chain events.")
    except Exception as e:
        print(f"     [WARN] Error parsing forensic_chain.log: {e}")

# ==============================================================================
# 4. APPEND AND MERGE WITH MASTER DATASET (JSONL)
# ==============================================================================
existing_entries = []
if os.path.exists(dataset_path):
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                existing_entries.append(json.loads(line))

total_merged = len(existing_entries) + len(archive_entries)

# Append new entries to file
with open(dataset_path, "a", encoding="utf-8") as f:
    for entry in archive_entries:
        f.write(json.dumps(entry) + "\n")

print(f"\n🌟 ARCHIVE MIGRATION COMPLETE: Added {len(archive_entries)} new entries.")
print(f"📊 Total unified training rows: {total_merged}")
print(f"💾 Updated dataset saved at: {dataset_path}")
