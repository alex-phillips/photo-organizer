#!/usr/bin/env python

import subprocess
import os
import json
from datetime import datetime
import argparse
import shutil
import hashlib
from pathlib import Path
import re
import glob

EXIF_TS_FORMAT = "%Y:%m:%d %H:%M:%S"


class ExifTool(object):

    sentinel = "{ready}\n"

    def __init__(self, executable="/usr/bin/exiftool"):
        self.executable = executable

    def __enter__(self):
        self.process = subprocess.Popen(
            [self.executable, "-stay_open", "True", "-@", "-"],
            universal_newlines=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.process.stdin.write("-stay_open\nFalse\n")
        self.process.stdin.flush()

    def execute(self, *args):
        args = args + ("-execute\n",)
        self.process.stdin.write(str.join("\n", args))
        self.process.stdin.flush()
        output = ""
        fd = self.process.stdout.fileno()
        while not output.endswith(self.sentinel):
            output += os.read(fd, 4096).decode("utf-8")
        return output[: -len(self.sentinel)]

    def get_metadata(self, *filenames):
        return json.loads(self.execute("-G", "-j", "-n", *filenames))


def process_file(fname, extensions=None):
    filename = os.path.basename(fname)
    extension = ".".join(Path(filename).suffix.lower().split(".")[1:])

    """Only process file if extension exists in list of extensions passed"""
    if extensions is not None and extension not in extensions:
        print(f"Excluding {filename}")
        return

    exif = e.get_metadata(fname)[0]

    print(f"Processing {filename}")

    date = None

    for metadata_field in [
        "EXIF:DateTimeOriginal",
        "EXIF:CreateDate",
        "XMP:CreateDate",
        "XMP:DateCreated",
        "QuickTime:CreateDate",
    ]:
        if metadata_field in exif:
            print(f"  Field {metadata_field} found. Value: {exif[metadata_field]}")
            date = datetime.strptime(exif[metadata_field].split(".")[0], EXIF_TS_FORMAT)
            break

    if date is None:
        print(f"ERROR: Unable to parse file {fname}")
        return

    dest_dir = os.path.join(args.destination, date.strftime("%Y/%m"))
    if os.path.exists(dest_dir) == False and args.dry_run == False:
        os.makedirs(dest_dir)

    destination = os.path.join(dest_dir, filename)
    if os.path.exists(destination):
        print(f"  Destination file already exists: {destination}")

        if args.move == True:
            with open(fname, "rb") as file_to_check:
                file_hash = hashlib.md5(file_to_check.read()).hexdigest()

            with open(destination, "rb") as file_to_check:
                existing_hash = hashlib.md5(file_to_check.read()).hexdigest()

            if file_hash == existing_hash:
                print("  Files are identical, removing source")
                if args.dry_run == False:
                    os.remove(fname)
            else:
                print("  Files are NOT identical, keeping source.")

        return

    if args.move == False:
        print(f"COPYING {fname} -> {destination}")
        if args.dry_run == False:
            shutil.copy2(fname, destination)
    else:
        print(f"MOVING {fname} -> {destination}")
        if args.dry_run == False:
            shutil.move(fname, destination)


parser = argparse.ArgumentParser(description="Organize files based on EXIF date.")
parser.add_argument("source", help="Source to scan for files", nargs='+')
parser.add_argument("-d", "--destination", help="Destination to move files to")
parser.add_argument(
    "-m", "--move", help="Move files instead of copy", action="store_true"
)
parser.add_argument(
    "--dry-run", help="Don't perform any copy or move actions", action="store_true"
)
parser.add_argument(
    "-e", "--extensions", help="Specify file extensions to act on (comma-separated)"
)

args = parser.parse_args()

if args.destination is None:
    print("Must include destination. Exiting.")
    quit()

if args.extensions is not None:
    args.extensions = args.extensions.lower().split(",")

with ExifTool() as e:
    for source in args.source:
        if os.path.isfile(source):
            process_file(os.path.abspath(source), args.extensions)
        elif os.path.isdir(source):
            for dirpath, dirs, files in os.walk(source):
                for filename in files:
                    fname = os.path.join(dirpath, filename)
                    process_file(fname, args.extensions)
