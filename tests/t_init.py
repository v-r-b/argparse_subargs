import pprint
from argparse import ArgumentParser
from argparse_subargs import *

print("""
################################################
### Sample usage of structured subargs
################################################
""")

parser = ArgumentParser(formatter_class=SubargHelpFormatter, exit_on_error=False)

# create subarg list with in_file and out_file positional parameters, where in_file is mandatory
# because of num_mandatory_pos_args = 1, and one non-mandatory keyword parameter "lterm". 
# For in_file and lterm, help texts are provided. No additional subargs are allowed.
subarg_parser = SubargParser(pos_args=[PSubarg("in_file", "path to input file"), 
                                       "out_file"], 
                             kw_args=[KWSubarg("lterm", help="line termination characters", mand=False)], 
                             num_mandatory_pos_args=1,
                             allow_excess_args=False)
# create argument mandatory argument "--translate" with the above subarg list.
# To do so, action is set to SubargAction and the subarg_parser instance is passed in as well.
parser.add_argument("--translate", required=True, 
                    action=SubargAction, 
                    help="Translate in_file to out_file (default: to stdout)",
                    subarg_parser=subarg_parser)

# create another almost identical subarg list without mandatory positional args.
# For all subargs, help texts are provided. Additional subargs are allowed.
# This time, use a user defined metavar value for lterm= argument.
subarg_parser = SubargParser(pos_args=[PSubarg("in_file", "path to input file"), 
                                       PSubarg("out_file", "path to output file")], 
                             kw_args=[KWSubarg("lterm", help="line termination characters", mand=False, metavar="TERM_CHARS")], 
                             num_mandatory_pos_args=0,
                             allow_excess_args=True)
# create argument non-mandatory argument "--xlate" with the above subarg list.
# To do so, action is set to SubargAction and the subarg_parser instance is passed in as well.
parser.add_argument("--xlate", required=False, 
                    action=SubargAction, 
                    help="Translate in_file to out_file (default: to stdout)",
                    subarg_parser=subarg_parser)

if len(sys.argv) > 1:    # command line parameters
    print("parsing cli parameters", sys.argv[1:])
    args=parser.parse_args(sys.argv[1:])
    print(getattr(args, "translate"))
    pprint.pp(args)
    sys.exit(0)

print("""
################################################
### print usage and help messages
################################################
""")
parser.print_help()
parser.print_usage()    

print("""
################################################
### missing argument "--translate"
################################################
""")
try:
    args = parser.parse_args(["--xlate", "/path/to/linfile", "lterm=\n"])
except BaseException as exc:
    assert exc.__class__ is SystemExit, "program should try to terminate here"

print("""
################################################
### missing subarg "in_file"
################################################
""")
args = parser.parse_args(["--translate", "lterm=\n"])
subargs = getattr(args, "translate")
print("subargs:", subargs)
assert not subargs, "parser should have returned None due to missing subarg"

print("""
################################################
### too many subargs
################################################
""")
args = parser.parse_args(["--translate", "/path/to/linfile", "/path/to/outfile", "/additional/path"])
subargs = getattr(args, "translate")
print("subargs:", subargs)
assert hasattr(subargs[0], SubargParser.EXC_POS_SUBARGS_FIELD) and \
       "/additional/path" in getattr(subargs[0], SubargParser.EXC_POS_SUBARGS_FIELD), \
       f"there should be {SubargParser.EXC_POS_SUBARGS_FIELD} containing /additional/path"

print("""
################################################
### parse a correct command line 
### with additional parameters to --xlate
################################################
""")
args = parser.parse_args(["--translate", "/path/to/linfile", "lterm=\n",
                          "--xlate", "/path/to/file1", "/path/to/file2", "/path/to/file3", "lterm=\r\n", "switch=xyz"])
# print namespace produced by parse_args
print("args:", args)
# print namespaces with subargs to --translate arg
subargs = getattr(args, "xlate")
print("subargs:", subargs)
for i, ns in enumerate(subargs):
    assert hasattr(ns, "in_file"), "in_file should have been found here"
    assert hasattr(ns, "out_file"), "out_file should have been found here"
    assert hasattr(ns, SubargParser.EXC_POS_SUBARGS_FIELD), \
        f"{SubargParser.EXC_POS_SUBARGS_FIELD} should have been found here"
    assert hasattr(ns, SubargParser.EXC_KW_SUBARG_NAMES_FIELD), \
        f"{SubargParser.EXC_KW_SUBARG_NAMES_FIELD} should have been found here"
    print(i, ":subargs to --translate:", ns)
    print("-> translate", getattr(ns, "in_file"), "to", getattr(ns, "out_file"))
    print("   additonal subargs:")
    for sub in getattr(ns, SubargParser.EXC_POS_SUBARGS_FIELD):
        print("     ", sub)
    for sub in getattr(ns, SubargParser.EXC_KW_SUBARG_NAMES_FIELD):
        print("     ", sub, "=", getattr(ns, sub))

print("""
################################################
### Done.
################################################
""")
