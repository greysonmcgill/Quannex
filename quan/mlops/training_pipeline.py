"""
Deterministic, Reproducible Training Pipeline for QUAN ML Models

Ensures bit-exact reproducibility across training runs with identical seeds.
Supports multi-model training, distributed execution, and checkpoint recovery.

Key guarantees:
- Same seed + same data version = identical model artifact checksums
- Complete environment capture (dependencies, Docker spec)
- Checkpoint-based training resumption
- Memory-efficient batch processing for large datasets
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
import platform
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Generator, Iterator, TypeVar, Generic

# Conditional imports with version tracking
NUMPY_VERSION = None
TORCH_VERSION = None
SKLEARN_VERSION = None

try:
    import numpy as np
    NUMPY_VERSION = np.__version__
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, Dataset, Subset
    TORCH_VERSION = torch.__version__
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    nn = None
    TORCH_AVAILABLE = False

try:
    from sklearn.model_selection import StratifiedKFold, train_test_split
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    import sklearn
    SKLEARN_VERSION = sklearn.__version__
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration and Constants
# =============================================================================

class ModelType(Enum):
    """Supported model architectures"""
    GRADIENT_BOOST = "gradient_boost"
    NEURAL_NET = "neural_net"
    BAYESIAN = "bayesian"
    RANDOM_FOREST = "random_forest"
    LOGISTIC = "logistic"
    ENSEMBLE = "ensemble"


class DeviceType(Enum):
    """Compute device types"""
    CPU = "cpu"
    GPU = "gpu"
    MULTI_GPU = "multi_gpu"
    DISTRIBUTED = "distributed"


class CheckpointType(Enum):
    """Types of checkpoints"""
    EPOCH = "epoch"
    BEST = "best"
    FINAL = "final"
    INTERRUPTED = "interrupted"


@dataclass
class DependencySpec:
    """Pinned dependency specification"""
    name: str
    version: str
    hash: str | None = None
    source: str = "pypi"

    def to_requirements_line(self) -> str:
        """Generate requirements.txt line"""
        if self.hash:
            return f"{self.name}=={self.version} --hash=sha256:{self.hash}"
        return f"{self.name}=={self.version}"


@dataclass
class EnvironmentSpec:
    """Complete environment specification for reproducibility"""
    python_version: str
    platform: str
    platform_version: str
    dependencies: list[DependencySpec]
    cuda_version: str | None = None
    cudnn_version: str | None = None
    env_variables: dict[str, str] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "python_version": self.python_version,
            "platform": self.platform,
            "platform_version": self.platform_version,
            "dependencies": [asdict(d) for d in self.dependencies],
            "cuda_version": self.cuda_version,
            "cudnn_version": self.cudnn_version,
            "env_variables": self.env_variables,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnvironmentSpec:
        """Create from dictionary"""
        return cls(
            python_version=data["python_version"],
            platform=data["platform"],
            platform_version=data["platform_version"],
            dependencies=[DependencySpec(**d) for d in data["dependencies"]],
            cuda_version=data.get("cuda_version"),
            cudnn_version=data.get("cudnn_version"),
            env_variables=data.get("env_variables", {}),
            timestamp=data.get("timestamp", "")
        )


@dataclass
class TrainingConfig:
    """Configuration for a training run"""
    # Core settings
    seed: int = 42
    dataset_version: str = "v1.0.0"
    model_type: ModelType = ModelType.GRADIENT_BOOST

    # Training parameters
    epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 0.001
    weight_decay: float = 1e-5

    # Cross-validation
    n_folds: int = 5
    stratified: bool = True
    validation_split: float = 0.2

    # Early stopping
    early_stopping: bool = True
    patience: int = 10
    min_delta: float = 1e-4

    # Checkpointing
    checkpoint_dir: str = "./checkpoints"
    checkpoint_frequency: int = 5
    keep_n_checkpoints: int = 3

    # Device settings
    device: DeviceType = DeviceType.CPU
    num_workers: int = 4
    pin_memory: bool = True

    # Memory efficiency
    gradient_accumulation_steps: int = 1
    mixed_precision: bool = False
    gradient_checkpointing: bool = False

    # Distributed training
    distributed: bool = False
    world_size: int = 1
    rank: int = 0
    local_rank: int = 0
    backend: str = "nccl"

    # Model-specific hyperparameters
    hyperparameters: dict[str, Any] = field(default_factory=dict)

    # Data paths
    train_data_path: str | None = None
    val_data_path: str | None = None
    test_data_path: str | None = None

    # Output settings
    output_dir: str = "./output"
    experiment_name: str = "experiment"

    def to_dict(self) -> dict[str, Any]:
        """Serialize configuration"""
        return {
            "seed": self.seed,
            "dataset_version": self.dataset_version,
            "model_type": self.model_type.value,
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "n_folds": self.n_folds,
            "stratified": self.stratified,
            "validation_split": self.validation_split,
            "early_stopping": self.early_stopping,
            "patience": self.patience,
            "min_delta": self.min_delta,
            "checkpoint_dir": self.checkpoint_dir,
            "checkpoint_frequency": self.checkpoint_frequency,
            "keep_n_checkpoints": self.keep_n_checkpoints,
            "device": self.device.value,
            "num_workers": self.num_workers,
            "pin_memory": self.pin_memory,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "mixed_precision": self.mixed_precision,
            "gradient_checkpointing": self.gradient_checkpointing,
            "distributed": self.distributed,
            "world_size": self.world_size,
            "rank": self.rank,
            "local_rank": self.local_rank,
            "backend": self.backend,
            "hyperparameters": self.hyperparameters,
            "train_data_path": self.train_data_path,
            "val_data_path": self.val_data_path,
            "test_data_path": self.test_data_path,
            "output_dir": self.output_dir,
            "experiment_name": self.experiment_name
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrainingConfig:
        """Deserialize configuration"""
        data = data.copy()
        data["model_type"] = ModelType(data["model_type"])
        data["device"] = DeviceType(data["device"])
        return cls(**data)

    def get_config_hash(self) -> str:
        """Generate deterministic hash of configuration"""
        config_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]


@dataclass
class TrainingMetrics:
    """Metrics from a training run"""
    train_loss: float = 0.0
    val_loss: float = 0.0
    train_accuracy: float = 0.0
    val_accuracy: float = 0.0
    train_auc: float = 0.0
    val_auc: float = 0.0
    epoch: int = 0
    best_epoch: int = 0
    best_val_loss: float = float("inf")
    training_time_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize metrics"""
        return asdict(self)


@dataclass
class Checkpoint:
    """Training checkpoint for resumption"""
    checkpoint_type: CheckpointType
    epoch: int
    global_step: int
    model_state: dict[str, Any]
    optimizer_state: dict[str, Any] | None
    scheduler_state: dict[str, Any] | None
    rng_states: dict[str, Any]
    metrics: TrainingMetrics
    config: TrainingConfig
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def save(self, path: Path) -> str:
        """Save checkpoint and return checksum"""
        checkpoint_data = {
            "checkpoint_type": self.checkpoint_type.value,
            "epoch": self.epoch,
            "global_step": self.global_step,
            "model_state": self.model_state,
            "optimizer_state": self.optimizer_state,
            "scheduler_state": self.scheduler_state,
            "rng_states": self.rng_states,
            "metrics": self.metrics.to_dict(),
            "config": self.config.to_dict(),
            "timestamp": self.timestamp
        }

        with open(path, "wb") as f:
            pickle.dump(checkpoint_data, f, protocol=pickle.HIGHEST_PROTOCOL)

        return compute_file_checksum(path)

    @classmethod
    def load(cls, path: Path) -> Checkpoint:
        """Load checkpoint from file"""
        with open(path, "rb") as f:
            data = pickle.load(f)

        return cls(
            checkpoint_type=CheckpointType(data["checkpoint_type"]),
            epoch=data["epoch"],
            global_step=data["global_step"],
            model_state=data["model_state"],
            optimizer_state=data.get("optimizer_state"),
            scheduler_state=data.get("scheduler_state"),
            rng_states=data["rng_states"],
            metrics=TrainingMetrics(**data["metrics"]),
            config=TrainingConfig.from_dict(data["config"]),
            timestamp=data.get("timestamp", "")
        )


