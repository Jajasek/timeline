#!/usr/bin/env python
import argparse
import os
import locale
import datetime
import tempfile
from bisect import bisect, insort
from dataclasses import dataclass, field
from io import StringIO
from typing import Iterable
from thefuzz import fuzz
from configparser import ConfigParser
from pathlib import Path

from traverser import Traverser, Element, Date, Enter, Leave, Spaced, Dated, \
    Note, Description, Empty, Ellipse


@dataclass(slots=True, order=True)
class DescriptionEntry:
    distance: int
    name: str
    linenumber: int
    description: str = field(compare=False)


class Filter(Traverser):
    def __init__(self, find: str, tolerance: int) -> None:
        super(Filter, self).__init__()
        # instead of files, first write to output buffers - at the end, we will
        # need to prepend these buffers with the header
        self.buffer_out = StringIO()
        self.buffer_sync = StringIO()
        # set of linenumbers of currently open blocks whose names got matched
        self.matched_enters: set[int] = set()
        # a flag that is set when a date is matched, to print the whole day
        self.matched_date = False
        # last printed date
        self.date_printed = self.date
        # list of description entries of matched names together with
        # distances of those names from the filter term
        #   (distance, name, linenumber, description)
        self.descriptions: list[DescriptionEntry] = []
        # the list of linenumbers of the starting points all ommited structure
        # blocks since the last printed information
        self.omitted_linenumbers: list[tuple[int, int]] = []
        self.last_printed_element: Element | None = None
        # the search term
        self.find: str = find.lower()
        # the tolerance, 0 meaning always match, 100 meaning perfect match
        self.tolerance: int = tolerance

    def filter(self, file_in: Iterable[str]) -> None:
        self.traverse(file_in)
        # if some information has been omitted after the last printed
        # element, print an ellipse
        if self.omitted_linenumbers:
            self.print_atom(Ellipse(
                self.omitted_linenumbers[0][0],
                ' ' * self.omitted_linenumbers[0][1] + '...'
            ))
        # sort the descriptions by distance, name and linenumber
        self.descriptions.sort()

    def handle_date(self, date: Date) -> None:
        # update date while keeping the newline in case that there are two
        # consecutive dates
        self.date = self.date.update(
            date, isinstance(self.last_parsed, Date) and self.last_parsed >
            self.date_printed
        )
        # if the date explicitely matched, print it together with the
        # whole day
        if self.fuzzysearch(str(self.date)):
            if self.matched_enters or self.matched_date:
                self.print_spaced(self.date)
            else:
                # print open blocks with dates
                self.print_structured(self.date)
            # manually tell future us that we printed the new date
            self.date_printed = self.date
            self.matched_date = True
        else:
            # reset the flag, in case the previous date matched
            self.matched_date = False

    def fuzzysearch(self, string: str) -> int:
        ratio = fuzz.partial_ratio(self.find, string.lower())
        # the maximum ratio is 100
        if ratio >= self.tolerance:
            # when sorting in the end, lower values take priority
            return 101 - ratio
        return 0

    def handle_enter(self, enter: Enter) -> None:
        # Even if we are in matched mode and print everything, it is necessary
        # to search for match in the block name, since blocks can partially 
        # overlap and also because in case of match we have to copy the 
        # description to the top.
        # But if we are in a matched date, then the date with all relevant
        # preceding blocks and all subsequent elements has been printed, so it
        # is sufficient to use print_atom.
        # If we are in a matched block instead, then the block entering with all
        # relevant preceding block has been printed and no information has been
        # omitted since then, so it is sufficient to use print_dated.
        distance = self.fuzzysearch(enter.name)
        if self.matched_date:
            self.print_spaced(enter)
            enter.printed = True
        elif self.matched_enters:
            self.print_spaced_dated(enter)
            enter.printed = True
        elif distance or self.fuzzysearch(enter.line):
            self.print_structured_dated(enter)
            enter.printed = True
        if distance:
            for description in enter.descriptions:
                self.descriptions.append(DescriptionEntry(
                    distance, enter.name, enter.linenumber, description
                ))
            self.matched_enters.add(enter.linenumber)

    def handle_leave_matched(self, leave: Leave, enter: Enter) -> None:
        # This method is called during the loop in Traverser.block_leave()
        # when the matching enter is found. It is this method's job to do
        # everything that has to be done in this situation, including taking
        # care of the internal Traverser.blocks dictionary.
        if not enter.printed:
            # we can safely forget this block
            # remove from blocks
            del self.blocks[enter.linenumber]
            # add to omitted_linenumbers
            insort(
                self.omitted_linenumbers, (enter.linenumber, enter.get_indent())
            )
            self.omitted_linenumbers.append(
                (leave.linenumber, leave.get_indent())
            )
            # for each BlockLeave that waits for this BlockEnter, remove the
            # reference and if it is the last one, resolve
            for leave_waiting in enter.waited_by:
                leave_waiting.waiting_for.remove(enter.linenumber)
                if not leave_waiting.waiting_for:
                    # not waiting anymore, remove from blocks and print
                    del self.blocks[leave_waiting.linenumber_enter]
                    del self.blocks[leave_waiting.linenumber]
                    self.print_ellipsed_dated(leave_waiting)
            return
        if not leave.waiting_for:
            # print the leave immediatelly and forget about it
            del self.blocks[enter.linenumber]
            # If we are in a matched date, then the date with all relevant
            # preceding blocks and all subsequent elements has been printed, so
            # it is sufficient to use print_spaced (in matched date we
            # always keep spaces).
            if self.matched_date:
                self.print_spaced(leave)
            # If we are in a matched block instead, then the block entering with
            # all relevant preceding blocks has been printed and no information
            # has been omitted since then, so it is sufficient to use
            # print_spaced_dated.
            elif self.matched_enters:
                self.print_spaced_dated(leave)
            else:
                self.print_ellipsed_dated(leave)
            # remove the block from the set of matched block, if it is there
            self.matched_enters.discard(enter.linenumber)
            return
        # set flag and references and save the BlockLeave
        enter.waiting = True
        leave.linenumber_enter = enter.linenumber
        for linenum_interleaved in leave.waiting_for:
            # linenum_interleaved references Leave, but I have no way of typing
            # that information
            # noinspection PyUnresolvedReferences
            self.blocks[linenum_interleaved].waited_by.append(leave)
        self.blocks[leave.linenumber] = leave

    def handle_leave_nonmatched(self, leave: Leave, enter: Enter) -> None:
        if not enter.printed and not enter.waiting:
            leave.waiting_for.add(enter.linenumber)
            # the reference to leave in block.waited_by will be added at the
            # end, because right now we don't know whether the matched
            # BlockEnter will have 'printed == True'.

    def handle_description(self, description: Description) -> None:
        # Even if we are in matched mode and print everything, it is necessary
        # to search for match in the name, because in case of match we have to
        # copy the description to the top.
        # But if we are in a matched date, then the date with all relevant
        # preceding blocks and all subsequent elements has been printed, so it
        # is sufficient to use print_atom.
        # If we are in a matched block instead, then the block entering with all
        # relevant preceding block has been printed and no information has been
        # omitted since then, so it is sufficient to use print_dated.
        distance = self.fuzzysearch(description.name)
        if self.matched_date:
            self.print_spaced(description)
        elif self.matched_enters:
            self.print_spaced_dated(description)
        elif distance or self.fuzzysearch(description.line):
            self.print_structured_dated(description)
        else:
            self.omitted_linenumbers.append(
                (description.linenumber, description.get_indent())
            )
        if distance:
            for desc in description.descriptions:
                self.descriptions.append(DescriptionEntry(
                    distance, description.name, description.linenumber, desc
                ))

    def handle_note(self, note: Note) -> None:
        if self.matched_date:
            self.print_spaced(note)
        elif self.matched_enters:
            self.print_spaced_dated(note)
        elif self.fuzzysearch(note.searchable):
            self.print_structured_dated(note)
        else:
            self.omitted_linenumbers.append(
                (note.linenumber, note.get_indent())
            )

    def print_structured(self, date: Date) -> None:
        # used to print date that explicitely matched
        self.print_structure()
        self.print_ellipsed(date)

    def print_structure(self) -> None:
        # print all relevant Enters and Leaves that haven't been printed yet,
        # potentially including dates and ellipses.
        to_be_deleted = list()
        for linenumber, block in self.blocks.items():
            if isinstance(block, Enter) and not block.printed:
                self.print_ellipsed_dated(block)
                block.printed = True
            elif isinstance(block, Leave):
                self.print_ellipsed_dated(block)
                # the pair has been freed from the waiting
                to_be_deleted += [block.linenumber_enter, linenumber]
        for linenumber in to_be_deleted:
            del self.blocks[linenumber]

    def print_structured_dated(self, dated: Dated) -> None:
        # print all preceding open blocks with dates and ellipses, then print
        # the element using print_ellipsed_dated. During the whole procedure,
        # check if not printing empty lines would cause unclear search result.
        self.print_structure()
        self.print_ellipsed_dated(dated)

    def print_ellipsed_dated(self, dated: Dated) -> None:
        # print the element, preceding it with date if the last printed date
        # is not up-to-date. Check for ellipses both before and after the date.
        if dated.date > self.date_printed:
            self.set_indent(dated.date, dated.get_indent())
            self.print_ellipsed(dated.date)
            self.date_printed = dated.date
        self.print_ellipsed(dated)

    def print_ellipsed(self, spaced: Spaced) -> None:
        # print the element, but check if some information has been omitted
        # before it. Use self.print to precede the element with empty line if
        # not doing so would cause unclear search result.
        self.print_ellipse(spaced.linenumber)
        self.print(spaced)

    def print_ellipse(self, linenumber: int) -> None:
        # To be called before printing a line with line number 'linenumber'.
        # If there have been some information omitted before the
        # 'linenumber', print an ellipse and forget the ommitted information.
        if index := bisect(self.omitted_linenumbers, (linenumber, 0)):
            # the first line number is the smallest
            # it can never happen that the ellipse is printed after an empty
            # line
            self.print_atom(Ellipse(
                self.omitted_linenumbers[0][0],
                ' ' * max(
                    self.omitted_linenumbers[0][1],
                    self.omitted_linenumbers[index - 1][1]
                ) + '...'
            ))
            # forget about the information omitted until linenumber
            del self.omitted_linenumbers[:index]

    def print_spaced_dated(self, dated: Dated) -> None:
        # as print_spaced, but precede the element with its date and the
        # date's empty line if necessary.
        if dated.date > self.date_printed:
            self.set_indent(dated.date, dated.get_indent())
            self.print_spaced(dated.date)
            self.date_printed = dated.date
        self.print_spaced(dated)

    def print_spaced(self, spaced: Spaced) -> None:
        # print the element's empty line if there is some and if last printed
        # element is not considered an empty line, then print the element
        if spaced.empty_line and not isinstance(self.last_printed_element,
                                                Empty):
            self.print_atom(spaced.empty_line)
        self.print_atom(spaced)

    def print(self, spaced: Spaced) -> None:
        # print the element while checking whether we should divide it from
        # last_printed_element by an empty line to avoid unclear search result
        if (spaced.empty_line and
                (type(self.last_printed_element), type(spaced)) in (
                    (Note, Note),
                    (Note, Enter),
                    (Note, Date),
                    (Note, Description),
                    (Leave, Note),
                    (Description, Note)
                )):
            self.print_atom(spaced.empty_line)
        self.print_atom(spaced)

    def print_atom(self, element: Element) -> None:
        # elementary print method, the only one that actually prints
        print(element, file=self.buffer_out)
        print(element.get_sync(), file=self.buffer_sync)
        self.last_printed_element = element

    def set_indent(self, date: Date, indent: int) -> None:
        if self.last_printed_element:
            date.indent = max(indent, self.last_printed_element.get_indent())
        else:
            date.indent = indent


