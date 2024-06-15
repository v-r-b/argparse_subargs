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
of ArgumentParser. Uses SubargHelpFormatterMixin and HelpFormatter
to do the actual work.

```class SubargHelpFormatterMixin```
  
Mixin for creating formatter classes for use with ArgumentParser
when SubargHelpFormatter is not suitable. This could, e.g., be
```
class MyDefaultsFormatter(
         SubargHelpFormatterMixin, 
         argparse.ArgumentDefaultsHelpFormatter)
    pass
```
```class PSubarg```
  
Positional subarg description with \_\_eq__ operator.

```class KWSubarg```
  
Keyword subarg description with \_\_eq__ operator.
"""

import sys
from dataclasses import dataclass, fields as dc_fields
from argparse import Action, _AppendAction, ArgumentError, ArgumentParser
from argparse import HelpFormatter, Namespace, ZERO_OR_MORE
from argparse import _copy_items # type: ignore
from typing import Any, Sequence

@dataclass
class PSubarg:
    """ Positional subarg description with \_\_eq__ operator.

    Args:
        name (str): parameter name
        help (str, optional): help text for parameter. Defaults to None.
    """
    name: str
    help: str|None = None

    def __eq__(self, other) -> bool:
        """ call _compare_subargs(self, other) and return result """
        return _compare_args(self, other)
    
@dataclass
class KWSubarg:
    """ Keyword subarg description with \_\_eq__ operator.

    Args:
        name (str): parameter name
        mand (bool, optional): Mandatory argument or not? Defaults to True.
        help (str, optional): help text for parameter. Defaults to None.
        metavar (str, optional): displayed name behind the "="
    """
    name: str
    mand: bool = True
    help: str|None = None
    metavar: str|None = None

    def __eq__(self, other) -> bool:
        """ call _compare_subargs(self, other) and return result """
        return _compare_args(self, other)

def _compare_args(arg1: PSubarg|KWSubarg, arg2: Any) -> bool:
    """ Allow comparison of Subarg instances to other Subarg or to str instances

    Args:
        other (Any): If of type Subarg and of same type as self, compare all fields, 
                        else if of type str, compare self.name to other,
                        else return False

    Returns:
        bool: result of comparison
    """
    if arg1 is arg2: # test identity
        return True
    elif (isinstance(arg2, PSubarg) or isinstance(arg2, KWSubarg)) \
                and type(arg1) is type(arg2):
        # for P/KWSubarg instances, exact types and all fields must match
        for field in dc_fields(arg1):
            if getattr(arg1, field.name) != getattr(arg2, field.name):
                return False
        return True
    elif isinstance(arg2, str): # arg1 name field must match arg2
        return arg1.name == arg2
    return False
    
class SubargParser:
    """ Parser for structured sub-arguments of argparse arguments. The subarguments
    can be positional arguments or keyword-arguments, e.g.:
      myprog.py --print Welcome Message name=Michael role=brother

    SubargParser stores the positional and keyword arguments in a Namespace
    object. Besides these, the complete original argument list passed to
    the parse_subargs() method of the parser, is stored inside the namespace
    unter the identifier stored in ARG_LIST_FIELD. 
    
    Under certain circumstances, there can be two more additional fields, 
    named after EXC_POS_SUBARGS_FIELD and EXC_KW_SUBARG_NAMES_FIELD. For Details
    see parse_subargs()

    Using a SubargParser(pos_args=["W1", "W2"], lw_args=["name", "role"]) 
    instance and calling parse_subargs() on the arguments to --print (see above), 
    a list of namespace objects is returned. Since --print is only called once
    in this example, we would get a list with one element:
    [Namespace(W1='Welcome', W2='Message', name="Michael", role="Brother", 
    _arg_list=["Welcome", "Message", "name=Michael", "role=brother"])]

    SubargParser objects are to be passed to a SubargAction instance using
    action=SubargAction and subarg_parser=<SubargParser instance> when calling
    add_parameter() method of ArgumentParser.

    Raises:
        TypeError, ArgumentError: see method descriptions
    """

    ARG_LIST_FIELD = "_arg_list"
    EXC_POS_SUBARGS_FIELD = "_excess_pos_subargs"
    EXC_KW_SUBARG_NAMES_FIELD = "_excess_kw_subarg_names"

    def __init__(self, *, pos_args: Sequence[str|PSubarg] = [], kw_args: Sequence[str|KWSubarg] = [], 
                 num_mandatory_pos_args: int = -1, allow_excess_args: bool = True,
                 parser: ArgumentParser|None = None, arg_name: str|None = None) -> None:
        """ Constructor. Stores parameter values. The entries of the sequences are copied into
        internal lists. Entries can either be strings or P/KWSubargs instances (mixing is allowed).
        For P/KWSubargs, a help text can be passed in, for KWSubargs there's an additional field
        that denotes whether the argument is mandatory or not, plus a field for a metavar text
        (default is <name>.upper()). 
        
        Positional arguments are mandatory by default. 
        
        Optional positional arguments are possible by using num_mandatory_pos_args.

        Args:
            pos_args (Sequence[str | PSubarg], optional): Positional sub-arguments. Defaults to [].
            kw_args (Sequence[str | KWSubarg], optional): List of keywowd sub-arguments (see above). Defaults to [].
            num_mandatory_pos_args (int, optional): Number of mandatory positional arguments. Defaults to -1 (= all).
            allow_excess_args (bool, optional): Allows additional arguments to those in the lists. Defaults to True.
            parser (ArgumentParser | None, optional): May be set by SubargAction. Defaults to None.
            arg_name (str | None, optional): Name of the argument to which the subargs belong. May be set by SubargAction. Defaults to None.

        Raises:
            TypeError: if an entry in pos_args or kw_args is not of appropriate type
            TypeError: if num_mandatory_pos_args exceeds length of pos_args list
        """
        # copy pos_args
        self._pos_args: list[PSubarg] = []
        for parg in pos_args:
            if isinstance(parg, PSubarg):
                self._pos_args.append(parg)
            elif isinstance(parg, str):
                self._pos_args.append(PSubarg(parg))
            else:
                raise TypeError(f"argument must be of type str|PSubarg "
                                f"but is of type {type(parg)}")
        if num_mandatory_pos_args > len(pos_args):
            raise TypeError(f"num_mandatory_arguments ({num_mandatory_pos_args}) "
                            f"exceeds length of pos_args list ({len(pos_args)})")

        self._num_mandatory_pos_args = num_mandatory_pos_args

        # copy kw_args
        self._kw_args: list[KWSubarg] = []
        for kwarg in kw_args:
            if isinstance(kwarg, KWSubarg):
                self._kw_args.append(kwarg)
            elif isinstance(kwarg, str):
                self._kw_args.append(KWSubarg(kwarg, metavar=kwarg.upper()))
            else:
                raise TypeError(f"argument must be of type str|KWSubarg "
                                f"but is of type {type(kwarg)}")

        self._allow_excess_args: bool = allow_excess_args

        # parser and arg_name may be set by AppendOptAction object
        self._parser = parser
        self._arg_name = arg_name

    def format_metavar_str(self) -> str:
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
        for i, parg in enumerate(self._pos_args):
            if i < self._num_mandatory_pos_args:
                # mandatory
                metavar += parg.name
            else:
                # optional
                metavar += "[" + parg.name + "]"
            if i < l-1:
                metavar += " "
        
        if self._pos_args and self._kw_args:
            metavar += " "

        # then, kw_args:
        l = len(self._kw_args)
        for i, kwarg in enumerate(self._kw_args):
            # use arg's user defined metavar value if it exists, else uppercase argname
            arg_meta = kwarg.metavar if kwarg.metavar else kwarg.name.upper()
            if kwarg.mand:
                # mandatory
                metavar += kwarg.name + "=" + arg_meta
            else:
                # optional
                metavar += "[" + kwarg.name + "=" + arg_meta + "]"
            if i < l-1:
                metavar += " "
        
        if self._allow_excess_args:
            metavar += " [...]"
        return metavar
    
    def format_args_help(self, *, indent: int = 2, line_width: int = 70) -> str:
        """ Return a formatted (multiline) string with help for all the
         parser's  _pos_args and _kw_args. Entries for the arguments are
         added only, if <arg>.help is not None. keyword arguments are
         displayed as <name>=<metavar>. If <arg>.metavar is None, uppercase
         name is used as metavar.

        Args:
            indent (int, optional): indentation at the beginning of an entry. Defaults to 2.
            line_width (int, optional): display width of the help text. Defaults to 70

        Returns:
            str: formatted help string, NOT prepended by a "usage" line
        """
        # find width of name column
        name_len = 0
        for parg in self._pos_args:
            if parg.help:
                name_len = max(name_len, len(parg.name))
        for kwarg in self._kw_args:
            if kwarg.help:
                kw_parm = kwarg.metavar if kwarg.metavar else kwarg.name.upper()
                kw_parm = f"{kwarg.name}={kw_parm}"
                name_len = max(name_len, len(kw_parm))
        # early return if no help was found
        if not name_len:
            return ""

        # width is not bigger than 30
        name_len = min(name_len, 30)

        import textwrap

        # construct text
        result: list[str] = []
        for parg in self._pos_args:
            if parg.help:
                help = f"{parg.name.ljust(name_len)}  {parg.help}"
                result.extend(textwrap.wrap(help, line_width, initial_indent= "".ljust(indent),
                                            subsequent_indent=" ".ljust(name_len+2+indent)))
        for kwarg in self._kw_args:
            if kwarg.help:
                kw_parm = kwarg.metavar if kwarg.metavar else kwarg.name.upper()
                kw_parm = f"{kwarg.name}={kw_parm}"
                help = f"{kw_parm.ljust(name_len)}  {kwarg.help}"
                result.extend(textwrap.wrap(help, line_width, initial_indent= "".ljust(indent),
                                            subsequent_indent=" ".ljust(name_len+2+indent)))
        if result:
            help = result[0]
            for s in result[1:]:
                help += "\n" + s
            return help
        return ""

    def get_pos_args(self) -> list[PSubarg]:
        """ Return list of positional arguments. Other than the list passed to
        the constructor, where list elements can be either of type str or PSubarg,
        the list returned consists entirely of PSubargs.

        Returns:
            list[PSubarg]: list of positional arguments
        """
        return self._pos_args
    
    def get_kw_args(self) -> list[KWSubarg]:
        """ Return list of keyword arguments. Other than the list passed to
        the constructor, where list elements can be either of type str or KWSubarg,
        the list returned consists entirely of KWSubargs.

        Returns:
            list[KWSubarg]: list of keyword arguments
        """
        return self._kw_args
    
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
        """ Print error message using _error(self.parser, _arg_message(message)).

        Args:
            message (str): error message
        """
        _error(self._parser, message)

    def parse_subargs(self, args: Sequence[str]) -> Namespace:
        """ Parse command line subargs against the lists passed to the constructor,
        regarding the values of allow_excess_arguments and num_mandatory_pos_arguments.
        If allow_axcess_arguments is True, then within the returned namespace,
         - values of excess positional arguments are reported in EXC_POS_SUBARGS_FIELD
         - names of excess keyword arguments are reported in EXC_KW_SUBARG_NAMES_FIELD
        Otherwise an error is reported using the _error() method.

        parse_subargs stores the contents of "args" in _arg_list. This list can later
        be retrieved by calling get_arg_list().

        If parsing is successful, parse_subargs stores the resulting namespace in _arg_namespace.
        This field can be accessed by calling get_arg_ns().

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
                    name = self._pos_args[pos_counter].name
                    value = arg
                    setattr(ns, name, value)
                    pos_counter += 1
                else:   # too many positional arguments
                    excess_pos_args.append(arg)

        # store copy of original argument list in namespace
        setattr(ns, SubargParser.ARG_LIST_FIELD, [x for x in args])
        
        if excess_pos_args:
            setattr(ns, SubargParser.EXC_POS_SUBARGS_FIELD, excess_pos_args)
            if not self._allow_excess_args:
                self._error(f"too many positional sub-args: {excess_pos_args}")
        if excess_kw_arg_names:
            setattr(ns, SubargParser.EXC_KW_SUBARG_NAMES_FIELD, excess_kw_arg_names)
            if not self._allow_excess_args:
                self._error(f"too many keyword sub-args: {excess_kw_arg_names}")

        self._check_mandatory_args(ns)

        # store result in case we get here (successful parsing)
        self._arg_namespace = ns
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
                if not hasattr(ns, self._pos_args[i].name):
                    raise ArgumentError(None, 
                                        self._arg_message("Missing mandatory positional subarg ") + \
                                        str(self._pos_args[i].name))
        for i in range(0, len(self._kw_args)):
            if self._kw_args[i].mand:
                if not hasattr(ns, self._kw_args[i].name):
                    raise ArgumentError(None,
                                        self._arg_message("Missing mandatory keyword subarg ") + \
                                        str(self._pos_args[i].name))
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
            if not self.help:
                self.help = " "
            # TODO: set help text to "Plugin subargs:" if help is None AND parser has help texts in P(KWSubarg List)
        else:
            raise TypeError(f"{self.__class__.__name__}.__init__(): 'subarg_parser' must not be None")

    def __call__(self, parser: ArgumentParser, namespace: Namespace, 
                 values: str|Sequence[Any]|None, option_string: str|None=None) -> None:
        """ Perform SubargAction. The method will be call by an ArgumentParser instance.
        The values passed in will be transformed into a Namespace object, which is
        appended to the list stored in <namespace>'s attribute <self.dest>. In other words:
        SubargAction works similar to AppendAction, but does not store a list[list[str]],
        but a list[Namespace].

        Args:
            parser (ArgumentParser): parser instance calling this method
            namespace (Namespace): namespace to which the result will be added
            values (str | Sequence[Any] | None): command line arguments to parse
            option_string (str | None, optional): _description_. option string with
                which the action was invoked (None for positional arguments).

        Raises:
            TypeError: if the values could not be parsed by self._subarg_parser
        """
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
                _error(parser, str(exc))
        else:
            _error(parser, "No valid SubargParser object found")

    def get_subarg_parser(self) -> SubargParser:
        """ 
        Returns: 
            SubargParser instance used by this SubargAction instance """
        return self._subarg_parser

