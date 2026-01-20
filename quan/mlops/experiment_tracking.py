"""
MLflow Experiment Tracking and Model Registry Integration

Comprehensive MLOps infrastructure for:
1. Experiment tracking with automatic parameter/metric logging
2. Artifact management (models, plots, feature importance)
3. Model registry with staging/production transitions
4. Run comparison and experiment search
5. Hyperparameter tuning integration (Optuna compatible)
6. Full reproducibility with environment and git tracking
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from pathlib import Path
from abc import ABC, abstractmethod
import hashlib
import json
import logging
import math
import os
import platform
import subprocess
import sys
import tempfile
import time
import uuid
from collections import defaultdict
from functools import wraps

logger = logging.getLogger(__name__)


# =============================================================================
# MLflow Configuration
# =============================================================================

@dataclass
class MLflowConfig:
    """MLflow server and client configuration"""

    # Server settings
    tracking_uri: str = "http://localhost:5000"
    artifact_location: str = "mlflow-artifacts"
    backend_store_uri: str = "sqlite:///mlflow.db"

    # Authentication
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None

    # Defaults
    default_experiment_name: str = "quan-default"
    auto_log_models: bool = True
    log_model_signatures: bool = True

    # Retention
    artifact_retention_days: int = 90
    run_retention_days: int = 365

    # Performance
    async_logging: bool = True
    batch_metrics_size: int = 100

    @classmethod
    def from_env(cls) -> "MLflowConfig":
        """Load configuration from environment variables"""
        return cls(
            tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"),
            artifact_location=os.getenv("MLFLOW_ARTIFACT_LOCATION", "mlflow-artifacts"),
            backend_store_uri=os.getenv("MLFLOW_BACKEND_STORE_URI", "sqlite:///mlflow.db"),
            username=os.getenv("MLFLOW_USERNAME"),
            password=os.getenv("MLFLOW_PASSWORD"),
            token=os.getenv("MLFLOW_TOKEN"),
            default_experiment_name=os.getenv("MLFLOW_DEFAULT_EXPERIMENT", "quan-default"),
        )


# =============================================================================
# Enums and Constants
# =============================================================================

class ModelStage(Enum):
    """Model registry stages"""
    NONE = "None"
    STAGING = "Staging"
    PRODUCTION = "Production"
    ARCHIVED = "Archived"


class RunStatus(Enum):
    """Run status values"""
    RUNNING = "RUNNING"
    SCHEDULED = "SCHEDULED"
    FINISHED = "FINISHED"
    FAILED = "FAILED"
    KILLED = "KILLED"


class MetricType(Enum):
    """Types of metrics tracked"""
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CALIBRATION = "calibration"
    RANKING = "ranking"
    CUSTOM = "custom"


class ArtifactType(Enum):
    """Types of artifacts stored"""
    MODEL = "model"
    PLOT = "plot"
    DATA = "data"
    CONFIG = "config"
    FEATURE_IMPORTANCE = "feature_importance"
    CALIBRATION_CURVE = "calibration_curve"
    SHAP_VALUES = "shap_values"
    CONFUSION_MATRIX = "confusion_matrix"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SemanticVersion:
    """Semantic versioning for models"""
    major: int = 1
    minor: int = 0
    patch: int = 0
    prerelease: Optional[str] = None
    build: Optional[str] = None

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version

    @classmethod
    def parse(cls, version_str: str) -> "SemanticVersion":
        """Parse version string"""
        build = None
        prerelease = None

        if "+" in version_str:
            version_str, build = version_str.split("+", 1)
        if "-" in version_str:
            version_str, prerelease = version_str.split("-", 1)

        parts = version_str.split(".")
        return cls(
            major=int(parts[0]) if len(parts) > 0 else 1,
            minor=int(parts[1]) if len(parts) > 1 else 0,
            patch=int(parts[2]) if len(parts) > 2 else 0,
            prerelease=prerelease,
            build=build,
        )

    def bump_major(self) -> "SemanticVersion":
        return SemanticVersion(self.major + 1, 0, 0)

    def bump_minor(self) -> "SemanticVersion":
        return SemanticVersion(self.major, self.minor + 1, 0)

    def bump_patch(self) -> "SemanticVersion":
        return SemanticVersion(self.major, self.minor, self.patch + 1)


@dataclass
class EnvironmentInfo:
    """Captured environment information for reproducibility"""
    python_version: str = ""
    platform_info: str = ""
    hostname: str = ""
    username: str = ""
    working_directory: str = ""
    dependencies: Dict[str, str] = field(default_factory=dict)
    env_variables: Dict[str, str] = field(default_factory=dict)
    gpu_info: Optional[Dict[str, Any]] = None
    timestamp: str = ""

    @classmethod
    def capture(cls, include_env_vars: bool = False) -> "EnvironmentInfo":
        """Capture current environment"""
        info = cls(
            python_version=sys.version,
            platform_info=platform.platform(),
            hostname=platform.node(),
            username=os.getenv("USER", os.getenv("USERNAME", "unknown")),
            working_directory=os.getcwd(),
            timestamp=datetime.now().isoformat(),
        )

        # Capture dependencies
        info.dependencies = cls._get_dependencies()

        # Capture selected env vars
        if include_env_vars:
            safe_vars = ["CUDA_VISIBLE_DEVICES", "OMP_NUM_THREADS", "PYTHONPATH"]
            info.env_variables = {
                k: v for k, v in os.environ.items()
                if k in safe_vars or k.startswith("MLFLOW_")
            }

        # Capture GPU info
        info.gpu_info = cls._get_gpu_info()

        return info

    @staticmethod
    def _get_dependencies() -> Dict[str, str]:
        """Get installed package versions"""
        try:
            import pkg_resources
            return {
                pkg.key: pkg.version
                for pkg in pkg_resources.working_set
            }
        except Exception:
            return {}

    @staticmethod
    def _get_gpu_info() -> Optional[Dict[str, Any]]:
        """Get GPU information if available"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                gpus = []
                for line in lines:
                    parts = line.split(", ")
                    if len(parts) >= 3:
                        gpus.append({
                            "name": parts[0],
                            "memory": parts[1],
                            "driver": parts[2],
                        })
                return {"gpus": gpus, "count": len(gpus)}
        except Exception:
            pass
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "python_version": self.python_version,
            "platform_info": self.platform_info,
            "hostname": self.hostname,
            "username": self.username,
            "working_directory": self.working_directory,
            "dependencies": self.dependencies,
            "env_variables": self.env_variables,
            "gpu_info": self.gpu_info,
            "timestamp": self.timestamp,
        }


@dataclass
class GitInfo:
    """Git repository information for reproducibility"""
    commit_hash: str = ""
    branch: str = ""
    remote_url: str = ""
    is_dirty: bool = False
    uncommitted_files: List[str] = field(default_factory=list)
    commit_message: str = ""
    commit_author: str = ""
    commit_date: str = ""
    tags: List[str] = field(default_factory=list)

    @classmethod
    def capture(cls, repo_path: Optional[str] = None) -> "GitInfo":
        """Capture git information from repository"""
        info = cls()

        try:
            cwd = repo_path or os.getcwd()

            # Get commit hash
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, cwd=cwd, timeout=5
            )
            if result.returncode == 0:
                info.commit_hash = result.stdout.strip()

            # Get branch name
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, cwd=cwd, timeout=5
            )
            if result.returncode == 0:
                info.branch = result.stdout.strip()

            # Get remote URL
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                capture_output=True, text=True, cwd=cwd, timeout=5
            )
            if result.returncode == 0:
                info.remote_url = result.stdout.strip()

            # Check if dirty
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, cwd=cwd, timeout=5
            )
            if result.returncode == 0:
                files = result.stdout.strip().split("\n")
                info.uncommitted_files = [f for f in files if f]
                info.is_dirty = len(info.uncommitted_files) > 0

            # Get commit message
            result = subprocess.run(
                ["git", "log", "-1", "--format=%s"],
                capture_output=True, text=True, cwd=cwd, timeout=5
            )
            if result.returncode == 0:
                info.commit_message = result.stdout.strip()

            # Get commit author
            result = subprocess.run(
                ["git", "log", "-1", "--format=%an <%ae>"],
                capture_output=True, text=True, cwd=cwd, timeout=5
            )
            if result.returncode == 0:
                info.commit_author = result.stdout.strip()

            # Get commit date
            result = subprocess.run(
                ["git", "log", "-1", "--format=%ci"],
                capture_output=True, text=True, cwd=cwd, timeout=5
            )
            if result.returncode == 0:
                info.commit_date = result.stdout.strip()

            # Get tags pointing to HEAD
            result = subprocess.run(
                ["git", "tag", "--points-at", "HEAD"],
                capture_output=True, text=True, cwd=cwd, timeout=5
            )
            if result.returncode == 0:
                tags = result.stdout.strip().split("\n")
                info.tags = [t for t in tags if t]

        except Exception as e:
            logger.warning(f"Failed to capture git info: {e}")

        return info

    def to_dict(self) -> Dict[str, Any]:
        return {
            "commit_hash": self.commit_hash,
            "branch": self.branch,
            "remote_url": self.remote_url,
            "is_dirty": self.is_dirty,
            "uncommitted_files": self.uncommitted_files,
            "commit_message": self.commit_message,
            "commit_author": self.commit_author,
            "commit_date": self.commit_date,
            "tags": self.tags,
        }