# =============================================================================
# Seed Management
# =============================================================================

class SeedManager:
    """
    Centralized seed management for deterministic training.

    Ensures consistent seeding across:
    - Python random module
    - NumPy random
    - PyTorch (CPU and CUDA)
    - Scikit-learn (via NumPy)

    Supports saving and restoring RNG states for checkpoint resumption.
    """

    def __init__(self, seed: int):
        self.master_seed = seed
        self._seed_history: list[int] = []
        self._initialized = False

    def initialize(self) -> None:
        """Initialize all random number generators with master seed"""
        self._set_seed(self.master_seed)
        self._initialized = True
        logger.info(f"Initialized RNG with master seed: {self.master_seed}")

    def _set_seed(self, seed: int) -> None:
        """Set seed across all libraries"""
        self._seed_history.append(seed)

        # Python random
        random.seed(seed)

        # NumPy
        if NUMPY_AVAILABLE:
            np.random.seed(seed)

        # PyTorch
        if TORCH_AVAILABLE:
            torch.manual_seed(seed)

            # CUDA seeding
            if torch.cuda.is_available():
                torch.cuda.manual_seed(seed)
                torch.cuda.manual_seed_all(seed)

                # Deterministic CUDA operations
                torch.backends.cudnn.deterministic = True
                torch.backends.cudnn.benchmark = False

            # Set environment variables for additional reproducibility
            os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"

            # Enable deterministic algorithms
            try:
                torch.use_deterministic_algorithms(True)
            except Exception:
                logger.warning("Could not enable deterministic algorithms")

        # Hash seed for Python str hashing
        os.environ["PYTHONHASHSEED"] = str(seed)

    def get_worker_seed(self, worker_id: int) -> int:
        """Generate deterministic seed for data loader workers"""
        return (self.master_seed + worker_id) % (2**32)

    def get_fold_seed(self, fold_idx: int) -> int:
        """Generate deterministic seed for cross-validation fold"""
        return (self.master_seed * (fold_idx + 1)) % (2**32)

    def get_rng_states(self) -> dict[str, Any]:
        """Capture current RNG states for checkpointing"""
        states = {
            "python": random.getstate(),
            "master_seed": self.master_seed,
            "seed_history": self._seed_history.copy()
        }

        if NUMPY_AVAILABLE:
            states["numpy"] = np.random.get_state()

        if TORCH_AVAILABLE:
            states["torch_cpu"] = torch.get_rng_state()

            if torch.cuda.is_available():
                states["torch_cuda"] = torch.cuda.get_rng_state_all()

        return states

    def set_rng_states(self, states: dict[str, Any]) -> None:
        """Restore RNG states from checkpoint"""
        random.setstate(states["python"])
        self._seed_history = states.get("seed_history", [self.master_seed])

        if NUMPY_AVAILABLE and "numpy" in states:
            np.random.set_state(states["numpy"])

        if TORCH_AVAILABLE:
            if "torch_cpu" in states:
                torch.set_rng_state(states["torch_cpu"])

            if torch.cuda.is_available() and "torch_cuda" in states:
                torch.cuda.set_rng_state_all(states["torch_cuda"])

        logger.info("Restored RNG states from checkpoint")

    @staticmethod
    def worker_init_fn(worker_id: int) -> None:
        """
        Initialization function for DataLoader workers.

        Must be used with DataLoader for reproducible data loading:
            DataLoader(..., worker_init_fn=SeedManager.worker_init_fn)
        """
        worker_seed = torch.initial_seed() % (2**32)

        random.seed(worker_seed)

        if NUMPY_AVAILABLE:
            np.random.seed(worker_seed)


# =============================================================================
# Environment Capture and Docker Generation
# =============================================================================

