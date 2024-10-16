# About

timeline is an editor and analyzer for structured chronological notes, refered
to as `timelines`. 

# Syntax

A a general rule, a leading or trailing whitespace, as well as excessive
whitespace between parts of a command, is ignored. Whenever a line contains
`--`, any string after that is also ignored.

The basic unit of the file is a `note`, which is defined to be a maximal
sequence of consecutive lines which are neither of the following special
commands:

- `empty`: an empty line is a delimiter between consecutive notes, or just a
  visual element if it is not between two consecutive notes.
- `date`: a line beginning with `#` has to contain at most 3 strings delimited
  by `.`. Each string must be an integer, empty or `?` (whitespace is ignored,
  as usual). Negative values, empty string and `?` are aliases of `0`. The
  integers represent day, month and year, respectively. If any of the numbers
  is `0`, it is implied that this value is the same as the corresponding value
  in the previous date, inductively. This may leave the value undefined.The
  dates are required to appear in consecutive order (i.e. lexicographical, but
  ignoring undefined values).
- `block enter`: A line beginning with `>` enters a block, more about them in
  the next subsection.
- `block leave`: A line beginning with `<` leaves a block.
- `description`: A line beginning with `=` is split at `=` into several
  strings, let us denote them `{0}`, `{1}`, `{n}` for `n >= 0`. The string
  `{0}` must be nonempty, then the description is equivalent with this empty
  block:

`> {0} = {1} = {...} = {n}
<`

- `ellipse`: a literal `...` stands for an omitted information. Notice that a
  presence or absence of an ellipse carries an information.

## Blocks

Blocks can be used to group several consecutive notes together based on some
common metadata. Typical examples are notes from a single dialog, location or
process. The blocks create a structure which is respected during filtering.

A block-entering line has the following syntax (`{foo}` are placeholders,
`[foo]` denotes optional parts):

`>[{type}] {name}[={description1}[={description2}{...}]]`

Here `{type}` is meant to indicate a type of the block (i.e. whether it
corresponds to a conversation, location etc.) For historical reasons, `{type}`
has to be 1 character. This restriction is likely to be removed. 

`{name}` has to be nonempty, and is meant to indicate the precise reason why
the notes inside are grouped (i.e. name of the interviewed person, name of the
location etc.)

The optional `{description?}` entries are meant to hold additional information
about `{name}` (e.g. the appearance or occupation of the person).

The blocks can be partially interleaved with no firm structure, as opposed to
the rigid tree-like structure of the code blocks of most programming languages.
Therefore, a block-leaving command doesn't have to leave the last open block.
Its syntax is similar to the syntax of block-enter:

`>[{type}][ {name}]`

Such command can match a block-enter with the same type (if provided) and name
(if provided). Of those, the most recent one is matched. If there are none, a
syntax error is raised.

# Operations

The following keybindings are defined. Each of those siletly saves
the current file before doing anything.
- `<C-s>s` in Visual mode filters the timeline according to the current visual
  selection. Selecting a line break leads to undefined behaviour.
- `<C-s>s` in Normal mode selects the word under cursor and filters the
  timeline according to that.
- `<C-s>q` in any mode filters according to a user-supplied string.
- `<C-s>l` in any mode lists all relevant structure elements. This can
  abstracty be described as running a filter such that only the line under te
  cursor is matched, and then omitting all ellipses and the line under the
  cursor from the result.
- `<C-s>d` in any mode scans the file for the last date before the cursor. Then
  it attempts to increase it by one day and puts the result on the cursor
  location.

When viewing a filter result, there is one special operation.
- `<C-z>` in any mode attempts to switch to the tab with the input file for the
  filter operation (its so-called `parent file`). If it cannot find such tab,
  it creates a new tab and opens the parent file there. In either case, it
  moves the cursor to the first line of the element(s) which corespond to the
  line under the cursor in the filter result.

## Filtering

Filtering can be started by several shortcuts. Each time, there is some input
prompt, which we shall denote `{find}`. The filter script reads the timeline
and searches for `{find}` in each:
- `note`, which is first transformed into a one-line string
- `date`, which is first transformed into a canonical form
  `# DD.MM.YYYY --WEEKDAY`
- `block-enter`
- `description`

The search is performed using `thefuzz.fuzz.partial_ratio()` and its tolerance can be customized (see Configuration).

This procedure selects some elements, which will be included in the output.
However, each selected element is bound to some other elements collectively
called `context`. The final output then consists of the context of each
selected element (in chronological order, of course) together with an ellipsis
in the place of each sequence of consecutive elements left out from the output,
with one exception: if such sequence consists only of dates or empty lines, an
ellipsis isn't generated.

- Each element includes the delimiters of all blocks it is located in in its
  context.
- Each element except `date` includes the previous date, if any, in its
  context.
- `block-enter` includes the corresponding `block-leave` and every element the
  block contains in its context.

Additionally, a header is inserted at the beginning of the output. Whenever the
`{name}` of a `block-enter` or `description` matched, the corresponding
`{description?}` strings are included in the header for quick reference.

The output of the filtering procedure is saved to a temporary file, which is
then opened in nvim in new terminal tab.

# Configuration

timeline can be configured using configuration files `/etc/timeline.conf`,
`~/.config/timeline.conf` and  `./timeline.conf`, which are read in order and
configuration options overwrite the options set in previous files. The
configuration uses Python's `ini` format. All options should be under
`[timeline]` header. The following options are available (listed with their
default values):
- `MainFile = timeline.tln`: the file to open when `timeline` is invoked
  without arguments.
- `FuzzySearchTolerance = 75`: the tolerance of the fuzzy matching during the
  filtering. `0` causes everything to match, `100` requires perfectly matching
  substring.
- `Locale = C`: the locale to use when assigning weekdays to dates. See the
  documentation of `locale.setlocale()` for details.
- `FilterHistoryCount = 10`: the maximum number of filter results to store in
  the result cache. Values below `1` act like `1`.
- `FilterHistorySize = 100000000`: the maximum number of bytes worth of files
  in the cache. The most current result is kept regardless of its size.

