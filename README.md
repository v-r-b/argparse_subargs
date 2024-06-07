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

```class PSubarg```
  
Positional subarg description with \_\_eq__ operator.

```class KWSubarg```
  
Keyword subarg description with \_\_eq__ operator.
