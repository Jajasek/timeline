#!/usr/bin/env python
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from math import inf
from typing import Iterable, TypeAlias
from itertools import repeat, chain
import datetime

from config import config


def get_indent(line: str) -> int:
    return len(line) - len(line.lstrip(' '))


class LineParsingError(Exception):
    pass


class StructureError(Exception):
    pass


class ExtendedInt(float):
    """
    Element of the set of integers, extended with 󰦒∞. We consider this set to be
    only linear order, the ring and metric structure should be considered
    to be undefined.
    """
    _convert_store = {
            '': 0,
            '?': 0,
            'oo': inf,
            '∞': inf,
            'inf': inf,
            '-oo': -inf,
            '-∞': -inf,
            '-inf': -inf,
        }
    _convert_print = {
        inf: '∞',
        -inf: '-∞',
        0: '?',
    }

    def __new__(cls, value):
        """
        Construct new ExtendedInt instance from given value. The value is
        converted using int, unless it is one of the following aliases:
            ? -> 0
            oo, inf -> ∞
            -oo, -inf -> -∞
        If the value is a string, it is stripped of leading and trailing
        whitespace before conversion.
        """
        if isinstance(value, str):
            value = value.strip()
        value = cls._convert_store.get(value, int(value))
        return float.__new__(ExtendedInt, value)

    def __repr__(self):
        return self._convert_print.get(self, None) or repr(int(self))

    def __str__(self):
        return repr(self)

    def __bool__(self):
        """
        Test if the value is finite positive integer, because then it defines
        date in standard way.
        """
        return 1 <= self < inf


DateElement: TypeAlias = ExtendedInt | str | int
"""
The type of each number in a date. When passed into the constructor of Date,
it is always converted to ExtendedInt as the standard representation.
"""


class Syntax:
    COMMENT = '#'
    DATE = '@'
    DATE_DELIMITER = '.'
    ENTER = '>'
    LEAVE = '<'
    DESCRIPTION = '='
    DESCRIPTION_DELIMITER = '='
    ELLIPSE = '...'
    LIST_TYPE = '-'
    ITEM = '-'


@dataclass(slots=True)
class Element:
    linenumber: int

    def get_sync(self) -> str:
        return str(self.linenumber)

    def get_indent(self) -> int:
        return 0


@dataclass(slots=True)
class Empty(Element):
    line: str

    def __str__(self) -> str:
        return self.line


@dataclass(slots=True)
class Ellipse(Empty):
    line: str = Syntax.ELLIPSE

    def get_indent(self) -> int:
        return get_indent(self.line)


@dataclass(slots=True)
class Spaced(Element):
    empty_line: Empty | None


@dataclass(slots=True)
class Date(Spaced):
    # the line in file_in where the date appeared
    linenumber: int = 0
    empty_line: Empty | None = None
    day: DateElement = 0
    month: DateElement = 0
    year: DateElement = 0
    indent: int = 0
    day_of_week: str | None = field(default=None, init=False)

    def __post_init__(self):
        self.day = ExtendedInt(self.day)
        self.month = ExtendedInt(self.month)
        self.year = ExtendedInt(self.year)

    def get_day_of_week(self) -> str:
        if self.day_of_week is None:
            date = (self.year, self.month, self.day)
            if all(date):
                self.day_of_week = (f' {Syntax.COMMENT}'
                                    f' {datetime.date(*date).strftime("%A")}')
            else:
                self.day_of_week = ''
        return self.day_of_week

    def __gt__(self, other):
        if not isinstance(other, Date):
            return NotImplemented
        # 14.3. › 3.3.
        # ?.?.2000 > ?.?.1999
        # ?.?.2000 > 31.12.?
        pairs = (
            (self.year, other.year),
            (self.month, other.month),
            (self.day, other.day),
        )
        for s, o in pairs:
            if s > o:
                return True
            if 0 < s < o:
                return False
        return False

    def __str__(self):
        return ''.join(map(str, (
            ' ' * self.indent,
            Syntax.DATE,
            ' ',
            self.day,
            Syntax.DATE_DELIMITER,
            self.month,
            Syntax.DATE_DELIMITER,
            self.year,
            self.get_day_of_week(),
        )))

    def update(self, other: 'Date', keep_empty_line: bool = False) -> 'Date':
        """Return 'union' of dates, where 'other' is taking precedence"""
        return Date(
            other.linenumber,
            # here it is maybe a bit more intuitive to give self precedence
            (keep_empty_line and self.empty_line) or other.empty_line,
            other.day or self.day,
            other.month or self.month,
            other.year or self.year,
            other.indent
        )

    def get_indent(self) -> int:
        return self.indent

    def tomorrow(self) -> 'Date':
        date = (self.year, self.month, self.day)
        if all(date):
            tomorrow = datetime.date(*date) + datetime.timedelta(1)
            out = Date(0, None, tomorrow.day, tomorrow.month, tomorrow.year)
            out.day_of_week = f' {Syntax.COMMENT} ' + tomorrow.strftime('%A')
            return out
        out = Date().update(self)
        out.day_of_week = f' {Syntax.COMMENT} UNABLE TO INCREMENT'
        return out

    def __repr__(self) -> str:
        return ''.join(map(str, (
            self.linenumber,
            '|',
            Syntax.DATE,
            ' ',
            self.day,
            Syntax.DATE_DELIMITER,
            self.month,
            Syntax.DATE_DELIMITER,
            self.year,
        )))