def get_main_file(file: str, ignore_parent: bool) -> Path:
    # return path to the parent of 'file', in case 'file' was created as a
    # filter result.
    path_tln = Path(file).resolve()
    if ignore_parent:
        return path_tln
    path_sync = path_tln.with_suffix('.sync')
    try:
        with open(path_sync, 'r') as syncfile:
            # second line contains the main .tln file from which 'file' was
            # created as a filter result
            syncfile.readline()
            return Path(syncfile.readline().strip()).resolve()
    except FileNotFoundError:
        # 'file' was not created as a filter result, hence it is the main file
        return path_tln


def get_cache_dir() -> Path:
    cache = Path(os.environ.get('XDG_CACHE_HOME', '~/.cache')).expanduser()
    our_cache = cache / 'timeline'
    our_cache.mkdir(exist_ok=True, parents=True)
    return our_cache


def get_tmp_file() -> Path:
    now = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f-')
    return get_cache_dir() / now


def prune_cache(max_count, max_size, keep) -> None:
    # remove all directories in cache and all files above count and size, oldest
    # first. Corresponding .tln and .sync files are counted as one file. keep is
    # the basename of just-created files, which will be kept regardless of their
    # size.
    cache = get_cache_dir()
    # basename: (size, timestamp, [path, ...])
    info: dict[str, tuple[int, int, list]] = dict()
    for child in cache.iterdir():
        if not child.is_file():
            child.unlink()
        elif str(child).endswith('.sync') or str(child).endswith('.tln'):
            basename = str(child).rsplit('.', 1)[0]
            size, timestamp, files = info.get(basename, (0, 2**100, []))  # 2**100 is practically infinite
            info[basename] = (
                size + child.stat().st_size,
                min(timestamp, child.stat().st_mtime_ns),
                files + [child]
            )
        else:
            child.unlink()
    if keep in info:
        count = 1
        size_sum = info.pop(keep)[0]
    else:
        count = size_sum = 0
    # iterate from newest and when we exceed size or count, delete everything
    for basename, (size, _, paths) in sorted(
            info.items(), key=lambda x: x[1][1], reverse=True
    ):
        size_sum += size
        count += 1
        if size_sum > max_size or count > max_count:
            for path in paths:
                path.unlink()


