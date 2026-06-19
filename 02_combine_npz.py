import argparse
import os
import glob
import numpy as np

def main():
    parser = argparse.ArgumentParser(description="Combine multiple BirdNET NPZ files into one master dataset.")
    parser.add_argument("--npz_dir", required=True, help="Directory containing the individual .npz files.")
    parser.add_argument("--output_npz", required=True, help="Path to save the combined master .npz file.")
    args = parser.parse_args()

    npz_files = glob.glob(os.path.join(args.npz_dir, "*.npz"))
    if not npz_files:
        print(f"No .npz files found in {args.npz_dir}")
        return

    print(f"Found {len(npz_files)} NPZ files. Scanning for unique labels...")
    
    master_labels_set = set()
    metadata = None

    # First pass: collect all unique labels
    for f in npz_files:
        try:
            data = np.load(f, allow_pickle=True)
            labels = data["labels"]
            for label in labels:
                master_labels_set.add(label)
            
            # Save the metadata from the first valid file to reuse later
            if metadata is None:
                metadata = {
                    "fmin": data.get("fmin", 0.0),
                    "fmax": data.get("fmax", 15000.0),
                    "audio_speed": data.get("audio_speed", 1.0),
                    "crop_mode": data.get("crop_mode", "center"),
                    "overlap": data.get("overlap", 0.0),
                }
        except Exception as e:
            print(f"Error reading {f}: {e}")

    master_labels_list = sorted(list(master_labels_set))
    print(f"Master Label List ({len(master_labels_list)} classes): {master_labels_list}")

    all_x_train = []
    all_y_train = []

    # Second pass: read features and reconstruct one-hot y_train
    for f in npz_files:
        print(f"Processing {os.path.basename(f)}...")
        try:
            data = np.load(f, allow_pickle=True)
            x_train = data["x_train"]
            old_y_train = data["y_train"]
            old_labels = list(data["labels"])

            if len(x_train) == 0:
                continue

            # We need to map the old y_train to the new one-hot length
            for i in range(len(x_train)):
                # Find which label is active in the old_y_train
                # old_y_train[i] is a one-hot array like [0, 1, 0]
                active_index = np.argmax(old_y_train[i])
                active_label_str = old_labels[active_index]
                
                # Find its index in the new master list
                new_index = master_labels_list.index(active_label_str)
                
                # Create the new one-hot vector
                new_y_vector = np.zeros(len(master_labels_list), dtype="float32")
                new_y_vector[new_index] = 1.0
                
                all_x_train.append(x_train[i])
                all_y_train.append(new_y_vector)

        except Exception as e:
            print(f"Error processing features from {f}: {e}")

    all_x_train = np.array(all_x_train, dtype="float32")
    all_y_train = np.array(all_y_train, dtype="float32")

    is_binary = len(master_labels_list) == 1

    print(f"Stacking complete. Total samples: {len(all_x_train)}")
    
    # Save the combined master NPZ
    directory = os.path.dirname(os.path.abspath(args.output_npz))
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

    # Use metadata from the first file, or defaults
    if metadata is None:
        metadata = {
            "fmin": 0.0, "fmax": 15000.0, "audio_speed": 1.0,
            "crop_mode": "center", "overlap": 0.0
        }

    np.savez(
        args.output_npz,
        x_train=all_x_train,
        y_train=all_y_train,
        x_test=np.array([]),
        y_test=np.array([]),
        labels=np.array(master_labels_list, dtype=object),
        binary_classification=is_binary,
        multi_label=False,
        fmin=metadata["fmin"],
        fmax=metadata["fmax"],
        audio_speed=metadata["audio_speed"],
        crop_mode=metadata["crop_mode"],
        overlap=metadata["overlap"],
    )
    print(f"Successfully saved combined dataset to {args.output_npz}")

if __name__ == "__main__":
    main()
