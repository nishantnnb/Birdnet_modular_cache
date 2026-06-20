"""
create_npz.py
=============
Extracts 1024-dim BirdNET embeddings using the SavedModel's "embeddings" signature.
No binary classification checks — works with any number of bird folders.

Usage:
    py -3.11 create_npz.py --audio_dir "D:\\path\\to\\bird_folders"
    py -3.11 create_npz.py --audio_dir "D:\\path\\to\\bird_folders" --output_npz "D:\\path\\out.npz"
"""

import argparse
import os
import sys
import numpy as np
import tqdm
import tensorflow as tf

# ── SavedModel path (pip-installed, contains "embeddings" signature) ──────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PB_MODEL_PATH = os.path.join(SCRIPT_DIR, "model", "BirdNET_GLOBAL_6K_V2.4_Model")

# ── Audio constants matching BirdNET V2.4 ─────────────────────────────────────
SAMPLE_RATE   = 48000   # Hz
SIG_LENGTH    = 3.0     # seconds per chunk → 144000 samples
ALLOWED_FILETYPES = {"wav", "flac", "mp3", "ogg", "m4a", "mp4", "wma", "aiff"}


def load_pbmodel(model_path):
    """Load the SavedModel once and return it."""
    print(f"Loading SavedModel from:\n  {model_path}")
    if not os.path.isdir(model_path):
        print("ERROR: SavedModel directory not found.")
        print("Run the debug_train.py script once so it downloads the model, then re-run this script.")
        sys.exit(1)
    pbm = tf.saved_model.load(model_path)
    if "embeddings" not in pbm.signatures:
        print("ERROR: SavedModel does not have an 'embeddings' signature.")
        print("The model in the checkpoints folder may be the wrong version.")
        sys.exit(1)
    print("Model loaded. Embeddings signature confirmed (1024-dim).")
    return pbm.signatures["embeddings"]


def get_embedding(embed_fn, audio_chunk: np.ndarray) -> np.ndarray:
    """Run one 3-second audio chunk through SavedModel → 1024-dim embedding."""
    inp = tf.constant(audio_chunk.reshape(1, -1), dtype=tf.float32)
    out = embed_fn(inp)
    # output is a dict; the embedding value has shape (1, 1024)
    emb = list(out.values())[0].numpy()  # (1, 1024)
    return emb[0]                        # (1024,)


def open_audio(filepath: str, fmin: float, fmax: float, speed: float, duration: float = None):
    """Open audio file via local audio.py (no birdnet_analyzer dependency)."""
    import audio as ba_audio  # local copy
    try:
        sig, rate = ba_audio.open_audio_file(
            filepath,
            sample_rate=SAMPLE_RATE,
            fmin=fmin if fmin > 0 else None,
            fmax=fmax if fmax < SAMPLE_RATE // 2 else None,
            speed=speed,
            duration=duration,
        )
        return sig, rate
    except Exception as e:
        return None, None


def split_audio(sig, rate, crop_mode, overlap, min_len):
    """Split signal into 3-second chunks based on crop mode. Uses local audio.py + config.py."""
    import audio as ba_audio  # local copy
    import config as cfg      # local copy
    cfg.SAMPLE_RATE = SAMPLE_RATE
    cfg.SIG_LENGTH  = SIG_LENGTH
    cfg.SIG_OVERLAP = overlap
    cfg.SIG_MINLEN  = min_len
    cfg.USE_NOISE   = False

    if crop_mode == "center":
        return [ba_audio.crop_center(sig, rate, SIG_LENGTH)]
    elif crop_mode == "first":
        chunks = ba_audio.split_signal(sig, rate, SIG_LENGTH, overlap, min_len)
        return [chunks[0]] if chunks else []
    elif crop_mode == "smart":
        return ba_audio.smart_crop_signal(sig, rate, SIG_LENGTH, overlap, min_len)
    else:  # "segments"
        return ba_audio.split_signal(sig, rate, SIG_LENGTH, overlap, min_len)


