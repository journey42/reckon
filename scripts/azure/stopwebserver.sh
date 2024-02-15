#!/bin/bash

# Replace 'your_binary_name' with the actual name of your binary
PROCESS_NAME="your_binary_name"

# Find all PIDs of the given process name
PIDS=$(pgrep -f $PROCESS_NAME)

# Check if any PIDs were found
if [ -z "$PIDS" ]; then
    echo "No process found with name $PROCESS_NAME"
    exit 1
fi

# Iterate over each PID and terminate it
for PID in $PIDS; do
    echo "Terminating process with PID $PID"
    kill $PID

    # Optional: check if the process needs a force kill
    # sleep 2
    # if kill -0 $PID > /dev/null 2>&1; then
    #     echo "Process $PID did not terminate, using force kill."
    #     kill -9 $PID
    # fi
done

echo "All processes terminated."
