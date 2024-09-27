# Proxmox Cluster Trimmer

**Proxmox Cluster Trimmer** is a powerful utility designed for Proxmox users to maintain optimal disk performance across their clusters. When installed on any node within your Proxmox cluster, this software automatically conducts file system trims on all containers, helping to keep your file systems healthy and conserve valuable disk space.

## Current Version

**Version:** 0.2

### Release Notes
- This is the initial public commit.
- The software is currently being structured into a `.deb` release, which is why it is folded the way it is. As it is structured in this repository, it will not currently work; however, I will be working on a release for this version that should be coming out in the next week or so, which will include the actual Debian release.
- The actual Debian release will be included in a proper repository, allowing installation using `apt` after adding my repository.

## Why Trimming Your File Systems Is Important

File system trimming is crucial for SSDs and other modern storage devices as it allows the operating system to inform the storage device which blocks of data are no longer in use and can be wiped. Regularly trimming your file systems can prevent performance degradation over time, enhance write performance, and prolong the lifespan of your storage media. By ensuring that your containers are regularly trimmed, you help maintain a smooth and efficient operation of your Proxmox cluster.

## Configuration Options

The **Proxmox Cluster Trimmer** offers flexible configuration options to suit your needs. After installation, you can easily manage these configurations using the command:

```bash
cluster-trimmer
```

### Key Configuration Options Include:

- **Frequency of Trimming**: Set how often the trimmer runs.
- **Start Time**: Specify the time at which the trimming process begins.
- **Days of Operation**: Choose which days of the week the trimming process is active.
- **Container Exclusions**: Specify container IDs that should not be trimmed.
- **Running Container Check**: Configure the software to skip trimming on containers that are currently running.

For an easy walkthrough of the configuration options, simply run:

```bash
cluster-trimmer --easy
```

If you prefer to adjust configurations directly using command-line arguments, you can view more information by using:

```bash
cluster-trimmer --help
```

## How It Works

The **Proxmox Cluster Trimmer** communicates with your Proxmox cluster to gather the primary and secondary IP addresses of every node. Utilizing SSH, along with the node's SSH key, it establishes a secure connection to each node. The process begins with the first node, where it trims all containers, before proceeding to the next node in the cluster. This continues until all nodes have been processed.

### Data Storage and Logging

The software uses SQLite3 for storing configuration settings and logging operational details. This includes records of trimming activities for each container. While not all features are fully utilized in the current version, they are designed with future enhancements in mind.

### System Service

To ensure reliable performance, **Proxmox Cluster Trimmer** includes a system service that continuously monitors the configuration and guarantees that the trimmer runs as scheduled.

## Upcoming Features and Changes

- In the next version, the software will be installable directly from the repository using `apt`.
- Future versions will include a statistics script that provides details for each container, including how much has been trimmed from each container, fun statistics such as the total amount trimmed, and potentially an estimate of the performance advantage achieved through trimming operations.

## Licensing

**Proxmox Cluster Trimmer** is distributed under a custom license. You can view the full licensing terms in the `LICENSE.md` file included in the repository.

By providing users with these capabilities, the **Proxmox Cluster Trimmer** ensures that your Proxmox cluster remains efficient, effectively managing disk space and maintaining optimal performance over time.
