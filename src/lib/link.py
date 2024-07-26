#!.code/venv/bin/python
import argparse
import linecache
import subprocess
import pathlib


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('line', type=int)
    parser.add_argument('column', type=int)
    args = parser.parse_args()

    path_tln = pathlib.Path(args.filename)
    path_sync = path_tln.with_suffix('.sync')
    try:
        source_line = int(linecache.getline(str(path_sync), args.line).strip())
    except ValueError:
        # the sync file doesn't exist or the particular line doesn't have a link
        return
    try:
        parent_window_id = int(linecache.getline(str(path_sync), 1).strip())
    except ValueError:
        # no parent window id is supplied, open the timeline in new tab
        subprocess.run(
            f"kitten @ launch --type=tab --title=timeline --cwd=current "
            f"--hold timeline '+call cursor({source_line}, {args.column})'",
            shell=True
        )
        # todo: print the id of the opened window into syncfile for subsequent
        #  linking
    else:
        # return vim in parent window to normal mode if not already there and
        # then move cursor to the linked position
        subprocess.run(f"kitten @ send-text --match id:{parent_window_id} "
                       f"'\e{source_line}G{args.column}|'",
                       shell=True)
        # switch to the tab containing the parent window
        subprocess.run(f"kitty @ focus-window --match id:{parent_window_id}",
                       shell=True)


if __name__ == '__main__':
    main()
