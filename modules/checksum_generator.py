"""
Per-folder checksum manifests for bootleg recordings.

Each recording folder (which may hold a single video file, a set of tracked
audio files, or a VOB rip with VIDEO_TS/AUDIO_TS subfolders) gets one
`Checksums.b2` manifest listing every contained file's BLAKE2b-512 digest,
relative to the folder root. BLAKE2b is used because it's stdlib
(`hashlib.blake2b`, no extra dependency), faster than SHA-256 on 64-bit
hardware, and produces the exact same digest as GNU `b2sum` -- so any
manifest this module writes can also be checked manually with
`b2sum -c Checksums.b2` without Python.

Generation is incremental: a file already listed in an existing manifest is
trusted and not re-read, so re-running the organiser over an already
checksummed library only hashes newly added files. To actually catch
bit-rot/corruption, use `verify_all_checksums`, which fully re-reads and
re-hashes every file against its manifest.
"""
import os
import hashlib
import json

CHECKSUM_FILENAME = 'Checksums.b2'
CACHE_FILENAME = '.checksums.cache'
_CHUNK_SIZE = 4 * 1024 * 1024
_SKIP_NAMES = {'Cast.txt', CHECKSUM_FILENAME, CACHE_FILENAME}


def _is_skipped(filename):
    return filename in _SKIP_NAMES or filename.startswith('.encora-')


def _collect_files(folder):
    """Return sorted (relative_path, absolute_path) pairs for every file under folder, recursively."""
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


def _hash_file(path):
    h = hashlib.blake2b()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b''):
            h.update(chunk)
    return h.hexdigest()


def _read_manifest(manifest_path):
    """Return {relative_path: hash} from an existing manifest."""
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


def _write_manifest(manifest_path, digests):
    lines = [f"{digest}  {rel}" for rel, digest in sorted(digests.items())]
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + ('\n' if lines else ''))


def _read_cache(cache_path):
    """Return {relative_path: [size, mtime, hash]} used to detect changed source files cheaply (stat only, no re-read)."""
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_cache(cache_path, cache):
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f)


def generate_checksum_manifest(folder, force=False):
    """
    Create/update the checksum manifest for a single recording folder.

    A per-folder .checksums.cache records each file's size + mtime alongside
    its hash. If a file's size/mtime still match the cache, its hash is
    trusted and not re-read. If either changed -- e.g. a re-graded/re-encoded
    file was dropped in under the same filename -- it's re-hashed
    automatically. New files are always hashed; files no longer present are
    dropped from the manifest.

    Folders that already have a Checksums.b2 from before this cache existed
    are migrated without a redundant re-hash: their existing manifest hash is
    trusted once, and today's size/mtime is recorded as the new baseline, so
    only *future* changes get detected -- past history isn't re-verified
    here (use --verify-checksums for that).

    Returns True if the manifest was created or changed.
    """
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
            # Pre-cache manifest entry: trust it once, start tracking from now on.
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


def create_checksum_files(encora_data):
    """Generate/update checksum manifests for every local recording in encora_data."""
    from modules.config import config
    excluded_ids = config.excluded_ids
    skip_checksums = config.exclude_checksum_files
    updated_count = 0

    for entry in encora_data:
        path = entry['path']
        encora_id = str(entry['encora_id'])

        if skip_checksums and encora_id in excluded_ids:
            continue

        if generate_checksum_manifest(path):
            updated_count += 1

    if updated_count > 0:
        print(f"Updated checksum manifests for {updated_count} recordings.")
    else:
        print("All local checksum manifests are already up to date.")


def verify_checksum_manifest(folder):
    """
    Fully re-hash every file in folder and compare against its manifest.
    Returns None if there's no manifest, otherwise a list of
    (problem_type, relative_path) tuples where problem_type is one of
    'mismatch' (content changed), 'missing' (listed but no longer present),
    or 'extra' (present but never checksummed).
    """
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


def verify_all_checksums(main_directory):
    """Walk main_directory, re-hashing and checking every checksum manifest found. Prints a report."""
    checked = 0
    failed = 0

    for root, dirs, files in os.walk(main_directory):
        dirs[:] = [d for d in dirs if not d.startswith('.') and not os.path.islink(os.path.join(root, d))]
        if CHECKSUM_FILENAME not in files:
            continue

        # A manifest covers everything below its folder (e.g. VIDEO_TS/AUDIO_TS,
        # multi-track audio subfolders) -- don't look for another manifest inside it.
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