def main():
    # C locale is the python's default, so setting it changes nothing
    config = ConfigParser(allow_no_value=False, empty_lines_in_values=False)
    # do not change the case of keys
    config.optionxform = lambda option: option
    config.read_dict({'timeline': {
            'Locale': 'C',
            'MainFile': 'timeline.tln',
            'FuzzySearchTolerance': 75,
            'FilterHistoryCount': 10,
            'FilterHistorySize': 100000000,
        }})
    config.read([
        '/etc/timeline.conf',
        Path('~/.config/timeline.conf').expanduser()
    ])
    # we care only about this one header
    config = config['timeline']
    # we can set the locale program-wide, because the only locale-dependent
    # thing we are doing are the days of the week
    locale.setlocale(locale.LC_TIME, config['Locale'])

    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true',
                        help='do not open filtered file in nvim')
    parser.add_argument('--file', type=str, default=config['MainFile'],
                        help='the .tln file the filter is called from. By '
                             'default, the file to be filtered will be '
                             'determined by the second line in the '
                             'corresponding syncfile.')
    parser.add_argument('--ignore-parent', action='store_true',
                        help='filter the file given by --file even if it was '
                             'created as a filter result')
    parser.add_argument('--parent-id', type=int, default=None,
                        help='kitty window id to be saved to the sync file')
    parser.add_argument('find', nargs='*',
                        help='the search term to search for')
    args = parser.parse_args()
    find = ' '.join(args.find) or input('Enter filter phrase: ')
    print(args, find, sep='\n')

    # split into lines, strip leading and trailing whitespace and join with
    # spaces - this procedure makes a line from an indented paragraph
    find = ' '.join(map(str.strip, find.split('\n')))
    # get the path of the file to filter
    main_file = get_main_file(args.file, args.ignore_parent)
    tmp_file_basename = f'{get_tmp_file()}{find}'

    with (open(main_file, 'r') as file_in,
          open(f'{tmp_file_basename}.tln', 'w') as file_out,
          open(f'{tmp_file_basename}.sync', 'w') as file_sync):
        filter_ = Filter(find, config.getint('FuzzySearchTolerance'))
        filter_.filter(file_in)
        # insert a heading to the top
        print(f'-- {find}', file=file_out)
        print('-' * (len(find) + 6), file=file_out)
        # if supplied, print an id of the parent kitty window to the syncfile
        print(args.parent_id if args.parent_id is not None else '',
              file=file_sync)
        # print the name of the parent file to the second line of the syncfile
        print(main_file, file=file_sync)
        # print the description lines under the heading
        for entry in filter_.descriptions:
            print(f'-- {entry.name} = {entry.description}', file=file_out)
            print(entry.linenumber, file=file_sync)
        # divide by an empty line, keeping the sync file synchronized
        print(file=file_out)
        print(file=file_sync)
        # print the filtered timeline
        print(filter_.buffer_out.getvalue(), end='', file=file_out)
        print(filter_.buffer_sync.getvalue(), end='', file=file_sync)

    prune_cache(
        config.getint('FilterHistoryCount'),
        config.getint('FilterHistorySize'),
        tmp_file_basename
    )

    if not args.debug:
        # TIMELINE_INSTALL_DIR is a token that will be substituted by sed during
        # install time
        os.system(f"nvim -R -u TIMELINE_INSTALL_DIR/lib/timeline/nvim.config '{tmp_file_basename}.tln'")


if __name__ == '__main__':
    main()
