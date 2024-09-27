#!/usr/bin/env python3

import configparser
import subprocess
import os
from datetime import datetime, timedelta

CONFIG_PATH = "/etc/cluster-trimmer/trimmer.conf"

def load_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    return config

def should_run(config):
    current_time = datetime.now()
    current_day = current_time.strftime("%a")
    
    days = config.get("GENERAL", "days").split()
    run_hour = config.getint("GENERAL", "run_time_hours")
    run_minute = config.getint("GENERAL", "run_time_minutes")
    run_interval_hours = config.getint("GENERAL", "run_interval_hours")
    
    if current_day not in days:
        return False
    
    if run_interval_hours > 0:
        last_run_file = "/var/run/cluster_trimmer_last_run"
        if os.path.exists(last_run_file):
            with open(last_run_file, "r") as f:
                last_run = datetime.strptime(f.read().strip(), "%Y-%m-%d %H:%M:%S")
            next_run = last_run + timedelta(hours=run_interval_hours)
            if current_time < next_run:
                return False
        with open(last_run_file, "w") as f:
            f.write(current_time.strftime("%Y-%m-%d %H:%M:%S"))
        return True

    if current_time.hour == run_hour and current_time.minute == run_minute:
        return True

    return False

def run_trimmer():
    config = load_config()
    
    if not should_run(config):
        return
    
    skip_containers = config.get("SKIP_CONTAINERS", "containers", fallback="")
    skip_running = config.getboolean("OPTIONS", "skip_running", fallback=False)
    
    cmd = ["python3", "/path/to/cluster_trimmer.py"]
    
    if skip_containers:
        skip_containers_list = skip_containers.split(',')
        for container in skip_containers_list:
            cmd.append("--skip")
            cmd.append(container)
    
    if skip_running:
        cmd.append("--skip-running")
    
    subprocess.run(cmd)

if __name__ == "__main__":
    run_trimmer()
