"""
spotDL Interactive Launcher
One script from first launch to music on disk.
"""

import json
import os
import sys
import shutil
import subprocess
import threading
import time
from pathlib import Path


# ── Config ────────────────────────────────────────────────────────────
MUSIC_DIR = "Music"
FORMAT = "mp3"
BITRATE = "320k"
OUTPUT_TEMPLATE = "{artists} - {title}.{output-ext}"
WHEEL_NAME = "spotdl-4.4.3-py3-none-any.whl"
MIN_PYTHON = (3, 10)
MAX_PYTHON = (3, 13)  # 3.14 has mutagen compat issues

# Spotify API credentials (built into the app — no user config needed)
SPOTIFY_CLIENT_ID = "32dd9efac2c14a8198d38deafceee619"
SPOTIFY_CLIENT_SECRET = "4c8e8a7269ce46489ddac305d6963bea"

# Tuned settings baked in
BUNDLED_CONFIG = {
    "client_id": SPOTIFY_CLIENT_ID,
    "client_secret": SPOTIFY_CLIENT_SECRET,
    "user_auth": False,
    "headless": False,
    "max_retries": 20,
    "no_cache": False,
    "use_cache_file": False,
    "audio_providers": ["youtube-music"],
    "lyrics_providers": ["genius", "azlyrics", "musixmatch"],
    "playlist_numbering": False,
    "output": OUTPUT_TEMPLATE,
    "overwrite": "skip",
    "format": FORMAT,
    "bitrate": BITRATE,
    "threads": 4,
    "filter_results": True,
    "print_errors": False,
    "sponsor_block": False,
    "load_config": True,
    "log_level": "INFO",
    "simple_tui": False,
    "fetch_albums": False,
    "id3_separator": "/",
    "ytm_data": False,
    "add_unavailable": False,
    "generate_lrc": False,
    "force_update_metadata": False,
    "only_verified_results": False,
    "sync_without_deleting": False,
    "skip_explicit": False,
    "redownload": False,
    "skip_album_art": False,
    "create_skip_file": False,
    "respect_skip_file": False,
    "sync_remove_lrc": False,
    "spotify_sleep": 0.5,
    "download_sleep": 1.0,
}


# ── Helpers ───────────────────────────────────────────────────────────

def clear():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    print()
    print("=" * 52)
    print("       spotDL  -  Spotify Music Downloader")
    print("=" * 52)
    print()


def pause(msg="  Press Enter to continue..."):
    input(msg)


def script_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def count_songs_in_source(source_args):
    """Run spotdl save to count how many songs are in a source (saved, playlist, etc.)."""
    tmp = os.path.join(script_dir(), ".count_check.spotdl")
    cmd = [sys.executable, "-u", "-m", "spotdl", "save"] + source_args + [
        "--save-file", tmp, "--simple-tui",
    ]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    try:
        proc = subprocess.run(cmd, capture_output=True, env=env, timeout=300)
        if proc.returncode == 0 and os.path.exists(tmp):
            with open(tmp, "r") as f:
                data = json.load(f)
            return len(data) if isinstance(data, list) else 0
    except Exception:
        pass
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return 0


def run_spotdl(args, cwd=None, track_progress=False, total_songs=0):
    """Run spotdl with the given arguments, streaming output live.
    If track_progress=True, monitors the cwd for new audio files
    and prints a running count.
    """
    cmd = [sys.executable, "-u", "-m", "spotdl"] + args
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    print()
    print("  " + "-" * 48)

    stop_event = threading.Event()
    progress_thread = None

    if track_progress and cwd:
        baseline = count_music_files(cwd)

        def _format_elapsed(seconds):
            m, s = divmod(int(seconds), 60)
            h, m = divmod(m, 60)
            if h > 0:
                return f"{h}h {m}m"
            elif m > 0:
                return f"{m}m {s}s"
            return f"{s}s"

        def _progress_watcher():
            last_msg = ""
            t0 = time.time()
            total = total_songs
            while not stop_event.is_set():
                elapsed = _format_elapsed(time.time() - t0)
                done = count_music_files(cwd) - baseline
                active = count_temp_files(cwd)
                if done > 0 or active > 0:
                    parts = []
                    if total > 0:
                        parts.append(f"{done}/{total} downloaded")
                    else:
                        parts.append(f"{done} downloaded")
                    if active > 0:
                        parts.append(f"{active} in progress")
                    msg = f"[{', '.join(parts)} | {elapsed}]"
                else:
                    msg = f"Fetching metadata... ({elapsed})"
                if msg != last_msg:
                    print(f"\r  {msg}" + " " * 10, end="", flush=True)
                    last_msg = msg
                stop_event.wait(2)
            # Final count
            elapsed = _format_elapsed(time.time() - t0)
            final = count_music_files(cwd) - baseline
            if total > 0:
                print(f"\r  [{final}/{total} downloaded | {elapsed}]" + " " * 15, flush=True)
            elif final > 0:
                print(f"\r  [{final} downloaded | {elapsed}]" + " " * 15, flush=True)
            print(flush=True)

        progress_thread = threading.Thread(target=_progress_watcher, daemon=True)
        progress_thread.start()

    try:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stderr=subprocess.PIPE)
        _, stderr_bytes = proc.communicate()
        stop_event.set()
        if progress_thread:
            progress_thread.join(timeout=3)
        print("  " + "-" * 48)
        errors = stderr_bytes.decode("utf-8", errors="replace").strip() if stderr_bytes else ""
        if proc.returncode == 0:
            return (True, "")
        return (False, errors)
    except KeyboardInterrupt:
        stop_event.set()
        if progress_thread:
            progress_thread.join(timeout=3)
        print("\n\n  Download interrupted.")
        print("  " + "-" * 48)
        return (False, "Interrupted by user")
    except FileNotFoundError:
        stop_event.set()
        print("  [ERROR] spotdl not found. Choose Setup from menu.")
        print("  " + "-" * 48)
        return (False, "spotdl not found")


