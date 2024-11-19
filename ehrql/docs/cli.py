import argparse

from ehrql.__main__ import (
    USER_ARGS_HELP,
    USER_ARGS_NAME,
    USER_ARGS_USAGE,
    create_parser,
)


def build_cli():
    parser = create_parser(user_args=[], environ={})
    return {
        "description": parser.description,
        "argument_groups": get_argument_groups(parser, options_first=True),
        "subcommands": get_subcommands(parser),
    }


def get_argument_groups(parser, options_first=False):
    groups = [
        {
            "name": group.title,
            "description": group.description,
            "arguments": [get_argument(action) for action in group._group_actions],
        }
        for group in parser._action_groups
    ]
    if "user_args" in parser._defaults:
        groups.append(
            {
                "name": "user_args",
                "description": None,
                "arguments": [
                    {
                        "id": "user_args",
                        "usage_short": f"[{USER_ARGS_USAGE}]",
                        "usage_long": USER_ARGS_NAME,
                        "description": USER_ARGS_HELP,
                    }
                ],
            }
        )
    if options_first:
        groups = sorted(
            groups, key=lambda group: 0 if group["name"] == "options" else 1
        )
    return groups


def get_argument(action):
    if isinstance(action, argparse._HelpAction | argparse._VersionAction):
        return {
            "id": action.dest,
            "usage_short": f"[{action.option_strings[-1]}]",
            "usage_long": ", ".join(action.option_strings),
            "description": action.help,
        }
    elif isinstance(action, argparse._StoreAction) and action.nargs == "?":
        return {
            "id": action.dest,
            "usage_short": f"[{action.dest.upper()}]",
            "usage_long": action.dest.upper(),
            "description": action.help,
        }
    elif isinstance(action, argparse._StoreAction) and not action.required:
        return {
            "id": action.option_strings[-1].lstrip("-"),
            "usage_short": f"[{action.option_strings[-1]} {action.dest.upper()}]",
            "usage_long": f"{', '.join(action.option_strings)} {action.dest.upper()}",
            "description": action.help,
        }
    elif isinstance(action, argparse._StoreAction) and action.required:
        return {
            "id": action.dest,
            "usage_short": action.dest.upper(),
            "usage_long": action.dest.upper(),
            "description": action.help,
        }
    elif isinstance(action, argparse._SubParsersAction):
        return {
            "id": "command_name",
            "usage_short": "COMMAND_NAME ...",
            "usage_long": "COMMAND_NAME",
            "description": action.help,
            "subcommands": [
                {"name": sa.metavar, "description": sa.help}
                for sa in action._get_subactions()
            ],
        }
    else:
        assert False, f"Unhandled arg type: {action}"


def get_subcommands(parser):
    subparsers = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    assert (
        len(subparsers) == 1
    ), f"Expected exactly one subcommand parser, got: {subparsers}"
    subparser = subparsers[0]
    return [
        get_subcommand(action, subparser.choices[action.metavar])
        for action in subparser._get_subactions()
    ]


def get_subcommand(action, parser):
    return {
        "id": action.metavar,
        "name": action.metavar,
        "description": action.help,
        "argument_groups": get_argument_groups(parser),
    }