def main():
    parser = argparse.ArgumentParser(
        description="Extract 1024-dim BirdNET embeddings to NPZ (no binary-class checks)."
    )
    parser.add_argument("--audio_dir",  required=True,
                        help="Folder whose sub-folders are bird-class labels.")
    parser.add_argument("--output_npz", required=False, default=None,
                        help="Output .npz path (default: saved inside --audio_dir).")
    parser.add_argument("--model_path", default=PB_MODEL_PATH,
                        help="Path to the BirdNET SavedModel directory.")
    parser.add_argument("--crop_mode", choices=["center", "first", "segments", "smart"], default="center",
                        help="Crop mode to use for processing audio files longer than 3 seconds.")
    parser.add_argument("--fmin",        type=float, default=0.0)
    parser.add_argument("--fmax",        type=float, default=15000.0)
    parser.add_argument("--audio_speed", type=float, default=1.0)
    parser.add_argument("--overlap",     type=float, default=0.0)
    parser.add_argument("--min_len",     type=float, default=1.0)
    parser.add_argument("--separate_files", dest="separate_files", action="store_true",
                        help="Save each class folder in a separate .npz file.")
    parser.add_argument("--combined_file", dest="separate_files", action="store_false",
                        help="Save all classes in a single combined .npz file.")
    parser.set_defaults(separate_files=None)
    args = parser.parse_args()

    audio_input = args.audio_dir
    if not os.path.isdir(audio_input):
        print(f"ERROR: {audio_input} is not a valid directory.")
        sys.exit(1)

    # ── Output path ───────────────────────────────────────────────────────────
    if args.output_npz:
        output_path = args.output_npz
    else:
        folder_name = os.path.basename(os.path.normpath(audio_input)) or "extracted_features"
        output_path = os.path.join(audio_input, f"{folder_name}.npz")

    # ── Discover labels (no birdnet_analyzer dependency) ─────────────────────
    all_folders = sorted(
        f for f in os.listdir(audio_input)
        if os.path.isdir(os.path.join(audio_input, f))
    )
    
    has_subfolders = len(all_folders) > 0
    
    if not has_subfolders:
        class_name = os.path.basename(os.path.normpath(audio_input))
        valid_labels = [class_name]
        print(f"No sub-folders found. Treating directory itself as single class: {valid_labels}")
    else:
        NON_EVENT_CLASSES = ["noise", "other", "background", "silence"]
        valid_labels = [f for f in all_folders if f.lower() not in NON_EVENT_CLASSES and not f.startswith("-")]
        print(f"Found {len(valid_labels)} target label(s): {valid_labels}")

    # Ask the user if multiple classes are found and option is not provided via command line
    separate_files = args.separate_files
    if has_subfolders and len(valid_labels) > 1 and separate_files is None:
        print("\nMultiple class folders found.")
        print("How would you like to save the extracted features?")
        print("  [1] Separate NPZ file for each class (default)")
        print("  [2] Single combined NPZ file")
        try:
            choice = input("Enter choice (1 or 2, default=1): ").strip()
            if choice == "2":
                separate_files = False
            else:
                separate_files = True
        except (KeyboardInterrupt, EOFError):
            print("\nNo choice entered. Defaulting to separate NPZ files.")
            separate_files = True
    elif separate_files is None:
        separate_files = True

    # ── Load model ────────────────────────────────────────────────────────────
    embed_fn = load_pbmodel(args.model_path)

    # ── Extract embeddings ────────────────────────────────────────────────────
    x_train, y_train = [], []

    if not has_subfolders:
        class_name = valid_labels[0]
        label_vector = np.array([1.0], dtype="float32")
        files = sorted([
            os.path.join(audio_input, f)
            for f in os.listdir(audio_input)
            if not f.startswith(".")
            and f.rsplit(".", 1)[-1].lower() in ALLOWED_FILETYPES
        ])

        print(f"\nProcessing '{class_name}' ({len(files)} file(s)) directly from input directory...")

        with tqdm.tqdm(total=len(files), unit="f") as pbar:
            for fpath in files:
                duration = SIG_LENGTH if args.crop_mode == "first" else None
                sig, rate = open_audio(fpath, args.fmin, args.fmax, args.audio_speed, duration)
                if sig is None:
                    print(f"  [WARN] Could not open: {fpath}")
                    pbar.update(1)
                    continue

                chunks = split_audio(sig, rate, args.crop_mode, args.overlap, args.min_len)
                for chunk in chunks:
                    try:
                        emb = get_embedding(embed_fn, chunk)  # shape (1024,)
                        x_train.append(emb)
                        y_train.append(label_vector.copy())
                    except Exception as e:
                        print(f"  [WARN] Embedding failed for chunk in {fpath}: {e}")
                pbar.update(1)
                
    elif separate_files:
        # Multiple class folders, separate files mode
        # Each folder gets its own clean NPZ file. Combining happens later via 02_combine_npz.py.
        
        # Determine output directory
        if args.output_npz:
            if args.output_npz.endswith(".npz"):
                out_dir = os.path.dirname(args.output_npz)
            else:
                out_dir = args.output_npz
        else:
            out_dir = audio_input
        os.makedirs(out_dir, exist_ok=True)
        
        for folder in all_folders:
            folder_path = os.path.join(audio_input, folder)
            files = sorted([
                os.path.join(folder_path, f)
                for f in os.listdir(folder_path)
                if not f.startswith(".")
                and f.rsplit(".", 1)[-1].lower() in ALLOWED_FILETYPES
            ])
            
            if not files:
                print(f"\n[Skip] '{folder}' has no audio files.")
                continue

            # Determine label for this folder
            is_noise = folder.lower() in NON_EVENT_CLASSES
            is_negative = folder.startswith("-")
            
            if is_noise:
                label_name = folder
                label_vector = np.array([0.0], dtype="float32")
            elif is_negative:
                label_name = folder[1:]  # strip leading dash
                label_vector = np.array([-1.0], dtype="float32")
            else:
                label_name = folder
                label_vector = np.array([1.0], dtype="float32")
            
            print(f"\nProcessing '{folder}' ({len(files)} file(s))...")
            x_class = []
            y_class = []
            
            with tqdm.tqdm(total=len(files), unit="f") as pbar:
                for fpath in files:
                    duration = SIG_LENGTH if args.crop_mode == "first" else None
                    sig, rate = open_audio(fpath, args.fmin, args.fmax, args.audio_speed, duration)
                    if sig is None:
                        print(f"  [WARN] Could not open: {fpath}")
                        pbar.update(1)
                        continue
                    chunks = split_audio(sig, rate, args.crop_mode, args.overlap, args.min_len)
                    for chunk in chunks:
                        try:
                            emb = get_embedding(embed_fn, chunk)
                            x_class.append(emb)
                            y_class.append(label_vector.copy())
                        except Exception as e:
                            print(f"  [WARN] Embedding failed for chunk in {fpath}: {e}")
                    pbar.update(1)
            
            if not x_class:
                print(f"  WARNING: No samples extracted for '{folder}'. Skipping.")
                continue
            
            class_out_path = os.path.join(out_dir, f"{label_name}.npz")
            np.savez(
                class_out_path,
                x_train=np.array(x_class, dtype="float32"),
                y_train=np.array(y_class, dtype="float32"),
                x_test=np.array([]),
                y_test=np.array([]),
                labels=np.array([label_name], dtype=object),
                binary_classification=False,
                multi_label=False,
                fmin=args.fmin,
                fmax=args.fmax,
                audio_speed=args.audio_speed,
                crop_mode=args.crop_mode,
                overlap=args.overlap,
            )
            print(f"  Saved -> {class_out_path} ({len(x_class)} samples)")
            
        print("\nAll separate classes processed.")
        sys.exit(0)
        
    else:
        # Multiple class folders, single combined file mode (existing logic)
        for folder in all_folders:
            label_vector = np.zeros(len(valid_labels), dtype="float32")
            if folder in valid_labels:
                label_vector[valid_labels.index(folder)] = 1.0
            elif folder.startswith("-") and folder[1:] in valid_labels:
                label_vector[valid_labels.index(folder[1:])] = -1.0
            # If folder is 'Noise'/'Background', it remains all zeros.

            folder_path = os.path.join(audio_input, folder)
            files = sorted([
                os.path.join(folder_path, f)
                for f in os.listdir(folder_path)
                if not f.startswith(".")
                and f.rsplit(".", 1)[-1].lower() in ALLOWED_FILETYPES
            ])

            print(f"\nProcessing '{folder}' ({len(files)} file(s))...")

            with tqdm.tqdm(total=len(files), unit="f") as pbar:
                for fpath in files:
                    duration = SIG_LENGTH if args.crop_mode == "first" else None
                    sig, rate = open_audio(fpath, args.fmin, args.fmax, args.audio_speed, duration)
                    if sig is None:
                        print(f"  [WARN] Could not open: {fpath}")
                        pbar.update(1)
                        continue

                    chunks = split_audio(sig, rate, args.crop_mode, args.overlap, args.min_len)
                    for chunk in chunks:
                        try:
                            emb = get_embedding(embed_fn, chunk)  # shape (1024,)
                            x_train.append(emb)
                            y_train.append(label_vector.copy())
                        except Exception as e:
                            print(f"  [WARN] Embedding failed for chunk in {fpath}: {e}")
                    pbar.update(1)

    if not x_train:
        print("ERROR: No samples extracted. Check your audio files.")
        sys.exit(1)

    x_train = np.array(x_train, dtype="float32")
    y_train = np.array(y_train, dtype="float32")
    print(f"\nExtraction complete. Total samples: {len(x_train)}, embedding shape: {x_train.shape}")

    # ── Save NPZ ──────────────────────────────────────────────────────────────
    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    np.savez(
        output_path,
        x_train=x_train,
        y_train=y_train,
        x_test=np.array([]),
        y_test=np.array([]),
        labels=np.array(valid_labels, dtype=object),
        binary_classification=False,
        multi_label=False,
        fmin=args.fmin,
        fmax=args.fmax,
        audio_speed=args.audio_speed,
        crop_mode=args.crop_mode,
        overlap=args.overlap,
    )
    print(f"Saved -> {output_path}")


if __name__ == "__main__":
    main()
