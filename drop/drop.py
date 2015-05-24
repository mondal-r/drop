#!/usr/bin/env python
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import sys
import tempfile
import subprocess
import os
import hashlib
import base64
from datetime import datetime
try:
    # Python 3 only
    from configparser import SafeConfigParser
except ImportError:
    # Python 2 only
    from ConfigParser import SafeConfigParser
try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen

try:
    import pyperclip
    clipboard = True
except ImportError:
    clipboard = False

def upload(localpath, remoteserver, remotepath):
    cmd = ['scp', '-pq', localpath, remoteserver+':'+remotepath]
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        print("SCP failed, this has mainly these reasons: remote directory not present, scp " +
              "command invalid or unable to login.", file=sys.stderr)
        sys.exit(1)


def check_config(cfg):
    # TODO
    pass


def main():
    parser = argparse.ArgumentParser(description='Uploads data to a remote www directory via scp' +
                                     ' and returns a public url.')
    parser.add_argument('--destination', '-d', nargs=1,
                        help='Name of destination as found in configuration file.')
    parser.add_argument('--list-destinations', '-l', action='store_true',
                        help='List all destinations defined in configuration file.')
    parser.add_argument('infile', nargs='?', type=argparse.FileType('rb'), default=sys.stdin)
    parser.add_argument('--extension', '-e', nargs=1, required=False,
                        help='Overwrites extension on uploaded file.')
    parser.add_argument('--config-file', '-c', required=False, type=argparse.FileType('r'))
    parser.add_argument('--test', action='store_true', help='Runs a test on destination.')
    args = parser.parse_args()

    cfg = SafeConfigParser()
    cfg.read(['defaults.cfg'])
    cfg.read([os.path.expanduser('~/.drop.cfg'), '/etc/drop.cfg'])
    if args.config_file:
        cfg.readfp(args.config_file)
    check_config(cfg)
    
    # Gather all possible destinations from configuration file
    all_destiantions = cfg.sections()

    # Create temporary test file with timestamp
    if args.test:
        args.infile = tempfile.NamedTemporaryFile()
        test_data = ('TEST '+str(datetime.now())+'\n').encode('utf-8')
        args.infile.write(test_data)
        args.infile.seek(0)
        args.extension = ['test']

    # List all destinations:
    if args.list_destinations:
        for s in all_destiantions:
            if s == cfg.get('DEFAULT', 'destination'):
                s += " (default)"
            print(s)
        sys.exit(0)

    # Check and select destination
    destination = None
    if not args.destination:
        # Get default destination from config
        destination = [cfg.get('DEFAULT', 'destination')]
    elif cfg.has_section(args.destination[0]):
        # Found perfect fit
        destination = args.destination[0]
    else:
        # Select best fitting destination, if available
        possible_dests = filter(lambda d: d.startswith(args.destination[0]), all_destiantions)
        assert possible_dests, "Could not find destination section in config."
        assert len(possible_dests) == 1, "Could not find unique destination section in config."
        destination = possible_dests[0]

    # Get extension before it is overwritten
    ext = os.path.splitext(args.infile.name)[1]

    # Copy into a tempfile, so we can have chmod applied
    tempinfile = tempfile.NamedTemporaryFile()
    data = args.infile.read()
    if hasattr(args.infile, 'encoding') and args.infile.encoding:
        data = data.encode(args.infile.encoding)
    tempinfile.write(data)
    tempinfile.seek(0)
    args.infile = tempinfile
    #if cfg.has_option(args.destination[0], 'chmod'):
    chmod = cfg.getint(destination, 'chmod')
    os.chmod(args.infile.name, chmod)

    # Get remote location
    remoteserver = cfg.get(destination, 'remoteserver')
    remotedir = cfg.get(destination, 'remotedir')

    # Generate hash for uploaded filename
    hash_ = hashlib.sha1(args.infile.read())
    hashstr = base64.urlsafe_b64encode(hash_.digest()).decode('utf-8')
    hashstr = hashstr[:cfg.getint(destination, 'hashlength')]

    # Choose extension for uploaded file
    if args.extension:
        ext = '.'+args.extension[0]
    remotefilename = hashstr+ext

    assert '/' not in ext, "extension may not contain any slashes."

    upload(args.infile.name, remoteserver, os.path.join(remotedir, remotefilename))

    url = cfg.get(destination, 'url')+remotefilename
    print(url)
    if clipboard:
        pyperclip.copy(url)
        print('copied to clipboard.')

    if args.test:
        remote_data = urlopen(url).read()
        if remote_data != test_data:
            print("Failure. Different data found at remote url than expected.", file=sys.stderr)
            sys.exit(1)
        else:
            print("Success. Retreived same data from url as expected.", file=sys.stderr)


if __name__ == '__main__':
    main()
    