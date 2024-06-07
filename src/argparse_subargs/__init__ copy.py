"""
# argparse_subargs

Parse parameter lists in argparse arguments, e.g. --arg sub1 sub2=val ...

  - On PyPI: https://pypi.org/project/argparse-subargs/
  - On GitHub: https://github.com/v-r-b/argparse_subargs

This module defines:

```class SubargParser```
  
Parser for structured sub-arguments of argparse arguments. The subarguments
can be positional arguments or keyword-arguments, e.g.:
myprog.py --print Welcome Message name=Michael role=brother

```class SubargAction```
  
Action class to be used with a SubargParser instance. To do so, use arguments
action=SubargAction and subarg_parser=<SubargParser instance> when calling
add_parameter() method of ArgumentParser.

```class SubargHelpFormatter```
  
Formatter for help when using action=SubargAction in add_parameter()
of ArgumentParser.

```class SubargHelp```
  
Structured storage for help texts for subargs
"""

from dataclasses import dataclass
import sys
from argparse_subargs.xargparse import Action, _AppendAction, ArgumentError, ArgumentParser
from argparse_subargs.xargparse import HelpFormatter, Namespace, ZERO_OR_MORE
from argparse_subargs.xargparse import _copy_items # type: ignore
from typing import Any, Sequence

@dataclass
class SubargHelp:
    """ Structured storage for help texts for subargs """
    pos_args_help: dict[str, str]|None = None
    """ Help text for positional subargs in the form name:text """
    kw_args_help: dict[str, str]|None = None
    """ Help text for keyword subargs in the form name:text """

