"""
split_npz.py
============
The reverse of combine_npz.py. Loads a combined master NPZ file and splits it
back into individual species-specific NPZ files based on the label indices.
"""

import argparse
import os
import numpy as np

def main():
    parser = argparse.ArgumentParser(
        description="Split a combined master BirdNET NPZ file back into individual species NPZ files."
    )
    parser.add_argument("--input_npz", required=True, help="Path to the combined master .npz file.")
    parser.add_argument("--output_dir", required=True, help="Directory to save the individual species .npz files.")
    args = parser.parse_args()

    if not os.path.exists(args.input_npz):
        print(f"ERROR: Combined NPZ file not found at: {args.input_npz}")
        return

    # Load master NPZ
    print(f"Loading master combined NPZ: {args.input_npz}")
    try:
        master_data = np.load(args.input_npz, allow_pickle=True)
    except Exception as e:
        print(f"ERROR: Could not load NPZ: {e}")
        return

    x_train = master_data["x_train"]
    y_train = master_data["y_train"]
    labels = master_data["labels"]

    # Gather metadata to replicate in children
    metadata = {
        "fmin": master_data.get("fmin", 0.0),
        "fmax": master_data.get("fmax", 15000.0),
        "audio_speed": master_data.get("audio_speed", 1.0),
        "crop_mode": master_data.get("crop_mode", "center"),
        "overlap": master_data.get("overlap", 0.0),
    }

    print(f"Found {len(labels)} classes in master file. Total samples: {len(x_train)}")

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Split species by species
    split_count = 0
    for idx, label_name in enumerate(labels):
        # Find indices where this class is active (1.0 or -1.0)
        class_column = y_train[:, idx]
        active_indices = np.where((class_column == 1.0) | (class_column == -1.0))[0]

        if len(active_indices) == 0:
            print(f"  [Skip] '{label_name}' has 0 samples.")
            continue

        # Extract subsets
        sub_x = x_train[active_indices]
        # Re-create single-class y_train vector shape (N, 1)
        sub_y = class_column[active_indices].reshape(-1, 1)

        # Output filename
        # Clean label name to prevent invalid Windows filename characters
        safe_label_name = "".join([c for c in label_name if c.isalpha() or c.isdigit() or c in " _-."]).strip()
        out_filename = f"{safe_label_name}.npz"
        out_path = os.path.join(args.output_dir, out_filename)

        # Save single-species NPZ
        np.savez(
            out_path,
            x_train=sub_x,
            y_train=sub_y,
            x_test=np.array([]),
            y_test=np.array([]),
            labels=np.array([label_name], dtype=object),
            binary_classification=False,
            multi_label=False,
            fmin=metadata["fmin"],
            fmax=metadata["fmax"],
            audio_speed=metadata["audio_speed"],
            crop_mode=metadata["crop_mode"],
            overlap=metadata["overlap"],
        )
        print(f"  [Saved] '{label_name}' -> {out_path} ({len(active_indices)} samples)")
        split_count += 1

    print(f"\nSplit complete! Successfully created {split_count} species-specific NPZ files in:\n  {args.output_dir}")

if __name__ == "__main__":
    main()
