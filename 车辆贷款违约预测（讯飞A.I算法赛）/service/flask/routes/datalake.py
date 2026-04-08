from __future__ import annotations

import json
import os
import subprocess
from flask import Blueprint, jsonify, request

datalake_bp = Blueprint("datalake_bp", __name__)

# HDFS WebHDFS endpoint (can be configured via environment)
HDFS_HOST = os.environ.get("HDFS_NAMENODE", "localhost")
HDFS_PORT = os.environ.get("HDFS_PORT", "9870")
HDFS_WEB_URL = f"http://{HDFS_HOST}:{HDFS_PORT}"

# Data lake paths
DATA_LAKE_PATHS = {
    "raw": "/data_lake/raw",
    "cleaned": "/data_lake/cleaned",
    "featured": "/data_lake/featured",
    "model": "/data_lake/model",
}


def run_hdfs_command(cmd: list[str]) -> dict:
    """Execute HDFS CLI command and return parsed output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return {"success": True, "output": result.stdout}
        return {"success": False, "error": result.stderr or "Command failed"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timeout"}
    except FileNotFoundError:
        return {"success": False, "error": "hdfs command not found. Is Hadoop installed?"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_directory_listing(path: str) -> dict:
    """Get directory listing using hdfs dfs -ls command."""
    cmd = ["hdfs", "dfs", "-ls", "-R", path]
    result = run_hdfs_command(cmd)

    if not result["success"]:
        return {"error": result["error"], "files": []}

    files = []
    for line in result["output"].strip().split("\n"):
        if not line or line.startswith("Found"):
            continue

        parts = line.split()
        if len(parts) >= 8:
            # Format: permissions replication owner group size modification_date modification_time path
            permission = parts[0]
            # Determine if it's a directory
            file_type = "DIRECTORY" if permission.startswith("d") else "FILE"
            # Try to parse size
            try:
                size = int(parts[4])
            except (ValueError, IndexError):
                size = 0
            # Parse date and time
            date_str = parts[5] if len(parts) > 5 else ""
            time_str = parts[6] if len(parts) > 6 else ""
            # Path is everything after the 7th space (date) and 8th space (time)
            # But simpler: last item is always the path
            file_path = parts[-1]

            # Extract pathSuffix (filename)
            path_suffix = file_path.split("/")[-1]

            # Skip the parent directory entry
            if path_suffix == "":
                continue

            files.append({
                "pathSuffix": path_suffix,
                "type": file_type,
                "length": size,
                "permission": permission[-9:] if len(permission) >= 9 else permission,
                "modificationTime": f"{date_str} {time_str}",
                "path": file_path,
            })

    return {"files": files}


def get_directory_size(path: str) -> int:
    """Get total size of a directory using hdfs dfs -du command."""
    cmd = ["hdfs", "dfs", "-du", "-s", path]
    result = run_hdfs_command(cmd)

    if not result["success"]:
        return 0

    try:
        # Output format: size path or size (space_replication) path
        first_line = result["output"].strip().split("\n")[0]
        parts = first_line.split()
        size = int(parts[0])
        return size
    except (ValueError, IndexError, KeyError):
        return 0


def check_service_status(service: str) -> str:
    """Check if a service is running."""
    try:
        if service == "hdfs":
            cmd = ["hdfs", "dfsadmin", "-report"]
        elif service == "hive":
            cmd = ["hive", "--version"]
        elif service == "flume":
            cmd = ["flume-ng", "version"]
        elif service == "kafka":
            cmd = ["kafka-topics.sh", "--version"]
        else:
            return "unknown"

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return "running"
        return "stopped"
    except Exception:
        return "unknown"


@datalake_bp.get("/api/datalake/ls")
def datalake_ls():
    """List HDFS directory contents."""
    path = request.args.get("path", "/data_lake")

    # Validate path
    if not path.startswith("/"):
        return jsonify({"error": "Invalid path"}), 400

    listing = get_directory_listing(path)
    return jsonify(listing)


@datalake_bp.get("/api/datalake/summary")
def datalake_summary():
    """Get data lake storage summary."""
    summary = {
        "rawSize": 0,
        "cleanedSize": 0,
        "featuredSize": 0,
        "modelSize": 0,
        "capacity": {
            "used": 0,
            "total": 0,
        },
        "services": {
            "hdfs": "unknown",
            "flume": "unknown",
            "kafka": "unknown",
            "hive": "unknown",
        },
    }

    # Get directory sizes
    for key, path in DATA_LAKE_PATHS.items():
        size = get_directory_size(path)
        if key == "raw":
            summary["rawSize"] = size
        elif key == "cleaned":
            summary["cleanedSize"] = size
        elif key == "featured":
            summary["featuredSize"] = size
        elif key == "model":
            summary["modelSize"] = size

    # Get HDFS capacity
    cmd = ["hdfs", "dfsadmin", "-report"]
    result = run_hdfs_command(cmd)
    if result["success"]:
        for line in result["output"].split("\n"):
            if "DFS Used:" in line:
                try:
                    used_str = line.split(":")[1].strip().split()[0]
                    # Handle sizes like "10 GB" or "10T"
                    parts = used_str.split()
                    value = float(parts[0])
                    unit = parts[1] if len(parts) > 1 else "B"
                    multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
                    summary["capacity"]["used"] = int(value * multipliers.get(unit, 1))
                except Exception:
                    pass
            elif "DFS Remaining:" in line:
                try:
                    remaining_str = line.split(":")[1].strip().split()[0]
                    parts = remaining_str.split()
                    value = float(parts[0])
                    unit = parts[1] if len(parts) > 1 else "B"
                    multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
                    remaining = int(value * multipliers.get(unit, 1))
                    summary["capacity"]["total"] = summary["capacity"]["used"] + remaining
                except Exception:
                    pass

    # Check service status (may timeout, so use cached values on failure)
    services = ["hdfs", "flume", "kafka", "hive"]
    for svc in services:
        status = check_service_status(svc)
        summary["services"][svc] = status

    return jsonify(summary)


@datalake_bp.get("/api/datalake/file")
def datalake_file():
    """Get details of a specific file."""
    path = request.args.get("path")
    if not path:
        return jsonify({"error": "path parameter required"}), 400

    cmd = ["hdfs", "dfs", "-stat", "%n,%b,%o,%r,%u,%g,%y", path]
    result = run_hdfs_command(cmd)

    if not result["success"]:
        return jsonify({"error": result["error"]}), 500

    try:
        # Parse stat output
        parts = result["output"].strip().split(",")
        return jsonify({
            "name": parts[0],
            "size": int(parts[1]),
            "blockSize": int(parts[2]),
            "replication": int(parts[3]),
            "owner": parts[4],
            "group": parts[5],
            "modificationTime": parts[6],
        })
    except Exception:
        return jsonify({"error": "Failed to parse file info"}), 500