def ask_threads(default=4):
    """Prompt user for concurrent download count."""
    print(f"  Simultaneous downloads (1-16, default {default}): ", end="", flush=True)
    raw = input().strip()
    if not raw:
        return default
    try:
        n = int(raw)
        return max(1, min(16, n))
    except ValueError:
        return default


def ensure_music_dir() -> str:
    music = os.path.join(script_dir(), MUSIC_DIR)
    os.makedirs(music, exist_ok=True)
    return music


def count_music_files(directory):
    exts = {".mp3", ".flac", ".ogg", ".opus", ".m4a", ".wav"}
    if not os.path.isdir(directory):
        return 0
    return sum(1 for f in os.listdir(directory) if os.path.splitext(f)[1].lower() in exts)


def count_temp_files(directory):
    exts = {".tmp", ".part", ".temp", ".ytdl"}
    if not os.path.isdir(directory):
        return 0
    return sum(1 for f in os.listdir(directory) if os.path.splitext(f)[1].lower() in exts)


# ── Status checks ────────────────────────────────────────────────────

def python_version_ok():
    """Check Python version is in supported range."""
    v = sys.version_info[:2]
    return MIN_PYTHON <= v <= MAX_PYTHON


def python_version_str():
    return f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}"


def spotdl_installed():
    try:
        r = subprocess.run(
            [sys.executable, "-m", "spotdl", "--version"],
            capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0
    except Exception:
        return False


def ffmpeg_available():
    # Check PATH first
    if shutil.which("ffmpeg") is not None:
        return True
    # Check where spotdl typically downloads ffmpeg on Windows
    check_paths = [
        Path.home() / ".spotdl" / "ffmpeg.exe",
        Path.home() / ".spotdl" / "ffmpeg",
        Path(os.environ.get("LOCALAPPDATA", "")) / "spotdl" / "ffmpeg.exe",
        Path(script_dir()) / "ffmpeg.exe",
        Path(script_dir()) / ".runtime" / "ffmpeg.exe",
    ]
    for p in check_paths:
        try:
            if p.exists():
                return True
        except (OSError, ValueError):
            pass
    return False


def spotify_authenticated():
    for d in [Path.home() / ".config" / "spotdl", Path.home() / ".spotdl"]:
        cache = d / ".spotipy"
        if cache.exists() and cache.stat().st_size > 10:
            return True
    return False


def get_spotdl_config_dir():
    """Get the spotdl config directory (platform-aware)."""
    if sys.platform == "linux":
        xdg = Path.home() / ".config" / "spotdl"
        old = Path.home() / ".spotdl"
        if xdg.exists():
            return xdg
        if old.exists():
            return old
        return xdg
    return Path.home() / ".spotdl"


def ensure_config():
    """Write the bundled config.json if one doesn't exist yet."""
    config_dir = get_spotdl_config_dir()
    config_file = config_dir / "config.json"

    if config_file.exists():
        # Merge: keep existing values, add any new keys from BUNDLED_CONFIG
        try:
            with open(config_file, "r") as f:
                existing = json.load(f)
            changed = False
            for key, val in BUNDLED_CONFIG.items():
                if key not in existing:
                    existing[key] = val
                    changed = True
            # Always enforce rate-limit-critical values
            if existing.get("max_retries", 3) < 10:
                existing["max_retries"] = 20
                changed = True
            if existing.get("spotify_sleep", 0) < 0.3:
                existing["spotify_sleep"] = 0.5
                changed = True
            if existing.get("download_sleep", 0) < 0.5:
                existing["download_sleep"] = 1.0
                changed = True
            if changed:
                with open(config_file, "w") as f:
                    json.dump(existing, f, indent=4)
        except (json.JSONDecodeError, OSError):
            pass  # corrupted config, leave it
        return

    # Fresh install: write the whole config
    os.makedirs(config_dir, exist_ok=True)
    with open(config_file, "w") as f:
        json.dump(BUNDLED_CONFIG, f, indent=4)


# ── First-run / Setup ────────────────────────────────────────────────

def show_python_error():
    """Show a helpful message if Python version is wrong."""
    clear()
    banner()
    v = python_version_str()
    lo = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    hi = f"{MAX_PYTHON[0]}.{MAX_PYTHON[1]}"

    print(f"  Your Python version: {v}")
    print(f"  Required: {lo} through {hi}\n")

    if sys.version_info[:2] > MAX_PYTHON:
        print(f"  Python {v} is too new — a dependency (mutagen) doesn't")
        print(f"  support it yet. Install Python {hi} instead.\n")
    else:
        print(f"  Python {v} is too old. Install Python {hi} or newer.\n")

    print("  Download Python:")
    print(f"  https://www.python.org/downloads/\n")
    print("  IMPORTANT: During install, check the box that says")
    print('  "Add Python to PATH"\n')
    pause()
    sys.exit(1)


def do_setup():
    """Interactive setup: install spotdl + ffmpeg."""
    clear()
    banner()
    print("  SETUP\n")

    # Python version
    v = python_version_str()
    if python_version_ok():
        print(f"  [OK] Python {v}")
    else:
        lo = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
        hi = f"{MAX_PYTHON[0]}.{MAX_PYTHON[1]}"
        print(f"  [!!] Python {v}  (need {lo}-{hi})")
        print()
        if sys.version_info[:2] > MAX_PYTHON:
            print(f"  Python {v} is too new. Install Python")
            print(f"  {hi}.x from python.org, then re-run this.\n")
        else:
            print(f"  Python {v} is too old. Install Python")
            print(f"  {hi}.x from python.org, then re-run this.\n")
        print("  https://www.python.org/downloads/")
        print('  (check "Add Python to PATH" during install)\n')
        pause()
        return False

    # spotDL
    if spotdl_installed():
        print("  [OK] spotDL installed")
    else:
        wheel = os.path.join(script_dir(), WHEEL_NAME)
        if not os.path.exists(wheel):
            print(f"  [!!] Can't find {WHEEL_NAME}")
            print("       Make sure it's in the same folder as this script.\n")
            pause()
            return False

        print("  [..] Installing spotDL...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--force-reinstall", wheel],
        )
        if result.returncode == 0:
            print("  [OK] spotDL installed!")
        else:
            print("  [!!] Installation failed.\n")
            print("  Try running this as Administrator.\n")
            pause()
            return False

    # ffmpeg
    if ffmpeg_available():
        print("  [OK] FFmpeg found")
    else:
        print("  [..] Downloading FFmpeg (this can take a moment)...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "spotdl", "--download-ffmpeg"],
                timeout=120
            )
            if result.returncode == 0 or ffmpeg_available():
                print("  [OK] FFmpeg downloaded!")
            else:
                print("  [!!] FFmpeg download may have failed.")
                print("       spotDL will retry on first use.")
        except subprocess.TimeoutExpired:
            print("  [!!] FFmpeg download timed out. Will retry on first use.")
        except Exception as e:
            print(f"  [!!] FFmpeg download error: {e}")
            print("       spotDL will retry on first use.")

    # Config
    ensure_config()
    print("  [OK] Config written")

    # Auth status
    if spotify_authenticated():
        print("  [OK] Spotify login found")
    else:
        print('  [--] Not logged in  (choose "Log in to Spotify" next)')

    print()
    print("  Setup complete!\n")
    pause()
    return True