class SubargParser:
    """ Parser for structured sub-arguments of argparse arguments. The subarguments
    can be positional arguments or keyword-arguments, e.g.:
      myprog.py --print Welcome Message name=Michael role=brother

    Using a SubargParser(["W1", "W2"], ["name", "role"]) instance and calling
    parse_subargs() on the arguments to --print, a list of namespace
    objects is returned. In this example we would get [Namespace(W1='Welcome',
    W2='Message', name="Michael", role="Brother")]

    SubargParser objects are to be passed to a SubargAction instance using
    action=SubargAction and subarg_parser=<SubargParser instance> when calling
    add_parameter() method of ArgumentParser.

    Raises:
        TypeError, ArgumentError: see method descriptions
    """

    EXC_POS_SUBARGS_FIELD = "excess_pos_subargs"
    EXC_KW_SUBARG_NAMES_FIELD = "excess_kw_subarg_names"

    def __init__(self, *, pos_args: Sequence[str] = [], kw_args: Sequence[str|tuple[str, bool]] = [], 
                 num_mandatory_pos_args: int = -1, allow_excess_ags: bool = True, subarg_help: SubargHelp = SubargHelp(),
                 parser: ArgumentParser|None = None, arg_name: str|None = None) -> None:
        """ Constructor. Stores parameter values. The entries of the sequences are copied into
        internal lists. Entries to kw_args can either be strings or tuples (mixing is allowed).
        If tuples are used, the first entry is the name of the subarg, the second entry denotes
        whether the argument is mandatory or not (default: False). Positional arguments are
        mandatory by default. Optional positional arguments are possible by using num_mandatory_pos_args.

        Args:
            pos_args (Sequence[str], optional): Names of positional sub-arguments. Defaults to [].
            kw_args (Sequence[str | tuple[str, bool]], optional): List of keywowd sub-arguments (see above). Defaults to [].
            num_mandatory_pos_args (int, optional): Number of mandatory positional arguments. Defaults to -1 (= all).
            allow_excess_ags (bool, optional): Allows additional arguments to those in the lists. Defaults to True.
            subarg_help (SubargHelp, optional): Help texts for the subargs
            parser (ArgumentParser | None, optional): May be set by SubargAction. Defaults to None.
            arg_name (str | None, optional): Name of the argument to which the subargs belong. May be set by SubargAction. Defaults to None.

        Raises:
            TypeError: if an entry in pos_args is not of type str
            TypeError: if an entry in kw_args is not of type str|tuple[str, bool]
        """
        # copy pos_args
        self._pos_args: list[str] = []
        for parg in pos_args:
            if isinstance(parg, str):
                self._pos_args.append(parg)
            else:
                raise TypeError(f"argument must be of type str "
                                f"but is of type {type(parg)}")
        self._num_mandatory_pos_args = num_mandatory_pos_args

        # copy kw_args
        self._kw_args: list[str] = []
        self._kw_args_mandatory: list[bool] = []
        # kw arguments are optional by default
        for kwarg in kw_args:
            if isinstance(kwarg, tuple):
                self._kw_args.append(kwarg[0])
                self._kw_args_mandatory.append(kwarg[1])
            elif isinstance(kwarg, str):
                self._kw_args.append(kwarg)
                self._kw_args_mandatory.append(False)
            else:
                raise TypeError(f"argument must be of type str|tuple[str, bool] "
                                f"but is of type {type(kwarg)}")

        self._allow_excess_args: bool = allow_excess_ags

        # parser and arg_name may be set by AppendOptAction object
        self._parser = parser
        self._arg_name = arg_name
        self._subarg_help = subarg_help

    def get_metavar_str(self) -> str:
        """ Get a string for use with metavar= parameter of ArgumentParser's add_arguments() method.
        The string is constructed from the information passed to the constructor (subarg lists
        and allow_excess_args)

        Returns:
            str: String for a proper metavar description
        """
        # if we have no subarg information, return "..."
        if not self._pos_args and not self._kw_args:
            return "..."

        metavar = ""
        # positional arguments first
        l = len(self._pos_args)
        for i, arg in enumerate(self._pos_args):
            if i < self._num_mandatory_pos_args:
                # mandatory
                metavar += arg
            else:
                # optional
                metavar += "[" + arg + "]"
            if i < l-1:
                metavar += " "
        if self._pos_args and self._kw_args:
            metavar += " "

        # then, kw_args:
        l = len(self._kw_args)
        for i, arg in enumerate(self._kw_args):
            if self._kw_args_mandatory[i]:
                # mandatory
                metavar += arg + "=" + arg.upper()
            else:
                # optional
                metavar += "[" + arg + "=" + arg.upper() + "]"
            if i < l-1:
                metavar += " "
        
        if self._allow_excess_args:
            metavar += " [...]"
        return metavar
    
    def get_metavar_tuple(self) -> tuple:
        """ Get a tuple with all metavars. The tuple is constructed from the information 
        passed to the constructor (subarg lists and allow_excess_args)

        Returns:
            tuple: metavar tuple
        """
        metavar_tuple = tuple[str]()
        # see get_metavar_str()        
        for i, arg in enumerate(self._pos_args):
            if i < self._num_mandatory_pos_args:
                metavar_tuple += (arg, )
            else:
                metavar_tuple += ("[" + arg + "]", )
        for i, arg in enumerate(self._kw_args):
            if self._kw_args_mandatory[i]:
                metavar_tuple += (arg + "=" + arg.upper(), )
            else:
                metavar_tuple += ("[" + arg + "=" + arg.upper() + "]", )
        if self._allow_excess_args:
            metavar_tuple += ("[...]", )
        return metavar_tuple

    def _arg_message(self, message: str) -> str:
        """ If self._arg_name is not None, prepend message with "[<arg_name>]" and return it.
        Otherwise return unchanged message string. 

        Args:
            message (str): arbitrary message string

        Returns:
            str: "extended" message string; see above
        """
        if self._arg_name:
            return "[" + self._arg_name + "] " + message
        else:
            return message

    def _error(self, message: str) -> None:
        """ Print error message using _arg_message(message).
        If self._parser is set and self._parser._exit_on_error is True, use parser's error() method,
        else print error to stderr and exit with exit code 2.

        Args:
            message (str): _description_
        """
        if self._parser and self._parser.exit_on_error: # type: ignore
            self._parser.error(self._arg_message(message))
        else:
            print(self._arg_message(message), file=sys.stderr)
            sys.exit(2)

    def parse_subargs(self, args: Sequence[str]) -> Namespace:
        """ Parse command line subargs against the lists passed to the constructor,
        regarding the values of allow_excess_arguments and num_mandatory_pos_arguments.
        If allow_axcess_arguments is True, then within the returned namespace,
         - values of excess positional arguments are reported in EXC_POS_SUBARGS_FIELD
         - names of excess keyword arguments are reported in EXC_KW_SUBARG_NAMES_FIELD
        Otherwise an error is reported using the _error() method.

        Args:
            args (Sequence[str]): subargs from the command line

        Raises:
            ArgumentError: see _check_mandatory_args()

        Returns:
            Namespace: all positional and keyword arguments found.
        """
        ns = Namespace()
        pos_counter = 0
        excess_kw_arg_names: list[str] = []
        excess_pos_args: list[str] = []
        for arg in args:
            if arg.find("=") > 0:   # of type "x=y"
                kwarg = arg.split("=", 1)
                name = kwarg[0]
                value = kwarg[1]
                if name not in self._kw_args:
                    excess_kw_arg_names.append(name)
                setattr(ns, name, value)
            else:   # positional option
                if len(self._pos_args) > pos_counter:   # pos. argument expected
                    name = self._pos_args[pos_counter]
                    value = arg
                    setattr(ns, name, value)
                    pos_counter += 1
                else:   # too many positional arguments
                    excess_pos_args.append(arg)
        if excess_pos_args:
            if self._allow_excess_args:
                setattr(ns, SubargParser.EXC_POS_SUBARGS_FIELD, excess_pos_args)
            else:
                self._error(f"too many positional sub-args: {excess_pos_args}")
        if excess_kw_arg_names:
            if self._allow_excess_args:
                setattr(ns, SubargParser.EXC_KW_SUBARG_NAMES_FIELD, excess_kw_arg_names)
            else:
                self._error(f"too many keyword sub-args: {excess_kw_arg_names}")

        self._check_mandatory_args(ns)
        return ns
    
    def _check_mandatory_args(self, ns: Namespace) -> bool:
        """ Check, if all mandatory subargs could be found.

        Args:
            ns (Namespace): namespace object to check.

        Raises:
            ArgumentError: if there are to little mandatory  positional subarg
            ArgumentError: if there's a missing mandatory keyword subarg

        Returns:
            bool: _description_
        """
        for i in range(0, len(self._pos_args)):
            if self._num_mandatory_pos_args < 0 or i < self._num_mandatory_pos_args:
                if not hasattr(ns, self._pos_args[i]):
                    raise ArgumentError(None, 
                                        self._arg_message("Missing mandatory positional subarg ") + \
                                        str(self._pos_args[i]))
        for i in range(0, len(self._kw_args)):
            if self._kw_args_mandatory[i]:
                if not hasattr(ns, self._kw_args[i]):
                    raise ArgumentError(None,
                                        self._arg_message("Missing mandatory keyword subarg ") + \
                                        str(self._pos_args[i]))
        return True

