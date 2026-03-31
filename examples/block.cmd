# NCLI Command Blocklist
# Regex patterns, one per line. Lines starting with # are comments.
# These patterns are checked against show/exec commands before execution.

# Dangerous exec commands
^reload$
^write erase
^delete
^format
^erase