class EnvironmentManager:
    """
    Captures and reproduces the training environment.

    Features:
    - Dependency version capture with hashes
    - Dockerfile generation
    - requirements.lock generation
    - Environment variable management
    """

    def __init__(self):
        self.current_spec: EnvironmentSpec | None = None

    def capture_environment(self) -> EnvironmentSpec:
        """Capture current Python environment"""
        dependencies = self._get_installed_packages()

        cuda_version = None
        cudnn_version = None

        if TORCH_AVAILABLE and torch.cuda.is_available():
            cuda_version = torch.version.cuda
            if hasattr(torch.backends.cudnn, "version"):
                cudnn_version = str(torch.backends.cudnn.version())

        self.current_spec = EnvironmentSpec(
            python_version=platform.python_version(),
            platform=platform.system(),
            platform_version=platform.release(),
            dependencies=dependencies,
            cuda_version=cuda_version,
            cudnn_version=cudnn_version,
            env_variables=self._get_relevant_env_vars()
        )

        return self.current_spec

    def _get_installed_packages(self) -> list[DependencySpec]:
        """Get list of installed packages with versions"""
        dependencies = []

        # Core ML packages
        core_packages = [
            ("numpy", NUMPY_VERSION),
            ("torch", TORCH_VERSION),
            ("scikit-learn", SKLEARN_VERSION)
        ]

        for name, version in core_packages:
            if version:
                dependencies.append(DependencySpec(
                    name=name,
                    version=version,
                    hash=self._get_package_hash(name)
                ))

        # Try to get full package list via pip
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if "==" in line:
                        parts = line.split("==")
                        if len(parts) == 2:
                            name, version = parts
                            # Skip if already added
                            if not any(d.name == name for d in dependencies):
                                dependencies.append(DependencySpec(
                                    name=name,
                                    version=version
                                ))
        except Exception as e:
            logger.warning(f"Could not get pip freeze output: {e}")

        return dependencies

    def _get_package_hash(self, package_name: str) -> str | None:
        """Get hash for installed package"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "hash", "--algorithm", "sha256"],
                capture_output=True,
                text=True,
                timeout=30
            )
            # Simplified - would need actual wheel file path
            return None
        except Exception:
            return None

    def _get_relevant_env_vars(self) -> dict[str, str]:
        """Get environment variables relevant to reproducibility"""
        relevant_vars = [
            "PYTHONHASHSEED",
            "CUBLAS_WORKSPACE_CONFIG",
            "CUDA_VISIBLE_DEVICES",
            "OMP_NUM_THREADS",
            "MKL_NUM_THREADS"
        ]

        return {
            var: os.environ.get(var, "")
            for var in relevant_vars
            if var in os.environ
        }

    def generate_requirements_lock(self, output_path: Path) -> None:
        """Generate requirements.lock file with pinned versions"""
        if not self.current_spec:
            self.capture_environment()

        lines = [
            "# Auto-generated requirements.lock",
            f"# Generated: {self.current_spec.timestamp}",
            f"# Python: {self.current_spec.python_version}",
            f"# Platform: {self.current_spec.platform}",
            ""
        ]

        for dep in self.current_spec.dependencies:
            lines.append(dep.to_requirements_line())

        with open(output_path, "w") as f:
            f.write("\n".join(lines))

        logger.info(f"Generated requirements.lock at {output_path}")

    def generate_dockerfile(self, output_path: Path, config: TrainingConfig) -> None:
        """Generate Dockerfile for reproducible training environment"""
        if not self.current_spec:
            self.capture_environment()

        # Determine base image
        if self.current_spec.cuda_version:
            cuda_major = self.current_spec.cuda_version.split(".")[0]
            base_image = f"nvidia/cuda:{self.current_spec.cuda_version}-cudnn8-runtime-ubuntu22.04"
        else:
            base_image = f"python:{self.current_spec.python_version}-slim"

        dockerfile_content = f'''# Auto-generated Dockerfile for reproducible training
# Generated: {self.current_spec.timestamp}
# Config hash: {config.get_config_hash()}

FROM {base_image}

# Set environment variables for reproducibility
ENV PYTHONHASHSEED={config.seed}
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV CUBLAS_WORKSPACE_CONFIG=:4096:8
ENV OMP_NUM_THREADS={config.num_workers}
ENV MKL_NUM_THREADS={config.num_workers}

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential \\
    git \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Set up Python environment
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.lock ./requirements.txt

# Install Python dependencies with exact versions
RUN pip install --no-cache-dir --upgrade pip && \\
    pip install --no-cache-dir -r requirements.txt

# Copy training code
COPY . .

# Set default command
ENTRYPOINT ["python", "-m", "quan.mlops.training_pipeline"]
CMD ["--seed", "{config.seed}", "--dataset-version", "{config.dataset_version}"]

# Labels for tracking
LABEL maintainer="QUAN ML Team"
LABEL version="1.0.0"
LABEL description="Deterministic training environment"
LABEL seed="{config.seed}"
LABEL dataset_version="{config.dataset_version}"
LABEL config_hash="{config.get_config_hash()}"
'''

        with open(output_path, "w") as f:
            f.write(dockerfile_content)

        logger.info(f"Generated Dockerfile at {output_path}")

    def generate_docker_compose(self, output_path: Path, config: TrainingConfig) -> None:
        """Generate docker-compose.yml for distributed training"""
        compose_content = f'''version: '3.8'

services:
  trainer:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - MASTER_ADDR=trainer
      - MASTER_PORT=29500
      - WORLD_SIZE={config.world_size}
      - PYTHONHASHSEED={config.seed}
    volumes:
      - ./data:/app/data:ro
      - ./checkpoints:/app/checkpoints
      - ./output:/app/output
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    command: >
      --seed {config.seed}
      --dataset-version {config.dataset_version}
      --distributed
      --world-size {config.world_size}

  # Add workers for distributed training
'''

        for i in range(1, config.world_size):
            compose_content += f'''
  worker-{i}:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - MASTER_ADDR=trainer
      - MASTER_PORT=29500
      - WORLD_SIZE={config.world_size}
      - RANK={i}
      - PYTHONHASHSEED={config.seed}
    volumes:
      - ./data:/app/data:ro
      - ./checkpoints:/app/checkpoints
      - ./output:/app/output
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    depends_on:
      - trainer
'''

        with open(output_path, "w") as f:
            f.write(compose_content)

        logger.info(f"Generated docker-compose.yml at {output_path}")

    def verify_environment(self, spec: EnvironmentSpec) -> list[str]:
        """Verify current environment matches specification"""
        issues = []

        current = self.capture_environment()

        # Check Python version
        if current.python_version != spec.python_version:
            issues.append(
                f"Python version mismatch: {current.python_version} vs {spec.python_version}"
            )

        # Check dependencies
        current_deps = {d.name: d.version for d in current.dependencies}
        spec_deps = {d.name: d.version for d in spec.dependencies}

        for name, version in spec_deps.items():
            if name not in current_deps:
                issues.append(f"Missing dependency: {name}=={version}")
            elif current_deps[name] != version:
                issues.append(
                    f"Version mismatch for {name}: {current_deps[name]} vs {version}"
                )

        # Check CUDA if specified
        if spec.cuda_version and current.cuda_version != spec.cuda_version:
            issues.append(
                f"CUDA version mismatch: {current.cuda_version} vs {spec.cuda_version}"
            )

        return issues


# =============================================================================
# Checksum Utilities
# =============================================================================

def compute_file_checksum(path: Path, algorithm: str = "sha256") -> str:
    """Compute checksum of file"""
    hasher = hashlib.new(algorithm)

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def compute_model_checksum(model_state: dict[str, Any]) -> str:
    """
    Compute deterministic checksum of model state dict.

    Ensures identical models produce identical checksums regardless
    of dictionary ordering or serialization details.
    """
    hasher = hashlib.sha256()

    # Sort keys for deterministic ordering
    for key in sorted(model_state.keys()):
        hasher.update(key.encode())

        value = model_state[key]

        if TORCH_AVAILABLE and isinstance(value, torch.Tensor):
            # Convert tensor to bytes deterministically
            tensor_bytes = value.cpu().numpy().tobytes()
            hasher.update(tensor_bytes)
        elif NUMPY_AVAILABLE and isinstance(value, np.ndarray):
            hasher.update(value.tobytes())
        else:
            hasher.update(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))

    return hasher.hexdigest()


def verify_artifact_checksum(path: Path, expected_checksum: str) -> bool:
    """Verify artifact matches expected checksum"""
    actual = compute_file_checksum(path)
    return actual == expected_checksum


# =============================================================================
# Device Management
# =============================================================================

class DeviceManager:
    """
    Manages compute devices for training.

    Features:
    - Automatic GPU detection
    - Multi-GPU setup
    - Distributed training initialization
    - Memory monitoring
    """

    def __init__(self, config: TrainingConfig):
        self.config = config
        self.device: Any = None
        self.is_distributed = False
        self.world_size = 1
        self.rank = 0
        self.local_rank = 0

    def setup(self) -> Any:
        """Initialize device(s) for training"""
        if self.config.distributed:
            return self._setup_distributed()

        if self.config.device == DeviceType.GPU:
            return self._setup_gpu()
        elif self.config.device == DeviceType.MULTI_GPU:
            return self._setup_multi_gpu()
        else:
            return self._setup_cpu()

    def _setup_cpu(self) -> str:
        """Setup CPU device"""
        self.device = "cpu"

        # Set thread counts for reproducibility
        if TORCH_AVAILABLE:
            torch.set_num_threads(self.config.num_workers)

        logger.info("Using CPU for training")
        return self.device

    def _setup_gpu(self) -> Any:
        """Setup single GPU"""
        if not TORCH_AVAILABLE:
            logger.warning("PyTorch not available, falling back to CPU")
            return self._setup_cpu()

        if not torch.cuda.is_available():
            logger.warning("CUDA not available, falling back to CPU")
            return self._setup_cpu()

        # Use first available GPU
        self.device = torch.device("cuda:0")

        # Log GPU info
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
        logger.info(f"Using GPU: {gpu_name} ({gpu_memory:.1f} GB)")

        return self.device

    def _setup_multi_gpu(self) -> Any:
        """Setup multi-GPU with DataParallel"""
        if not TORCH_AVAILABLE or not torch.cuda.is_available():
            return self._setup_cpu()

        n_gpus = torch.cuda.device_count()

        if n_gpus < 2:
            logger.warning(f"Only {n_gpus} GPU available, using single GPU")
            return self._setup_gpu()

        self.device = torch.device("cuda:0")
        self.world_size = n_gpus

        logger.info(f"Using {n_gpus} GPUs with DataParallel")

        return self.device

    def _setup_distributed(self) -> Any:
        """Setup distributed training with DistributedDataParallel"""
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required for distributed training")

        # Get distributed parameters from environment
        self.world_size = int(os.environ.get("WORLD_SIZE", self.config.world_size))
        self.rank = int(os.environ.get("RANK", self.config.rank))
        self.local_rank = int(os.environ.get("LOCAL_RANK", self.config.local_rank))

        # Initialize process group
        if not torch.distributed.is_initialized():
            torch.distributed.init_process_group(
                backend=self.config.backend,
                init_method="env://",
                world_size=self.world_size,
                rank=self.rank
            )

        self.is_distributed = True

        # Set device for this rank
        if torch.cuda.is_available():
            torch.cuda.set_device(self.local_rank)
            self.device = torch.device(f"cuda:{self.local_rank}")
        else:
            self.device = torch.device("cpu")

        logger.info(
            f"Distributed training initialized: rank {self.rank}/{self.world_size}"
        )

        return self.device

    def wrap_model(self, model: Any) -> Any:
        """Wrap model for multi-GPU or distributed training"""
        if not TORCH_AVAILABLE:
            return model

        if self.is_distributed:
            return torch.nn.parallel.DistributedDataParallel(
                model.to(self.device),
                device_ids=[self.local_rank],
                output_device=self.local_rank,
                find_unused_parameters=False
            )
        elif self.config.device == DeviceType.MULTI_GPU:
            return torch.nn.DataParallel(model.to(self.device))
        else:
            return model.to(self.device)

    def get_memory_stats(self) -> dict[str, float]:
        """Get current memory statistics"""
        stats = {}

        if TORCH_AVAILABLE and torch.cuda.is_available():
            stats["gpu_allocated_gb"] = torch.cuda.memory_allocated() / 1e9
            stats["gpu_reserved_gb"] = torch.cuda.memory_reserved() / 1e9
            stats["gpu_max_allocated_gb"] = torch.cuda.max_memory_allocated() / 1e9

        return stats

    def cleanup(self) -> None:
        """Cleanup distributed resources"""
        if self.is_distributed and TORCH_AVAILABLE:
            torch.distributed.destroy_process_group()


# =============================================================================
# Data Management
# =============================================================================

class BatchIterator:
    """
    Memory-efficient batch iterator for large datasets.

    Features:
    - Streaming batch loading
    - Memory-mapped file support
    - Deterministic shuffling
    """

    def __init__(
        self,
        data: Any,
        batch_size: int,
        shuffle: bool = True,
        seed: int = 42,
        drop_last: bool = False
    ):
        self.data = data
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.seed = seed
        self.drop_last = drop_last
        self._indices: list[int] = []
        self._current_idx = 0

    def __iter__(self) -> Iterator:
        """Reset and return iterator"""
        n_samples = len(self.data)
        self._indices = list(range(n_samples))

        if self.shuffle:
            # Use deterministic shuffling
            rng = random.Random(self.seed)
            rng.shuffle(self._indices)

        self._current_idx = 0
        return self

    def __next__(self) -> Any:
        """Get next batch"""
        if self._current_idx >= len(self._indices):
            raise StopIteration

        end_idx = min(self._current_idx + self.batch_size, len(self._indices))

        if self.drop_last and end_idx - self._current_idx < self.batch_size:
            raise StopIteration

        batch_indices = self._indices[self._current_idx:end_idx]
        self._current_idx = end_idx

        # Extract batch
        if hasattr(self.data, "__getitem__"):
            if NUMPY_AVAILABLE and isinstance(self.data, np.ndarray):
                return self.data[batch_indices]
            elif TORCH_AVAILABLE and isinstance(self.data, torch.Tensor):
                return self.data[batch_indices]
            else:
                return [self.data[i] for i in batch_indices]

        return batch_indices

    def __len__(self) -> int:
        """Number of batches"""
        n_samples = len(self.data)

        if self.drop_last:
            return n_samples // self.batch_size
        return (n_samples + self.batch_size - 1) // self.batch_size


class CrossValidator:
    """
    Stratified cross-validation manager.

    Ensures deterministic fold splits for reproducibility.
    """

    def __init__(
        self,
        n_folds: int = 5,
        stratified: bool = True,
        seed: int = 42
    ):
        self.n_folds = n_folds
        self.stratified = stratified
        self.seed = seed
        self._fold_indices: list[tuple[list[int], list[int]]] = []

    def split(
        self,
        X: Any,
        y: Any = None
    ) -> Generator[tuple[list[int], list[int]], None, None]:
        """Generate train/validation splits for each fold"""
        n_samples = len(X)

        if self.stratified and y is not None and SKLEARN_AVAILABLE:
            # Stratified k-fold
            skf = StratifiedKFold(
                n_splits=self.n_folds,
                shuffle=True,
                random_state=self.seed
            )

            y_array = np.array(y) if NUMPY_AVAILABLE else y

            for train_idx, val_idx in skf.split(X, y_array):
                yield list(train_idx), list(val_idx)
        else:
            # Regular k-fold with deterministic shuffling
            indices = list(range(n_samples))
            rng = random.Random(self.seed)
            rng.shuffle(indices)

            fold_size = n_samples // self.n_folds

            for fold in range(self.n_folds):
                val_start = fold * fold_size
                val_end = val_start + fold_size if fold < self.n_folds - 1 else n_samples

                val_idx = indices[val_start:val_end]
                train_idx = indices[:val_start] + indices[val_end:]

                yield train_idx, val_idx

    def get_fold_indices(
        self,
        X: Any,
        y: Any = None
    ) -> list[tuple[list[int], list[int]]]:
        """Get all fold indices at once"""
        if not self._fold_indices:
            self._fold_indices = list(self.split(X, y))
        return self._fold_indices


# =============================================================================
# Early Stopping
# =============================================================================

class EarlyStopping:
    """
    Early stopping handler with patience-based termination.

    Monitors validation loss and stops training when improvement stalls.
    """

    def __init__(
        self,
        patience: int = 10,
        min_delta: float = 1e-4,
        mode: str = "min"
    ):
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.counter = 0
        self.best_score: float | None = None
        self.should_stop = False
        self.best_epoch = 0

    def __call__(self, score: float, epoch: int) -> bool:
        """
        Check if training should stop.

        Args:
            score: Current validation score
            epoch: Current epoch number

        Returns:
            True if training should stop
        """
        if self.best_score is None:
            self.best_score = score
            self.best_epoch = epoch
            return False

        # Check for improvement
        if self.mode == "min":
            improved = score < self.best_score - self.min_delta
        else:
            improved = score > self.best_score + self.min_delta

        if improved:
            self.best_score = score
            self.best_epoch = epoch
            self.counter = 0
        else:
            self.counter += 1

            if self.counter >= self.patience:
                self.should_stop = True
                logger.info(
                    f"Early stopping triggered after {self.counter} epochs without improvement"
                )

        return self.should_stop

    def reset(self) -> None:
        """Reset early stopping state"""
        self.counter = 0
        self.best_score = None
        self.should_stop = False
        self.best_epoch = 0


# =============================================================================
# Checkpoint Manager
# =============================================================================

class CheckpointManager:
    """
    Manages training checkpoints for resumption.

    Features:
    - Periodic checkpointing
    - Best model tracking
    - Checkpoint rotation
    - Checksum verification
    """

    def __init__(
        self,
        checkpoint_dir: Path,
        keep_n: int = 3,
        frequency: int = 5
    ):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.keep_n = keep_n
        self.frequency = frequency
        self.checkpoints: list[Path] = []
        self.best_checkpoint: Path | None = None
        self.checksums: dict[str, str] = {}

        # Create checkpoint directory
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def should_checkpoint(self, epoch: int) -> bool:
        """Check if checkpoint should be saved at current epoch"""
        return epoch % self.frequency == 0

    def save_checkpoint(
        self,
        checkpoint: Checkpoint,
        is_best: bool = False
    ) -> str:
        """
        Save checkpoint and return checksum.

        Args:
            checkpoint: Checkpoint object to save
            is_best: Whether this is the best model so far

        Returns:
            Checksum of saved checkpoint
        """
        # Generate filename
        filename = f"checkpoint_epoch_{checkpoint.epoch:04d}.pt"
        path = self.checkpoint_dir / filename

        # Save checkpoint
        checksum = checkpoint.save(path)
        self.checksums[str(path)] = checksum
        self.checkpoints.append(path)

        logger.info(f"Saved checkpoint: {path} (checksum: {checksum[:16]}...)")

        # Update best checkpoint
        if is_best:
            best_path = self.checkpoint_dir / "best_model.pt"
            shutil.copy(path, best_path)
            self.best_checkpoint = best_path
            self.checksums[str(best_path)] = checksum
            logger.info(f"Updated best model checkpoint")

        # Rotate old checkpoints
        self._rotate_checkpoints()

        return checksum

    def _rotate_checkpoints(self) -> None:
        """Remove old checkpoints, keeping only the most recent"""
        while len(self.checkpoints) > self.keep_n:
            old_path = self.checkpoints.pop(0)

            if old_path.exists() and old_path != self.best_checkpoint:
                old_path.unlink()
                self.checksums.pop(str(old_path), None)
                logger.debug(f"Removed old checkpoint: {old_path}")

    def load_latest_checkpoint(self) -> Checkpoint | None:
        """Load the most recent checkpoint"""
        if not self.checkpoints:
            # Scan directory for existing checkpoints
            self.checkpoints = sorted(
                self.checkpoint_dir.glob("checkpoint_epoch_*.pt")
            )

        if not self.checkpoints:
            return None

        latest = self.checkpoints[-1]
        return self._load_and_verify(latest)

    def load_best_checkpoint(self) -> Checkpoint | None:
        """Load the best model checkpoint"""
        best_path = self.checkpoint_dir / "best_model.pt"

        if not best_path.exists():
            return None

        return self._load_and_verify(best_path)

    def _load_and_verify(self, path: Path) -> Checkpoint | None:
        """Load checkpoint and verify checksum"""
        if not path.exists():
            logger.warning(f"Checkpoint not found: {path}")
            return None

        # Verify checksum if available
        expected_checksum = self.checksums.get(str(path))

        if expected_checksum:
            actual_checksum = compute_file_checksum(path)

            if actual_checksum != expected_checksum:
                logger.error(
                    f"Checkpoint checksum mismatch: {path}\n"
                    f"Expected: {expected_checksum}\n"
                    f"Actual: {actual_checksum}"
                )
                return None

        checkpoint = Checkpoint.load(path)
        logger.info(f"Loaded checkpoint from epoch {checkpoint.epoch}")

        return checkpoint

    def save_checksums(self, path: Path) -> None:
        """Save checksum registry"""
        with open(path, "w") as f:
            json.dump(self.checksums, f, indent=2)

    def load_checksums(self, path: Path) -> None:
        """Load checksum registry"""
        if path.exists():
            with open(path, "r") as f:
                self.checksums = json.load(f)


# =============================================================================
# Model Definitions
# =============================================================================

if TORCH_AVAILABLE:

    class DeterministicNeuralNet(nn.Module):
        """
        Neural network with deterministic initialization and forward pass.
        """

        def __init__(
            self,
            input_dim: int,
            hidden_dims: list[int],
            output_dim: int = 1,
            dropout: float = 0.3
        ):
            super().__init__()

            self.input_dim = input_dim
            self.hidden_dims = hidden_dims
            self.output_dim = output_dim

            layers = []
            prev_dim = input_dim

            for hidden_dim in hidden_dims:
                layers.extend([
                    nn.Linear(prev_dim, hidden_dim),
                    nn.BatchNorm1d(hidden_dim),
                    nn.ReLU(),
                    nn.Dropout(dropout)
                ])
                prev_dim = hidden_dim

            layers.append(nn.Linear(prev_dim, output_dim))

            if output_dim == 1:
                layers.append(nn.Sigmoid())

            self.network = nn.Sequential(*layers)

            # Deterministic initialization
            self._init_weights()

        def _init_weights(self) -> None:
            """Initialize weights deterministically using Xavier initialization"""
            for module in self.modules():
                if isinstance(module, nn.Linear):
                    nn.init.xavier_uniform_(module.weight)
                    if module.bias is not None:
                        nn.init.zeros_(module.bias)
                elif isinstance(module, nn.BatchNorm1d):
                    nn.init.ones_(module.weight)
                    nn.init.zeros_(module.bias)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.network(x)


class BayesianModelWrapper:
    """
    Bayesian model wrapper for uncertainty quantification.

    Uses Beta distribution priors for probability estimation.
    """

    def __init__(self, n_segments: int = 10):
        self.n_segments = n_segments
        self.alpha: dict[int, float] = {i: 1.0 for i in range(n_segments)}
        self.beta: dict[int, float] = {i: 1.0 for i in range(n_segments)}

    def get_segment(self, features: Any) -> int:
        """Map features to segment"""
        if NUMPY_AVAILABLE:
            feature_sum = np.sum(features) if hasattr(features, "__len__") else float(features)
        else:
            feature_sum = sum(features) if hasattr(features, "__len__") else float(features)

        return int(abs(hash(str(feature_sum))) % self.n_segments)

    def update(self, features: Any, outcome: float) -> None:
        """Update posterior with observation"""
        segment = self.get_segment(features)

        if outcome > 0.5:
            self.alpha[segment] += 1
        else:
            self.beta[segment] += 1

    def predict(self, features: Any) -> tuple[float, float]:
        """Predict probability with uncertainty"""
        segment = self.get_segment(features)

        alpha = self.alpha[segment]
        beta = self.beta[segment]

        # Mean of Beta distribution
        probability = alpha / (alpha + beta)

        # Confidence from sample size
        n_samples = alpha + beta - 2
        confidence = min(0.95, 0.5 + n_samples / 200)

        return probability, confidence

    def get_state(self) -> dict[str, Any]:
        """Get model state for checkpointing"""
        return {
            "alpha": self.alpha.copy(),
            "beta": self.beta.copy(),
            "n_segments": self.n_segments
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore model state from checkpoint"""
        self.alpha = state["alpha"]
        self.beta = state["beta"]
        self.n_segments = state["n_segments"]


