# Installation & Setup Guide

## 1. Prerequisites
Ensure you have **Python 3.11** installed on your Windows machine. When installing Python, make sure to check the box that says "Add Python to PATH".

## 2. Install Dependencies
Download or clone this repository to your computer. Open your command prompt (or PowerShell), navigate to the `Codes` directory, and run the following command to install the required libraries:

```bash
pip install -r requirements.txt
```
*(Note: This uses the exact, tested versions of TensorFlow and NumPy to ensure maximum stability.)*

## 3. Download the BirdNET Model
This application requires the official BirdNET pre-trained neural network model to extract features.
1. Download the **BirdNET V2.4 Model** (specifically the `BirdNET_GLOBAL_6K_V2.4_Model` folder that contains the `saved_model.pb` file and the `variables` folder).
2. Inside your main project directory, locate or create a folder named `model`.
3. Place the entire downloaded model folder inside this `model` directory.

## 4. Run the Application
Once the dependencies are installed and the model is in place, you can launch the graphical interface by double-clicking the main script, or by running this command in your terminal from the `Codes` folder:

```bash
py -3.11 birdnet_modular_cache.py
```
