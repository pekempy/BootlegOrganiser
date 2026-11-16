import hashlib
import json
import logging
import os

from modules.config import config
from modules.path_utils import walk_library_dirs

logger = logging.getLogger(__name__)

CHECKSUM_FILENAME = 'Checksums.b2'
CACHE_FILENAME = '.checksums.cache'
_CHUNK_SIZE = 4 * 1024 * 1024
_SKIP_NAMES = {'Cast.txt', CHECKSUM_FILENAME, CACHE_FILENAME}


def _is_skipped(filename: str) -> bool:
    return filename in _SKIP_NAMES or filename.startswith('.encora-')


def _collect_files(folder: str) -> list[tuple[str, str]]:
    """Return sorted (relative_path, absolute_path) pairs for every file under folder."""
    entries = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith('.') and not os.path.islink(os.path.join(root, d))]
        for name in files:
            if root == folder and _is_skipped(name):
                continue
            full = os.path.join(root, name)
            if os.path.islink(full):
                continue
            rel = os.path.relpath(full, folder).replace(os.sep, '/')
            entries.append((rel, full))
    entries.sort(key=lambda e: e[0])
    return entries


def _hash_file(path: str) -> str:
    h = hashlib.blake2b()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b''):
            h.update(chunk)
    return h.hexdigest()


def _read_manifest(manifest_path: str) -> dict[str, str]:
    existing = {}
    if not os.path.exists(manifest_path):
        return existing
    with open(manifest_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line:
                continue
            digest, sep, rel_path = line.partition('  ')
            if sep and digest:
                existing[rel_path] = digest
    return existing


def _write_manifest(manifest_path: str, digests: dict[str, str]) -> None:
    lines = [f"{digest}  {rel}" for rel, digest in sorted(digests.items())]
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + ('\n' if lines else ''))


def _read_cache(cache_path: str) -> dict:
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_cache(cache_path: str, cache: dict) -> None:
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f)


def generate_checksum_manifest(folder: str, force: bool = False) -> bool:
    """Create or incrementally update Checksums.b2 for a recording folder."""
    manifest_path = os.path.join(folder, CHECKSUM_FILENAME)
    cache_path = os.path.join(folder, CACHE_FILENAME)
    files = _collect_files(folder)
    if not files:
        return False

    cache = {} if force else _read_cache(cache_path)
    manifest_hashes = {} if force else _read_manifest(manifest_path)
    digests = {}
    new_cache = {}
    changed = force or not os.path.exists(manifest_path)

    for rel, full in files:
        st = os.stat(full)
        fingerprint = [st.st_size, st.st_mtime]
        cached = cache.get(rel)

        if cached and cached[0] == fingerprint[0] and cached[1] == fingerprint[1]:
            digest = cached[2]
        elif rel in manifest_hashes and rel not in cache:
            digest = manifest_hashes[rel]
        else:
            digest = _hash_file(full)
            changed = True

        digests[rel] = digest
        new_cache[rel] = [fingerprint[0], fingerprint[1], digest]

    if set(manifest_hashes.keys()) != set(digests.keys()):
        changed = True

    if new_cache != cache:
        _write_cache(cache_path, new_cache)

    if not changed:
        return False

    _write_manifest(manifest_path, digests)
    return True


def create_checksum_files(encora_data: list[dict]) -> None:
    """Generate/update checksum manifests for every local recording in encora_data."""
    import tqdm

    excluded_ids = config.excluded_ids
    skip_checksums = config.exclude_checksum_files
    updated_count = 0

    for entry in tqdm.tqdm(encora_data, desc="Checksumming recordings...", unit="recording"):
        path = entry['path']
        encora_id = str(entry['encora_id'])
        if skip_checksums and encora_id in excluded_ids:
            continue

        try:
            if generate_checksum_manifest(path):
                updated_count += 1
        except OSError as e:
            logger.warning(f"Checksum update failed for {path}: {e}")

    if updated_count > 0:
        print(f"Updated checksum manifests for {updated_count} recordings.")
    else:
        print("All local checksum manifests are already up to date.")


def verify_checksum_manifest(folder: str) -> list[tuple[str, str]] | None:
    manifest_path = os.path.join(folder, CHECKSUM_FILENAME)
    expected = _read_manifest(manifest_path)
    if not expected and not os.path.exists(manifest_path):
        return None

    problems = []
    seen = set()
    for rel, full in _collect_files(folder):
        seen.add(rel)
        if rel not in expected:
            problems.append(('extra', rel))
            continue
        if _hash_file(full) != expected[rel]:
            problems.append(('mismatch', rel))

    for rel in expected:
        if rel not in seen:
            problems.append(('missing', rel))

    return problems


def verify_all_checksums(main_directory: str) -> tuple[int, int]:
    """Walk main_directory, re-hashing and checking every checksum manifest found."""
    checked = 0
    failed = 0

    for root, dirs, files in walk_library_dirs(main_directory):
        if CHECKSUM_FILENAME not in files:
            continue
        dirs[:] = []
        checked += 1
        problems = verify_checksum_manifest(root)
        if problems:
            failed += 1
            print(f"[FAIL] {root}")
            for kind, rel in problems:
                print(f"    {kind}: {rel}")

    if checked == 0:
        print("No checksum manifests found.")
    elif failed == 0:
        print(f"Verified {checked} recordings: all checksums match.")
    else:
        print(f"Verified {checked} recordings: {failed} had problems.")

    return checked, failed