@dataclass(slots=True)
class Dated(Spaced):
    date: Date
    line: str

    def __str__(self) -> str:
        return self.line

    def get_indent(self) -> int:
        return get_indent(self.line)


@dataclass(slots=True)
class Description(Dated):
    name: str
    descriptions: Iterable[str]

    def __post_init__(self):
        self.descriptions = tuple(self.descriptions)

    def __repr__(self):
        return f'{self.linenumber}|{Syntax.DESCRIPTION} {self.name}' + ''.join(
            (f' {Syntax.DESCRIPTION_DELIMITER} ' + d for d in self.descriptions)
        )


@dataclass(slots=True)
class Block(Dated):
    type: str
    name: str


@dataclass(slots=True)
class Enter(Block):
    descriptions: Iterable[str]
    printed: bool = field(default=False, init=False)
    # set if a corresponding Leave was found, but cannot be printed because
    # of interleaved blocks. Prevents matching this Enter to another Leave.
    waiting: bool = field(default=False, init=False)
    # list of linenumbers of Leaves that are waiting for this BlockEnter to
    # be resolved - either by printing it because of a matched element inside,
    # or by leaving without a match and without any other unresolved interleaved
    # block. When this BlockEnter is resolved, the BlockLeaves waiting for it
    # are checked.
    waited_by: list['Leave'] = field(default_factory=list, init=False)

    def __post_init__(self):
        self.descriptions = tuple(self.descriptions)

    def __repr__(self):
        return (
            f'{self.linenumber}|{Syntax.ENTER}{self.type} {self.name}'
            + ''.join(
                (f' {Syntax.DESCRIPTION_DELIMITER} ' + d
                 for d in self.descriptions)
            )
        )


@dataclass(slots=True)
class Leave(Block):
    # the linenumber of Enter it has been matched to
    linenumber_enter: int = field(default=0, init=False)
    # set of linenumbers of interleaved Enters this block is waiting for
    # to be resolved - either by printing them because of a matched element
    # inside, or by leaving without a match and without any other unresolved
    # interleaved block.
    waiting_for: set[int] = field(default_factory=set, init=False)

    def __repr__(self):
        return f'{self.linenumber}|{Syntax.LEAVE}{self.type} {self.name}'


@dataclass(slots=True)
class Note(Dated):
    # is actually a string - consecutive linenumbers delimited by newlines
    linenumber: int
    searchable: str = field(default='', init=False)
    _last_linenumber: int = field(init=False)
    _sync: str = field(init=False)

    def __post_init__(self) -> None:
        self._last_linenumber = self.linenumber
        # noinspection PyTypeChecker
        self._sync = str(self.linenumber)
        self.searchable = self.line

    def add_line(self, line: str) -> None:
        self.line += '\n' + line
        self.searchable += ' ' + line
        self._last_linenumber += 1
        self._sync += '\n' + str(self._last_linenumber)

    def get_sync(self) -> str:
        return self._sync

    def __repr__(self) -> str:
        return ''.join(chain(*zip(
            self._sync.split('\n'), repeat('|'),
            self.line.split('\n'), repeat('\n')
        )))[:-1]


class Item(Note):
    pass


