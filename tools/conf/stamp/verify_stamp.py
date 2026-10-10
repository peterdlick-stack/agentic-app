"""Verify the stamp against Git object bytes, independent of checkout EOL settings.

Install blake3 in an isolated directory, then pass --deps DIR if needed.
Use --ref HEAD (default), a commit, or a tree from git write-tree.
"""
import argparse
import io
import json
from pathlib import Path, PurePosixPath
import struct
import subprocess
import sys
import tarfile


def archive_files(repo, ref):
    data = subprocess.check_output(['git', '-c', 'safe.directory=' + str(repo.as_posix()),
                                    '-C', str(repo), 'archive', ref, 'bundle'])
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive:
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError('Unsupported bundle entry: ' + member.name)
            rel = str(PurePosixPath(member.name).relative_to('bundle'))
            files[rel] = archive.extractfile(member).read()
    return files


def digest(files):
    import blake3
    h = blake3.blake3()
    for name in sorted(files, key=lambda value: PurePosixPath(value).parts):
        if name == 'manifest.json':
            continue
        data = files[name]
        h.update(name.encode('utf-8') + b'\0' + struct.pack('<Q', len(data)) + data)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[3])
    ap.add_argument('--ref', default='HEAD')
    ap.add_argument('--deps', type=Path)
    args = ap.parse_args()
    if args.deps:
        sys.path.insert(0, str(args.deps))
    files = archive_files(args.repo.resolve(), args.ref)
    expected = json.loads(files['manifest.json'])['integrity']['bundle_blake3']
    actual = digest(files)
    passed = actual == expected
    print(json.dumps({'status': 'PASS' if passed else 'FAIL', 'ref': args.ref,
                      'expected': expected, 'actual': actual}, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
