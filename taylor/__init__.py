"""
Written by Dominic Fitzgerald
On 14 Feb 2017

Tools for use with the OpenStack Object Storage system
"""
import argparse

from taylor import integrity


def execute_from_command_line():
    parser = argparse.ArgumentParser(prog='taylor')
    subparsers = parser.add_subparsers()

    subprograms = [
        (integrity, 'check-integrity', None)
    ]
    for module, name, description in subprograms:
        subp = subparsers.add_parser(
           name,
           description=description
        )
        subp.set_defaults(func=module.main)
        module.populate_parser(subp)

    args = parser.parse_args()
    args.func(vars(args))