def first_run_check():
    """On first run, walk through setup automatically."""
    if spotdl_installed():
        return True

    clear()
    banner()
    print("  Welcome! Looks like this is your first time.\n")
    print("  Let's get everything set up. This takes about")
    print("  a minute and only needs to happen once.\n")

    go = input("  Ready to set up? (y/n): ").strip().lower()
    if go not in ("y", "yes", ""):
        return False

    return do_setup()


# ── Screens ───────────────────────────────────────────────────────────

def do_login():
    """Walk user through Spotify OAuth."""
    clear()
    banner()
    print("  LOG IN TO SPOTIFY\n")

    if spotify_authenticated():
        print("  You're already logged in!\n")
        print("  Want to log in again? (e.g. different account)")
        go = input("  Re-login? (y/n): ").strip().lower()
        if go not in ("y", "yes"):
            return

    print("  A browser window will open for Spotify login.")
    print("  Log in, then it will redirect to a local page.")
    print("  That redirect means it worked.\n")
    print("  You only need to do this once.\n")
    pause("  Press Enter to open Spotify login...")

    print("\n  Opening Spotify...\n")
    print("  (A browser window should open. Log in, then come back here.)\n")

    # Use a single known track to trigger OAuth — fast, no pagination
    tmp_save = os.path.join(script_dir(), ".auth_check.spotdl")
    ok, errors = run_spotdl([
        "save",
        "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT",
        "--user-auth",
        "--save-file", tmp_save,
        "--simple-tui",
    ])
    # Clean up temp file
    try:
        os.remove(tmp_save)
    except OSError:
        pass

    print()
    if ok or spotify_authenticated():
        print("  Logged in successfully!\n")
    else:
        print("  Login may have failed.\n")
        if errors:
            print(f"  Error: {errors[:300]}\n")
    pause()


