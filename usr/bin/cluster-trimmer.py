import paramiko
import subprocess
import sqlite3
import re
import argparse
from datetime import datetime, timedelta
import time
import sys

# SQLite database setup
DB_NAME = 'trimmer_data.db'
COROSYNC_CONF_PATH = '/etc/pve/corosync.conf'

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("trimmer_log.txt", "a") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(message)
    insert_log_entry(timestamp, message)

def initialize_db():
    conn = sqlite3.connect(DB_NAME)
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS trim_data (
                container_id INTEGER,
                pre_trim_size TEXT,
                post_trim_size TEXT,
                trim_date TEXT,
                reclaimed_space TEXT,
                reclaimed_percentage REAL,
                errors TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS log_entries (
                timestamp TEXT,
                message TEXT
            )
        ''')
    conn.close()

def insert_trim_data(container_id, pre_trim_size, post_trim_size, trim_date, reclaimed_space, reclaimed_percentage, error_message):
    conn = sqlite3.connect(DB_NAME)
    with conn:
        conn.execute('''
            INSERT INTO trim_data (container_id, pre_trim_size, post_trim_size, trim_date, reclaimed_space, reclaimed_percentage, errors)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (container_id, pre_trim_size, post_trim_size, trim_date, reclaimed_space, reclaimed_percentage, error_message))
    conn.close()

def insert_log_entry(timestamp, message):
    conn = sqlite3.connect(DB_NAME)
    with conn:
        conn.execute('''
            INSERT INTO log_entries (timestamp, message)
            VALUES (?, ?)
        ''', (timestamp, message))
    conn.close()

def get_cluster_nodes_from_corosync():
    try:
        with open(COROSYNC_CONF_PATH, 'r') as file:
            corosync_conf = file.read()
        
        node_pattern = re.compile(r'node\s*{\s*name:\s*(\S+).*?ring0_addr:\s*(\S+).*?ring1_addr:\s*(\S+)', re.DOTALL)
        nodes = node_pattern.findall(corosync_conf)
        
        node_info = {}
        for name, ring0, ring1 in nodes:
            node_info[name] = {"ring0_addr": ring0, "ring1_addr": ring1}
        
        return node_info
    except Exception as e:
        log(f"Failed to parse corosync.conf: {e}")
        sys.exit(1)

# Function to get disk usage
def get_disk_usage(ssh_client, container_id):
    try:
        stdin, stdout, stderr = ssh_client.exec_command(f"pct df {container_id} | awk 'NR==2 {{print $3, $4}}'")
        usage = stdout.read().decode().strip()
        if not usage:
            raise ValueError("Failed to retrieve disk usage.")
        return usage.split()
    except Exception as e:
        log(f"Failed to get disk usage for container {container_id}: {e}")
        return "Error", "Error"

def convert_size_to_bytes(size):
    size_conversion = {'K': 1<<10, 'M': 1<<20, 'G': 1<<30, 'T': 1<<40}  # Size suffixes
    if size[-1].isdigit():  # If no suffix, it's in bytes
        return int(size)
    return int(float(size[:-1]) * size_conversion[size[-1]])

# Check if container is locked and unlock if necessary
def is_container_locked(ssh_client, container_id):
    try:
        stdin, stdout, stderr = ssh_client.exec_command(f"pct config {container_id} | grep '^lock:'")
        output = stdout.read().decode().strip()
        return bool(output)
    except Exception as e:
        log(f"Failed to check lock status for container {container_id}: {e}")
        return False

def unlock_container(ssh_client, container_id):
    try:
        ssh_client.exec_command(f"pct unlock {container_id}")
        log(f"Container {container_id} unlocked successfully.")
    except Exception as e:
        log(f"Failed to unlock container {container_id}: {e}")

def wait_for_unlock(ssh_client, container_id, max_attempts=10, wait_time=5):
    attempts = 0
    while attempts < max_attempts:
        if not is_container_locked(ssh_client, container_id):
            return True
        log(f"Container {container_id} is still locked. Waiting for {wait_time} seconds...")
        time.sleep(wait_time)
        attempts += 1
    return False