@dataclass
class DatasetVersion:
    """Dataset version tracking"""
    name: str
    version: str
    hash: str = ""
    size_bytes: int = 0
    num_records: int = 0
    features: List[str] = field(default_factory=list)
    split: str = "train"  # train/val/test
    source_uri: str = ""
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dataframe(
        cls,
        df: Any,
        name: str,
        version: str,
        split: str = "train",
    ) -> "DatasetVersion":
        """Create dataset version from dataframe"""
        # Compute hash from data
        try:
            import pandas as pd
            if isinstance(df, pd.DataFrame):
                data_str = df.to_json()
                data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:12]
                return cls(
                    name=name,
                    version=version,
                    hash=data_hash,
                    size_bytes=df.memory_usage(deep=True).sum(),
                    num_records=len(df),
                    features=list(df.columns),
                    split=split,
                    created_at=datetime.now().isoformat(),
                )
        except Exception:
            pass

        return cls(
            name=name,
            version=version,
            split=split,
            created_at=datetime.now().isoformat(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "hash": self.hash,
            "size_bytes": self.size_bytes,
            "num_records": self.num_records,
            "features": self.features,
            "split": self.split,
            "source_uri": self.source_uri,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class Hyperparameters:
    """Hyperparameters container with validation"""
    params: Dict[str, Any] = field(default_factory=dict)
    search_space: Dict[str, Any] = field(default_factory=dict)
    fixed_params: Dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        return self.params.get(key) or self.fixed_params.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.params[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.params.get(key) or self.fixed_params.get(key, default)

    def update(self, params: Dict[str, Any]) -> None:
        self.params.update(params)

    def all_params(self) -> Dict[str, Any]:
        return {**self.fixed_params, **self.params}

    def validate(self) -> List[str]:
        """Validate parameters against search space"""
        errors = []
        for key, value in self.params.items():
            if key in self.search_space:
                space = self.search_space[key]
                if "min" in space and value < space["min"]:
                    errors.append(f"{key}={value} below min {space['min']}")
                if "max" in space and value > space["max"]:
                    errors.append(f"{key}={value} above max {space['max']}")
                if "choices" in space and value not in space["choices"]:
                    errors.append(f"{key}={value} not in choices {space['choices']}")
        return errors


@dataclass
class RunMetrics:
    """Collection of metrics from a run"""
    classification: Dict[str, float] = field(default_factory=dict)
    calibration: Dict[str, float] = field(default_factory=dict)
    ranking: Dict[str, float] = field(default_factory=dict)
    custom: Dict[str, float] = field(default_factory=dict)
    step_metrics: Dict[str, List[Tuple[int, float]]] = field(default_factory=dict)

    def add(self, name: str, value: float, metric_type: MetricType = MetricType.CUSTOM, step: Optional[int] = None) -> None:
        """Add a metric"""
        target = getattr(self, metric_type.value, self.custom)
        target[name] = value

        if step is not None:
            if name not in self.step_metrics:
                self.step_metrics[name] = []
            self.step_metrics[name].append((step, value))

    def all_metrics(self) -> Dict[str, float]:
        """Get all metrics as flat dict"""
        metrics = {}
        metrics.update(self.classification)
        metrics.update(self.calibration)
        metrics.update(self.ranking)
        metrics.update(self.custom)
        return metrics


@dataclass
class ExperimentRun:
    """Represents a single experiment run"""
    run_id: str
    experiment_id: str
    experiment_name: str
    run_name: str
    status: RunStatus = RunStatus.RUNNING
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    # Tracked data
    params: Hyperparameters = field(default_factory=Hyperparameters)
    metrics: RunMetrics = field(default_factory=RunMetrics)
    artifacts: Dict[str, str] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)

    # Reproducibility
    environment: Optional[EnvironmentInfo] = None
    git_info: Optional[GitInfo] = None
    datasets: List[DatasetVersion] = field(default_factory=list)

    # Model info
    model_name: Optional[str] = None
    model_version: Optional[SemanticVersion] = None

    # Parent/child relationships
    parent_run_id: Optional[str] = None
    child_run_ids: List[str] = field(default_factory=list)

    @property
    def duration(self) -> Optional[timedelta]:
        if self.end_time:
            return self.end_time - self.start_time
        return datetime.now() - self.start_time


@dataclass
class RegisteredModel:
    """Registered model in model registry"""
    name: str
    description: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    versions: List["ModelVersion"] = field(default_factory=list)
    latest_version: Optional[int] = None
    creation_timestamp: str = ""
    last_updated_timestamp: str = ""


@dataclass
class ModelVersion:
    """Version of a registered model"""
    model_name: str
    version: int
    semantic_version: SemanticVersion = field(default_factory=SemanticVersion)
    stage: ModelStage = ModelStage.NONE
    run_id: str = ""
    source_uri: str = ""
    description: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    creation_timestamp: str = ""
    last_updated_timestamp: str = ""

    # Performance metrics at registration
    metrics: Dict[str, float] = field(default_factory=dict)

    # Transition history
    stage_transitions: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# Metrics Calculator
# =============================================================================

class MetricsCalculator:
    """Calculate ML metrics for experiment tracking"""

    @staticmethod
    def calculate_auc_roc(y_true: List[float], y_pred: List[float]) -> float:
        """Calculate Area Under ROC Curve"""
        if len(y_true) != len(y_pred) or len(y_true) == 0:
            return 0.0

        pairs = sorted(zip(y_pred, y_true), reverse=True)
        n_pos = sum(y_true)
        n_neg = len(y_true) - n_pos

        if n_pos == 0 or n_neg == 0:
            return 0.5

        tp = 0
        auc = 0.0

        for pred, actual in pairs:
            if actual == 1:
                tp += 1
            else:
                auc += tp

        return auc / (n_pos * n_neg)

    @staticmethod
    def calculate_brier_score(y_true: List[float], y_pred: List[float]) -> float:
        """Calculate Brier score (lower is better)"""
        if len(y_true) != len(y_pred) or len(y_true) == 0:
            return 1.0

        return sum((p - a) ** 2 for p, a in zip(y_pred, y_true)) / len(y_true)

    @staticmethod
    def calculate_ece(
        y_true: List[float],
        y_pred: List[float],
        n_bins: int = 10,
    ) -> float:
        """Calculate Expected Calibration Error"""
        if len(y_true) != len(y_pred) or len(y_true) == 0:
            return 1.0

        bins = [[] for _ in range(n_bins)]

        for pred, actual in zip(y_pred, y_true):
            bin_idx = min(int(pred * n_bins), n_bins - 1)
            bins[bin_idx].append((pred, actual))

        ece = 0.0
        total = len(y_true)

        for bin_data in bins:
            if bin_data:
                avg_pred = sum(p for p, _ in bin_data) / len(bin_data)
                avg_actual = sum(a for _, a in bin_data) / len(bin_data)
                ece += abs(avg_pred - avg_actual) * len(bin_data) / total

        return ece

    @staticmethod
    def calculate_precision_recall_curve(
        y_true: List[float],
        y_pred: List[float],
        n_thresholds: int = 100,
    ) -> Dict[str, List[float]]:
        """Calculate precision-recall curve"""
        thresholds = [i / n_thresholds for i in range(n_thresholds + 1)]
        precisions = []
        recalls = []

        for threshold in thresholds:
            tp = sum(1 for p, a in zip(y_pred, y_true) if p >= threshold and a == 1)
            fp = sum(1 for p, a in zip(y_pred, y_true) if p >= threshold and a == 0)
            fn = sum(1 for p, a in zip(y_pred, y_true) if p < threshold and a == 1)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

            precisions.append(precision)
            recalls.append(recall)

        return {
            "thresholds": thresholds,
            "precision": precisions,
            "recall": recalls,
        }

    @staticmethod
    def calculate_calibration_curve(
        y_true: List[float],
        y_pred: List[float],
        n_bins: int = 10,
    ) -> Dict[str, List[float]]:
        """Calculate calibration curve data"""
        bins = [[] for _ in range(n_bins)]

        for pred, actual in zip(y_pred, y_true):
            bin_idx = min(int(pred * n_bins), n_bins - 1)
            bins[bin_idx].append((pred, actual))

        mean_predicted = []
        fraction_positive = []
        bin_counts = []

        for bin_data in bins:
            if bin_data:
                mean_predicted.append(sum(p for p, _ in bin_data) / len(bin_data))
                fraction_positive.append(sum(a for _, a in bin_data) / len(bin_data))
                bin_counts.append(len(bin_data))
            else:
                mean_predicted.append(0.0)
                fraction_positive.append(0.0)
                bin_counts.append(0)

        return {
            "mean_predicted": mean_predicted,
            "fraction_positive": fraction_positive,
            "bin_counts": bin_counts,
        }

    @staticmethod
    def calculate_all_classification_metrics(
        y_true: List[float],
        y_pred: List[float],
        threshold: float = 0.5,
    ) -> Dict[str, float]:
        """Calculate all classification metrics"""
        # Convert to binary predictions
        y_pred_binary = [1 if p >= threshold else 0 for p in y_pred]

        tp = sum(1 for p, a in zip(y_pred_binary, y_true) if p == 1 and a == 1)
        tn = sum(1 for p, a in zip(y_pred_binary, y_true) if p == 0 and a == 0)
        fp = sum(1 for p, a in zip(y_pred_binary, y_true) if p == 1 and a == 0)
        fn = sum(1 for p, a in zip(y_pred_binary, y_true) if p == 0 and a == 1)

        accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "auc_roc": MetricsCalculator.calculate_auc_roc(y_true, y_pred),
            "brier_score": MetricsCalculator.calculate_brier_score(y_true, y_pred),
            "ece": MetricsCalculator.calculate_ece(y_true, y_pred),
            "true_positives": tp,
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn,
        }


# =============================================================================
# Artifact Handler
# =============================================================================

class ArtifactHandler:
    """Handle artifact storage and retrieval"""

    def __init__(self, base_path: str = "mlflow-artifacts"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save_model(
        self,
        model: Any,
        run_id: str,
        model_name: str,
        framework: str = "sklearn",
    ) -> str:
        """Save model artifact"""
        artifact_path = self.base_path / run_id / "models" / model_name
        artifact_path.mkdir(parents=True, exist_ok=True)

        model_file = artifact_path / "model.pkl"

        try:
            import pickle
            with open(model_file, "wb") as f:
                pickle.dump(model, f)
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
            # Save model metadata instead
            metadata = {
                "framework": framework,
                "model_type": type(model).__name__,
                "saved_at": datetime.now().isoformat(),
            }
            with open(artifact_path / "metadata.json", "w") as f:
                json.dump(metadata, f)

        return str(artifact_path)

    def save_plot(
        self,
        figure: Any,
        run_id: str,
        plot_name: str,
        format: str = "png",
    ) -> str:
        """Save plot artifact"""
        artifact_path = self.base_path / run_id / "plots"
        artifact_path.mkdir(parents=True, exist_ok=True)

        plot_file = artifact_path / f"{plot_name}.{format}"

        try:
            figure.savefig(plot_file, dpi=150, bbox_inches="tight")
        except Exception as e:
            logger.error(f"Failed to save plot: {e}")

        return str(plot_file)

    def save_feature_importance(
        self,
        importance: Dict[str, float],
        run_id: str,
        model_name: str,
    ) -> str:
        """Save feature importance as JSON and plot"""
        artifact_path = self.base_path / run_id / "feature_importance"
        artifact_path.mkdir(parents=True, exist_ok=True)

        # Save as JSON
        json_file = artifact_path / f"{model_name}_importance.json"
        sorted_importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
        with open(json_file, "w") as f:
            json.dump(sorted_importance, f, indent=2)

        # Try to create plot
        try:
            import matplotlib.pyplot as plt

            features = list(sorted_importance.keys())[:20]
            values = [sorted_importance[f] for f in features]

            fig, ax = plt.subplots(figsize=(10, 8))
            ax.barh(features[::-1], values[::-1])
            ax.set_xlabel("Importance")
            ax.set_title(f"Feature Importance - {model_name}")

            plot_file = artifact_path / f"{model_name}_importance.png"
            fig.savefig(plot_file, dpi=150, bbox_inches="tight")
            plt.close(fig)
        except ImportError:
            logger.debug("matplotlib not available for feature importance plot")

        return str(json_file)

    def save_calibration_curve(
        self,
        calibration_data: Dict[str, List[float]],
        run_id: str,
        model_name: str,
    ) -> str:
        """Save calibration curve"""
        artifact_path = self.base_path / run_id / "calibration"
        artifact_path.mkdir(parents=True, exist_ok=True)

        # Save data as JSON
        json_file = artifact_path / f"{model_name}_calibration.json"
        with open(json_file, "w") as f:
            json.dump(calibration_data, f, indent=2)

        # Try to create plot
        try:
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(8, 8))

            # Plot calibration curve
            ax.plot(
                calibration_data["mean_predicted"],
                calibration_data["fraction_positive"],
                "s-",
                label="Model",
            )

            # Plot perfect calibration line
            ax.plot([0, 1], [0, 1], "k--", label="Perfectly calibrated")

            ax.set_xlabel("Mean Predicted Probability")
            ax.set_ylabel("Fraction of Positives")
            ax.set_title(f"Calibration Curve - {model_name}")
            ax.legend()
            ax.grid(True, alpha=0.3)

            plot_file = artifact_path / f"{model_name}_calibration.png"
            fig.savefig(plot_file, dpi=150, bbox_inches="tight")
            plt.close(fig)
        except ImportError:
            logger.debug("matplotlib not available for calibration curve plot")

        return str(json_file)

    def save_confusion_matrix(
        self,
        confusion_matrix: List[List[int]],
        run_id: str,
        model_name: str,
        labels: Optional[List[str]] = None,
    ) -> str:
        """Save confusion matrix"""
        artifact_path = self.base_path / run_id / "confusion_matrix"
        artifact_path.mkdir(parents=True, exist_ok=True)

        # Save as JSON
        json_file = artifact_path / f"{model_name}_confusion_matrix.json"
        data = {
            "matrix": confusion_matrix,
            "labels": labels or ["Negative", "Positive"],
        }
        with open(json_file, "w") as f:
            json.dump(data, f, indent=2)

        # Try to create plot
        try:
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(8, 6))

            im = ax.imshow(confusion_matrix, cmap="Blues")
            ax.figure.colorbar(im, ax=ax)

            ax.set_xticks(range(len(labels or ["N", "P"])))
            ax.set_yticks(range(len(labels or ["N", "P"])))
            ax.set_xticklabels(labels or ["Negative", "Positive"])
            ax.set_yticklabels(labels or ["Negative", "Positive"])

            ax.set_xlabel("Predicted")
            ax.set_ylabel("Actual")
            ax.set_title(f"Confusion Matrix - {model_name}")

            # Add text annotations
            for i in range(len(confusion_matrix)):
                for j in range(len(confusion_matrix[0])):
                    ax.text(j, i, str(confusion_matrix[i][j]),
                           ha="center", va="center", color="black")

            plot_file = artifact_path / f"{model_name}_confusion_matrix.png"
            fig.savefig(plot_file, dpi=150, bbox_inches="tight")
            plt.close(fig)
        except ImportError:
            logger.debug("matplotlib not available for confusion matrix plot")

        return str(json_file)

    def save_pr_curve(
        self,
        pr_data: Dict[str, List[float]],
        run_id: str,
        model_name: str,
    ) -> str:
        """Save precision-recall curve"""
        artifact_path = self.base_path / run_id / "pr_curve"
        artifact_path.mkdir(parents=True, exist_ok=True)

        # Save data as JSON
        json_file = artifact_path / f"{model_name}_pr_curve.json"
        with open(json_file, "w") as f:
            json.dump(pr_data, f, indent=2)

        # Try to create plot
        try:
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(8, 6))
            ax.plot(pr_data["recall"], pr_data["precision"], "b-", linewidth=2)
            ax.set_xlabel("Recall")
            ax.set_ylabel("Precision")
            ax.set_title(f"Precision-Recall Curve - {model_name}")
            ax.grid(True, alpha=0.3)
            ax.set_xlim([0, 1])
            ax.set_ylim([0, 1])

            plot_file = artifact_path / f"{model_name}_pr_curve.png"
            fig.savefig(plot_file, dpi=150, bbox_inches="tight")
            plt.close(fig)
        except ImportError:
            logger.debug("matplotlib not available for PR curve plot")

        return str(json_file)

    def load_artifact(self, artifact_path: str) -> Any:
        """Load artifact from path"""
        path = Path(artifact_path)

        if path.suffix == ".json":
            with open(path) as f:
                return json.load(f)
        elif path.suffix == ".pkl":
            import pickle
            with open(path, "rb") as f:
                return pickle.load(f)
        else:
            with open(path) as f:
                return f.read()

    def list_artifacts(self, run_id: str) -> List[Dict[str, Any]]:
        """List all artifacts for a run"""
        run_path = self.base_path / run_id
        artifacts = []

        if run_path.exists():
            for artifact_path in run_path.rglob("*"):
                if artifact_path.is_file():
                    artifacts.append({
                        "path": str(artifact_path.relative_to(run_path)),
                        "full_path": str(artifact_path),
                        "size_bytes": artifact_path.stat().st_size,
                        "modified": datetime.fromtimestamp(
                            artifact_path.stat().st_mtime
                        ).isoformat(),
                    })

        return artifacts


