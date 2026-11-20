"""Figure generation for the report (matplotlib, Agg backend)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

COLORS = {
    "ink": "#1a2b3c",
    "accent": "#c8553d",
    "blue": "#2e5eaa",
    "green": "#3a7d44",
    "grey": "#8a8f98",
    "gold": "#c9a227",
}


def _style(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, alpha=0.22, linewidth=0.6)
    ax.tick_params(colors=COLORS["ink"], labelsize=9)
    for s in ("bottom", "left"):
        ax.spines[s].set_color(COLORS["grey"])


def k_distribution(dist: Dict[int, int], path: Path):
    ks = sorted(int(k) for k in dist)
    counts = [dist[k] if k in dist else dist[str(k)] for k in ks]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.bar([str(k) for k in ks], counts, color=COLORS["blue"], width=0.72)
    ax.set_yscale("log")
    ax.set_xlabel("greedy index k(n)")
    ax.set_ylabel("count (log scale)")
    ax.set_title("Distribution of the greedy index (n ≤ 2×10⁷)", fontsize=11)
    _style(ax)
    for i, c in enumerate(counts):
        ax.text(i, c * 1.25, f"{c:,}", ha="center", va="bottom", fontsize=6.5,
                rotation=90, color=COLORS["ink"])
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def records_plot(records: Sequence[Tuple[int, int]], path: Path):
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ns = [n for n, _ in records]
    ks = [k for _, k in records]
    ax.plot(ns, ks, "-o", color=COLORS["accent"], lw=1.4, ms=4)
    ax.set_xscale("log")
    ax.set_xlabel("n (log scale)")
    ax.set_ylabel("record value of k(n)")
    ax.set_title("Record holders of the greedy index", fontsize=11)
    for n, k in records:
        ax.annotate(f"{n:,}", (n, k), textcoords="offset points", xytext=(4, 5),
                    fontsize=6.5, color=COLORS["ink"])
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def growth_plot(points: Sequence[Tuple[int, int]], a: float, b: float, path: Path):
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    xs = [np.log10(n) for n, _ in points]
    ys = [k for _, k in points]
    ax.plot(xs, ys, "o", color=COLORS["blue"], ms=4, label="k_max(N)")
    grid = np.linspace(min(xs), max(xs), 100)
    ax.plot(grid, a * grid * np.log(10) + b, "--", color=COLORS["accent"],
            lw=1.3, label=f"fit  k ≈ {a:.2f} ln N + {b:.2f}")
    ax.set_xlabel("log₁₀ N")
    ax.set_ylabel("k_max(N)")
    ax.set_title("Growth of the maximal greedy index", fontsize=11)
    ax.legend(frameon=False, fontsize=8)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def chain_plot(steps: Sequence[dict], n: int, path: Path):
    fig, ax = plt.subplots(figsize=(7.4, 3.7))
    xs = [s["j"] for s in steps]
    ratio = [s["reachable"] / s["p"] for s in steps]
    colors = [COLORS["green"] if s["success"] else COLORS["blue"] for s in steps]
    ax.bar(xs, ratio, color=colors, width=0.72)
    ax.set_xlabel("greedy step j  (a_j = 4j − 1)")
    ax.set_ylabel("|S_j| / p_j")
    ax.set_ylim(0, 1.05)
    ax.set_title(f"Obstruction chain for n = {n:,}: success at j = {steps[-1]['j']}",
                 fontsize=11)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def height_plot(sample: Sequence[Tuple[int, int, int]],
                top: Sequence[Tuple[float, int, int, int]], path: Path):
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    ns = [n for n, _, _ in sample]
    rs = [z / n**2 for n, _, z in sample]
    ax.scatter(ns, rs, s=3, alpha=0.35, color=COLORS["blue"], label="sample")
    tn = [t[1] for t in top]
    tr = [t[0] for t in top]
    ax.scatter(tn, tr, s=28, color=COLORS["accent"], marker="*",
               label="top 20 by z/n²")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("n (log scale)")
    ax.set_ylabel("z(n) / n²  (log scale)")
    ax.set_title("Greedy witness height: extreme divisor-gap spikes", fontsize=11)
    ax.legend(frameon=False, fontsize=8)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def height_ratio_plot(top: Sequence[Tuple[float, int, int, int]], path: Path):
    fig, ax = plt.subplots(figsize=(7.2, 3.7))
    ns = [t[1] for t in top]
    rs = [t[0] for t in top]
    ax.plot(ns, rs, "o-", color=COLORS["accent"], ms=4, lw=1.1)
    ax.set_xscale("log")
    ax.set_xlabel("n (log scale)")
    ax.set_ylabel("z(n) / n³")
    ax.set_title("Super-cubic growth of greedy witness heights", fontsize=11)
    for n, r in zip(ns, rs):
        ax.annotate(f"{r:.1f}", (n, r), textcoords="offset points", xytext=(3, 4),
                    fontsize=6.5)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def failure_residue_plot(dist_by_residue: Dict[int, Tuple[int, int]], path: Path):
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    labels = [str(r) for r in sorted(dist_by_residue)]
    dens = []
    for r in sorted(dist_by_residue):
        bad, total = dist_by_residue[r]
        dens.append(100.0 * bad / total)
    ax.bar(labels, dens, color=COLORS["green"], width=0.7)
    ax.set_xlabel("n mod 12")
    ax.set_ylabel("P(k(n) > 1)  (%)")
    ax.set_title("First-step failures by residue class", fontsize=11)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def agent_loop(path: Path):
    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    ax.axis("off")
    boxes = [
        ("Observe\n(range scan)", 0.06, 0.55),
        ("Hypothesise\n(rule / growth / height)", 0.28, 0.55),
        ("Design\nexperiment", 0.50, 0.55),
        ("Execute\ntool + certificate", 0.72, 0.55),
        ("Reflect &\nupdate beliefs", 0.50, 0.12),
        ("Synthesise\nreport + trace", 0.90, 0.12),
    ]
    for text, x, y in boxes:
        ax.add_patch(plt.Rectangle((x - 0.085, y - 0.10), 0.17, 0.20,
                                   facecolor="#eef3f8", edgecolor=COLORS["blue"],
                                   linewidth=1.0, zorder=2))
        ax.text(x, y, text, ha="center", va="center", fontsize=8.2, zorder=3)
    arrows = [((0.145, 0.55), (0.195, 0.55)), ((0.365, 0.55), (0.415, 0.55)),
              ((0.585, 0.55), (0.635, 0.55)), ((0.72, 0.45), (0.60, 0.22)),
              ((0.41, 0.22), (0.28, 0.45)), ((0.72, 0.22), (0.815, 0.22))]
    for (x1, y1), (x2, y2) in arrows:
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=COLORS["grey"], lw=1.2))
    ax.text(0.5, 0.93, "The research loop of ERDOS-GREEDY-AGENT", ha="center",
            fontsize=11, color=COLORS["ink"])
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