def do_download_saved():
    """Download all liked/saved songs."""
    clear()
    banner()
    print("  DOWNLOAD LIKED SONGS\n")

    if not spotify_authenticated():
        print("  You need to log in to Spotify first.")
        print('  Choose "Log in to Spotify" from the main menu.\n')
        pause()
        return

    music_dir = ensure_music_dir()
    existing = count_music_files(music_dir)
    if existing > 0:
        print(f"  You have {existing} songs already downloaded.")
        print("  Existing songs will be skipped.\n")

    print(f"  Output: {music_dir}")
    print(f"  Format: {FORMAT} @ {BITRATE}")
    print()
    print("  This might take a while for large libraries.")
    print("  You can close the window anytime — already-downloaded")
    print("  songs won't need to be re-downloaded.\n")

    threads = ask_threads()

    print("\n  Counting liked songs...", end="", flush=True)
    total = count_songs_in_source(["saved", "--user-auth"])
    if total > 0:
        print(f" {total} found.\n")
    else:
        print(" done.\n")

    ok, errors = run_spotdl([
        "download", "saved",
        "--user-auth",
        "--output", OUTPUT_TEMPLATE,
        "--format", FORMAT,
        "--bitrate", BITRATE,
        "--threads", str(threads),
        "--simple-tui",
    ], cwd=music_dir, track_progress=True, total_songs=total)

    new_count = count_music_files(music_dir)
    downloaded = new_count - existing

    print()
    if downloaded > 0:
        print(f"  Downloaded {downloaded} new songs! ({new_count} total)")
    elif ok:
        print(f"  All songs already downloaded. ({new_count} total)")
    else:
        print(f"  Finished with errors. ({new_count} songs in folder)")
        if errors:
            for line in errors.splitlines()[-5:]:
                print(f"    {line}")
            print()
    print(f"  Folder: {music_dir}\n")
    pause()


def do_download_url():
    """Download from a Spotify URL."""
    clear()
    banner()
    print("  DOWNLOAD FROM URL\n")
    print("  Paste a Spotify link. Works with:")
    print("    - Playlists")
    print("    - Albums")
    print("    - Single tracks")
    print("    - Artist pages (downloads all songs)")
    print()
    print("  Example:")
    print("  https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M\n")

    url = input("  URL: ").strip()
    if not url:
        return

    if "spotify.com" not in url and "spotify:" not in url:
        print("\n  That doesn't look like a Spotify URL.")
        go = input("  Try it anyway? (y/n): ").strip().lower()
        if go not in ("y", "yes"):
            return

    music_dir = ensure_music_dir()
    existing = count_music_files(music_dir)

    multi = any(x in url for x in ["playlist", "album", "artist", "collection"])

    print(f"\n  Downloading to: {music_dir}")
    print(f"  Format: {FORMAT} @ {BITRATE}\n")

    threads = ask_threads() if multi else 1

    args = [
        "download", url,
        "--output", OUTPUT_TEMPLATE,
        "--format", FORMAT,
        "--bitrate", BITRATE,
        "--threads", str(threads),
        "--simple-tui",
    ]

    if "playlist" in url or "collection" in url:
        args.append("--user-auth")

    ok, errors = run_spotdl(args, cwd=music_dir, track_progress=multi)

    new_count = count_music_files(music_dir)
    downloaded = new_count - existing

    print()
    if downloaded > 0:
        print(f"  Downloaded {downloaded} new songs! ({new_count} total)")
    elif ok:
        print("  All songs already downloaded.")
    else:
        print(f"  Finished with errors. ({new_count} songs in folder)")
        if errors:
            for line in errors.splitlines()[-5:]:
                print(f"    {line}")
            print()
    print(f"  Folder: {music_dir}\n")
    pause()