class Traverser:
    def __init__(self) -> None:
        # Keys are linenumbers - in the future, when more enter/leave commands
        # on single line are supported, the keys may become tuples (linenumber,
        # index).
        # When a match is found inside the block, the block has to be
        # printed - then the 'printed' flag is set, preventing it to be printed
        # again and indicating that the leaving line has to be printed, too.
        self.blocks: dict[int, Block] = {}
        # last encountered date
        self.date: Date = Date()
        # The following flag is reset each time an element other than
        # the empty line and date is encountered.
        self.empty_line: Empty | None = None
        self.last_parsed: Spaced | None = None

    def get_empty_line(self) -> Empty | None:
        out = self.empty_line
        self.empty_line = None
        return out

    def traverse(self, file_in: Iterable[str], max_lines: int = -1) -> None:
        for element in self.parse_lines(file_in, max_lines):
            if isinstance(element, Empty):
                self.empty_line = self.empty_line or element
                # don't save Empty as last parsed element, we aren't interested
                # in that
                continue
            elif isinstance(element, Date):
                # check chronology
                if not element > self.date:
                    raise StructureError(
                        element.linenumber, f'new date {element} is not after'
                                            f' {self.date}')
                self.handle_date(element)
            elif isinstance(element, Enter):
                self.handle_enter(element)
                self.blocks[element.linenumber] = element
            elif isinstance(element, Leave):
                self.block_leave(element)
            elif isinstance(element, Description):
                self.handle_description(element)
            elif isinstance(element, Note):
                self.handle_note(element)
            self.last_parsed = element

    def parse_lines(self, file_in: Iterable[str], max_lines: int)\
            -> Iterator[Element]:
        note: Note | None = None
        for linenumber, line in enumerate(file_in, 1):
            if linenumber == max_lines:
                # Traverse only lines above cursor, not including the line
                # under cursor. This makes closing blocks easier.
                break
            # strip the trailing newline and whitespace
            line = line.rstrip()
            # throw off comment
            if (comment_index := line.find(Syntax.COMMENT)) != -1:
                line = line[:comment_index]
            # from now on, line is left unchanged and is passed to the resulting
            # element as its string representation.
            processed_line = line.lstrip()

            def startswith(prefix: str) -> bool:
                nonlocal processed_line
                if processed_line.startswith(prefix):
                    processed_line = processed_line[len(prefix):]
                    return True
                return False

            def yielder(to_yield: Element | None = None) -> Iterator[Element]:
                nonlocal note
                if note:
                    yield note
                    note = None
                if to_yield is not None:
                    yield to_yield

            if not processed_line:
                yield from yielder(Empty(linenumber, line))
            # date
            elif startswith(Syntax.DATE):
                numbers = processed_line.split(Syntax.DATE_DELIMITER)
                if len(numbers) > 3:
                    raise LineParsingError(linenumber, line,
                                           'incorrect date format')
                # add zeros such that there are 3 values
                yield from yielder(
                    Date(linenumber, self.get_empty_line(), *numbers,
                         *([0] * (3 - len(numbers))), get_indent(line))
                )
            # enter
            elif startswith(Syntax.ENTER):
                first_space = (processed_line + ' ').find(' ')
                block_type = processed_line[:first_space]
                splitted = map(str.strip, processed_line[first_space:].split(
                    Syntax.DESCRIPTION_DELIMITER
                ))
                yield from yielder(
                    Enter(linenumber, self.get_empty_line(), self.date, line,
                          block_type, next(splitted, ''), splitted)
                )
            # leave
            elif startswith(Syntax.LEAVE):
                first_space = (processed_line + ' ').find(' ')
                yield from yielder(
                    Leave(linenumber, self.get_empty_line(), self.date, line,
                          processed_line[:first_space],
                          processed_line[first_space:].strip())
                )
            # description
            elif startswith(Syntax.DESCRIPTION):
                # split by '=', strip each part
                splitted = map(
                    str.strip,
                    processed_line.split(Syntax.DESCRIPTION_DELIMITER)
                )
                yield from yielder(
                    Description(linenumber, self.get_empty_line(), self.date,
                                line, next(splitted, ''), splitted)
                )
            elif processed_line.startswith(Syntax.ITEM) and self.inside_list():
                yield from yielder()
                note = Item(linenumber, self.get_empty_line(), self.date, line)
            elif processed_line == Syntax.ELLIPSE:
                self.empty_line = None
                yield from yielder(Ellipse(linenumber, line))
            elif note:
                note.add_line(line)
            else:
                note = Note(linenumber, self.get_empty_line(), self.date, line)

    def inside_list(self) -> bool:
        for block in reversed(self.blocks.values()):
            if isinstance(block, Enter) and self.block_match(
                    block,
                    Leave(sys.maxsize, None, self.date, Syntax.LEAVE, '', '')
            ):
                return block.type.startswith(Syntax.LIST_TYPE)
        return False

    def handle_date(self, date: Date) -> None:
        # update date
        self.date = self.date.update(date)

    def handle_enter(self, enter: Enter) -> None:
        pass

    def block_leave(self, leave: Leave) -> None:
        # Walk through self.blocks in reverse, searching for the first matching
        # non-waiting Enter. If another non-waiting not printed Enter
        # was encountered, save the Leave, mark the block as waiting and
        # return None. In other case, remove the corresponding Enter and
        # resolve eventual waiting blocks.
        for block in reversed(self.blocks.values()):
            if not isinstance(block, Enter):
                continue
            if self.block_match(block, leave):
                self.handle_leave_matched(leave, block)
                return
            self.handle_leave_nonmatched(leave, block)
        raise StructureError(leave.linenumber, leave.line,
                             'No such block is open')

    @staticmethod
    def block_match(enter: Enter, leave: Leave) -> bool:
        if enter.waiting:
            return False
        if (leave.name and re.search(
                leave.name, enter.name,
                re.NOFLAG if config.CaseSensitiveLeave else re.IGNORECASE
        ) is None):
            return False
        if leave.type and enter.type != leave.type:
            return False
        return True

    def handle_leave_matched(self, leave: Leave, enter: Enter) -> None:
        del self.blocks[enter.linenumber]

    def handle_leave_nonmatched(self, leave: Leave, enter: Enter) -> None:
        pass

    def handle_description(self, description: Description) -> None:
        pass

    def handle_note(self, note: Note) -> None:
        pass
