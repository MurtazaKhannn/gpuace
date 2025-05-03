from flask import Flask, jsonify, request
import psutil
import os
import platform
import subprocess
import threading
import time
import json
from datetime import datetime
import docker
import signal
import sys

app = Flask(__name__)

# Initialize Docker client
docker_client = None
try:
    docker_client = docker.from_env()
    docker_client.ping()
    print("Docker client successfully initialized")
except docker.errors.DockerException as de:
    print(f"Docker error: {de}. Is Docker daemon running?")
    docker_client = None
except Exception as e:
    print(f"Warning: Docker client initialization failed: {e}")
    docker_client = None

# Global variables to store metrics
baseline_metrics = {
    "cpu_usage": 0,
    "memory_usage_mb": 0,
    "gpu_usage": None,
    "disk_io": None,
    "network_io": None,
    "timestamp": None
}

current_metrics = {
    "cpu_usage": 0,
    "memory_usage_mb": 0,
    "gpu_usage": None,
    "disk_io": None,
    "network_io": None,
    "timestamp": None
}

container_info = {
    "container_id": None,
    "image": None,
    "running": False,
    "start_time": None,
    "command": None,
    "stats": None
}

# Graceful shutdown handler
def graceful_shutdown(signum, frame):
    print("\nShutting down gracefully...")
    if container_info["running"] and container_info["container_id"]:
        try:
            container = docker_client.containers.get(container_info["container_id"])
            container.stop()
            print(f"Stopped container {container_info['container_id']}")
        except Exception as e:
            print(f"Error stopping container: {e}")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)

def get_disk_io():
    """Get disk I/O statistics"""
    try:
        disk_io = psutil.disk_io_counters()
        return {
            "read_mb": disk_io.read_bytes / (1024 * 1024),
            "write_mb": disk_io.write_bytes / (1024 * 1024),
            "read_count": disk_io.read_count,
            "write_count": disk_io.write_count
        }
    except Exception as e:
        return {"error": str(e)}

def get_network_io():
    """Get network I/O statistics"""
    try:
        net_io = psutil.net_io_counters()
        return {
            "bytes_sent_mb": net_io.bytes_sent / (1024 * 1024),
            "bytes_recv_mb": net_io.bytes_recv / (1024 * 1024),
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv
        }
    except Exception as e:
        return {"error": str(e)}

def get_gpu_info():
    """Get GPU usage based on available tools with enhanced cloud support"""
    try:
        # Check for NVIDIA GPUs (common in cloud instances)
        if os.path.exists('/usr/bin/nvidia-smi'):
            result = subprocess.check_output([
                "nvidia-smi", 
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits"
            ])
            gpu_util, gpu_memory_used, gpu_memory_total = result.decode().strip().split(",")
            return {
                "utilization_percent": float(gpu_util),
                "memory_used_mb": float(gpu_memory_used),
                "memory_total_mb": float(gpu_memory_total),
                "memory_usage_percent": (float(gpu_memory_used) / float(gpu_memory_total)) * 100,
                "type": "nvidia"
            }
        
        # Check for AMD GPUs (some cloud instances)
        elif os.path.exists('/opt/rocm/bin/rocm-smi'):
            result = subprocess.check_output([
                "rocm-smi",
                "--showuse",
                "--showmeminfo",
                "vram"
            ])
            # Parse the output (simplified for example)
            return {
                "info": "AMD GPU detected",
                "output": result.decode(),
                "type": "amd"
            }
        
        # Check for Intel GPUs
        elif os.path.exists('/usr/bin/intel_gpu_top'):
            return {
                "info": "Intel GPU detected - monitoring not implemented",
                "type": "intel"
            }
        
        # Cloud-specific checks (AWS, GCP, Azure)
        elif os.path.exists('/sys/class/dmi/id/product_name'):
            with open('/sys/class/dmi/id/product_name', 'r') as f:
                product_name = f.read().strip()
            
            if 'Amazon EC2' in product_name:
                # AWS specific checks
                return {"info": "AWS instance - GPU detection not implemented"}
            elif 'Google Compute Engine' in product_name:
                # GCP specific checks
                return {"info": "GCP instance - GPU detection not implemented"}
            elif 'Microsoft Corporation' in product_name and 'Virtual Machine' in product_name:
                # Azure specific checks
                return {"info": "Azure VM - GPU detection not implemented"}
        
        return {"info": "No GPU detected or GPU monitoring not available"}
    
    except Exception as e:
        return {"error": f"GPU detection failed: {str(e)}"}

