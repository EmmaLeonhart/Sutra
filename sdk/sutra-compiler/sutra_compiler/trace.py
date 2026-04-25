"""Sutra vector trace — records all vectors and operations during execution.

When the compiler runs with --trace, the generated Python includes a
_SutraTracer that wraps _NumpyVSA and records every vector allocation
and operation. After execution, call tracer.to_json() to get a
Three.js-ready trace with PCA-projected 3D positions.

The trace format:
{
    "program": "fuzzy_branching.su",
    "vectors": [
        {"name": "v_hello", "type": "basis", "step": 0, "pos": [x, y, z]},
        ...
    ],
    "operations": [
        {"type": "bind", "inputs": [0, 1], "output": 2, "step": 2},
        ...
    ]
}
"""
from __future__ import annotations

import json
import numpy as np
from typing import Any


def _to_numpy(vec: Any) -> np.ndarray:
    # Pytorch backend hands us torch.Tensor; numpy backend hands ndarray.
    # Normalize at record time so PCA / serialization stay numpy-only.
    if hasattr(vec, "detach"):
        return vec.detach().cpu().numpy().copy()
    return np.asarray(vec).copy()


class SutraTracer:
    """Records vectors and operations for 3D visualization."""

    def __init__(self, program_name: str = ""):
        self.program_name = program_name
        self._vectors: list[dict] = []      # {name, type, step, raw_vec}
        self._operations: list[dict] = []   # {type, inputs, output, step}
        self._step = 0
        self._vec_index: dict[int, int] = {}  # id(input vec) → index

    def record_vector(self, name: str, vec: Any, vtype: str = "other") -> int:
        """Record a named vector. Returns its index."""
        idx = len(self._vectors)
        self._vectors.append({
            "name": name,
            "type": vtype,
            "step": self._step,
            "raw": _to_numpy(vec),
        })
        self._vec_index[id(vec)] = idx
        self._step += 1
        return idx

    def record_op(self, op_type: str, inputs: list[Any],
                  output: Any, output_name: str = "") -> int:
        """Record an operation linking input vectors to an output."""
        out_idx = self.record_vector(output_name or f"_{op_type}_out", output, op_type)
        in_indices = []
        for inv in inputs:
            vid = id(inv)
            if vid in self._vec_index:
                in_indices.append(self._vec_index[vid])
        self._operations.append({
            "type": op_type,
            "inputs": in_indices,
            "output": out_idx,
            "step": self._step - 1,
        })
        return out_idx

    def _pca_3d(self) -> np.ndarray:
        """Project all recorded vectors to 3D via PCA."""
        if not self._vectors:
            return np.zeros((0, 3))
        raw = np.array([v["raw"] for v in self._vectors], dtype=np.float64)
        # Center
        mean = raw.mean(axis=0)
        centered = raw - mean
        # SVD for top-3 components
        if centered.shape[0] < 2:
            return np.zeros((centered.shape[0], 3))
        U, S, Vt = np.linalg.svd(centered, full_matrices=False)
        # Project onto top 3
        k = min(3, Vt.shape[0])
        proj = centered @ Vt[:k].T
        # Pad if fewer than 3 components
        if k < 3:
            proj = np.hstack([proj, np.zeros((proj.shape[0], 3 - k))])
        # Scale so points spread nicely in the scene
        max_extent = np.abs(proj).max()
        if max_extent > 0:
            proj = proj * (8.0 / max_extent)
        return proj

    def to_dict(self) -> dict[str, Any]:
        """Return the trace as a JSON-serializable dict with 3D positions."""
        positions = self._pca_3d()
        vectors = []
        for i, v in enumerate(self._vectors):
            entry = {
                "name": v["name"],
                "type": v["type"],
                "step": v["step"],
                "pos": [round(float(positions[i, j]), 4) for j in range(3)],
            }
            vectors.append(entry)
        return {
            "program": self.program_name,
            "vectors": vectors,
            "operations": self._operations,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_html(self, template_path: str | None = None) -> str:
        """Generate a standalone HTML file with embedded trace data."""
        import os
        if template_path is None:
            # Default: look for visualizer.html in the vscode-sutra media dir
            here = os.path.dirname(os.path.abspath(__file__))
            template_path = os.path.join(
                here, "..", "..", "vscode-sutra", "media", "visualizer.html"
            )
        with open(template_path, encoding="utf-8") as f:
            html = f.read()
        # Inject trace data before the module script
        inject = f'<script>window.SUTRA_TRACE_DATA = {self.to_json()};</script>'
        html = html.replace('<script type="module">', inject + '\n<script type="module">')
        return html
