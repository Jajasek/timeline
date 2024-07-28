#!/usr/bin/env python
import argparse
from functools import partial

from traverser import Traverser, Date


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('line', type=int)
    parser.add_argument('--generate-date', action='store_true')
    args = parser.parse_args()

    with open(args.filename, 'r') as file_in:
        traverser = Traverser()
        traverser.traverse(file_in, args.line)

    if args.generate_date:
        tomorrow = traverser.date.tomorrow()
        tomorrow.indent = traverser.last_parsed.get_indent()
        print(tomorrow)
    else:
        # all printing will begin with \n instead of ending, it generates better
        # output in vim
        myprint = partial(print, '\n', sep='', end='')
        date_printed = Date()
        for enter in traverser.blocks.values():
            if enter.date > date_printed:
                date_printed = enter.date
                myprint(enter.date)
            myprint(enter)
        if traverser.date > date_printed:
            myprint(traverser.date)


if __name__ == '__main__':
    main()