def get_system_metrics():
    """Get comprehensive system metrics with cloud optimizations"""
    try:
        # Get CPU usage with 1 second interval for more accuracy
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Get memory with detailed breakdown
        mem = psutil.virtual_memory()
        
        # Get detailed metrics
        metrics = {
            "cpu": {
                "usage_percent": cpu_percent,
                "cores": psutil.cpu_count(logical=False),
                "threads": psutil.cpu_count(logical=True),
                "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else None
            },
            "memory": {
                "used_mb": mem.used / (1024 * 1024),
                "available_mb": mem.available / (1024 * 1024),
                "total_mb": mem.total / (1024 * 1024),
                "usage_percent": mem.percent,
                "free_mb": mem.free / (1024 * 1024)
            },
            "gpu": get_gpu_info(),
            "disk_io": get_disk_io(),
            "network_io": get_network_io(),
            "timestamp": datetime.now().isoformat() + "Z",  # UTC time for cloud
            "system": {
                "os": platform.system(),
                "release": platform.release(),
                "machine": platform.machine()
            }
        }
        
        # Cloud-specific metrics
        if os.path.exists('/proc/self/cgroup'):
            with open('/proc/self/cgroup', 'r') as f:
                if 'docker' in f.read():
                    metrics['environment'] = 'docker-container'
                elif 'kubepods' in f.read():
                    metrics['environment'] = 'kubernetes-pod'
        
        return metrics
    
    except Exception as e:
        return {"error": f"Failed to get system metrics: {str(e)}"}

def calculate_differences(before, after):
    """Calculate resource usage differences with safety checks"""
    if not before or not after or "error" in before or "error" in after:
        return {"error": "Invalid metrics for comparison"}
    
    try:
        diff = {
            "cpu": {
                "usage_percent_diff": after["cpu"]["usage_percent"] - before["cpu"]["usage_percent"],
                "load_avg_diff": [
                    after["cpu"].get("load_avg", [0,0,0])[i] - before["cpu"].get("load_avg", [0,0,0])[i]
                    for i in range(3)
                ] if "load_avg" in after["cpu"] and "load_avg" in before["cpu"] else None
            },
            "memory": {
                "used_mb_diff": after["memory"]["used_mb"] - before["memory"]["used_mb"],
                "usage_percent_diff": after["memory"]["usage_percent"] - before["memory"]["usage_percent"]
            },
            "timestamp": {
                "start": before["timestamp"],
                "end": after["timestamp"],
                "duration_seconds": (
                    datetime.fromisoformat(after["timestamp"].replace('Z', '')) - 
                    datetime.fromisoformat(before["timestamp"].replace('Z', ''))
                ).total_seconds()
            }
        }
        
        # GPU differences
        if "gpu" in before and "gpu" in after:
            gpu_diff = {}
            for metric in ["utilization_percent", "memory_used_mb", "memory_usage_percent"]:
                if metric in before["gpu"] and metric in after["gpu"]:
                    gpu_diff[metric + "_diff"] = after["gpu"][metric] - before["gpu"][metric]
            if gpu_diff:
                diff["gpu"] = gpu_diff
        
        # Disk I/O differences
        if "disk_io" in before and "disk_io" in after:
            disk_diff = {}
            for metric in ["read_mb", "write_mb", "read_count", "write_count"]:
                if metric in before["disk_io"] and metric in after["disk_io"]:
                    disk_diff[metric + "_diff"] = after["disk_io"][metric] - before["disk_io"][metric]
            if disk_diff:
                diff["disk_io"] = disk_diff
        
        # Network I/O differences
        if "network_io" in before and "network_io" in after:
            net_diff = {}
            for metric in ["bytes_sent_mb", "bytes_recv_mb", "packets_sent", "packets_recv"]:
                if metric in before["network_io"] and metric in after["network_io"]:
                    net_diff[metric + "_diff"] = after["network_io"][metric] - before["network_io"][metric]
            if net_diff:
                diff["network_io"] = net_diff
        
        return diff
    
    except Exception as e:
        return {"error": f"Failed to calculate differences: {str(e)}"}

