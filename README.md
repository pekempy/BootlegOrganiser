# Bootleg Organiser

Bootleg Organiser is a Python script designed to help you organise your local files, update Encora, and ensure that your local data is kept up to date with Encora.

## Features

- File Organisation: Bootleg Organiser scans your specified directories and organises your files based on customizable rules.
- Encora Update: Bootleg Organiser automatically updates your Encora formats with the latest files from your local storage.
- Data Synchronization: Bootleg Organiser ensures that your local data is always synchronized with Encora, keeping everything up to date.

## Installation

1. Clone the Bootleg Organiser repository to your local machine.
2. Install the required dependencies by running `pip install -r requirements.txt`.
3. Configure the script by copying `.env.example` to `.env` and editing the `.env` file with your settings.
4. Run the script using `python full-organise.py`.

## Usage

1. Specify the directories you want to organise in the `.env` file.
2. Customize the file organisation rules according to your preferences.
3. Run the script to start organising your files and updating Encora.

## Configuration

Bootleg Organiser uses a `.env` file for configuration. You can customize various settings, including:

- Directories to organise
- File organisation rules
- Encora API credentials
- Synchronization options

Please refer to the comments in the `.env.example` file for detailed instructions on how to configure each setting.

## Running the Scripts

- **Full Organise**: Run `python full-organise.py` to perform a complete organisation of your files, download subtitles, and update your formats. It will also update any Cast.txt you have with corrected data from Encora.
- **Add Formats**: Run `python format-organise.py` to handle the format step, which updates your Encora formats with your local files.
- **Download Subtitles**: Run `python subtitle-download.py` to download subtitles for the specified directories.
