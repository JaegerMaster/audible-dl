# Audible Downloader & Decrypter

A command-line tool to interactively browse your Audible library, download audiobooks, decrypt them to the standard `.m4b` format, and clean up the intermediate files.

This script acts as a user-friendly wrapper around the powerful `audible-cli` and `ffmpeg` tools.

## Features

-   **Interactive Library Browsing:** Navigate your entire Audible library in a clean, paginated table right in your terminal.
-   **Configurable Sorting:** View your library with the newest or oldest books first.
-   **Direct Download:** If you already know the book's ASIN, you can download it directly without browsing.
-   **Automatic Decryption:** Converts the proprietary `.aaxc` format to a standard, DRM-free `.m4b` audiobook file.
-   **Metadata Included:** Chapters, cover art, and other metadata are preserved in the final file.
-   **Automatic Cleanup:** All intermediate files (`.aaxc`, `.voucher`, `.jpg`, `.json`) are deleted after a successful conversion, keeping your download directory clean.
-   **External Configuration:** Easy-to-edit `config.ini` file for all user settings.
-   **Profile Support:** Works with named profiles from your `audible-cli` setup.

## Prerequisites

Before you begin, you must have the following software installed and configured on your system.

1.  **Python 3.8+**
    -   You can check your version with `python3 --version`.

2.  **FFmpeg**
    -   This is a critical dependency for decrypting and converting the audio files.
    -   **On macOS (using Homebrew):**
        ```shell
        brew install ffmpeg
        ```
    -   **On Debian/Ubuntu:**
        ```shell
        sudo apt update && sudo apt install ffmpeg
        ```
    -   **On Windows (using Chocolatey):**
        ```shell
        choco install ffmpeg
        ```

3.  **audible-cli**
    -   This is the underlying tool used to communicate with Audible's servers.
    -   Install it via pip:
        ```shell
        pip install audible-cli
        ```

## Installation

1.  **Clone or Download:**
    -   Download the files (`audible_downloader.py`, `config.ini.example`, `requirements.txt`) from this repository and place them in a single directory.

2.  **Install Python Dependencies:**
    -   Navigate to the directory in your terminal and run:
        ```shell
        pip install -r requirements.txt
        ```

## Configuration

1.  **Configure `audible-cli` (Crucial Step):**
    -   You must authenticate `audible-cli` with your Audible account. Run the quickstart command and follow the on-screen instructions. It will likely open a browser for you to log in.
        ```shell
        audible quickstart
        ```
    -   If you have multiple Audible accounts, you can create named profiles. This script supports them via the `--profile` flag.

2.  **Configure the Script:**
    -   Make a copy of the example configuration file:
        ```shell
        cp config.ini.example config.ini
        ```
    -   Open `config.ini` in a text editor and customize the settings:
        -   `output_dir`: The default folder where your final `.m4b` files will be saved.
        -   `page_size`: How many books to show on each page in the library browser.
        -   `default_sort`: Set to `newest_first` or `oldest_first`.

## Usage

Make sure the script is executable (you only need to do this once):
```shell
chmod +x audible_downloader.py
```

### Interactive Mode

To start the interactive menu, simply run the script without any options:

```shell
./audible_downloader.py
```

You will be presented with a choice to either browse your library or download a book directly by its ASIN.

-   **Library Browser Controls:**
    -   `Enter a book #`: Downloads the corresponding book.
    -   `n`: Go to the next page of results.
    -   `p`: Go to the previous page.
    -   `q`: Quit the library browser.

### Direct Download Mode

If you already know a book's ASIN, you can download it directly:

```shell
./audible_downloader.py --asin B002V5A12Y
```

### Command-Line Options

```
Usage: audible_downloader.py [OPTIONS]

Options:
  -a, --asin TEXT     The ASIN of the book to download directly.
  --profile TEXT      The audible-cli profile to use.
  -k, --keep-files    Keep intermediate files after decryption.
  --version           Show the version and exit.
  -h, --help          Show this message and exit.
```

## Troubleshooting

-   **Error: "Could not get library data" or "command failed"**
    -   This is almost always an authentication issue with `audible-cli`. Your login token may have expired.
    -   **Solution:** Run `audible quickstart` again to refresh your credentials.

-   **"rich" or "click" module not found**
    -   You haven't installed the Python dependencies.
    -   **Solution:** Run `pip install -r requirements.txt`.

-   **"ffmpeg: command not found"**
    -   FFmpeg is not installed or is not in your system's PATH.
    -   **Solution:** Follow the installation instructions for FFmpeg in the [Prerequisites](#prerequisites) section.
