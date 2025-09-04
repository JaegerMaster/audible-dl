#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Audible Downloader & Decrypter

A command-line tool to interactively browse your Audible library,
download audiobooks, decrypt them to a standard .m4b format, and
clean up the intermediate files.
"""

import configparser
import json
import pathlib
import re
import subprocess
import sys
from typing import Optional, List, Dict

import click

# --- SCRIPT METADATA (FIX) ---
# This section was missing, causing the NameError.
__version__ = "2.0.1"
__author__ = "JaegerMaster & Gemini"
# -----------------------------

# --- Configuration ---
def get_config() -> configparser.ConfigParser:
    """Reads and returns the configuration from config.ini."""
    config = configparser.ConfigParser()
    config_file = pathlib.Path(__file__).parent / "config.ini"
    if not config_file.exists():
        click.secho(f"Error: Configuration file not found at {config_file}", fg="red")
        click.echo("Please copy 'config.ini.example' to 'config.ini' and fill it out.")
        sys.exit(1)
    config.read(config_file)
    return config

# --- Core Functions ---
def validate_asin(asin: str) -> bool:
    """Validate ASIN format."""
    return len(asin) == 10 and asin.startswith('B')

def run_command(cmd: List[str]) -> subprocess.CompletedProcess:
    """Runs a command and captures its output."""
    return subprocess.run(cmd, capture_output=True, text=True, check=True)

def download_audiobook(asin: str, output_dir: pathlib.Path, profile: Optional[str]) -> tuple[bool, Optional[str]]:
    """Download audiobook using audible-cli."""
    try:
        cmd = ['audible']
        if profile:
            cmd.extend(['--profile', profile])
        cmd.extend([
            'download', '--asin', asin, '--output-dir', str(output_dir),
            '--aaxc', '--quality', 'best', '--resolve-podcasts',
            '--chapter', '--cover', '--no-confirm'
        ])
        run_command(cmd)
        return True, None
    except subprocess.CalledProcessError as e:
        return False, f"Download failed:\n{e.stderr}"

def get_aaxc_credentials(voucher_file: pathlib.Path) -> tuple[str, str]:
    """Extract decryption credentials from voucher file."""
    if not voucher_file.exists():
        raise click.ClickException(f"Voucher file not found: {voucher_file}")
    
    voucher_data = json.loads(voucher_file.read_text())
    content_license = voucher_data.get('content_license', {}).get('license_response', {})
    key, iv = content_license.get('key'), content_license.get('iv')
    if not key or not iv:
        raise click.ClickException("Could not find key/iv in voucher file")
    return key, iv

def decrypt_audiobook(input_file: pathlib.Path, output_dir: pathlib.Path, credentials: tuple[str, str]) -> tuple[bool, Optional[pathlib.Path]]:
    """Decrypt audiobook using ffmpeg."""
    key, iv = credentials
    output_file = output_dir / input_file.with_suffix('.m4b').name
    try:
        cmd = [
            'ffmpeg', '-y', '-audible_key', key, '-audible_iv', iv, '-i', str(input_file),
            '-map', '0:a', '-map', '0:t?', '-c', 'copy', '-f', 'mp4', str(output_file)
        ]
        process = subprocess.run(cmd, capture_output=True, text=True)
        if process.returncode != 0:
            click.secho(f"FFmpeg error: {process.stderr}", fg='red')
            return False, None
        if not output_file.exists() or output_file.stat().st_size == 0:
            click.secho("Error: FFmpeg created an empty output file.", fg='red')
            return False, None
        return True, output_file
    except Exception as e:
        click.secho(f"Decryption error: {str(e)}", fg='red')
        return False, None

def find_aaxc_file(directory: pathlib.Path) -> Optional[pathlib.Path]:
    """Find the first AAXC file in the directory."""
    return next(iter(directory.glob("*.aaxc")), None)

def get_related_files(aaxc_file: pathlib.Path) -> List[pathlib.Path]:
    """
    Robustly finds all related files for cleanup based on the AAXC filename.
    """
    directory = aaxc_file.parent
    stem = aaxc_file.stem
    
    match = re.search(r'(-AAX.*|-LC.*)$', stem)
    if not match:
        click.secho(f"Warning: Could not determine base name from '{stem}'. Cleanup may be incomplete.", fg='yellow')
        base_name = stem
    else:
        base_name = stem[:match.start()]

    related = [
        aaxc_file,
        aaxc_file.with_suffix('.voucher'),
        directory / f"{base_name}-chapters.json"
    ]
    related.extend(directory.glob(f"{base_name}*.[jJ][pP][gG]"))
    related.extend(directory.glob(f"{base_name}*.[jJ][pP][eE][gG]"))
    
    return [f for f in related if f.exists()]

def cleanup_files(files_to_remove: List[pathlib.Path]):
    """Clean up temporary files."""
    click.echo("\nCleaning up intermediate files...")
    for file in files_to_remove:
        try:
            file.unlink()
            click.echo(f"Removed: {file.name}")
        except Exception as e:
            click.secho(f"Warning: Could not remove {file.name}: {str(e)}", fg='yellow')

def verify_decrypted_file(file_path: pathlib.Path) -> bool:
    """Verify the decrypted file is a valid media file."""
    try:
        cmd = ['ffmpeg', '-v', 'error', '-i', str(file_path), '-f', 'null', '-']
        return subprocess.run(cmd, capture_output=True, text=True).returncode == 0
    except Exception:
        return False

def parse_library_list_output(text_output: str) -> List[Dict]:
    """Converts the 'ASIN: Author: Title' text format into a structured list."""
    library_data = []
    for line in text_output.strip().split('\n'):
        if not line: continue
        try:
            asin, author, title = [part.strip() for part in line.split(':', 2)]
            library_data.append({'asin': asin, 'title': title, 'authors': [{'name': author}]})
        except ValueError:
            click.secho(f"Warning: Could not parse library line: '{line}'", fg='yellow')
    return library_data

def process_book(asin: str, output_dir: pathlib.Path, keep_files: bool, profile: Optional[str]):
    """Main logic to download, decrypt, and clean up a single book."""
    if not validate_asin(asin):
        click.secho(f"Error: Invalid ASIN format: {asin}", fg='red'); sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"\nDownloading audiobook with ASIN: {asin}")
    
    success, error = download_audiobook(asin, output_dir, profile)
    if not success:
        click.secho(f"Error: {error}", fg='red'); sys.exit(1)

    # Re-scan for the aaxc file after download
    aaxc_file = find_aaxc_file(output_dir)
    if not aaxc_file:
        click.secho("Error: No AAXC file found in output directory after download.", fg='red'); sys.exit(1)
    click.echo(f"Found AAXC file: {aaxc_file.name}")

    try:
        credentials = get_aaxc_credentials(aaxc_file.with_suffix('.voucher'))
        click.echo("Successfully extracted decryption credentials.")
    except Exception as e:
        click.secho(f"Error: {str(e)}", fg='red'); sys.exit(1)

    click.echo("\nDecrypting audiobook...")
    success, output_file = decrypt_audiobook(aaxc_file, output_dir, credentials)
    if not success or not output_file:
        click.secho("Error: Failed to decrypt audiobook.", fg='red'); sys.exit(1)

    click.echo("\nVerifying decrypted file...")
    if not verify_decrypted_file(output_file):
        click.secho("Error: Decrypted file verification failed.", fg='red')
        if output_file.exists(): output_file.unlink()
        sys.exit(1)

    if not keep_files:
        cleanup_files(get_related_files(aaxc_file))
    else:
        click.echo("\nKeeping all intermediate files as requested.")

    click.secho("\nProcess completed successfully!", fg='green')
    click.echo(f"Decrypted audiobook: {output_file.name}")
    if output_file.exists():
        click.echo(f"File size: {output_file.stat().st_size / (1024 * 1024):.2f} MB")

def browse_and_download_mode(output_dir: pathlib.Path, keep_files: bool, profile: Optional[str], config: configparser.ConfigParser):
    """Fetches library, displays it with pagination, and lets the user choose a book."""
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        click.secho("Error: 'rich' library is required. Install with 'pip install rich'", fg='red'); sys.exit(1)

    console = Console()
    with console.status("[bold green]Fetching your Audible library..."):
        try:
            lib_cmd = ['audible']
            if profile:
                lib_cmd.extend(['--profile', profile])
            lib_cmd.extend(['library', 'list'])
            
            result = run_command(lib_cmd)
            library_data = parse_library_list_output(result.stdout)
        except subprocess.CalledProcessError as e:
            console.print(f"[bold red]Error: The 'audible library list' command failed.[/bold red]\n[yellow]{e.stderr}[/yellow]"); sys.exit(1)

    if not library_data:
        console.print("[bold red]Error: No books were found in your library output.[/bold red]"); sys.exit(1)
    
    sort_order = config.get('Settings', 'default_sort', fallback='newest_first')
    if click.confirm(f"Sort by '{sort_order.replace('_', ' ')}'?", default=True):
        if sort_order == 'newest_first':
            library_data.reverse()
    else:
        current_sort = 'oldest_first' if sort_order == 'newest_first' else 'newest_first'
        if current_sort == 'newest_first':
            library_data.reverse()
        click.echo(f"Sorting by {current_sort.replace('_', ' ')}.")

    page_size = config.getint('Settings', 'page_size', fallback=10)
    page_num = 0
    while True:
        start_index = page_num * page_size
        end_index = start_index + page_size
        page_data = library_data[start_index:end_index]
        
        if not page_data:
            click.echo("No more books."); page_num -= 1; continue

        table = Table(title=f"Your Audible Library - Page {page_num + 1} of {-(-len(library_data) // page_size)}")
        table.add_column("#", style="cyan"); table.add_column("Title", style="magenta")
        table.add_column("Author", style="green"); table.add_column("ASIN", style="bold blue")
        for i, item in enumerate(page_data, start=start_index):
            authors = ', '.join([a['name'] for a in item.get('authors', [])])
            table.add_row(str(i + 1), item.get('title', 'N/A'), authors, item.get('asin', 'N/A'))
        console.print(table)
        
        user_input = click.prompt("Enter book # to download, (n)ext, (p)revious, or (q)uit", type=str, default="").lower()

        if user_input.isdigit():
            choice = int(user_input)
            if 1 <= choice <= len(library_data):
                book = library_data[choice - 1]
                click.echo(f"\nYou selected: '{book['title']}' (ASIN: {book['asin']})")
                process_book(book['asin'], output_dir, keep_files, profile)
                break
            else:
                click.secho("Invalid book number.", fg='yellow')
        elif user_input == 'n':
            if end_index < len(library_data): page_num += 1
            else: click.echo("Already on the last page.")
        elif user_input == 'p':
            if page_num > 0: page_num -= 1
            else: click.echo("Already on the first page.")
        elif user_input == 'q':
            click.echo("Exiting library browser."); break
        else:
            click.secho("Invalid input.", fg='yellow')

@click.command()
@click.option('--asin', '-a', help='The ASIN of the book to download directly.')
@click.option('--profile', help='The audible-cli profile to use.')
@click.option('--keep-files', '-k', is_flag=True, help='Keep intermediate files after decryption.')
@click.version_option(version=__version__)
def main(asin: Optional[str], profile: Optional[str], keep_files: bool):
    """
    A tool to download and decrypt your Audible audiobooks.

    Run without options for an interactive menu.
    """
    config = get_config()
    settings = config['Settings']
    output_dir_str = settings.get('output_dir', '~/Downloads/audiobooks')
    output_dir = pathlib.Path(output_dir_str).expanduser()

    click.secho(f"Audible Downloader v{__version__}", fg='cyan')
    if profile: click.secho(f"Using audible-cli profile: {profile}", fg='green')

    if asin:
        process_book(asin, output_dir, keep_files, profile)
    else:
        click.echo("\nChoose an option:\n1. Browse library\n2. Download by ASIN")
        choice = click.prompt("Enter your choice", type=click.Choice(['1', '2']))
        if choice == '1':
            browse_and_download_mode(output_dir, keep_files, profile, config)
        elif choice == '2':
            asin_input = click.prompt("Please enter the book's ASIN")
            process_book(asin_input, output_dir, keep_files, profile)

if __name__ == '__main__':
    main()