class SubargAction(_AppendAction):
    """ Action class to be used with a SubargParser instance. To do so, use arguments
    action=SubargAction and subarg_parser=<SubargParser instance> when calling
    add_parameter() method of ArgumentParser. 
    The metavar=-argument to add_parameter() can be omitted: the appropriate string is
    constructed automatically by the SubargParser instance, if formatter=SubargHelpFormatter
    is passed to the constructor of the ArgumentParser.
    The nargs=-argument to add_parameter() should be omitted as well. In this case, the
    default value ZERO_OR_MORE in the constructor of SubargAction will be used.
    """
    def __init__(self, option_strings, dest, nargs=ZERO_OR_MORE, const=None, default=None, type=None,
                 choices=None, required=False, help=None, metavar=None,
                 subarg_parser: SubargParser|None = None) -> None:
        """ Constructor. Takes the same arguments as the superclass _AppendAction does
        plus one additional argument subarg_parser.
        Even though subarg_parser is marked as optional, it must be passed as an 
        argument to the constructor. This can be done by passing subarg_parser=... as
        an argument when calling parser.add_argument(...). Otherwise an exception is raised.

        Args:
            nargs: must be ZERO_OR_MORE ("*")
            subarg_parser (SubargParser): Parser instance to do the work. Must be passed.
            any other: see _AppendAction.__init__

        Raises:
            TypeError: if nargs is not ZERO_OR_MORE
            TypeError: if subarg_parser is missing or None
        """
        # Call superclass constructor with all arguments but subarg_parser
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar)
        if nargs != ZERO_OR_MORE:
            raise TypeError(f"{self.__class__.__name__}.__init__(): 'nargs' must be "
                            f"ZERO_OR_MORE ('{ZERO_OR_MORE}'), not '{nargs}'")
        if subarg_parser:
            self._subarg_parser = subarg_parser
            # store argument name in subarg_parser
            self._subarg_parser._arg_name = dest
        else:
            raise TypeError(f"{self.__class__.__name__}.__init__(): 'subarg_parser' must not be None")

    def __call__(self, parser: ArgumentParser, namespace: Namespace, 
                 values: str|Sequence[Any]|None, option_string: str|None=None) -> None:
        if self._subarg_parser:
            self._subarg_parser._parser = parser
            try:
                # parse subargs in argument "values"
                if isinstance(values, Sequence):
                    new_opts = self._subarg_parser.parse_subargs(values)
                else:
                    raise TypeError("Cannot parse values {values} of type {type(values)}")
                # adapted impl of super().__call__
                items = getattr(namespace, self.dest, None)
                items = _copy_items(items)
                # adaption: append opts (of type namespace) instead of values (of type list)
                items.append(new_opts) 
                setattr(namespace, self.dest, items)
            except BaseException as exc:
                if parser.exit_on_error: # type: ignore
                    parser.error(str(exc))
        elif parser.exit_on_error: # type: ignore
            parser.error("No valid SubargParser object found")
        else:
            print("No valid SubargParser object found", file=sys.stderr)
            sys.exit(2)