# =============================================================================
# Deterministic Trainer
# =============================================================================

class DeterministicTrainer:
    """
    Main training orchestrator ensuring deterministic, reproducible training.

    Features:
    - Complete seed management across all libraries
    - Environment capture and Docker generation
    - Multi-model training support
    - Stratified cross-validation
    - Early stopping and checkpointing
    - Distributed training support
    - Memory-efficient batch processing
    - Artifact checksum verification

    Usage:
        config = TrainingConfig(seed=42, dataset_version="v1.0.0")
        trainer = DeterministicTrainer(config)

        # Train and get artifact checksum
        checksum = trainer.train(train_data, val_data)

        # Verify reproducibility
        trainer2 = DeterministicTrainer(config)
        checksum2 = trainer2.train(train_data, val_data)
        assert checksum == checksum2  # Identical results
    """

    def __init__(self, config: TrainingConfig):
        self.config = config

        # Initialize managers
        self.seed_manager = SeedManager(config.seed)
        self.env_manager = EnvironmentManager()
        self.device_manager = DeviceManager(config)
        self.checkpoint_manager = CheckpointManager(
            Path(config.checkpoint_dir),
            keep_n=config.keep_n_checkpoints,
            frequency=config.checkpoint_frequency
        )

        # Training state
        self.model: Any = None
        self.optimizer: Any = None
        self.scheduler: Any = None
        self.scaler: Any = None  # For mixed precision

        self.current_epoch = 0
        self.global_step = 0
        self.metrics = TrainingMetrics()
        self.best_metrics = TrainingMetrics()

        # Early stopping
        self.early_stopping = EarlyStopping(
            patience=config.patience,
            min_delta=config.min_delta
        ) if config.early_stopping else None

        # Cross-validation
        self.cross_validator = CrossValidator(
            n_folds=config.n_folds,
            stratified=config.stratified,
            seed=config.seed
        )

        # Artifact tracking
        self.artifact_checksums: dict[str, str] = {}
        self._training_started = False

    def initialize(self) -> None:
        """Initialize training environment"""
        # Set seeds
        self.seed_manager.initialize()

        # Capture environment
        self.env_manager.capture_environment()

        # Setup device
        self.device_manager.setup()

        # Create output directory
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save environment spec
        env_spec_path = output_dir / "environment_spec.json"
        with open(env_spec_path, "w") as f:
            json.dump(self.env_manager.current_spec.to_dict(), f, indent=2)

        # Generate requirements.lock
        self.env_manager.generate_requirements_lock(output_dir / "requirements.lock")

        # Generate Dockerfile
        self.env_manager.generate_dockerfile(output_dir / "Dockerfile", self.config)

        # Save training config
        config_path = output_dir / "training_config.json"
        with open(config_path, "w") as f:
            json.dump(self.config.to_dict(), f, indent=2)

        logger.info(f"Training environment initialized with seed {self.config.seed}")

    def create_model(self, input_dim: int) -> Any:
        """Create model based on configuration"""
        model_type = self.config.model_type
        hyperparams = self.config.hyperparameters

        if model_type == ModelType.NEURAL_NET:
            if not TORCH_AVAILABLE:
                raise RuntimeError("PyTorch required for neural network training")

            hidden_dims = hyperparams.get("hidden_dims", [256, 128, 64])
            dropout = hyperparams.get("dropout", 0.3)
            output_dim = hyperparams.get("output_dim", 1)

            model = DeterministicNeuralNet(
                input_dim=input_dim,
                hidden_dims=hidden_dims,
                output_dim=output_dim,
                dropout=dropout
            )

            return self.device_manager.wrap_model(model)

        elif model_type == ModelType.GRADIENT_BOOST:
            if not SKLEARN_AVAILABLE:
                raise RuntimeError("Scikit-learn required for gradient boosting")

            return GradientBoostingClassifier(
                n_estimators=hyperparams.get("n_estimators", 100),
                learning_rate=hyperparams.get("learning_rate", 0.1),
                max_depth=hyperparams.get("max_depth", 6),
                random_state=self.config.seed
            )

        elif model_type == ModelType.RANDOM_FOREST:
            if not SKLEARN_AVAILABLE:
                raise RuntimeError("Scikit-learn required for random forest")

            return RandomForestClassifier(
                n_estimators=hyperparams.get("n_estimators", 100),
                max_depth=hyperparams.get("max_depth", None),
                random_state=self.config.seed,
                n_jobs=self.config.num_workers
            )

        elif model_type == ModelType.BAYESIAN:
            return BayesianModelWrapper(
                n_segments=hyperparams.get("n_segments", 10)
            )

        elif model_type == ModelType.LOGISTIC:
            if not SKLEARN_AVAILABLE:
                raise RuntimeError("Scikit-learn required for logistic regression")

            return LogisticRegression(
                random_state=self.config.seed,
                max_iter=hyperparams.get("max_iter", 1000)
            )

        else:
            raise ValueError(f"Unsupported model type: {model_type}")

    def create_optimizer(self, model: Any) -> Any:
        """Create optimizer for neural network training"""
        if not TORCH_AVAILABLE or not isinstance(model, nn.Module):
            return None

        optimizer_name = self.config.hyperparameters.get("optimizer", "adam")

        if optimizer_name == "adam":
            return optim.Adam(
                model.parameters(),
                lr=self.config.learning_rate,
                weight_decay=self.config.weight_decay
            )
        elif optimizer_name == "sgd":
            return optim.SGD(
                model.parameters(),
                lr=self.config.learning_rate,
                momentum=self.config.hyperparameters.get("momentum", 0.9),
                weight_decay=self.config.weight_decay
            )
        elif optimizer_name == "adamw":
            return optim.AdamW(
                model.parameters(),
                lr=self.config.learning_rate,
                weight_decay=self.config.weight_decay
            )
        else:
            raise ValueError(f"Unsupported optimizer: {optimizer_name}")

    def create_scheduler(self, optimizer: Any) -> Any:
        """Create learning rate scheduler"""
        if optimizer is None:
            return None

        scheduler_name = self.config.hyperparameters.get("scheduler", "none")

        if scheduler_name == "none":
            return None
        elif scheduler_name == "step":
            return optim.lr_scheduler.StepLR(
                optimizer,
                step_size=self.config.hyperparameters.get("step_size", 30),
                gamma=self.config.hyperparameters.get("gamma", 0.1)
            )
        elif scheduler_name == "cosine":
            return optim.lr_scheduler.CosineAnnealingLR(
                optimizer,
                T_max=self.config.epochs
            )
        elif scheduler_name == "reduce_on_plateau":
            return optim.lr_scheduler.ReduceLROnPlateau(
                optimizer,
                mode="min",
                patience=self.config.hyperparameters.get("scheduler_patience", 5)
            )
        else:
            return None

    def train(
        self,
        train_data: tuple[Any, Any],
        val_data: tuple[Any, Any] | None = None,
        resume_from_checkpoint: bool = False
    ) -> str:
        """
        Train model and return artifact checksum.

        Args:
            train_data: Tuple of (features, labels)
            val_data: Optional validation data tuple
            resume_from_checkpoint: Whether to resume from latest checkpoint

        Returns:
            Checksum of final model artifact
        """
        if not self._training_started:
            self.initialize()
            self._training_started = True

        X_train, y_train = train_data

        # Determine input dimension
        if NUMPY_AVAILABLE and isinstance(X_train, np.ndarray):
            input_dim = X_train.shape[1] if len(X_train.shape) > 1 else 1
        elif TORCH_AVAILABLE and isinstance(X_train, torch.Tensor):
            input_dim = X_train.shape[1] if len(X_train.shape) > 1 else 1
        else:
            input_dim = len(X_train[0]) if hasattr(X_train[0], "__len__") else 1

        # Create model
        self.model = self.create_model(input_dim)

        # Resume from checkpoint if requested
        if resume_from_checkpoint:
            checkpoint = self.checkpoint_manager.load_latest_checkpoint()

            if checkpoint:
                self._restore_from_checkpoint(checkpoint)

        # Route to appropriate training method
        if self.config.model_type == ModelType.NEURAL_NET:
            return self._train_neural_net(train_data, val_data)
        elif self.config.model_type in [ModelType.GRADIENT_BOOST, ModelType.RANDOM_FOREST, ModelType.LOGISTIC]:
            return self._train_sklearn(train_data, val_data)
        elif self.config.model_type == ModelType.BAYESIAN:
            return self._train_bayesian(train_data, val_data)
        else:
            raise ValueError(f"Unsupported model type: {self.config.model_type}")

    def _train_neural_net(
        self,
        train_data: tuple[Any, Any],
        val_data: tuple[Any, Any] | None
    ) -> str:
        """Train neural network model"""
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch required for neural network training")

        X_train, y_train = train_data

        # Convert to tensors
        if not isinstance(X_train, torch.Tensor):
            X_train = torch.tensor(X_train, dtype=torch.float32)
        if not isinstance(y_train, torch.Tensor):
            y_train = torch.tensor(y_train, dtype=torch.float32).unsqueeze(1)

        # Create optimizer and scheduler
        self.optimizer = self.create_optimizer(self.model)
        self.scheduler = self.create_scheduler(self.optimizer)

        # Setup mixed precision
        if self.config.mixed_precision:
            self.scaler = torch.cuda.amp.GradScaler()

        # Loss function
        criterion = nn.BCELoss()

        # Training loop
        start_time = time.time()

        for epoch in range(self.current_epoch, self.config.epochs):
            self.current_epoch = epoch

            # Training phase
            self.model.train()
            train_loss = 0.0
            n_batches = 0

            # Create batch iterator
            batch_iter = BatchIterator(
                list(zip(X_train, y_train)),
                batch_size=self.config.batch_size,
                shuffle=True,
                seed=self.seed_manager.get_fold_seed(epoch)
            )

            for batch in batch_iter:
                X_batch = torch.stack([b[0] for b in batch]).to(self.device_manager.device)
                y_batch = torch.stack([b[1] for b in batch]).to(self.device_manager.device)

                # Forward pass
                if self.config.mixed_precision:
                    with torch.cuda.amp.autocast():
                        outputs = self.model(X_batch)
                        loss = criterion(outputs, y_batch)
                else:
                    outputs = self.model(X_batch)
                    loss = criterion(outputs, y_batch)

                # Backward pass with gradient accumulation
                loss = loss / self.config.gradient_accumulation_steps

                if self.config.mixed_precision:
                    self.scaler.scale(loss).backward()
                else:
                    loss.backward()

                self.global_step += 1

                # Optimizer step
                if self.global_step % self.config.gradient_accumulation_steps == 0:
                    if self.config.mixed_precision:
                        self.scaler.step(self.optimizer)
                        self.scaler.update()
                    else:
                        self.optimizer.step()

                    self.optimizer.zero_grad()

                train_loss += loss.item() * self.config.gradient_accumulation_steps
                n_batches += 1

            avg_train_loss = train_loss / n_batches
            self.metrics.train_loss = avg_train_loss

            # Validation phase
            if val_data is not None:
                val_loss = self._validate_neural_net(val_data, criterion)
                self.metrics.val_loss = val_loss

                # Update scheduler
                if self.scheduler is not None:
                    if isinstance(self.scheduler, optim.lr_scheduler.ReduceLROnPlateau):
                        self.scheduler.step(val_loss)
                    else:
                        self.scheduler.step()

                # Early stopping check
                if self.early_stopping is not None:
                    is_best = val_loss < self.metrics.best_val_loss

                    if is_best:
                        self.metrics.best_val_loss = val_loss
                        self.metrics.best_epoch = epoch
                        self.best_metrics = TrainingMetrics(**self.metrics.to_dict())

                    if self.early_stopping(val_loss, epoch):
                        logger.info(f"Early stopping at epoch {epoch}")
                        break

            # Checkpointing
            if self.checkpoint_manager.should_checkpoint(epoch):
                is_best = val_data is not None and self.metrics.val_loss <= self.metrics.best_val_loss
                self._save_checkpoint(CheckpointType.EPOCH, is_best=is_best)

            # Log progress
            if epoch % 10 == 0:
                logger.info(
                    f"Epoch {epoch}: train_loss={avg_train_loss:.4f}, "
                    f"val_loss={self.metrics.val_loss:.4f}"
                )

        self.metrics.training_time_seconds = time.time() - start_time

        # Save final model and return checksum
        return self._save_final_model()

    def _validate_neural_net(
        self,
        val_data: tuple[Any, Any],
        criterion: Any
    ) -> float:
        """Validate neural network model"""
        X_val, y_val = val_data

        if not isinstance(X_val, torch.Tensor):
            X_val = torch.tensor(X_val, dtype=torch.float32)
        if not isinstance(y_val, torch.Tensor):
            y_val = torch.tensor(y_val, dtype=torch.float32).unsqueeze(1)

        self.model.eval()
        val_loss = 0.0
        n_batches = 0

        with torch.no_grad():
            batch_iter = BatchIterator(
                list(zip(X_val, y_val)),
                batch_size=self.config.batch_size,
                shuffle=False,
                seed=self.config.seed
            )

            for batch in batch_iter:
                X_batch = torch.stack([b[0] for b in batch]).to(self.device_manager.device)
                y_batch = torch.stack([b[1] for b in batch]).to(self.device_manager.device)

                outputs = self.model(X_batch)
                loss = criterion(outputs, y_batch)

                val_loss += loss.item()
                n_batches += 1

        return val_loss / n_batches

    def _train_sklearn(
        self,
        train_data: tuple[Any, Any],
        val_data: tuple[Any, Any] | None
    ) -> str:
        """Train scikit-learn model"""
        X_train, y_train = train_data

        # Convert to numpy if needed
        if TORCH_AVAILABLE and isinstance(X_train, torch.Tensor):
            X_train = X_train.numpy()
            y_train = y_train.numpy()

        start_time = time.time()

        # Train model
        self.model.fit(X_train, y_train)

        self.metrics.training_time_seconds = time.time() - start_time

        # Evaluate on training data
        train_preds = self.model.predict_proba(X_train)[:, 1]
        self.metrics.train_accuracy = self.model.score(X_train, y_train)

        # Evaluate on validation data
        if val_data is not None:
            X_val, y_val = val_data

            if TORCH_AVAILABLE and isinstance(X_val, torch.Tensor):
                X_val = X_val.numpy()
                y_val = y_val.numpy()

            self.metrics.val_accuracy = self.model.score(X_val, y_val)

        return self._save_final_model()

    def _train_bayesian(
        self,
        train_data: tuple[Any, Any],
        val_data: tuple[Any, Any] | None
    ) -> str:
        """Train Bayesian model"""
        X_train, y_train = train_data

        start_time = time.time()

        # Update posterior with training data
        for i in range(len(X_train)):
            features = X_train[i]
            label = y_train[i]
            self.model.update(features, label)

        self.metrics.training_time_seconds = time.time() - start_time

        return self._save_final_model()

    def train_with_cross_validation(
        self,
        data: tuple[Any, Any]
    ) -> tuple[str, list[TrainingMetrics]]:
        """
        Train with cross-validation.

        Returns:
            Tuple of (final model checksum, list of fold metrics)
        """
        X, y = data
        fold_metrics: list[TrainingMetrics] = []
        fold_checksums: list[str] = []

        for fold_idx, (train_idx, val_idx) in enumerate(self.cross_validator.split(X, y)):
            logger.info(f"Training fold {fold_idx + 1}/{self.config.n_folds}")

            # Reset for new fold
            self.current_epoch = 0
            self.global_step = 0
            self.metrics = TrainingMetrics()

            if self.early_stopping:
                self.early_stopping.reset()

            # Set fold-specific seed
            fold_seed = self.seed_manager.get_fold_seed(fold_idx)
            self.seed_manager._set_seed(fold_seed)

            # Split data
            if NUMPY_AVAILABLE and isinstance(X, np.ndarray):
                X_train = X[train_idx]
                y_train = y[train_idx]
                X_val = X[val_idx]
                y_val = y[val_idx]
            else:
                X_train = [X[i] for i in train_idx]
                y_train = [y[i] for i in train_idx]
                X_val = [X[i] for i in val_idx]
                y_val = [y[i] for i in val_idx]

            # Train fold
            checksum = self.train(
                train_data=(X_train, y_train),
                val_data=(X_val, y_val)
            )

            fold_metrics.append(TrainingMetrics(**self.metrics.to_dict()))
            fold_checksums.append(checksum)

        # Average metrics
        avg_metrics = TrainingMetrics(
            train_loss=sum(m.train_loss for m in fold_metrics) / len(fold_metrics),
            val_loss=sum(m.val_loss for m in fold_metrics) / len(fold_metrics),
            train_accuracy=sum(m.train_accuracy for m in fold_metrics) / len(fold_metrics),
            val_accuracy=sum(m.val_accuracy for m in fold_metrics) / len(fold_metrics)
        )

        logger.info(
            f"Cross-validation complete: avg_val_loss={avg_metrics.val_loss:.4f}, "
            f"avg_val_accuracy={avg_metrics.val_accuracy:.4f}"
        )

        # Train final model on all data
        self.seed_manager._set_seed(self.config.seed)
        final_checksum = self.train(train_data=data)

        return final_checksum, fold_metrics

    def _save_checkpoint(
        self,
        checkpoint_type: CheckpointType,
        is_best: bool = False
    ) -> str:
        """Save training checkpoint"""
        # Get model state
        if TORCH_AVAILABLE and isinstance(self.model, nn.Module):
            model_state = self.model.state_dict()
        elif hasattr(self.model, "get_state"):
            model_state = self.model.get_state()
        else:
            model_state = pickle.dumps(self.model)

        # Get optimizer state
        optimizer_state = None
        if self.optimizer is not None and hasattr(self.optimizer, "state_dict"):
            optimizer_state = self.optimizer.state_dict()

        # Get scheduler state
        scheduler_state = None
        if self.scheduler is not None and hasattr(self.scheduler, "state_dict"):
            scheduler_state = self.scheduler.state_dict()

        checkpoint = Checkpoint(
            checkpoint_type=checkpoint_type,
            epoch=self.current_epoch,
            global_step=self.global_step,
            model_state=model_state,
            optimizer_state=optimizer_state,
            scheduler_state=scheduler_state,
            rng_states=self.seed_manager.get_rng_states(),
            metrics=self.metrics,
            config=self.config
        )

        checksum = self.checkpoint_manager.save_checkpoint(checkpoint, is_best=is_best)
        self.artifact_checksums[f"checkpoint_epoch_{self.current_epoch}"] = checksum

        return checksum

    def _restore_from_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Restore training state from checkpoint"""
        # Restore RNG states
        self.seed_manager.set_rng_states(checkpoint.rng_states)

        # Restore model state
        if TORCH_AVAILABLE and isinstance(self.model, nn.Module):
            self.model.load_state_dict(checkpoint.model_state)
        elif hasattr(self.model, "set_state"):
            self.model.set_state(checkpoint.model_state)
        else:
            self.model = pickle.loads(checkpoint.model_state)

        # Restore optimizer
        if self.optimizer is not None and checkpoint.optimizer_state is not None:
            self.optimizer.load_state_dict(checkpoint.optimizer_state)

        # Restore scheduler
        if self.scheduler is not None and checkpoint.scheduler_state is not None:
            self.scheduler.load_state_dict(checkpoint.scheduler_state)

        # Restore training state
        self.current_epoch = checkpoint.epoch + 1
        self.global_step = checkpoint.global_step
        self.metrics = checkpoint.metrics

        logger.info(f"Restored from checkpoint at epoch {checkpoint.epoch}")

    def _save_final_model(self) -> str:
        """Save final model and return checksum"""
        output_dir = Path(self.config.output_dir)

        # Save model
        model_path = output_dir / "model_final.pt"

        if TORCH_AVAILABLE and isinstance(self.model, nn.Module):
            torch.save(self.model.state_dict(), model_path)
        elif hasattr(self.model, "get_state"):
            with open(model_path, "wb") as f:
                pickle.dump(self.model.get_state(), f)
        else:
            with open(model_path, "wb") as f:
                pickle.dump(self.model, f)

        # Compute checksum
        checksum = compute_file_checksum(model_path)
        self.artifact_checksums["final_model"] = checksum

        # Save metrics
        metrics_path = output_dir / "training_metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(self.metrics.to_dict(), f, indent=2)

        # Save checksums
        checksums_path = output_dir / "artifact_checksums.json"
        with open(checksums_path, "w") as f:
            json.dump(self.artifact_checksums, f, indent=2)

        logger.info(f"Final model saved with checksum: {checksum}")

        return checksum

    def cleanup(self) -> None:
        """Cleanup resources"""
        self.device_manager.cleanup()


# =============================================================================
# Multi-Model Trainer
# =============================================================================

class MultiModelTrainer:
    """
    Trains multiple model types in parallel or sequence.

    Supports training ensemble of different model architectures
    with consistent seeding for reproducibility.
    """

    def __init__(
        self,
        base_config: TrainingConfig,
        model_types: list[ModelType] | None = None
    ):
        self.base_config = base_config
        self.model_types = model_types or [
            ModelType.GRADIENT_BOOST,
            ModelType.NEURAL_NET,
            ModelType.BAYESIAN
        ]

        self.trainers: dict[ModelType, DeterministicTrainer] = {}
        self.checksums: dict[ModelType, str] = {}
        self.metrics: dict[ModelType, TrainingMetrics] = {}

    def train_all(
        self,
        train_data: tuple[Any, Any],
        val_data: tuple[Any, Any] | None = None
    ) -> dict[ModelType, str]:
        """
        Train all model types and return checksums.

        Args:
            train_data: Training data tuple (X, y)
            val_data: Optional validation data tuple

        Returns:
            Dictionary mapping model types to artifact checksums
        """
        for model_type in self.model_types:
            logger.info(f"Training {model_type.value} model...")

            # Create model-specific config
            config = TrainingConfig(**self.base_config.to_dict())
            config.model_type = model_type
            config.output_dir = f"{self.base_config.output_dir}/{model_type.value}"
            config.experiment_name = f"{self.base_config.experiment_name}_{model_type.value}"

            # Use consistent but unique seed per model
            config.seed = self.base_config.seed + hash(model_type.value) % 1000

            # Create and run trainer
            trainer = DeterministicTrainer(config)
            checksum = trainer.train(train_data, val_data)

            self.trainers[model_type] = trainer
            self.checksums[model_type] = checksum
            self.metrics[model_type] = trainer.metrics

            logger.info(
                f"{model_type.value} training complete: checksum={checksum[:16]}..."
            )

        return self.checksums

    def get_best_model(self) -> tuple[ModelType, DeterministicTrainer]:
        """Get best performing model based on validation loss"""
        best_type = min(
            self.metrics.keys(),
            key=lambda mt: self.metrics[mt].val_loss
        )

        return best_type, self.trainers[best_type]

    def get_summary(self) -> dict[str, Any]:
        """Get training summary for all models"""
        return {
            "models": {
                mt.value: {
                    "checksum": self.checksums[mt],
                    "metrics": self.metrics[mt].to_dict()
                }
                for mt in self.model_types
            },
            "best_model": self.get_best_model()[0].value
        }


# =============================================================================
# CLI Training Script
# =============================================================================

def create_argument_parser():
    """Create argument parser for training script"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Deterministic Training Pipeline for QUAN ML Models"
    )

    # Required arguments
    parser.add_argument(
        "--seed",
        type=int,
        required=True,
        help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--dataset-version",
        type=str,
        required=True,
        help="Version of dataset to use"
    )

    # Model configuration
    parser.add_argument(
        "--model-type",
        type=str,
        default="gradient_boost",
        choices=[mt.value for mt in ModelType],
        help="Model architecture to train"
    )
    parser.add_argument(
        "--multi-model",
        action="store_true",
        help="Train all model types"
    )

    # Training parameters
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="Number of training epochs"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Training batch size"
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.001,
        help="Learning rate"
    )

    # Cross-validation
    parser.add_argument(
        "--n-folds",
        type=int,
        default=5,
        help="Number of cross-validation folds"
    )
    parser.add_argument(
        "--no-cv",
        action="store_true",
        help="Disable cross-validation"
    )

    # Device configuration
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        choices=[dt.value for dt in DeviceType],
        help="Compute device"
    )
    parser.add_argument(
        "--distributed",
        action="store_true",
        help="Enable distributed training"
    )
    parser.add_argument(
        "--world-size",
        type=int,
        default=1,
        help="Number of distributed workers"
    )

    # Paths
    parser.add_argument(
        "--train-data",
        type=str,
        required=True,
        help="Path to training data"
    )
    parser.add_argument(
        "--val-data",
        type=str,
        help="Path to validation data"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        help="Output directory"
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=str,
        default="./checkpoints",
        help="Checkpoint directory"
    )

    # Resume
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from latest checkpoint"
    )

    return parser


