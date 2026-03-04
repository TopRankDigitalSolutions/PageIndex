#!/usr/bin/env python3
"""
Validate a PageIndex structure JSON file.

Checks:
- No literal "Error" in the file (from failed API calls)
- Every node has required fields and valid page ranges (start_index <= end_index, within 1..total_pages)
- Optional: total_pages matches expected (e.g. from PDF)

Exit code: 0 if valid, 1 if issues found.
"""
import argparse
import json
import sys

from pageindex.utils import structure_to_list


def load_structure(path: str):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "structure" in data:
        return data["structure"], data.get("doc_name", "")
    if isinstance(data, list):
        return data, ""
    raise ValueError(f"Unknown format in {path}")


def validate(structure_path: str, expected_pages: int | None = None) -> tuple[bool, list[str]]:
    issues = []
    try:
        tree, doc_name = load_structure(structure_path)
    except Exception as e:
        return False, [f"Failed to load JSON: {e}"]

    raw = open(structure_path, encoding="utf-8").read()
    if '"Error"' in raw or "'Error'" in raw:
        issues.append("File contains the literal string 'Error' (likely from a failed API call).")

    nodes = structure_to_list(tree)
    if not nodes:
        issues.append("No nodes found in structure.")
        return len(issues) == 0, issues

    # Infer total pages from max end_index
    total_pages = max(n.get("end_index", 0) for n in nodes if isinstance(n, dict))
    if expected_pages is not None and total_pages != expected_pages:
        issues.append(f"Max page in structure is {total_pages}, but expected {expected_pages} pages.")

    for node in nodes:
        if not isinstance(node, dict):
            continue
        title = node.get("title", "<no title>")
        start = node.get("start_index")
        end = node.get("end_index")
        if start is None or end is None:
            issues.append(f"Node '{title}' missing start_index or end_index.")
            continue
        if start > end:
            issues.append(f"Node '{title}': start_index ({start}) > end_index ({end}).")
        if start < 1 or end > total_pages:
            issues.append(f"Node '{title}': page range [{start}, {end}] outside [1, {total_pages}].")

    return len(issues) == 0, issues


def main():
    parser = argparse.ArgumentParser(description="Validate a PageIndex structure JSON file.")
    parser.add_argument("structure_path", help="Path to *_structure.json")
    parser.add_argument(
        "--expected-pages",
        type=int,
        default=None,
        help="Expected number of pages in the document (optional; if set, checks max page in structure matches).",
    )
    args = parser.parse_args()

    ok, issues = validate(args.structure_path, expected_pages=args.expected_pages)
    if issues:
        print("Validation issues:")
        for i in issues:
            print(f"  - {i}")
        sys.exit(1)
    print("Validation passed: structure looks consistent.")
    sys.exit(0)


if __name__ == "__main__":
    main()
