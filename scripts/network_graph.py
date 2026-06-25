"""
Email Network Graph Generator — Visualize sender-recipient relationships.
Detects threat actor clusters and communication patterns.

Usage: python scripts/network_graph.py [--output screenshots/email_network.png]
"""

import argparse
import os
from collections import defaultdict
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from database.models import QuarantineEmail

DB_URL = os.getenv("DB_URL", "sqlite:///./lti_antiphishing.db")
OUTPUT_DIR = Path("screenshots")
OUTPUT_DIR.mkdir(exist_ok=True)

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


def extract_domain(email_addr: str) -> str:
    if not email_addr:
        return "unknown"
    if "@" in email_addr:
        return email_addr.split("@")[-1].strip(">").strip()
    return email_addr.strip()


def generate_network_graph(output: str = None):
    db = SessionLocal()
    rows = db.query(QuarantineEmail.sender, QuarantineEmail.label).all()

    G = nx.DiGraph()
    domain_counts = defaultdict(int)
    threat_domains = set()

    for sender, label in rows:
        domain = extract_domain(sender)
        domain_counts[domain] += 1
        if label == "QUARANTINE":
            threat_domains.add(domain)

    for domain, count in domain_counts.items():
        is_threat = domain in threat_domains
        G.add_node(domain, size=min(count * 50, 2000),
                   color="red" if is_threat else "green",
                   is_threat=is_threat)

    # Add edges between domains that appear together
    all_domains = list(domain_counts.keys())
    for i in range(len(all_domains)):
        for j in range(i + 1, len(all_domains)):
            d1, d2 = all_domains[i], all_domains[j]
            if domain_counts[d1] > 1 and domain_counts[d2] > 1:
                G.add_edge(d1, d2, weight=min(domain_counts[d1], domain_counts[d2]))

    # Remove isolated nodes
    isolated = [n for n in G.nodes() if G.degree(n) == 0]
    G.remove_nodes_from(isolated)

    if len(G.nodes()) == 0:
        print("No connections found to visualize.")
        db.close()
        return

    plt.figure(figsize=(16, 12))
    pos = nx.spring_layout(G, k=3, iterations=50, seed=42)

    sizes = [G.nodes[n].get("size", 300) for n in G.nodes()]
    colors = [G.nodes[n].get("color", "gray") for n in G.nodes()]

    nx.draw_networkx_nodes(G, pos, node_size=sizes, node_color=colors, alpha=0.8)
    nx.draw_networkx_labels(G, pos, font_size=8, font_weight="bold")

    edges = G.edges()
    if edges:
        weights = [G.edges[e].get("weight", 1) for e in edges]
        nx.draw_networkx_edges(G, pos, width=[max(0.5, w * 0.3) for w in weights],
                               alpha=0.3, arrows=True, arrow_size=12)

    plt.title("Email Sender Network — Threat Actor Clusters", fontsize=16, fontweight="bold")
    plt.axis("off")

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="red", label="Threat Actor (QUARANTINE)"),
        Patch(facecolor="green", label="Legitimate Sender"),
    ]
    plt.legend(handles=legend_elements, loc="upper right")

    output_path = output or str(OUTPUT_DIR / "email_network_graph.png")
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Network graph saved: {output_path}")

    stats = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "threat_domains": len(threat_domains),
    }
    print(f"Nodes: {stats['nodes']}, Edges: {stats['edges']}, Threat domains: {stats['threat_domains']}")

    db.close()
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate email network graph")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    generate_network_graph(output=args.output)