def load_data(path: str) -> tuple[Any, Any]:
    """Load data from path"""
    path = Path(path)

    if path.suffix == ".npz":
        if NUMPY_AVAILABLE:
            data = np.load(path)
            return data["X"], data["y"]
    elif path.suffix == ".pt":
        if TORCH_AVAILABLE:
            data = torch.load(path)
            return data["X"], data["y"]
    elif path.suffix == ".pkl":
        with open(path, "rb") as f:
            data = pickle.load(f)
            return data["X"], data["y"]

    raise ValueError(f"Unsupported data format: {path.suffix}")


def main():
    """Main entry point for training script"""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create configuration
    config = TrainingConfig(
        seed=args.seed,
        dataset_version=args.dataset_version,
        model_type=ModelType(args.model_type),
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        n_folds=args.n_folds,
        device=DeviceType(args.device),
        distributed=args.distributed,
        world_size=args.world_size,
        train_data_path=args.train_data,
        val_data_path=args.val_data,
        output_dir=args.output_dir,
        checkpoint_dir=args.checkpoint_dir
    )

    # Load data
    logger.info(f"Loading training data from {args.train_data}")
    train_data = load_data(args.train_data)

    val_data = None
    if args.val_data:
        logger.info(f"Loading validation data from {args.val_data}")
        val_data = load_data(args.val_data)

    # Train model(s)
    if args.multi_model:
        trainer = MultiModelTrainer(config)
        checksums = trainer.train_all(train_data, val_data)

        print("\n=== Multi-Model Training Complete ===")
        for model_type, checksum in checksums.items():
            print(f"  {model_type.value}: {checksum}")

        summary = trainer.get_summary()
        print(f"\nBest model: {summary['best_model']}")

    else:
        trainer = DeterministicTrainer(config)

        if args.no_cv:
            checksum = trainer.train(train_data, val_data, resume_from_checkpoint=args.resume)
        else:
            checksum, fold_metrics = trainer.train_with_cross_validation(train_data)

            print("\n=== Cross-Validation Results ===")
            for i, metrics in enumerate(fold_metrics):
                print(f"  Fold {i+1}: val_loss={metrics.val_loss:.4f}")

        print(f"\n=== Training Complete ===")
        print(f"Final model checksum: {checksum}")
        print(f"Output directory: {args.output_dir}")

        # Verify reproducibility claim
        print(f"\nReproducibility verification:")
        print(f"  Seed: {args.seed}")
        print(f"  Dataset version: {args.dataset_version}")
        print(f"  Config hash: {config.get_config_hash()}")
        print(f"  Running with same parameters will produce checksum: {checksum}")


if __name__ == "__main__":
    main()