class SubargHelpFormatterMixin(HelpFormatter):
    """ ATTENTION: Do not instantiate this class, but do only derive from it!
    You can use SubargHelpFormatter or create an own subclass (see below)
    
    Mixin that implements the necessary changes to the formatting
    methods of HelpFormatter for formatting SubargActions when used in 
    add_parameter() of ArgumentParser. 

    The mixin can be used to construct arbitrary HelpFormatter classes
    that can handle SubargActions beside their own functionality. To create
    a subclass, build an empty class like:

    class MyFormatter(SubargHelpFormatterMixin, argparse.XXXHelpFormatter)
        pass
        
    where XXXHelpFormatter can be e.g. ArgumentDefaultsHelpFormatter.
    It is important that the HelpFormatter subclass is the second entry
    in the inheritance list!
    """
    def __init__(self, *args, **kwargs):
        """ Constructor """
        # first determine the second class from which the user has derived
        # their own formatter class (besides mixin, see class comment above)
        for cls in self.__class__.mro():
            # IF we have NOT the Mixin class (this one here)
            # AND we have NOT the user's class derived from the Mixin
            #     and from a HelpFormatter class (the one that has been instantiated)
            # AND we have NOT object (top of the inheritance graph),
            # THEN the first class found must be the HelpFormatter subclass class that shall be used
            # with any other than SubargAction actions (shoulb be the second entry in the inheritance list).
            #
            # Since SubargHelpFormatterMixin itself inherits from HelpFormatter, the mixin would
            # also work with single inheritance, because HelpFormatter is in the MRO
            if cls != SubargHelpFormatterMixin and cls != type(self) and cls != object:
                if issubclass(cls, HelpFormatter):
                    self._cls_formatter = cls
                    break
        # create flag for use in _split_lines
        self._has_SubargAction = False
        # call next constructor in inheritance list
        super().__init__(*args, **kwargs)

    def _format_args(self, action: Action, default_metavar: str) -> str:
        """ Format argument string in help message. If action is of type SubargAction,
        the string "{{ <metavar> }}" is returned. If <metavar> is not set by the
        user (as metavar=... in add_parameter()), call get_metavar_str() on the
        action's member _subarg_parser to get the right text.

        If action is not of type SubargAction, call the _format_args method of
        the second class in the inheritance list to do the formatting.

        Args:
            all: see Action._format_args

        Returns:
            str: formatted argument string
        """
        # set flag for use in _split_lines
        self._has_SubargAction = isinstance(action, SubargAction)
        get_metavar = self._metavar_formatter(action, default_metavar)
        if isinstance(action, SubargAction):
            metavar = get_metavar(1)
            # if metavar hasn't been set by the user, call subarg_parser:
            if metavar == (None,) or metavar == (action.dest.upper(),):
                metavar=(action._subarg_parser.format_metavar_str(),)
            return '{{ %s }}' % metavar
        else:
            return self._cls_formatter._format_args(self, action, default_metavar)

    def _get_help_string(self, action: Action) -> str|None:
        """ If action is of type SubargAction, construct help string from 
        action's help text plus help texts of the subargs. Else, return
        action's help text calling the _get_help_string() method of the second
        class in the inheritance list to do the formatting.

        Args:
            action (Action): parameter related Action instance

        Returns:
            str: help text containing newline characters
        """
        # set flag for use in _split_lines
        self._has_SubargAction = isinstance(action, SubargAction)
        # use implemtation of formatter class to get help text for action
        help = self._cls_formatter._get_help_string(self, action)
        # in case we have a SubargAction, use subarg_parser information
        if isinstance(action, SubargAction):
            if help is None:
                help = ""
            subarg_parser = action._subarg_parser
            if subarg_parser:
                if subarg_parser._pos_args:
                    for parg in subarg_parser._pos_args:
                        if parg.help:
                            help += f"\n  <{parg.name}>: {parg.help}"
                if subarg_parser._kw_args:
                    for kwarg in subarg_parser._kw_args:
                        if kwarg.help:
                            help += f"\n  <{kwarg.name}>: {kwarg.help}"
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
        # If we are not formatting a SubargAction, use the formatter class and return
        if not self._has_SubargAction:
            return self._cls_formatter._split_lines(self, text, width)
        
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

class SubargHelpFormatter(SubargHelpFormatterMixin, HelpFormatter):
    """ Formatter for help when using action=SubargAction in add_parameter()
    of ArgumentParser.  Uses SubargHelpFormatterMixin and HelpFormatter
    to do the actual work. No further implementation is necessary.
    """
    pass

def _error(parser: ArgumentParser|None, message: str) -> None:
    """ Print error message.
    If parser is not None, use parser's exiting error() method or simply print to stderr, 
    depending on the value of parser._exit_on_error.
    If parser is None, print error to stderr. and exit with exit code 2.

    Args:
        message (str): _description_
    """
    if parser:
        if parser.exit_on_error: # type: ignore
            parser.error(message)
        else:
            parser.print_usage(sys.stderr)
            print(f"{parser.prog}: error: {message}", file=sys.stderr)
    else:
        print(message, file=sys.stderr)
        sys.exit(2)
