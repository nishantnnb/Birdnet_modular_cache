---------------------------------------------------------
BirdNET Modular Cache Builder - Help Manual
---------------------------------------------------------

This application is designed to efficiently extract, combine, 
and split BirdNET feature embeddings (NPZ files) from audio 
recordings without relying on the full BirdNET library.

The interface is divided into three separate tabs depending 
on the stage of your workflow.

---------------------------------------------------------
TAB 1: Create cache (NPZ)
---------------------------------------------------------
This tab processes your raw audio files (.wav, .flac, .mp3, etc.) 
and passes them through the BirdNET deep learning model to 
extract 1024-dimensional feature embeddings. It saves these 
embeddings as mathematical arrays inside .npz files.

[Settings]
• Crop Mode: Determines how audio files longer than 3 seconds are handled.
   - Center: Extracts a single 3-second chunk precisely from the middle of the audio file.
   - First: Extracts only the very first 3 seconds of the audio file.
   - Segments: Slices the entire audio file into multiple consecutive 3-second chunks.
   - Smart: Analyzes the audio for high-energy peaks and saves only the 3-second chunks containing the loudest sounds (ideal for isolating bird calls).
• Fmin / Fmax: Bandpass filter frequencies in Hz. Fmin (default 0) is the lowest frequency allowed, and Fmax (default 15000) is the highest frequency allowed.
• Audio Speed: Adjusts the playback speed of the audio before processing (default 1.0).
• Overlap: Determines how many seconds consecutive chunks overlap. This is only enabled when using "Segments" or "Smart" crop modes. (Default 0.0)
• Reset Defaults: Quickly resets the above settings back to their factory default values.

[Paths]
• BirdNET Model Path: The directory where your actual BirdNET model (e.g., BirdNET_GLOBAL_6K_V2.4_Model) is located.
• Input Audio Directory: The main folder containing your audio files. This folder should ideally contain sub-folders named after the bird species (e.g., "Alexandrine Parakeet").
• Output NPZ Directory: The folder where the newly created .npz cache files will be saved.

[Options]
• Combined File: Combines all extracted species into one single master .npz file.
• Separate Files: Creates a distinct .npz file for every sub-folder it finds. (Default)

---------------------------------------------------------
TAB 2: Combine caches (NPZs)
---------------------------------------------------------
This tab takes a folder containing multiple individual .npz files 
(e.g., one file per bird species) and mathematically merges 
them into a single, massive master .npz file. This is highly 
useful when feeding data into a machine learning classifier.

[Paths]
• Input NPZ Directory: The folder containing your separate .npz files.
• Output NPZ Directory: The folder where the new master combined .npz file will be saved. 
  (Note: The new file will automatically be named "master_combined.npz").

---------------------------------------------------------
TAB 3: Split cache (NPZ)
---------------------------------------------------------
This tab does the exact opposite of Tab 2. It takes a master 
combined .npz file, analyzes the internal data labels, and 
slices the matrix back out into individual, species-specific 
.npz files.

[Paths]
• Master NPZ File: The exact path to the combined .npz file you want to split.
• Output NPZ Directory: The folder where all the newly separated .npz files will be exported.

---------------------------------------------------------
General Information
---------------------------------------------------------
• Log Files: Whenever you successfully run a task in Tab 1, a detailed log file is generated in the application folder detailing the exact settings and timestamps of the run.
• Background Processing: Pressing "Start" on any tab runs the heavy processing in the background. Your interface will remain responsive, and live progress will stream directly into the black console window at the bottom of the app.
• Stopping: Pressing the red "Stop" button will cleanly terminate the background process. Any files currently being written may be incomplete and should be deleted.