# =============================================================================
# Model Registry
# =============================================================================

class ModelRegistry:
    """Model registry for managing model versions and deployments"""

    def __init__(self, storage_path: str = "model-registry"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.models: Dict[str, RegisteredModel] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Load registry from storage"""
        registry_file = self.storage_path / "registry.json"
        if registry_file.exists():
            try:
                with open(registry_file) as f:
                    data = json.load(f)
                    for model_data in data.get("models", []):
                        model = RegisteredModel(
                            name=model_data["name"],
                            description=model_data.get("description", ""),
                            tags=model_data.get("tags", {}),
                            latest_version=model_data.get("latest_version"),
                            creation_timestamp=model_data.get("creation_timestamp", ""),
                            last_updated_timestamp=model_data.get("last_updated_timestamp", ""),
                        )
                        for v_data in model_data.get("versions", []):
                            version = ModelVersion(
                                model_name=model.name,
                                version=v_data["version"],
                                semantic_version=SemanticVersion.parse(
                                    v_data.get("semantic_version", "1.0.0")
                                ),
                                stage=ModelStage(v_data.get("stage", "None")),
                                run_id=v_data.get("run_id", ""),
                                source_uri=v_data.get("source_uri", ""),
                                description=v_data.get("description", ""),
                                tags=v_data.get("tags", {}),
                                metrics=v_data.get("metrics", {}),
                            )
                            model.versions.append(version)
                        self.models[model.name] = model
            except Exception as e:
                logger.error(f"Failed to load registry: {e}")

    def _save_registry(self) -> None:
        """Save registry to storage"""
        registry_file = self.storage_path / "registry.json"
        data = {
            "models": [
                {
                    "name": model.name,
                    "description": model.description,
                    "tags": model.tags,
                    "latest_version": model.latest_version,
                    "creation_timestamp": model.creation_timestamp,
                    "last_updated_timestamp": model.last_updated_timestamp,
                    "versions": [
                        {
                            "version": v.version,
                            "semantic_version": str(v.semantic_version),
                            "stage": v.stage.value,
                            "run_id": v.run_id,
                            "source_uri": v.source_uri,
                            "description": v.description,
                            "tags": v.tags,
                            "metrics": v.metrics,
                        }
                        for v in model.versions
                    ],
                }
                for model in self.models.values()
            ]
        }
        with open(registry_file, "w") as f:
            json.dump(data, f, indent=2)

    def register_model(
        self,
        name: str,
        run_id: str,
        source_uri: str,
        description: str = "",
        tags: Optional[Dict[str, str]] = None,
        metrics: Optional[Dict[str, float]] = None,
        semantic_version: Optional[SemanticVersion] = None,
    ) -> ModelVersion:
        """Register a new model version"""
        now = datetime.now().isoformat()

        if name not in self.models:
            self.models[name] = RegisteredModel(
                name=name,
                description=description,
                tags=tags or {},
                creation_timestamp=now,
                last_updated_timestamp=now,
            )

        model = self.models[name]
        version_num = (model.latest_version or 0) + 1

        # Determine semantic version
        if semantic_version is None:
            if model.versions:
                # Bump patch version
                last_semver = model.versions[-1].semantic_version
                semantic_version = last_semver.bump_patch()
            else:
                semantic_version = SemanticVersion(1, 0, 0)

        version = ModelVersion(
            model_name=name,
            version=version_num,
            semantic_version=semantic_version,
            stage=ModelStage.NONE,
            run_id=run_id,
            source_uri=source_uri,
            description=description,
            tags=tags or {},
            creation_timestamp=now,
            last_updated_timestamp=now,
            metrics=metrics or {},
        )

        model.versions.append(version)
        model.latest_version = version_num
        model.last_updated_timestamp = now

        self._save_registry()
        logger.info(f"Registered model {name} version {version_num} ({semantic_version})")

        return version

    def transition_model_stage(
        self,
        name: str,
        version: int,
        stage: ModelStage,
        archive_existing: bool = True,
    ) -> ModelVersion:
        """Transition model to a new stage"""
        if name not in self.models:
            raise ValueError(f"Model {name} not found in registry")

        model = self.models[name]
        target_version = None

        for v in model.versions:
            if v.version == version:
                target_version = v
                break

        if target_version is None:
            raise ValueError(f"Version {version} not found for model {name}")

        # Archive existing models in target stage
        if archive_existing and stage in [ModelStage.STAGING, ModelStage.PRODUCTION]:
            for v in model.versions:
                if v.stage == stage and v.version != version:
                    v.stage = ModelStage.ARCHIVED
                    v.stage_transitions.append({
                        "from_stage": stage.value,
                        "to_stage": ModelStage.ARCHIVED.value,
                        "timestamp": datetime.now().isoformat(),
                        "reason": f"Replaced by version {version}",
                    })

        # Update target version
        old_stage = target_version.stage
        target_version.stage = stage
        target_version.last_updated_timestamp = datetime.now().isoformat()
        target_version.stage_transitions.append({
            "from_stage": old_stage.value,
            "to_stage": stage.value,
            "timestamp": datetime.now().isoformat(),
        })

        self._save_registry()
        logger.info(f"Transitioned {name} v{version} from {old_stage.value} to {stage.value}")

        return target_version

    def get_model_version(
        self,
        name: str,
        version: Optional[int] = None,
        stage: Optional[ModelStage] = None,
    ) -> Optional[ModelVersion]:
        """Get specific model version"""
        if name not in self.models:
            return None

        model = self.models[name]

        if version is not None:
            for v in model.versions:
                if v.version == version:
                    return v
        elif stage is not None:
            for v in reversed(model.versions):
                if v.stage == stage:
                    return v
        else:
            # Return latest
            return model.versions[-1] if model.versions else None

        return None

    def get_production_model(self, name: str) -> Optional[ModelVersion]:
        """Get production model version"""
        return self.get_model_version(name, stage=ModelStage.PRODUCTION)

    def get_staging_model(self, name: str) -> Optional[ModelVersion]:
        """Get staging model version"""
        return self.get_model_version(name, stage=ModelStage.STAGING)

    def list_models(self) -> List[RegisteredModel]:
        """List all registered models"""
        return list(self.models.values())

    def search_models(
        self,
        name_pattern: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> List[RegisteredModel]:
        """Search for models"""
        results = []

        for model in self.models.values():
            # Match name pattern
            if name_pattern and name_pattern not in model.name:
                continue

            # Match tags
            if tags:
                if not all(model.tags.get(k) == v for k, v in tags.items()):
                    continue

            results.append(model)

        return results

    def compare_versions(
        self,
        name: str,
        version1: int,
        version2: int,
    ) -> Dict[str, Any]:
        """Compare two model versions"""
        v1 = self.get_model_version(name, version1)
        v2 = self.get_model_version(name, version2)

        if not v1 or not v2:
            raise ValueError("One or both versions not found")

        # Compare metrics
        metric_diff = {}
        all_metrics = set(v1.metrics.keys()) | set(v2.metrics.keys())

        for metric in all_metrics:
            val1 = v1.metrics.get(metric, 0.0)
            val2 = v2.metrics.get(metric, 0.0)
            metric_diff[metric] = {
                "v1": val1,
                "v2": val2,
                "diff": val2 - val1,
                "pct_change": ((val2 - val1) / val1 * 100) if val1 != 0 else 0,
            }

        return {
            "model_name": name,
            "version1": {
                "version": v1.version,
                "semantic_version": str(v1.semantic_version),
                "stage": v1.stage.value,
                "created": v1.creation_timestamp,
            },
            "version2": {
                "version": v2.version,
                "semantic_version": str(v2.semantic_version),
                "stage": v2.stage.value,
                "created": v2.creation_timestamp,
            },
            "metric_comparison": metric_diff,
        }


# =============================================================================
# A/B Experiment Manager
# =============================================================================

class ABExperimentManager:
    """Manage A/B experiment groups and allocation"""

    def __init__(self):
        self.experiments: Dict[str, Dict[str, Any]] = {}
        self.allocations: Dict[str, Dict[str, str]] = {}  # entity_id -> experiment -> variant

    def create_experiment(
        self,
        experiment_id: str,
        variants: List[str],
        weights: Optional[List[float]] = None,
        description: str = "",
    ) -> Dict[str, Any]:
        """Create a new A/B experiment"""
        if weights is None:
            weights = [1.0 / len(variants)] * len(variants)

        self.experiments[experiment_id] = {
            "id": experiment_id,
            "variants": variants,
            "weights": weights,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "status": "active",
            "metrics": {v: defaultdict(list) for v in variants},
        }

        return self.experiments[experiment_id]

    def allocate_variant(
        self,
        experiment_id: str,
        entity_id: str,
    ) -> str:
        """Allocate an entity to a variant"""
        if experiment_id not in self.experiments:
            raise ValueError(f"Experiment {experiment_id} not found")

        # Check existing allocation
        if entity_id in self.allocations:
            if experiment_id in self.allocations[entity_id]:
                return self.allocations[entity_id][experiment_id]

        # Deterministic allocation based on hash
        exp = self.experiments[experiment_id]
        hash_val = int(hashlib.md5(
            f"{experiment_id}:{entity_id}".encode()
        ).hexdigest(), 16)

        # Weighted random selection
        normalized = hash_val / (2 ** 128)
        cumsum = 0.0
        selected_variant = exp["variants"][-1]

        for variant, weight in zip(exp["variants"], exp["weights"]):
            cumsum += weight
            if normalized <= cumsum:
                selected_variant = variant
                break

        # Store allocation
        if entity_id not in self.allocations:
            self.allocations[entity_id] = {}
        self.allocations[entity_id][experiment_id] = selected_variant

        return selected_variant

    def record_metric(
        self,
        experiment_id: str,
        entity_id: str,
        metric_name: str,
        value: float,
    ) -> None:
        """Record a metric for an entity in the experiment"""
        if experiment_id not in self.experiments:
            return

        variant = self.allocate_variant(experiment_id, entity_id)
        self.experiments[experiment_id]["metrics"][variant][metric_name].append(value)

    def get_experiment_results(
        self,
        experiment_id: str,
    ) -> Dict[str, Any]:
        """Get experiment results with statistical analysis"""
        if experiment_id not in self.experiments:
            raise ValueError(f"Experiment {experiment_id} not found")

        exp = self.experiments[experiment_id]
        results = {
            "experiment_id": experiment_id,
            "status": exp["status"],
            "variants": {},
        }

        for variant in exp["variants"]:
            variant_metrics = exp["metrics"][variant]
            results["variants"][variant] = {}

            for metric_name, values in variant_metrics.items():
                if values:
                    results["variants"][variant][metric_name] = {
                        "mean": sum(values) / len(values),
                        "std": math.sqrt(
                            sum((v - sum(values) / len(values)) ** 2 for v in values) / len(values)
                        ) if len(values) > 1 else 0.0,
                        "count": len(values),
                        "min": min(values),
                        "max": max(values),
                    }

        return results

    def conclude_experiment(
        self,
        experiment_id: str,
        winning_variant: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Conclude experiment and select winner"""
        if experiment_id not in self.experiments:
            raise ValueError(f"Experiment {experiment_id} not found")

        exp = self.experiments[experiment_id]
        exp["status"] = "concluded"
        exp["concluded_at"] = datetime.now().isoformat()
        exp["winning_variant"] = winning_variant

        return self.get_experiment_results(experiment_id)


# =============================================================================
# Optuna Integration
# =============================================================================

class OptunaIntegration:
    """Integration with Optuna for hyperparameter tuning"""

    def __init__(self, tracker: "ExperimentTracker"):
        self.tracker = tracker
        self.study_runs: Dict[str, List[str]] = {}  # study_name -> run_ids

    def create_optuna_callback(
        self,
        study_name: str,
        experiment_name: str,
    ) -> Callable:
        """Create Optuna callback for MLflow logging"""
        if study_name not in self.study_runs:
            self.study_runs[study_name] = []

        def callback(study: Any, trial: Any) -> None:
            # Log trial as nested run
            run = self.tracker.start_run(
                experiment_name=experiment_name,
                run_name=f"{study_name}_trial_{trial.number}",
                tags={
                    "optuna.study_name": study_name,
                    "optuna.trial_number": str(trial.number),
                },
            )

            # Log parameters
            for key, value in trial.params.items():
                self.tracker.log_param(key, value)

            # Log value if available
            if trial.value is not None:
                self.tracker.log_metric("objective_value", trial.value)

            # Log trial state
            self.tracker.log_param("trial_state", str(trial.state))

            self.tracker.end_run()
            self.study_runs[study_name].append(run.run_id)

        return callback

    def log_study_summary(
        self,
        study: Any,
        study_name: str,
        experiment_name: str,
    ) -> ExperimentRun:
        """Log Optuna study summary"""
        run = self.tracker.start_run(
            experiment_name=experiment_name,
            run_name=f"{study_name}_summary",
            tags={
                "optuna.study_name": study_name,
                "optuna.type": "summary",
            },
        )

        # Log best trial info
        if study.best_trial:
            self.tracker.log_param("best_trial_number", study.best_trial.number)
            self.tracker.log_metric("best_value", study.best_value)

            for key, value in study.best_params.items():
                self.tracker.log_param(f"best_{key}", value)

        # Log study statistics
        self.tracker.log_metric("n_trials", len(study.trials))

        completed = [t for t in study.trials if t.state.name == "COMPLETE"]
        if completed:
            values = [t.value for t in completed]
            self.tracker.log_metric("trials_completed", len(completed))
            self.tracker.log_metric("mean_value", sum(values) / len(values))
            self.tracker.log_metric("std_value", math.sqrt(
                sum((v - sum(values) / len(values)) ** 2 for v in values) / len(values)
            ))

        self.tracker.end_run()
        return run

    def suggest_search_space(
        self,
        trial: Any,
        search_space: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Suggest values from search space using Optuna trial"""
        params = {}

        for name, config in search_space.items():
            space_type = config.get("type", "float")

            if space_type == "float":
                params[name] = trial.suggest_float(
                    name,
                    config.get("min", 0.0),
                    config.get("max", 1.0),
                    log=config.get("log", False),
                )
            elif space_type == "int":
                params[name] = trial.suggest_int(
                    name,
                    config.get("min", 0),
                    config.get("max", 100),
                )
            elif space_type == "categorical":
                params[name] = trial.suggest_categorical(
                    name,
                    config.get("choices", []),
                )

        return params


# =============================================================================
# Main Experiment Tracker
# =============================================================================

class ExperimentTracker:
    """
    Comprehensive experiment tracking system wrapping MLflow

    Features:
    - Automatic parameter and metric logging
    - Environment and git commit tracking
    - Dataset version linking
    - Model registry integration
    - A/B experiment grouping
    - Hyperparameter tuning integration
    """

    def __init__(self, config: Optional[MLflowConfig] = None):
        self.config = config or MLflowConfig.from_env()
        self.artifact_handler = ArtifactHandler(self.config.artifact_location)
        self.model_registry = ModelRegistry()
        self.ab_manager = ABExperimentManager()
        self.optuna_integration = OptunaIntegration(self)
        self.metrics_calculator = MetricsCalculator()

        # State
        self.experiments: Dict[str, str] = {}  # name -> id
        self.runs: Dict[str, ExperimentRun] = {}
        self.active_run: Optional[ExperimentRun] = None

        # Metrics buffer for batch logging
        self._metrics_buffer: List[Tuple[str, float, Optional[int]]] = []

        self._initialize()

    def _initialize(self) -> None:
        """Initialize tracker and configure MLflow"""
        try:
            import mlflow
            mlflow.set_tracking_uri(self.config.tracking_uri)
            logger.info(f"MLflow tracking URI: {self.config.tracking_uri}")
        except ImportError:
            logger.warning("MLflow not installed - using local tracking only")

    # -------------------------------------------------------------------------
    # Experiment Management
    # -------------------------------------------------------------------------

    def create_experiment(
        self,
        name: str,
        artifact_location: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> str:
        """Create a new experiment"""
        experiment_id = str(uuid.uuid4())
        self.experiments[name] = experiment_id

        try:
            import mlflow
            experiment_id = mlflow.create_experiment(
                name,
                artifact_location=artifact_location or self.config.artifact_location,
                tags=tags,
            )
            self.experiments[name] = experiment_id
        except ImportError:
            pass
        except Exception as e:
            # Experiment might already exist
            logger.debug(f"Create experiment: {e}")
            try:
                import mlflow
                experiment = mlflow.get_experiment_by_name(name)
                if experiment:
                    experiment_id = experiment.experiment_id
                    self.experiments[name] = experiment_id
            except Exception:
                pass

        return experiment_id

    def set_experiment(self, name: str) -> str:
        """Set active experiment"""
        if name not in self.experiments:
            return self.create_experiment(name)

        try:
            import mlflow
            mlflow.set_experiment(name)
        except ImportError:
            pass

        return self.experiments[name]

    # -------------------------------------------------------------------------
    # Run Management
    # -------------------------------------------------------------------------

    def start_run(
        self,
        experiment_name: Optional[str] = None,
        run_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        nested: bool = False,
        capture_environment: bool = True,
        capture_git: bool = True,
    ) -> ExperimentRun:
        """Start a new experiment run"""
        experiment_name = experiment_name or self.config.default_experiment_name
        experiment_id = self.set_experiment(experiment_name)

        run_id = str(uuid.uuid4())
        run_name = run_name or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        run = ExperimentRun(
            run_id=run_id,
            experiment_id=experiment_id,
            experiment_name=experiment_name,
            run_name=run_name,
            status=RunStatus.RUNNING,
            tags=tags or {},
        )

        # Capture reproducibility info
        if capture_environment:
            run.environment = EnvironmentInfo.capture()
        if capture_git:
            run.git_info = GitInfo.capture()

        # Handle nesting
        if nested and self.active_run:
            run.parent_run_id = self.active_run.run_id
            self.active_run.child_run_ids.append(run_id)

        self.runs[run_id] = run
        self.active_run = run

        # Start MLflow run
        try:
            import mlflow
            mlflow_run = mlflow.start_run(
                run_name=run_name,
                tags=tags,
                nested=nested,
            )
            run.run_id = mlflow_run.info.run_id
            self.runs[run.run_id] = run
        except ImportError:
            pass

        # Auto-log environment
        if run.environment:
            self.log_param("python_version", run.environment.python_version.split()[0])
            self.log_param("platform", run.environment.platform_info)

        if run.git_info and run.git_info.commit_hash:
            self.log_param("git_commit", run.git_info.commit_hash[:8])
            self.log_param("git_branch", run.git_info.branch)
            if run.git_info.is_dirty:
                self.log_param("git_dirty", "true")

        logger.info(f"Started run {run_name} ({run_id[:8]})")
        return run

    def end_run(
        self,
        status: RunStatus = RunStatus.FINISHED,
    ) -> Optional[ExperimentRun]:
        """End the current run"""
        if not self.active_run:
            return None

        run = self.active_run
        run.end_time = datetime.now()
        run.status = status

        # Flush metrics buffer
        self._flush_metrics_buffer()

        # End MLflow run
        try:
            import mlflow
            mlflow.end_run(
                status="FINISHED" if status == RunStatus.FINISHED else "FAILED"
            )
        except ImportError:
            pass

        logger.info(f"Ended run {run.run_name} ({run.run_id[:8]}) - {status.value}")

        # Restore parent run if nested
        if run.parent_run_id and run.parent_run_id in self.runs:
            self.active_run = self.runs[run.parent_run_id]
        else:
            self.active_run = None

        return run

    # -------------------------------------------------------------------------
    # Parameter Logging
    # -------------------------------------------------------------------------

    def log_param(self, key: str, value: Any) -> None:
        """Log a single parameter"""
        if self.active_run:
            self.active_run.params[key] = value

        try:
            import mlflow
            mlflow.log_param(key, value)
        except ImportError:
            pass

    def log_params(self, params: Dict[str, Any]) -> None:
        """Log multiple parameters"""
        for key, value in params.items():
            self.log_param(key, value)

    def log_hyperparameters(
        self,
        hyperparameters: Hyperparameters,
        prefix: str = "hp",
    ) -> None:
        """Log hyperparameters with prefix"""
        for key, value in hyperparameters.all_params().items():
            self.log_param(f"{prefix}.{key}", value)

    def log_seed(self, seed: int, set_seeds: bool = True) -> None:
        """Log random seed and optionally set it"""
        self.log_param("seed", seed)

        if set_seeds:
            import random
            random.seed(seed)

            try:
                import numpy as np
                np.random.seed(seed)
            except ImportError:
                pass

            try:
                import torch
                torch.manual_seed(seed)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(seed)
            except ImportError:
                pass

    # -------------------------------------------------------------------------
    # Metric Logging
    # -------------------------------------------------------------------------

    def log_metric(
        self,
        key: str,
        value: float,
        step: Optional[int] = None,
        metric_type: MetricType = MetricType.CUSTOM,
    ) -> None:
        """Log a single metric"""
        if self.active_run:
            self.active_run.metrics.add(key, value, metric_type, step)

        if self.config.async_logging:
            self._metrics_buffer.append((key, value, step))
            if len(self._metrics_buffer) >= self.config.batch_metrics_size:
                self._flush_metrics_buffer()
        else:
            self._log_metric_immediate(key, value, step)

    def _log_metric_immediate(self, key: str, value: float, step: Optional[int]) -> None:
        """Log metric immediately to MLflow"""
        try:
            import mlflow
            mlflow.log_metric(key, value, step=step)
        except ImportError:
            pass

    def _flush_metrics_buffer(self) -> None:
        """Flush metrics buffer to MLflow"""
        if not self._metrics_buffer:
            return

        try:
            import mlflow
            for key, value, step in self._metrics_buffer:
                mlflow.log_metric(key, value, step=step)
        except ImportError:
            pass

        self._metrics_buffer.clear()

    def log_metrics(
        self,
        metrics: Dict[str, float],
        step: Optional[int] = None,
    ) -> None:
        """Log multiple metrics"""
        for key, value in metrics.items():
            self.log_metric(key, value, step)

    def log_classification_metrics(
        self,
        y_true: List[float],
        y_pred: List[float],
        prefix: str = "",
    ) -> Dict[str, float]:
        """Log all classification metrics"""
        metrics = self.metrics_calculator.calculate_all_classification_metrics(y_true, y_pred)

        for key, value in metrics.items():
            full_key = f"{prefix}{key}" if prefix else key
            self.log_metric(full_key, value, metric_type=MetricType.CLASSIFICATION)

        return metrics

    def log_calibration_metrics(
        self,
        y_true: List[float],
        y_pred: List[float],
        prefix: str = "calibration_",
    ) -> Dict[str, float]:
        """Log calibration metrics (Brier, ECE)"""
        metrics = {
            "brier_score": self.metrics_calculator.calculate_brier_score(y_true, y_pred),
            "ece": self.metrics_calculator.calculate_ece(y_true, y_pred),
        }

        for key, value in metrics.items():
            self.log_metric(f"{prefix}{key}", value, metric_type=MetricType.CALIBRATION)

        # Log calibration curve artifact
        if self.active_run:
            curve_data = self.metrics_calculator.calculate_calibration_curve(y_true, y_pred)
            self.log_calibration_curve(curve_data, "model")

        return metrics

    def log_pr_curve(
        self,
        y_true: List[float],
        y_pred: List[float],
        model_name: str = "model",
    ) -> str:
        """Log precision-recall curve"""
        pr_data = self.metrics_calculator.calculate_precision_recall_curve(y_true, y_pred)

        if self.active_run:
            artifact_path = self.artifact_handler.save_pr_curve(
                pr_data,
                self.active_run.run_id,
                model_name,
            )
            self.active_run.artifacts[f"pr_curve_{model_name}"] = artifact_path

            try:
                import mlflow
                mlflow.log_artifact(artifact_path)
            except ImportError:
                pass

            return artifact_path

        return ""

    # -------------------------------------------------------------------------
    # Artifact Logging
    # -------------------------------------------------------------------------

    def log_model(
        self,
        model: Any,
        model_name: str,
        framework: str = "sklearn",
        register: bool = False,
        semantic_version: Optional[SemanticVersion] = None,
    ) -> str:
        """Log model artifact"""
        if not self.active_run:
            raise RuntimeError("No active run")

        artifact_path = self.artifact_handler.save_model(
            model,
            self.active_run.run_id,
            model_name,
            framework,
        )

        self.active_run.artifacts[f"model_{model_name}"] = artifact_path
        self.active_run.model_name = model_name
        self.active_run.model_version = semantic_version or SemanticVersion(1, 0, 0)

        try:
            import mlflow
            mlflow.log_artifact(artifact_path)
        except ImportError:
            pass

        # Register in model registry
        if register:
            self.register_model(
                model_name,
                artifact_path,
                semantic_version=semantic_version,
            )

        return artifact_path

    def log_feature_importance(
        self,
        importance: Dict[str, float],
        model_name: str = "model",
    ) -> str:
        """Log feature importance"""
        if not self.active_run:
            raise RuntimeError("No active run")

        artifact_path = self.artifact_handler.save_feature_importance(
            importance,
            self.active_run.run_id,
            model_name,
        )

        self.active_run.artifacts[f"feature_importance_{model_name}"] = artifact_path

        try:
            import mlflow
            mlflow.log_artifact(artifact_path)
        except ImportError:
            pass

        return artifact_path

    def log_calibration_curve(
        self,
        calibration_data: Dict[str, List[float]],
        model_name: str = "model",
    ) -> str:
        """Log calibration curve"""
        if not self.active_run:
            raise RuntimeError("No active run")

        artifact_path = self.artifact_handler.save_calibration_curve(
            calibration_data,
            self.active_run.run_id,
            model_name,
        )

        self.active_run.artifacts[f"calibration_curve_{model_name}"] = artifact_path

        try:
            import mlflow
            mlflow.log_artifact(artifact_path)
        except ImportError:
            pass

        return artifact_path

    def log_confusion_matrix(
        self,
        y_true: List[float],
        y_pred: List[float],
        model_name: str = "model",
        threshold: float = 0.5,
    ) -> str:
        """Log confusion matrix"""
        if not self.active_run:
            raise RuntimeError("No active run")

        # Calculate confusion matrix
        y_pred_binary = [1 if p >= threshold else 0 for p in y_pred]

        tp = sum(1 for p, a in zip(y_pred_binary, y_true) if p == 1 and a == 1)
        tn = sum(1 for p, a in zip(y_pred_binary, y_true) if p == 0 and a == 0)
        fp = sum(1 for p, a in zip(y_pred_binary, y_true) if p == 1 and a == 0)
        fn = sum(1 for p, a in zip(y_pred_binary, y_true) if p == 0 and a == 1)

        confusion_matrix = [[tn, fp], [fn, tp]]

        artifact_path = self.artifact_handler.save_confusion_matrix(
            confusion_matrix,
            self.active_run.run_id,
            model_name,
        )

        self.active_run.artifacts[f"confusion_matrix_{model_name}"] = artifact_path

        return artifact_path

    def log_artifact(
        self,
        local_path: str,
        artifact_type: ArtifactType = ArtifactType.DATA,
    ) -> str:
        """Log generic artifact"""
        if not self.active_run:
            raise RuntimeError("No active run")

        artifact_name = Path(local_path).name
        self.active_run.artifacts[artifact_name] = local_path

        try:
            import mlflow
            mlflow.log_artifact(local_path)
        except ImportError:
            pass

        return local_path

    # -------------------------------------------------------------------------
    # Dataset Version Tracking
    # -------------------------------------------------------------------------

    def log_dataset(
        self,
        dataset: Any,
        name: str,
        version: str,
        split: str = "train",
    ) -> DatasetVersion:
        """Log dataset version"""
        dataset_version = DatasetVersion.from_dataframe(
            dataset,
            name,
            version,
            split,
        )

        if self.active_run:
            self.active_run.datasets.append(dataset_version)

            # Log as params
            self.log_param(f"dataset.{split}.name", name)
            self.log_param(f"dataset.{split}.version", version)
            self.log_param(f"dataset.{split}.hash", dataset_version.hash)
            self.log_param(f"dataset.{split}.size", dataset_version.num_records)

        return dataset_version

    # -------------------------------------------------------------------------
    # Model Registry
    # -------------------------------------------------------------------------

    def register_model(
        self,
        name: str,
        source_uri: str,
        description: str = "",
        tags: Optional[Dict[str, str]] = None,
        semantic_version: Optional[SemanticVersion] = None,
    ) -> ModelVersion:
        """Register model in registry"""
        run_id = self.active_run.run_id if self.active_run else ""
        metrics = self.active_run.metrics.all_metrics() if self.active_run else {}

        version = self.model_registry.register_model(
            name=name,
            run_id=run_id,
            source_uri=source_uri,
            description=description,
            tags=tags,
            metrics=metrics,
            semantic_version=semantic_version,
        )

        return version

    def transition_model_stage(
        self,
        name: str,
        version: int,
        stage: ModelStage,
    ) -> ModelVersion:
        """Transition model to new stage"""
        return self.model_registry.transition_model_stage(name, version, stage)

    def promote_to_staging(self, name: str, version: int) -> ModelVersion:
        """Promote model to staging"""
        return self.transition_model_stage(name, version, ModelStage.STAGING)

    def promote_to_production(self, name: str, version: int) -> ModelVersion:
        """Promote model to production"""
        return self.transition_model_stage(name, version, ModelStage.PRODUCTION)

    def get_production_model(self, name: str) -> Optional[ModelVersion]:
        """Get production model"""
        return self.model_registry.get_production_model(name)

    # -------------------------------------------------------------------------
    # Run Comparison
    # -------------------------------------------------------------------------

    def compare_runs(
        self,
        run_ids: List[str],
        metrics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Compare multiple runs"""
        comparison = {
            "runs": [],
            "metrics_comparison": {},
        }

        for run_id in run_ids:
            if run_id in self.runs:
                run = self.runs[run_id]
                comparison["runs"].append({
                    "run_id": run.run_id,
                    "run_name": run.run_name,
                    "status": run.status.value,
                    "duration": str(run.duration),
                    "params": run.params.all_params(),
                    "metrics": run.metrics.all_metrics(),
                })

        # Compare specific metrics
        if metrics:
            for metric in metrics:
                values = []
                for run_id in run_ids:
                    if run_id in self.runs:
                        run = self.runs[run_id]
                        value = run.metrics.all_metrics().get(metric)
                        if value is not None:
                            values.append({"run_id": run_id, "value": value})

                if values:
                    comparison["metrics_comparison"][metric] = {
                        "values": values,
                        "best": max(values, key=lambda x: x["value"]),
                        "worst": min(values, key=lambda x: x["value"]),
                    }

        return comparison

    def get_best_run(
        self,
        experiment_name: str,
        metric: str,
        maximize: bool = True,
    ) -> Optional[ExperimentRun]:
        """Get best run by metric"""
        experiment_runs = [
            run for run in self.runs.values()
            if run.experiment_name == experiment_name
        ]

        if not experiment_runs:
            return None

        runs_with_metric = [
            run for run in experiment_runs
            if metric in run.metrics.all_metrics()
        ]

        if not runs_with_metric:
            return None

        return max(
            runs_with_metric,
            key=lambda r: r.metrics.all_metrics()[metric] * (1 if maximize else -1),
        )

    # -------------------------------------------------------------------------
    # Search and Filtering
    # -------------------------------------------------------------------------

    def search_runs(
        self,
        experiment_names: Optional[List[str]] = None,
        filter_string: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        status: Optional[RunStatus] = None,
        max_results: int = 100,
    ) -> List[ExperimentRun]:
        """Search for runs with filtering"""
        results = []

        for run in self.runs.values():
            # Filter by experiment
            if experiment_names and run.experiment_name not in experiment_names:
                continue

            # Filter by status
            if status and run.status != status:
                continue

            # Filter by tags
            if tags:
                if not all(run.tags.get(k) == v for k, v in tags.items()):
                    continue

            # Filter by string (simple contains check on run name)
            if filter_string and filter_string not in run.run_name:
                continue

            results.append(run)

            if len(results) >= max_results:
                break

        return results

    def list_experiments(self) -> List[Dict[str, Any]]:
        """List all experiments"""
        experiment_list = []

        for name, exp_id in self.experiments.items():
            runs = [r for r in self.runs.values() if r.experiment_name == name]
            experiment_list.append({
                "name": name,
                "id": exp_id,
                "run_count": len(runs),
                "latest_run": runs[-1].run_name if runs else None,
            })

        return experiment_list

    # -------------------------------------------------------------------------
    # A/B Testing
    # -------------------------------------------------------------------------

    def create_ab_experiment(
        self,
        experiment_id: str,
        variants: List[str],
        weights: Optional[List[float]] = None,
        description: str = "",
    ) -> Dict[str, Any]:
        """Create A/B experiment"""
        return self.ab_manager.create_experiment(
            experiment_id,
            variants,
            weights,
            description,
        )

    def get_ab_variant(
        self,
        experiment_id: str,
        entity_id: str,
    ) -> str:
        """Get A/B variant for entity"""
        return self.ab_manager.allocate_variant(experiment_id, entity_id)

    def record_ab_metric(
        self,
        experiment_id: str,
        entity_id: str,
        metric_name: str,
        value: float,
    ) -> None:
        """Record A/B experiment metric"""
        self.ab_manager.record_metric(experiment_id, entity_id, metric_name, value)

    def get_ab_results(self, experiment_id: str) -> Dict[str, Any]:
        """Get A/B experiment results"""
        return self.ab_manager.get_experiment_results(experiment_id)

    # -------------------------------------------------------------------------
    # Context Manager
    # -------------------------------------------------------------------------

    def __enter__(self) -> "ExperimentTracker":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.active_run:
            status = RunStatus.FAILED if exc_type else RunStatus.FINISHED
            self.end_run(status)


# =============================================================================
# Decorators
# =============================================================================

def track_experiment(
    experiment_name: str,
    run_name: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
    tracker: Optional[ExperimentTracker] = None,
):
    """Decorator to track function as experiment run"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            _tracker = tracker or ExperimentTracker()

            _run_name = run_name or func.__name__
            _tracker.start_run(
                experiment_name=experiment_name,
                run_name=_run_name,
                tags=tags,
            )

            try:
                result = func(*args, **kwargs)
                _tracker.end_run(RunStatus.FINISHED)
                return result
            except Exception as e:
                _tracker.end_run(RunStatus.FAILED)
                raise

        return wrapper
    return decorator


def autolog_params(tracker: ExperimentTracker):
    """Decorator to automatically log function parameters"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Log kwargs as params
            for key, value in kwargs.items():
                if isinstance(value, (int, float, str, bool)):
                    tracker.log_param(key, value)

            return func(*args, **kwargs)

        return wrapper
    return decorator


# =============================================================================
# Demonstration
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("MLflow Experiment Tracking Demo")
    print("=" * 60)

    # Initialize tracker
    tracker = ExperimentTracker()

    # Start an experiment run
    print("\n1. Starting experiment run...")
    run = tracker.start_run(
        experiment_name="quan-payment-prediction",
        run_name="gradient_boost_v1",
        tags={"model_type": "gradient_boost", "team": "ml"},
    )
    print(f"   Run ID: {run.run_id[:8]}...")
    print(f"   Git commit: {run.git_info.commit_hash[:8] if run.git_info else 'N/A'}...")

    # Log hyperparameters
    print("\n2. Logging hyperparameters...")
    hyperparams = Hyperparameters(
        params={
            "learning_rate": 0.01,
            "n_estimators": 100,
            "max_depth": 6,
        },
        fixed_params={"random_state": 42},
    )
    tracker.log_hyperparameters(hyperparams)
    tracker.log_seed(42)
    print("   Logged: learning_rate=0.01, n_estimators=100, max_depth=6")

    # Log dataset
    print("\n3. Logging dataset version...")
    dataset_version = DatasetVersion(
        name="payment_data",
        version="1.0.0",
        hash="abc123",
        num_records=10000,
        features=["balance", "days_past_due", "shadow_score"],
        split="train",
    )
    tracker.active_run.datasets.append(dataset_version)
    tracker.log_param("dataset.train.name", dataset_version.name)
    tracker.log_param("dataset.train.version", dataset_version.version)
    print(f"   Dataset: {dataset_version.name} v{dataset_version.version}")

    # Simulate predictions
    print("\n4. Simulating model predictions and logging metrics...")
    import random
    random.seed(42)

    y_true = [random.choice([0, 1]) for _ in range(1000)]
    y_pred = [random.random() for _ in range(1000)]

    # Log classification metrics
    metrics = tracker.log_classification_metrics(y_true, y_pred)
    print(f"   AUC-ROC: {metrics['auc_roc']:.4f}")
    print(f"   Brier Score: {metrics['brier_score']:.4f}")
    print(f"   ECE: {metrics['ece']:.4f}")

    # Log calibration metrics
    calibration = tracker.log_calibration_metrics(y_true, y_pred)
    print(f"   Calibration logged")

    # Log feature importance
    print("\n5. Logging feature importance...")
    feature_importance = {
        "shadow_score": 0.35,
        "balance": 0.25,
        "days_past_due": 0.20,
        "response_rate": 0.12,
        "total_contacts": 0.08,
    }
    tracker.log_feature_importance(feature_importance, "gradient_boost")
    print("   Feature importance artifact saved")

    # Register model
    print("\n6. Registering model...")
    model_version = tracker.register_model(
        name="payment_probability_model",
        source_uri="models/gradient_boost",
        description="Gradient boost payment prediction model",
        semantic_version=SemanticVersion(1, 0, 0),
    )
    print(f"   Registered: {model_version.model_name} v{model_version.version}")

    # End run
    tracker.end_run()
    print("\n7. Run completed!")

    # Model registry operations
    print("\n8. Model registry operations...")
    tracker.promote_to_staging("payment_probability_model", 1)
    print("   Promoted to staging")

    tracker.promote_to_production("payment_probability_model", 1)
    print("   Promoted to production")

    prod_model = tracker.get_production_model("payment_probability_model")
    print(f"   Production model: v{prod_model.version} ({prod_model.semantic_version})")

    # A/B experiment
    print("\n9. A/B experiment demo...")
    tracker.create_ab_experiment(
        "settlement_offer_test",
        variants=["control", "treatment_a", "treatment_b"],
        weights=[0.4, 0.3, 0.3],
    )

    # Simulate allocations
    allocations = {}
    for i in range(100):
        variant = tracker.get_ab_variant("settlement_offer_test", f"account_{i}")
        allocations[variant] = allocations.get(variant, 0) + 1

        # Record mock metric
        tracker.record_ab_metric(
            "settlement_offer_test",
            f"account_{i}",
            "conversion",
            random.random(),
        )

    print(f"   Variant allocation: {allocations}")
    results = tracker.get_ab_results("settlement_offer_test")
    print(f"   Experiment status: {results['status']}")

    # Run comparison
    print("\n10. Search and comparison...")
    runs = tracker.search_runs(
        experiment_names=["quan-payment-prediction"],
        status=RunStatus.FINISHED,
    )
    print(f"   Found {len(runs)} completed runs")

    experiments = tracker.list_experiments()
    print(f"   Total experiments: {len(experiments)}")

    print("\n" + "=" * 60)
    print("Demo completed successfully!")
    print("=" * 60)
