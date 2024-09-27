#!/bin/bash

CONFIG_PATH="/etc/cluster-trimmer/trimmer.conf"
SERVICE_NAME="cluster_trimmer"

function help() {
    echo "Usage: $0 [--add-skip CONTAINER_ID] [--remove-skip CONTAINER_ID] [--skip-running] [--no-skip-running] [--set-schedule INTERVAL_HOUR RUN_HOUR RUN_MINUTE DAYS] [--easy]"
    echo ""
    echo "Options:"
    echo "  --add-skip CONTAINER_ID       Add a container ID to the skip list"
    echo "  --remove-skip CONTAINER_ID    Remove a container ID from the skip list"
    echo "  --skip-running                Skip running containers"
    echo "  --no-skip-running             Do not skip running containers"
    echo "  --set-schedule INTERVAL RUN_HOUR RUN_MINUTE DAYS"
    echo "                                Set the schedule for the trimmer script"
    echo "                                INTERVAL: Time interval in hours"
    echo "                                RUN_HOUR: Hour to run the script"
    echo "                                RUN_MINUTE: Minute to run the script"
    echo "                                DAYS: Days of the week to run the script (e.g., 'Mon Tue Wed Thu Fri')"
    echo "  --easy                        Interactive mode to configure the trimmer script"
}

function add_skip() {
    container_id=$1
    sed -i "/containers *=/ s/$/,$container_id/" $CONFIG_PATH
    systemctl restart $SERVICE_NAME
}

function remove_skip() {
    container_id=$1
    sed -i "s/,$container_id//; s/$container_id,//" $CONFIG_PATH
    systemctl restart $SERVICE_NAME
}

function set_skip_running() {
    skip_running=$1
    sed -i "s/skip_running *=.*/skip_running = $skip_running/" $CONFIG_PATH
    systemctl restart $SERVICE_NAME
}

function set_schedule() {
    interval=$1
    hour=$2
    minute=$3
    days=$4
    sed -i "s/run_interval_hours *=.*/run_interval_hours = $interval/" $CONFIG_PATH
    sed -i "s/run_time_hours *=.*/run_time_hours = $hour/" $CONFIG_PATH
    sed -i "s/run_time_minutes *=.*/run_time_minutes = $minute/" $CONFIG_PATH
    sed -i "s/days *=.*/days = $days/" $CONFIG_PATH
    systemctl restart $SERVICE_NAME 
}

function easy() {
    echo "Entering interactive configuration mode..."

    # Set schedule
    echo "Set schedule for the trimmer script"
    echo "1) Every N hours"
    echo "2) Daily at specific time"
    read -p "Choose an option (1 or 2): " schedule_option

    if [[ $schedule_option -eq 1 ]]; then
        read -p "Enter the interval in hours: " interval
        hour=00
        minute=00
        days="Mon Tue Wed Thu Fri Sat Sun"
    elif [[ $schedule_option -eq 2 ]]; then
        interval=0
        read -p "Enter the run hour (24h format): " hour
        read -p "Enter the run minute: " minute
        read -p "Enter days of the week to run (e.g., 'Mon Tue Wed Thu Fri'): " days
    else
        echo "Invalid option. Exiting..."
        exit 1
    fi

    set_schedule $interval $hour $minute "$days"

    # Add containers to skip
    read -p "Would you like to add any containers to the skip list? (y/n): " add_skip_option
    if [[ $add_skip_option == "y" ]]; then
        while true; do
            read -p "Enter container ID to skip (or type 'done' to finish): " container_id
            if [[ $container_id == "done" ]]; then
                break
            else
                add_skip $container_id
            fi
        done
    fi

    # Current skip list
    echo "Currently skipped containers:"
    grep "containers" $CONFIG_PATH

    # Remove containers from skip
    read -p "Would you like to remove any containers from the skip list? (y/n): " remove_skip_option
    if [[ $remove_skip_option == "y" ]]; then
        while true; do
            read -p "Enter container ID to remove from skip (or type 'done' to finish): " container_id
            if [[ $container_id == "done" ]]; then
                break
            else
                remove_skip $container_id
            fi
        done
    fi

    # Skip running containers
    read -p "Would you like to skip running containers? (y/n): " skip_running_option
    if [[ $skip_running_option == "y" ]]; then
        echo "Warning: Skipping running containers may require manual trimming to ensure they are optimized."
        set_skip_running "true"
    else
        set_skip_running "false"
    fi

    echo "Configuration complete. Restarting service..."
    systemctl restart $SERVICE_NAME
}

case "$1" in
    --add-skip)
        add_skip $2
        ;;
    --remove-skip)
        remove_skip $2
        ;;
    --skip-running)
        set_skip_running "true"
        ;;
    --no-skip-running)
        set_skip_running "false"
        ;;
    --set-schedule)
        set_schedule $2 $3 $4 $5
        ;;
    --easy)
        easy
        ;;
    *)
        help
        ;;
esac
