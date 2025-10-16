import sys
import argparse
import json

def main():
    args = parse_arguments()
    try:
        with open(args['path']) as file:
            content = file.read()
    except FileNotFoundError:
        sys.stderr.write(f"Could not find {args['path']}. Creating it.")
        with open(args['path'], 'w') as file:
            file.write('[]')
        content = "[]"
    if args['action'] == 'read':
        sys.stdout.write(content)
        sys.exit(0)
        return
    # Convert both file content and the passed json_entry to dicts for easier processing and consistent formatting
    try:
        content_list = json.loads(content)
    except json.JSONDecodeError:
        sys.stderr.write(f"Decode error. {args['path']} seems to not be a valid JSON file.")
        sys.exit(1)
        return
    if type(content_list) != list:
        sys.stderr.write(f"Content of {args['path']} is not a list after loading it. This is unexpected. Not changing anything.")
        sys.exit(1)
        return
    if args['action'] == 'delete':
        content_list.pop(args['entry_index'])
    else:
        try:
            entry_dict = json.loads(args['json_entry'])
        except json.JSONDecodeError:
            sys.stderr.write(f"JSON entry in argument could not be parsed. Doing nothing.")
            sys.exit(1)
            return
        if args['action'] == 'write':
            if args['entry_index']:
                content_list.insert(args['entry_index'], entry_dict)
            else:
                content_list.append(entry_dict)
        elif args['action'] == 'update':
            content_list[args['entry_index']] = entry_dict
        else:
            raise NotImplementedError(f"action argument {args['action']} unknown.")
    with open(args['path'], 'w') as file:
        json.dump(content_list, file, indent=4)
    sys.exit(0)
    return


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--path',
        help='Path to the user profile JSON. Must always be supplied.',
        type=str,
        required=True,
    )
    parser.add_argument(
        '--action',
        help='Select this program`s operation: read all JSON entries, write given entry, or delete given entry. Must always be supplied.',
        choices=['read', 'write', 'delete', 'update'],
        required=True,
    )
    parser.add_argument(
        '--entry_index',
        help='Integer containing the index of the profile to change. Mandatory for `update` and `delete`, optional for `write`, ignored for `read`.',
        type=int,
        default=None,
    )
    parser.add_argument(
        'json_entry',
        help='String containing a simple JSON formatted entry to write or update in the file. Silently ignored for `read` and `delete`.',
        nargs='?',
        default='',
    )
    args = parser.parse_args()
    if args.action in {'write', 'update'} and args.json_entry == '':
        sys.stderr.write("Cannot process writes or updates without data element to write.")
        sys.exit(1)
        return
    if args.action in {'update', 'delete'} and args.entry_index is None:
        sys.stderr.write("Cannot process updates or deletes without a target.")
        sys.exit(1)
        return
    # We want to return a dict-like argument representation, which is why vars(...) is necessary (see argparse documentation)
    return vars(parser.parse_args())


if __name__ == "__main__":
    main()
