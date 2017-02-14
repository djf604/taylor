"""
Written by Dominic Fitzgerald
On 14 February 2017

Tools for download integrity checks.
"""
import os
import sys
import re
import subprocess
import argparse

from hashlib import md5
from functools import partial


def populate_parser(parser):
    """
    Populate the parser if this script is run directly.
    :param parser: argparse.ArgumentParser Argument parser
    :return: argparse.ArgumentParser Populated argument parser
    """
    parser.add_argument('--local-filepath', required=True, help='Path to local file')
    parser.add_argument('--remote-container', required=True,
                        help='Name of object store container housing the remote object')
    parser.add_argument('--remote-object', required=True, help='Name of the remote object')
    parser.add_argument('--segment-size', type=int, default=0,
                        help='Size of each segment for the remote object')
    parser.add_argument('--segment-container', help='Name of the object store container house the '
                                                    'remote object segments')


def main(args=None):
    if not args:
        parser = argparse.ArgumentParser()
        populate_parser(parser)
        args = vars(parser.parse_args())

    sys.stdout.write('Comparing {local} against {remote}\n'.format(
        local=args['local_filepath'],
        remote='/'.join([args['remote_container'], args['remote_object']])
    ))

    sys.stdout.write('File size check: ')
    passed_size_check = filesize_check(
        local_filepath=args['local_filepath'],
        object_container=args['remote_container'],
        object_name=args['remote_object']
    )
    sys.stdout.write('{}\n'.format('Passed' if passed_size_check else 'Failed'))

    sys.stdout.write('MD5 checksum check: ')
    passed_md5_check = md5_check(
        local_filepath=args['local_filepath'],
        object_container=args['remote_container'],
        object_name=args['remote_object'],
        segment_size=args['segment_size'],
        segment_container=args['segment_container']
    )
    sys.stdout.write('{}\n'.format('Passed' if passed_md5_check else 'Failed'))


def check_integrity(local_filepath, object_container, object_name, segment_size=0, segment_container=None):
    """
    Performs both file size and md5 integrity checks on a local file and a remote object in the object store.
    :param local_filepath: str Filepath to the local file to check against the remote object store
    :param object_container: str Name of the container housing the remote object
    :param object_name: str Name of the object in the remote object store
    :param segment_size: int Size of each segment for the remote object
    :param segment_container: str Name of the container housing the segments for the remote object
    :return: bool Whether both integrity checks passed
    """
    return filesize_check(
        local_filepath=local_filepath,
        object_container=object_container,
        object_name=object_name
    ) and md5_check(
        local_filepath=local_filepath,
        object_container=object_container,
        object_name=object_name,
        segment_size=segment_size,
        segment_container=segment_container
    )


def filesize_check(local_filepath, object_container, object_name):
    """
    Given a file on the local filesystem and a corresponding object in the object store,
    will check to ensure filesize in bytes is the same between local and remote.
    :param local_filepath: str Filepath to the local file to check against the remote object store
    :param object_container: str Name of the container housing the remote object
    :param object_name: str Name of the object in the remote object store
    :return:bool Whether the local file matches the size of the remote content
    """
    content_length_re = r'Content Length:\s+(\d+)'

    object_stat = subprocess.check_output('swift stat {container} {object}'.format(
        container=object_container,
        object=object_name
    ), shell=True)

    if not object_stat:
        raise ValueError('Swift stat returned nothing')

    content_length_search = re.search(content_length_re, object_stat)
    if content_length_search is None:
        raise AttributeError('Content length not found for object {object} in swift stat'.format(
            object=object_name
        ))

    return int(content_length_search.group(1)) == os.path.getsize(local_filepath)


def md5_check(local_filepath, object_container, object_name, segment_size=0, segment_container=None):
    """
    Given a file on the local filesystem and a corresponding object in the object store,
    will do an md5 check to ensure data integrity between local and remote. It does so
    by chunking up the local file in-memory to the same number of bytes as the segments
    for the full object, then comparing the md5 hases from those with the ETag for
    the respective segment. If all segments have a matching md5 and ETag, then it can
    be assumed that the local file is exactly concurrent with the remote full object.

    Segment size is incredibly important for this to work. Luckily, the segment size
    is stored by default when an object is segmented, so it can be grabbed just by
    knowing the location of the segment itself. The user may also provide a segment
    size.

    :param local_filepath: str Filepath to the local file to check against the remote object store
    :param object_container: str Name of the container housing the remote object
    :param object_name: str Name of the object in the remote object store
    :param segment_size: int Size of each segment for the remote object
    :param segment_container: str Name of the container housing the segments for the remote object
    :return: bool Whether the local file matches the remote md5 checksum
    """
    try:
        int(segment_size)
    except TypeError:
        raise TypeError('segment_size must be an int')

    manifest_re = r'Manifest:\s+(\S+)'
    etag_re = r'ETag:\s+(\w+)'

    # TODO Replace subprocess command line calls with direct calls to swiftclient module
    object_stat = subprocess.check_output('swift stat {container} {object}'.format(
        container=object_container,
        object=object_name
    ), shell=True)

    if not object_stat:
        raise AttributeError('Swift stat returned nothing')

    manifest_search = re.search(manifest_re, object_stat)
    if manifest_search is None:
        # Object is not segmented, compared md5 directly to ETag
        etag_search = re.search(etag_re, object_stat)
        if etag_search is None:
            raise AttributeError('ETag not found for object {object} in swift stat'.format(object=object_name))

        # Get md5 of non-segment object, which is just the Etag
        remote_md5 = etag_search.group(1).strip()
        with open(local_filepath, 'rb') as local_file:
            # TODO Read in chunks so it doesn't overwhelm the system
            local_md5 = md5(local_file.read()).hexdigest().strip()

        # Return whether the md5s are equal
        return local_md5 == remote_md5
    else:
        # Object is segmented, so get md5 segment-by-segment
        # Get segment names
        segment_container = segment_container if segment_container else object_container + '_segments'
        segments = subprocess.check_output('swift list {container} --prefix {object}'.format(
            container=segment_container,
            object=object_name
        ), shell=True).strip().split()

        # Get remote segment md5s from the object store
        try:
            remote_segment_md5s = {
                re.search(etag_re, subprocess.check_output('swift stat {container} {segment}'.format(
                    container=segment_container,
                    segment=segment
                ), shell=True)).group(1).strip()
                for segment in segments
            }
        except AttributeError:
            raise AttributeError('ETag not found for segment in swift stat')

        # If not given, calculate segment size from segment name
        segment_size = int(segment_size) if segment_size else int(segments[0].split('/')[-2])

        # Calculate md5s for chunks of the local file equal to segment_size
        local_segment_md5s = set()
        with open(local_filepath, 'rb') as local_file:
            for local_seg in iter(partial(local_file.read, segment_size), ''):
                local_segment_md5s.add(md5(local_seg).hexdigest().strip())

        # Return whether the md5s are equal
        return local_segment_md5s == remote_segment_md5s

if __name__ == '__main__':
    main()