class SubargHelpFormatter(HelpFormatter):
    """ Formatter for help when using action=SubargAction in add_parameter()
    of ArgumentParser. 
    """
    def _format_args(self, action: Action, default_metavar: str) -> str:
        """ Format argument string in help message. If action is of type SubargAction,
        the string "{{ <metavar> }}" is returned. If <metavar> is not set by the
        user (as metavar=... in add_parameter()), call get_metavar_str() on the
        action's member _subarg_parser to get the right text.

        Args:
            all: see Action._format_args

        Returns:
            str: formatted argument string
        """
        get_metavar = self._metavar_formatter(action, default_metavar)
        if isinstance(action, SubargAction):
            metavar = get_metavar(1)
            # if metavar hasn't been set by the user, call subarg_parser:
            if metavar == (None,) or metavar == (action.dest.upper(),):
                metavar=(action._subarg_parser.get_metavar_str(),)
            return '{{ %s }}' % metavar
        else:
            return super()._format_args(action, default_metavar)

    def _get_help_string(self, action: Action) -> str|None:
        """ If action is of type SubargAction, construct help string from 
        action's help text plus help texts of the subargs. Else, return
        action's help text only using _get_help_string() of the superclass.

        Args:
            action (Action): parameter related Action instance

        Returns:
            str: help text containing newline characters
        """
        # use implemtation of superclass to get help text for action
        help = super()._get_help_string(action)
        # in case we have a SubargAction, use subarg_parser information
        if isinstance(action, SubargAction):
            if help is None:
                help = ""
            subarg_parser = action._subarg_parser
            if subarg_parser and subarg_parser._subarg_help:
                if subarg_parser._subarg_help.pos_args_help:
                    help += "\n-- positional subargs --"
                    for name, text in subarg_parser._subarg_help.pos_args_help.items():
                        help += f"\n  {name}: {text}"
                if subarg_parser._subarg_help.kw_args_help:
                    help += "\n-- keyword subargs --"
                    for name, text in subarg_parser._subarg_help.kw_args_help.items():
                        help += f"\n  {name}: {text}"
        return help
    
    def _split_lines(self, text: str, width: int) -> list[str]:
        """ Split text into separate parts using splitlines(),
        then wrap the parts separately to the given text width. Doing so,
        the newline characters will be preserved in the result.

        Args:
            text (str): help text that may contain newline characters
            width (int): line width for text wrapping

        Returns:
            list[str]: help text, linewise
        """
        # The textwrap module is used only for formatting help.
        # Delay its import for speeding up the common usage of argparse.
        import textwrap
        result = []
        # use newline character to split the text into its parts
        parts = text.splitlines()
        for text in parts:
            # format text and wrap it into lines of the given width
            text = self._whitespace_matcher.sub(' ', text).strip()
            result.extend(textwrap.wrap(text, width))
        return result
