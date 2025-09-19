import sys
import argparse
import json

def main():
    args = parse_arguments()
    try:
        with open(args['path']) as file:
            content = file.read()
    except FileNotFoundError:
        with open(args['path'], 'w') as file:
            file.write('[]')
        content = "[]"
        sys.stderr.write(f"Could not find {args['path']}. Creating it.")
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
        sys.stderr.write(f"Content of {args['path']} is not a list after loading it. This is not expected.")
        sys.exit(2)
        return
    entry_dict = json.loads(args['json_entry'])
    if args['action'] == 'write':
        content_list.append(entry_dict)
    elif args['action'] == 'delete':
        for index, element in content_list:
            if element == entry_dict:
                content_list.pop(index)
                break
        else:
            sys.stderr.write("Found no exact match for provided entry. Doing nothing.")
    with open(args['path'], 'w') as file:
        json.dump(content_list, file)
    sys.exit(0)
    return


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-p',
        '--path',
        help='Path to the user profile JSON. Must always be supplied.',
        type=str,
        required=True,
    )
    parser.add_argument(
        '-a',
        '--action',
        help='Select this program`s operation: read all JSON entries, write given entry, or delete given entry.',
        choices=['read', 'write', 'delete'],
        required=True,
    )
    parser.add_argument(
        'json_entry',
        help='String containing a simple JSON formatted entry to write to or delete from the file.',
        nargs='?',
        default='',
    )

if __name__ == "__main__":
    main()
