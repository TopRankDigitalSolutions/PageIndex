#!/usr/bin/env python3
"""
Step 2: Reasoning-based retrieval with tree search.

Loads a local PageIndex structure JSON (from run_pageindex.py), sends the tree
plus your question to the LLM, and returns which nodes are relevant (node_list)
and the model's reasoning (thinking). Uses CHATGPT_API_KEY from .env.
"""
import argparse
import json
import os
import copy
import textwrap

from pageindex.utils import (
    ChatGPT_API,
    create_node_mapping,
    get_json_content,
    remove_fields,
)


def load_structure(path: str):
    """Load structure JSON. Handles both {doc_name, structure} and raw list."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "structure" in data:
        return data["structure"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unknown structure format in {path}")


def tree_for_prompt(tree):
    """Copy of tree with 'text' removed to keep the prompt smaller."""
    return remove_fields(copy.deepcopy(tree), fields=["text"])


def run_tree_search(structure_path: str, query: str, model: str = "gpt-4o-2024-11-20"):
    tree = load_structure(structure_path)
    node_map = create_node_mapping(tree)
    if not node_map:
        raise ValueError("No nodes with node_id found in the structure file.")

    tree_without_text = tree_for_prompt(tree)
    search_prompt = f"""You are given a question and a tree structure of a document.
Each node contains a node id, node title, and a corresponding summary.
Your task is to find all nodes that are likely to contain the answer to the question.

Question: {query}

Document tree structure:
{json.dumps(tree_without_text, indent=2)}

Please reply in the following JSON format:
{{
    "thinking": "<Your thinking process on which nodes are relevant to the question>",
    "node_list": ["node_id_1", "node_id_2", ..., "node_id_n"]
}}
Directly return the final JSON structure. Do not output anything else."""

    response = ChatGPT_API(model=model, prompt=search_prompt)
    if not response or response == "Error":
        raise RuntimeError("LLM call failed or returned no content.")

    # Parse JSON: allow raw JSON or inside ```json ... ```
    raw = get_json_content(response).strip() if "```" in response else response.strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: try to find JSON object in the response
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            result = json.loads(raw[start:end])
        else:
            raise ValueError("LLM response did not contain valid JSON.")

    thinking = result.get("thinking", "")
    node_list = result.get("node_list", [])
    if not isinstance(node_list, list):
        node_list = [node_list]

    return {
        "thinking": thinking,
        "node_list": node_list,
        "node_map": node_map,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Step 2: Run reasoning-based retrieval (tree search) on a PageIndex structure JSON."
    )
    parser.add_argument(
        "--structure_path",
        type=str,
        required=True,
        help="Path to the _structure.json file (e.g. results/my_doc_structure.json)",
    )
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="Question to ask about the document",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-2024-11-20",
        help="OpenAI model to use for tree search",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.structure_path):
        raise FileNotFoundError(f"Structure file not found: {args.structure_path}")

    out = run_tree_search(args.structure_path, args.query, model=args.model)
    thinking = out["thinking"]
    node_list = out["node_list"]
    node_map = out["node_map"]

    def print_wrapped(text, width=80):
        for line in text.split("\n"):
            for wrapped in textwrap.wrap(line, width=width) or [""]:
                print(wrapped)

    print("Reasoning process:")
    print_wrapped(thinking)
    print("\nRetrieved nodes:")
    for nid in node_list:
        node = node_map.get(str(nid))
        if node:
            page = node.get("page_index", node.get("start_index", "?"))
            title = node.get("title", "?")
            print(f"  Node ID: {nid}\tPage: {page}\tTitle: {title}")
        else:
            print(f"  Node ID: {nid}\t(not found in tree)")


if __name__ == "__main__":
    main()