def do_download_search():
    """Download by searching for a song."""
    clear()
    banner()
    print("  SEARCH & DOWNLOAD\n")
    print("  Type a song name, artist, or both.")
    print('  Example: Metallica - Nothing Else Matters\n')

    query = input("  Search: ").strip()
    if not query:
        return

    music_dir = ensure_music_dir()
    existing = count_music_files(music_dir)

    print(f"\n  Searching for: {query}\n")

    ok, errors = run_spotdl([
        "download", query,
        "--output", OUTPUT_TEMPLATE,
        "--format", FORMAT,
        "--bitrate", BITRATE,
        "--simple-tui",
    ], cwd=music_dir)

    new_count = count_music_files(music_dir)
    downloaded = new_count - existing

    print()
    if downloaded > 0:
        print(f"  Downloaded {downloaded} new songs!")
    elif ok:
        print("  Already exists or couldn't be found.")
    else:
        print("  Download had errors.")
        if errors:
            for line in errors.splitlines()[-5:]:
                print(f"    {line}")
            print()
    print(f"  Folder: {music_dir}\n")
    pause()


def do_open_folder():
    """Open the Music folder."""
    music_dir = ensure_music_dir()
    count = count_music_files(music_dir)
    print(f"\n  Opening Music folder ({count} songs)...")

    if os.name == "nt":
        os.startfile(music_dir)
    elif sys.platform == "darwin":
        subprocess.run(["open", music_dir])
    else:
        subprocess.run(["xdg-open", music_dir])


# ── Main Menu ─────────────────────────────────────────────────────────

def main_menu():
    while True:
        clear()
        banner()

        # Show song count if we have any
        music_dir = os.path.join(script_dir(), MUSIC_DIR)
        count = count_music_files(music_dir)
        if count > 0:
            print(f"  [{count} songs in Music folder]\n")

        # Show auth warning if needed
        if not spotify_authenticated():
            print("  [!] Not logged in — log in first for Liked Songs\n")

        print("  1.  Download my Liked Songs")
        print("  2.  Download from URL  (playlist / album / track)")
        print("  3.  Search & download a song")
        print()
        print("  4.  Log in to Spotify")
        print("  5.  Open Music folder")
        print("  6.  Setup / check status")
        print()
        print("  0.  Exit")
        print()

        choice = input("  > ").strip()

        if choice == "1":
            do_download_saved()
        elif choice == "2":
            do_download_url()
        elif choice == "3":
            do_download_search()
        elif choice == "4":
            do_login()
        elif choice == "5":
            do_open_folder()
        elif choice == "6":
            do_setup()
        elif choice in ("0", "q", "quit", "exit"):
            clear()
            print("\n  Later.\n")
            break


# ── Entry ─────────────────────────────────────────────────────────────

def is_portable():
    """Detect if running from a bootstrapped .runtime Python."""
    return ".runtime" in sys.executable.replace("\\", "/")


if __name__ == "__main__":
    # Silent config write — called by INSTALL.bat after pip install
    if "--write-config" in sys.argv:
        ensure_config()
        print("  [OK] Config written")
        sys.exit(0)

    if is_portable():
        # Bootstrapped Python: setup already handled by bootstrap.ps1.
        # Just write config and go to menu.
        try:
            ensure_config()
            main_menu()
        except KeyboardInterrupt:
            print("\n\n  Interrupted.\n")
            sys.exit(0)
    else:
        # System Python: check version, run setup if needed
        if sys.version_info[:2] < (3, 8):
            print(f"\n  Python {python_version_str()} is way too old.")
            print("  Get Python 3.12 or 3.13 from python.org\n")
            input("  Press Enter to exit...")
            sys.exit(1)

        if not python_version_ok():
            show_python_error()

        try:
            if not first_run_check():
                sys.exit(0)
            ensure_config()
            main_menu()
        except KeyboardInterrupt:
            print("\n\n  Interrupted.\n")
            sys.exit(0)
