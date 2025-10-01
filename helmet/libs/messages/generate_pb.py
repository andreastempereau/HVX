#!/usr/bin/env python3
"""Generate Python protobuf files from helmet.proto"""

import subprocess
import sys
from pathlib import Path

def generate_protobuf():
    """Generate Python protobuf and gRPC files"""
    proto_dir = Path(__file__).parent
    proto_file = proto_dir / "helmet.proto"

    if not proto_file.exists():
        print(f"Error: {proto_file} not found")
        sys.exit(1)

    # Generate Python protobuf files
    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"--proto_path={proto_dir}",
        f"--python_out={proto_dir}",
        f"--grpc_python_out={proto_dir}",
        str(proto_file)
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error generating protobuf files:")
        print(result.stderr)
        sys.exit(1)

    # Fix import issues in generated gRPC file
    grpc_file = proto_dir / "helmet_pb2_grpc.py"
    if grpc_file.exists():
        content = grpc_file.read_text()
        # Fix relative import
        content = content.replace(
            "import helmet_pb2 as helmet__pb2",
            "from . import helmet_pb2 as helmet__pb2"
        )
        grpc_file.write_text(content)
        print("Fixed import in helmet_pb2_grpc.py")

    print("Successfully generated protobuf files:")
    for pb_file in proto_dir.glob("*_pb2*.py"):
        print(f"  {pb_file.name}")

if __name__ == "__main__":
    generate_protobuf()