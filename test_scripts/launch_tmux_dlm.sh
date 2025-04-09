#!/bin/bash
SESSION_NAME="blackcat_dlm"
VENV_PATH="$HOME/.venvs/blackcat"
SCRIPT_PATH="/home/trbnet/pone-crate/chiara/blackcat/test_scripts/run_dlm.py"

# Create a single command string to run inside tmux
COMMAND="source $VENV_PATH/bin/activate  && which python && python $SCRIPT_PATH $@"

# Start a new tmux session running that command inside a bash shell
tmux new-session -d -s "$SESSION_NAME"
tmux send-keys "export PYTHONPATH=$PYTHONPATH:/home/trbnet/pone-crate/chiara/blackcat" C-m
tmux send-keys "$COMMAND" C-m

echo "Use 'tmux attach -t $SESSION_NAME' to watch it live"
echo "Use 'tmux kill-session -t $SESSION_NAME' to stop it"