def was_trimmed_recently(container_id, time_threshold):
    conn = sqlite3.connect(DB_NAME)
    with conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT MAX(trim_date) FROM trim_data WHERE container_id = ?
        ''', (container_id,))
        result = cursor.fetchone()
        if result[0] is None:
            return False
        last_trim_time = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
        if last_trim_time > time_threshold:
            return True
    return False

def trim_container(ssh_client, container_id, all_containers):
    error_message = ""
    try:
        # Check the last trimmed time and skip if within the last 24 hours
        if not all_containers:
            time_threshold = datetime.now() - timedelta(hours=24)
            if was_trimmed_recently(container_id, time_threshold):
                log(f"Skipping trim for container {container_id}, last trimmed within the last 24 hours.")
                return
        
        log(f"Starting trim on container {container_id}")

        # Check if the container is locked
        if is_container_locked(ssh_client, container_id):
            log(f"Container {container_id} is locked. Attempting to unlock.")
            unlock_container(ssh_client, container_id)
            if not wait_for_unlock(ssh_client, container_id):
                raise Exception("Failed to unlock container.")

        # Get pre-trim disk usage
        pre_trim_size, pre_trim_avail = get_disk_usage(ssh_client, container_id)
        log(f"Pre-trim disk usage for container {container_id}: Used={pre_trim_size}, Available={pre_trim_avail}")

        # Perform the trim operation from the node
        log(f"Trimming container {container_id} from the node.")
        stdin, stdout, stderr = ssh_client.exec_command(f"pct fstrim {container_id}")
        trim_output = stdout.read().decode().strip()
        stderr_output = stderr.read().decode()

        if stderr_output:
            log(f"Error occurred while trimming container {container_id}: {stderr_output}")
            error_message = stderr_output
        else:
            # Parse trim output to get the reclaimed size
            match = re.search(r' ([\d\.]+ [KMGTP]iB) \(.* bytes\) trimmed', trim_output)
            if match:
                reclaimed_space = match.group(1)
            else:
                reclaimed_space = "0 B"

            # Get post-trim disk usage
            post_trim_size, post_trim_avail = get_disk_usage(ssh_client, container_id)
            log(f"Post-trim disk usage for container {container_id}: Used={post_trim_size}, Available={post_trim_avail}")

            # Check and calculate reclaimed space and percentage
            if pre_trim_size != "Error" and post_trim_size != "Error":
                pre_size_bytes = convert_size_to_bytes(pre_trim_size)
                post_size_bytes = convert_size_to_bytes(post_trim_size)
                reclaimed_space_bytes = pre_size_bytes - post_size_bytes
                reclaimed_percentage = (reclaimed_space_bytes / pre_size_bytes) * 100 if pre_size_bytes != 0 else 0

                # Insert data into SQLite database
                trim_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                insert_trim_data(container_id, pre_trim_size, post_trim_size, trim_date, reclaimed_space, reclaimed_percentage, error_message)

                log(f"Finished trim on container {container_id}. Reclaimed {reclaimed_space} ({reclaimed_percentage:.2f}%)")
            else:
                raise Exception("Failed to retrieve valid disk usage data.")
    except Exception as e:
        error_message = str(e)
        log(f"Failed to trim container {container_id}: {error_message}")
        # Insert error data into SQLite database
        insert_trim_data(container_id, pre_trim_size, "", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "", 0.0, error_message)

def connect_to_node(node_name, primary_addr, backup_addr, all_containers):
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Try connection with primary address
        try:
            ssh_client.connect(primary_addr)  # Connect using existing SSH keys
            log(f"Successfully connected to node {node_name} at {primary_addr}")
        except Exception as primary_e:
            log(f"Failed to connect to node {node_name} at {primary_addr}: {primary_e}")
            # Fallback to backup address
            ssh_client.connect(backup_addr)  # Connect using existing SSH keys
            log(f"Successfully connected to node {node_name} at {backup_addr}")

        stdin, stdout, stderr = ssh_client.exec_command("pct list | awk 'NR>1 {print $1}'")
        containers = stdout.read().decode().splitlines()

        for container_id in containers:
            trim_container(ssh_client, container_id, all_containers)
        
        log(f"Finished all containers on node {node_name}")
    except Exception as e:
        log(f"Failed to connect to node {node_name}: {e}")
    finally:
        ssh_client.close()

def main(args):
    initialize_db()
    node_info = get_cluster_nodes_from_corosync()
    for node_name, addrs in node_info.items():
        primary_addr = addrs["ring0_addr"]
        backup_addr = addrs["ring1_addr"]
        try:
            connect_to_node(node_name, primary_addr, backup_addr, args.all)
        except Exception as e:
            log(f"Exception occurred during connection to node {node_name}: {e}")

    log("Cluster trimming completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Proxmox VE LXC Filesystem Trim Script")
    parser.add_argument('--all', action='store_true', help='Perform trim on all containers regardless of last trim')
    args = parser.parse_args()
    
    log("Starting cluster trimmer script.")
    main(args)
    log("Cluster trimmer script completed.")
