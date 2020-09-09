#!/usr/bin/env python

import subprocess
import os
import json
from datetime import datetime
import argparse
import shutil
import hashlib

EXIF_TS_FORMAT = "%Y:%m:%d %H:%M:%S"

class ExifTool(object):

    sentinel = "{ready}\n"

    def __init__(self, executable="/usr/bin/exiftool"):
        self.executable = executable

    def __enter__(self):
        self.process = subprocess.Popen(
            [self.executable, "-stay_open", "True",  "-@", "-"],
            universal_newlines=True,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        return self

    def  __exit__(self, exc_type, exc_value, traceback):
        self.process.stdin.write("-stay_open\nFalse\n")
        self.process.stdin.flush()

    def execute(self, *args):
        args = args + ("-execute\n",)
        self.process.stdin.write(str.join("\n", args))
        self.process.stdin.flush()
        output = ""
        fd = self.process.stdout.fileno()
        while not output.endswith(self.sentinel):
            output += os.read(fd, 4096).decode('utf-8')
        return output[:-len(self.sentinel)]

    def get_metadata(self, *filenames):
        return json.loads(self.execute("-G", "-j", "-n", *filenames))

def process_file(fname):
    filename = os.path.basename(fname)
    exif = e.get_metadata(fname)[0]

    date = None
    if 'EXIF:DateTimeOriginal' in exif:
        date = datetime.strptime(exif['EXIF:DateTimeOriginal'], EXIF_TS_FORMAT)
    elif 'QuickTime:CreateDate' in exif:
        date = datetime.strptime(exif['QuickTime:CreateDate'], EXIF_TS_FORMAT)

    if date is None:
        print("ERROR: Unable to parse file {}".format(fname))
        return

    dest_dir = os.path.join(args.destination, date.strftime("%Y/%m"))
    if os.path.exists(dest_dir) == False:
        os.makedirs(dest_dir)

    destination = os.path.join(dest_dir, filename)
    if os.path.exists(destination):
        print("Destination file already exists: {}".format(destination))

        if args.move == True:
            with open(fname, 'rb') as file_to_check:
                file_hash = hashlib.md5(file_to_check.read()).hexdigest()

            with open(destination, 'rb') as file_to_check:
                existing_hash = hashlib.md5(file_to_check.read()).hexdigest()

            if file_hash == existing_hash:
                print("Files are identical, removing source")
                if args.dry_run == False:
                    os.remove(fname)
            else:
                print("Files are NOT identical, keeping source.")

        return

    if args.move == False:
        print("COPYING {} -> {}".format(fname, destination))
        if args.dry_run == False:
            shutil.copy(fname, destination)
    else:
        print("MOVING {} -> {}".format(fname, destination))
        if args.dry_run == False:
            shutil.move(fname, destination)

parser = argparse.ArgumentParser(description='Organize files based on EXIF date.')
parser.add_argument('source',
                    help='Source to scan for files')
parser.add_argument('-d', '--destination',
                    help='Destination to move files to')
parser.add_argument('-m', '--move',
                    help='Move files instead of copy', action='store_true')
parser.add_argument('--dry-run',
                    help="Don't perform any copy or move actions", action='store_true')

args = parser.parse_args()

if args.destination is None:
    print("Must include destination. Exiting.")
    quit()

print("Scanning {}".format(args.source))
if os.path.exists(args.source) == False:
    print("Source doesn't exist. Exiting.")
    quit()

with ExifTool() as e:
    if os.path.isfile(args.source):
        process_file(os.path.abspath(args.source))
    elif os.path.isdir(args.source):
        for dirpath, dirs, files in os.walk(args.source):
            for filename in files:
                fname = os.path.join(dirpath, filename)
                process_file(fname)