def get_container_stats(container_id):
    """Enhanced container stats collection with cloud support"""
    try:
        if not docker_client:
            return {"error": "Docker client not available"}
            
        container = docker_client.containers.get(container_id)
        stats = container.stats(stream=False)
        
        result = {
            "container_state": container.status,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        # CPU stats with enhanced cloud support
        try:
            cpu_stats = stats.get('cpu_stats', {})
            precpu_stats = stats.get('precpu_stats', {})
            
            cpu_usage = cpu_stats.get('cpu_usage', {})
            precpu_usage = precpu_stats.get('cpu_usage', {})
            
            cpu_delta = cpu_usage.get('total_usage', 0) - precpu_usage.get('total_usage', 0)
            system_delta = cpu_stats.get('system_cpu_usage', 0) - precpu_stats.get('system_cpu_usage', 0)
            
            num_cpus = cpu_stats.get('online_cpus', 
                                  len(cpu_usage.get('percpu_usage', [1])))
            
            cpu_percent = 0.0
            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * num_cpus * 100.0
            
            result["cpu"] = {
                "usage_percent": round(cpu_percent, 2),
                "cpu_count": num_cpus,
                "throttled_time": cpu_stats.get('throttling_data', {}).get('throttled_time', 0)
            }
        except Exception as e:
            result["cpu_error"] = str(e)
        
        # Memory stats
        try:
            memory_stats = stats.get('memory_stats', {})
            result["memory"] = {
                "usage_mb": round(memory_stats.get('usage', 0) / (1024 * 1024), 2),
                "limit_mb": round(memory_stats.get('limit', 0) / (1024 * 1024), 2),
                "usage_percent": (
                    (memory_stats.get('usage', 0) / memory_stats.get('limit', 1)) * 100
                    if memory_stats.get('limit', 0) > 0 else 0
                ),
                "stats": memory_stats.get('stats', {})
            }
        except Exception as e:
            result["memory_error"] = str(e)
        
        # Network stats with cloud support
        try:
            networks = stats.get('networks', {})
            result["network"] = {
                "interfaces": list(networks.keys()),
                "total": {
                    "rx_mb": sum(
                        net.get('rx_bytes', 0) / (1024 * 1024)
                        for net in networks.values()
                    ),
                    "tx_mb": sum(
                        net.get('tx_bytes', 0) / (1024 * 1024)
                        for net in networks.values()
                    )
                }
            }
        except Exception as e:
            result["network_error"] = str(e)
        
        # Disk I/O stats
        try:
            blkio_stats = stats.get('blkio_stats', {})
            result["disk"] = {
                "io_service_bytes": blkio_stats.get('io_service_bytes_recursive', []),
                "io_serviced": blkio_stats.get('io_serviced_recursive', [])
            }
        except Exception as e:
            result["disk_error"] = str(e)
            
        return result
        
    except Exception as e:
        return {"error": f"Failed to get container stats: {str(e)}"}

def metrics_collector():
    """Background thread to continuously collect metrics with cloud optimizations"""
    global current_metrics, container_info
    
    while True:
        try:
            # Get system metrics
            current_metrics = get_system_metrics()
            
            # If container is running, collect its stats
            if container_info["container_id"] and container_info["running"]:
                container_info["stats"] = get_container_stats(container_info["container_id"])
                
            time.sleep(2)  # Update every 2 seconds
        
        except Exception as e:
            print(f"Error collecting metrics: {e}")
            time.sleep(5)

@app.route('/api/baseline', methods=['GET'])
def capture_baseline():
    """Capture baseline metrics before running the container with multiple samples"""
    global baseline_metrics
    
    try:
        # Take multiple samples to get a stable baseline
        samples = []
        for _ in range(3):
            samples.append(get_system_metrics())
            time.sleep(1)  # Wait between samples
        
        # Calculate average for each metric
        avg_metrics = {
            "cpu": {
                "usage_percent": sum(s["cpu"]["usage_percent"] for s in samples) / len(samples),
                "cores": samples[0]["cpu"]["cores"],
                "threads": samples[0]["cpu"]["threads"],
                "load_avg": [
                    sum(s["cpu"]["load_avg"][i] for s in samples if s["cpu"]["load_avg"]) / 
                    len([s for s in samples if s["cpu"]["load_avg"]])
                    for i in range(3)
                ] if samples[0]["cpu"]["load_avg"] else None
            },
            "memory": {
                "used_mb": sum(s["memory"]["used_mb"] for s in samples) / len(samples),
                "available_mb": sum(s["memory"]["available_mb"] for s in samples) / len(samples),
                "usage_percent": sum(s["memory"]["usage_percent"] for s in samples) / len(samples)
            },
            "gpu": samples[0]["gpu"],  # GPU metrics don't average well
            "disk_io": samples[-1]["disk_io"],  # Use last sample for counters
            "network_io": samples[-1]["network_io"],  # Use last sample for counters
            "timestamp": datetime.now().isoformat() + "Z",
            "system": samples[0]["system"]
        }
        
        baseline_metrics = avg_metrics
        
        return jsonify({
            "message": "Baseline metrics captured successfully (3-sample average)",
            "baseline": baseline_metrics,
            "samples": samples
        })
    
    except Exception as e:
        return jsonify({"error": f"Failed to capture baseline: {str(e)}"}), 500

@app.route('/api/start-container', methods=['POST'])
def start_container():
    """Start a container with comprehensive resource monitoring"""
    global container_info, baseline_metrics
    
    if not docker_client:
        return jsonify({"error": "Docker client not available"}), 500

    # Ensure we have a baseline
    if baseline_metrics.get("timestamp") is None:
        capture_baseline()

    data = request.json
    if not data or 'image' not in data:
        return jsonify({"error": "Missing required 'image' parameter"}), 400

    try:
        # Get container configuration from request
        image = data['image']
        command = data.get('command')
        environment = data.get('environment')
        ports = data.get('ports')
        volumes = data.get('volumes')
        name = data.get('name')
        
        # Pull the image if not already present
        try:
            docker_client.images.get(image)
        except docker.errors.ImageNotFound:
            print(f"Pulling image {image}...")
            docker_client.images.pull(image)
        
        # Create the container
        container = docker_client.containers.create(
            image=image,
            command=command,
            environment=environment,
            ports=ports,
            volumes=volumes,
            name=name,
            detach=True
        )
        
        # Capture pre-start metrics
        pre_start_metrics = get_system_metrics()
        
        # Start the container
        container.start()
        start_time = datetime.utcnow()
        
        # Wait a moment for the container to initialize
        time.sleep(1)
        
        # Capture post-start metrics
        post_start_metrics = get_system_metrics()
        
        # Get container stats
        container_stats = get_container_stats(container.id)
        
        # Update container info
        container_info = {
            "container_id": container.id,
            "image": image,
            "running": True,
            "start_time": start_time.isoformat() + "Z",
            "command": command,
            "stats": container_stats
        }
        
        # Calculate immediate impact
        startup_diff = calculate_differences(pre_start_metrics, post_start_metrics)
        
        return jsonify({
            "message": "Container started successfully",
            "container": {
                "id": container.id,
                "name": container.name,
                "status": container.status,
                "image": image
            },
            "metrics": {
                "pre_start": pre_start_metrics,
                "post_start": post_start_metrics,
                "startup_impact": startup_diff
            },
            "baseline": baseline_metrics
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stop-container', methods=['POST'])
def stop_container():
    """Stop the running container and calculate comprehensive resource usage"""
    global container_info
    
    if not docker_client:
        return jsonify({"error": "Docker client not available"}), 500
    
    if not container_info["container_id"] or not container_info["running"]:
        return jsonify({"error": "No container is currently running"}), 400
    
    try:
        # Get final metrics before stopping
        pre_stop_metrics = get_system_metrics()
        container_stats = get_container_stats(container_info["container_id"])
        
        # Stop the container
        container = docker_client.containers.get(container_info["container_id"])
        container.stop()
        
        # Wait a moment for resources to be released
        time.sleep(1)
        
        # Get post-stop metrics
        post_stop_metrics = get_system_metrics()
        
        # Calculate differences
        runtime_diff = calculate_differences(baseline_metrics, pre_stop_metrics)
        cleanup_diff = calculate_differences(pre_stop_metrics, post_stop_metrics)
        
        # Calculate duration
        duration = (datetime.fromisoformat(pre_stop_metrics["timestamp"].replace('Z', '')) - 
                   datetime.fromisoformat(container_info["start_time"].replace('Z', ''))).total_seconds()
        
        # Update container info
        container_info["running"] = False
        
        return jsonify({
            "message": "Container stopped successfully",
            "metrics": {
                "pre_stop": pre_stop_metrics,
                "post_stop": post_stop_metrics,
                "runtime_impact": runtime_diff,
                "cleanup_impact": cleanup_diff
            },
            "container": {
                "id": container_info["container_id"],
                "image": container_info["image"],
                "duration_seconds": duration,
                "stats": container_stats
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/current-metrics', methods=['GET'])
def get_current_metrics():
    """Get current metrics with detailed comparisons"""
    try:
        # Calculate differences from baseline
        differences = calculate_differences(baseline_metrics, current_metrics)
        
        return jsonify({
            "current": current_metrics,
            "baseline": baseline_metrics,
            "differences": differences,
            "container": {
                "running": container_info["running"],
                "stats": container_info["stats"]
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ... (keep the remaining endpoints like /api/list-containers, /api/list-images, /health)

if __name__ == '__main__':
    # Start metrics collector in a background thread
    collector_thread = threading.Thread(target=metrics_collector, daemon=True)
    collector_thread.start()
    
    # Start the Flask app with production-ready settings
    app.run(host='0.0.0.0', port=5000, threaded=True)