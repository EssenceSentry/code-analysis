#!/usr/bin/env python3
import argparse
import json
import os
import re

# --- Configuration for Parsing ---
# Regex to find the target path being analyzed
TARGET_PATH_RE = re.compile(r"Analyzing code complexity for: (.*)")

# --- Radon Raw ---
RADON_RAW_FILE_BLOCK_RE = re.compile(
    r"^(.*?\.py)\n\s+LOC: (\d+)\n\s+LLOC: (\d+)\n\s+SLOC: (\d+)\n\s+Comments: (\d+)",
    re.MULTILINE,
)
RADON_RAW_TOTAL_BLOCK_RE = re.compile(
    r"\*\* Total \*\*\n\s+LOC: (\d+)\n\s+LLOC: (\d+)\n\s+SLOC: (\d+)\n\s+Comments: (\d+)",
    re.MULTILINE,
)

# --- Radon CC ---
RADON_CC_FILE_RE = re.compile(r"^(.*?\.py)$", re.MULTILINE)
RADON_CC_BLOCK_RE = re.compile(r"\s+([FMC])\s+[\d:]+\s+(.*?)\s+-\s+([A-F])\s+\((\d+)\)")
RADON_CC_AVG_RE = re.compile(r"Average complexity:\s*([A-F])\s*\(([\d.]+)\)")

# --- Radon MI ---
RADON_MI_LINE_RE = re.compile(r"\s*(.*?\.py)\s+-\s+([A-F])\s+\(([\d.]+)\)")

# --- Flake8 Summary ---
FLAKE8_SUMMARY_RE = re.compile(
    r"\[WARNING\] Flake8 found (\d+) function\(s\) with CC > \d+\."
)

# --- Complexipy ---
COMPLEXIPY_ROW_RE = re.compile(
    r"│\s*(.*?)\s*│\s*(.*?)\s*│\s*(.*?)\s*│\s*(?:\x1b\[\d+m)?(\d+)(?:\x1b\[0m)?\s*│"
)
COMPLEXIPY_TOTAL_RE = re.compile(r"🧠 Total Cognitive Complexity: (\d+)")


def get_custom_mi_rank(mi_score):
    """Assigns a custom rank based on the MI score."""
    if mi_score >= 85:
        return "Excellent"
    elif mi_score >= 65:
        return "Good"
    elif mi_score >= 50:
        return "Moderate"
    else:
        return "Difficult"


def parse_radon_raw_section(section_text):
    """Parses Radon Raw metrics for files and totals."""
    file_metrics = []
    for match in RADON_RAW_FILE_BLOCK_RE.finditer(section_text):
        file_metrics.append(
            {
                "file_path": match.group(1).strip(),
                "loc": int(match.group(2)),
                "lloc": int(match.group(3)),
                "sloc": int(match.group(4)),
                "comments": int(match.group(5)),
            }
        )

    total_metrics = {}
    total_match = RADON_RAW_TOTAL_BLOCK_RE.search(section_text)
    if total_match:
        total_metrics = {
            "total_loc_radon": int(total_match.group(1)),
            "total_lloc_radon": int(total_match.group(2)),
            "total_sloc_radon": int(total_match.group(3)),
            "total_comments_radon": int(total_match.group(4)),
        }
    return {"files": file_metrics, "totals": total_metrics}


def parse_radon_cc_section(section_text):
    """Parses Radon CC metrics for functions/methods."""
    symbol_metrics = []
    current_file = None
    avg_cc = {}

    for line in section_text.splitlines():
        file_match = RADON_CC_FILE_RE.match(line)
        if file_match:
            current_file = file_match.group(1).strip()
            continue

        block_match = RADON_CC_BLOCK_RE.match(line)
        if block_match and current_file:
            symbol_type_map = {"F": "function", "M": "method", "C": "class"}
            symbol_metrics.append(
                {
                    "file_path": current_file,
                    "symbol_type": symbol_type_map.get(block_match.group(1), "unknown"),
                    "symbol_name": block_match.group(2).strip(),
                    "cc_rank": block_match.group(3),
                    "cc_score": int(block_match.group(4)),
                }
            )

        avg_match = RADON_CC_AVG_RE.search(line)
        if avg_match:
            avg_cc = {
                "average_cc_rank_radon": avg_match.group(1),
                "average_cc_score": float(avg_match.group(2)),
            }

    return {"symbols": symbol_metrics, "average": avg_cc}


def parse_radon_mi_section(section_text):
    """Parses Radon MI metrics for files by iterating lines and applies custom ranking."""
    file_metrics = []
    for line_number, line in enumerate(section_text.splitlines()):
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("[INFO]"):
            continue

        match = RADON_MI_LINE_RE.match(stripped_line)
        if match:
            mi_score = float(match.group(3))
            custom_rank = get_custom_mi_rank(mi_score)
            file_metrics.append(
                {
                    "file_path": match.group(1).strip(),
                    "mi_score": mi_score,
                    "mi_rank_custom": custom_rank,  # Using custom rank
                }
            )
    return {"files": file_metrics}


def parse_flake8_section(section_text):
    """Parses Flake8 summary for complex functions count."""
    match = FLAKE8_SUMMARY_RE.search(section_text)
    if match:
        return {"flake8_high_cc_functions_count": int(match.group(1))}
    if "Flake8 found 0 function(s)" in section_text:
        return {"flake8_high_cc_functions_count": 0}
    return {"flake8_high_cc_functions_count": -1}


def parse_complexipy_section(section_text):
    """Parses Complexipy table output."""
    symbol_metrics = []
    total_cognitive_complexity = 0

    table_content_match = re.search(
        r"(?:┡━+|│\s*Path\s*│).*?\n(.*?)\n\s*└─", section_text, re.DOTALL
    )
    actual_table_text = ""
    if table_content_match:
        actual_table_text = table_content_match.group(1)
    else:
        header_marker_match = re.search(r"(?:│\s*Path\s*│|┡━+)", section_text)
        if header_marker_match:
            actual_table_text = section_text[header_marker_match.end() :]

    for line in actual_table_text.splitlines():
        row_match = COMPLEXIPY_ROW_RE.match(line)
        if row_match:
            symbol_metrics.append(
                {
                    "complexipy_path": row_match.group(1).strip(),
                    "file_name_complexipy": row_match.group(2).strip(),
                    "symbol_name_complexipy": row_match.group(3).strip(),
                    "cognitive_complexity": int(row_match.group(4)),
                }
            )

    total_match_overall = COMPLEXIPY_TOTAL_RE.search(section_text)
    if total_match_overall:
        total_cognitive_complexity = int(total_match_overall.group(1))

    return {
        "symbols": symbol_metrics,
        "total_cognitive_complexity": total_cognitive_complexity,
    }


def generate_file_tree(
    root_dir,
    exclude_dirs_default=None,
    exclude_exts=None,
    prefix="",
):
    """Generates a string representation of a file tree, ignoring most hidden dirs."""
    if exclude_dirs_default is None:
        exclude_dirs_default = {
            "__pycache__",
            "build",
            "dist",
            ".egg-info",
            ".venv",
            ".git",
        }
    if exclude_exts is None:
        exclude_exts = {".pyc"}

    tree_lines = []
    try:
        items = sorted(os.listdir(root_dir))
    except FileNotFoundError:
        tree_lines.append(f"{prefix}└── [Error: Directory not found: {root_dir}]")
        return tree_lines
    except PermissionError:
        tree_lines.append(f"{prefix}└── [Error: Permission denied: {root_dir}]")
        return tree_lines

    for i, item_name in enumerate(items):
        path = os.path.join(root_dir, item_name)
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "

        if os.path.isdir(path):
            # Ignore hidden directories, unless it's .vscode
            if item_name.startswith(".") and item_name != ".vscode":
                continue
            # Always ignore default excluded dirs
            if item_name in exclude_dirs_default:
                continue

            tree_lines.append(f"{prefix}{connector}{item_name}/")
            new_prefix = prefix + ("    " if is_last else "│   ")
            tree_lines.extend(
                generate_file_tree(path, exclude_dirs_default, exclude_exts, new_prefix)
            )
        else:  # It's a file
            # Hidden files are included unless their extension is excluded
            if os.path.splitext(item_name)[1] in exclude_exts:
                continue
            tree_lines.append(f"{prefix}{connector}{item_name}")

    return tree_lines


def main(analysis_file_path):
    """Main function to parse the analysis file and print results."""
    try:
        with open(analysis_file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Analysis file not found at '{analysis_file_path}'")
        return
    except Exception as e:
        print(f"Error reading analysis file: {e}")
        return

    target_path_match = TARGET_PATH_RE.search(content)
    project_root_path = None
    if target_path_match:
        project_root_path = os.path.normpath(target_path_match.group(1).strip())
        print(
            f"Project Root Path (for file tree and path normalization): {project_root_path}\n"
        )
    else:
        print(
            "Warning: Could not determine project root path from analysis file. Path normalization might be affected.\n"
        )

    parsed_data = {
        "overall_summary": {},
        "file_level_metrics": [],
        "symbol_level_metrics": [],
    }
    temp_file_metrics = {}
    temp_symbol_metrics = {}

    def get_normalized_path(path, base_path=project_root_path):
        """Normalizes a path, making it absolute if base_path is provided and path is relative."""
        norm_p = os.path.normpath(path)
        if base_path and not os.path.isabs(norm_p):
            if (
                os.path.basename(base_path) == norm_p.split(os.sep)[0]
                and len(norm_p.split(os.sep)) > 1
            ):
                return os.path.normpath(
                    os.path.join(os.path.dirname(base_path), norm_p)
                )
            return os.path.normpath(os.path.join(base_path, norm_p))
        return norm_p

    def update_file_metric(path, data_dict):
        norm_path = get_normalized_path(path)
        if norm_path not in temp_file_metrics:
            temp_file_metrics[norm_path] = {"file_path": norm_path}
        temp_file_metrics[norm_path].update(data_dict)

    def update_symbol_metric(path, symbol_name, data_dict):
        norm_path = get_normalized_path(path)
        key = (norm_path, symbol_name)
        if key not in temp_symbol_metrics:
            temp_symbol_metrics[key] = {
                "file_path": norm_path,
                "symbol_name": symbol_name,
            }

        current_data = temp_symbol_metrics[key]
        for k, v in data_dict.items():
            if (
                k == "symbol_name_complexipy"
                and "symbol_name" in current_data
                and current_data["symbol_name"] != v
            ):
                current_data["symbol_name_complexipy_alt"] = v
            elif (
                k == "symbol_name"
                and "symbol_name_complexipy" in current_data
                and current_data["symbol_name_complexipy"] != v
            ):
                current_data["symbol_name_original_alt"] = v
            else:
                current_data[k] = v

    section_patterns = {
        "radon_raw_files": r"={10,}\nRadon - Raw Metrics \(Source Lines of Code, Comments etc\.\)\n={10,}\n(?:\[INFO\].*?\n)?(.*?)(?=\n\*\* Total \*\*|\n={10,}|$)",
        "radon_raw_total": r"(\*\* Total \*\*\n\s+LOC:.*?)(?:\n={10,}|$)",
        "radon_cc": r"={10,}\nRadon - Cyclomatic Complexity \(CC\)\n={10,}\n(?:\[INFO\].*?\n)?(.*?Average complexity:.*?)(?:\n={10,}|$)",
        "radon_mi": r"={10,}\nRadon - Maintainability Index \(MI\)\n={10,}\n(.*?)(?:\n={10,}|$)",
        "flake8": r"={10,}\nFlake8 - Count of Functions with Cyclomatic Complexity > \d+\n={10,}\n(.*?)(?:\n={10,}|$)",
        "complexipy": r"={10,}\nComplexipy - Cognitive Complexity\n={10,}\n(?:\[INFO\].*?\n){1,3}(.*?)(?:────────────────── 🎉 Analysis completed! 🎉 ──────────────────|\n={10,}|$)",
    }

    radon_raw_files_match = re.search(
        section_patterns["radon_raw_files"], content, re.DOTALL | re.IGNORECASE
    )
    if radon_raw_files_match:
        radon_raw_data_files = parse_radon_raw_section(radon_raw_files_match.group(1))
        for fm in radon_raw_data_files.get("files", []):
            update_file_metric(fm["file_path"], fm)

    radon_raw_total_match = re.search(
        section_patterns["radon_raw_total"], content, re.DOTALL | re.IGNORECASE
    )
    if radon_raw_total_match:
        radon_raw_data_total = parse_radon_raw_section(radon_raw_total_match.group(1))
        if radon_raw_data_total.get("totals"):
            parsed_data["overall_summary"].update(radon_raw_data_total["totals"])
    elif radon_raw_files_match and not parsed_data["overall_summary"].get(
        "total_sloc_radon"
    ):
        radon_raw_data_full_fallback = parse_radon_raw_section(
            radon_raw_files_match.group(1)
        )
        if radon_raw_data_full_fallback.get("totals"):
            parsed_data["overall_summary"].update(
                radon_raw_data_full_fallback["totals"]
            )

    radon_cc_match = re.search(section_patterns["radon_cc"], content, re.DOTALL)
    if radon_cc_match:
        radon_cc_data = parse_radon_cc_section(radon_cc_match.group(1))
        for sm in radon_cc_data.get("symbols", []):
            update_symbol_metric(sm["file_path"], sm["symbol_name"], sm)
        if radon_cc_data.get("average"):
            parsed_data["overall_summary"].update(radon_cc_data["average"])

    radon_mi_match = re.search(section_patterns["radon_mi"], content, re.DOTALL)
    if radon_mi_match:
        radon_mi_data = parse_radon_mi_section(radon_mi_match.group(1))
        for fm in radon_mi_data.get("files", []):
            update_file_metric(fm["file_path"], fm)

    flake8_match = re.search(section_patterns["flake8"], content, re.DOTALL)
    if flake8_match:
        parsed_data["overall_summary"].update(
            parse_flake8_section(flake8_match.group(1))
        )

    complexipy_match = re.search(
        section_patterns["complexipy"], content, re.DOTALL | re.IGNORECASE
    )
    if complexipy_match:
        complexipy_section_content = complexipy_match.group(1)
        complexipy_data = parse_complexipy_section(complexipy_section_content)
        for sm_complexipy in complexipy_data.get("symbols", []):
            path_for_merging = get_normalized_path(sm_complexipy["complexipy_path"])
            found_match = False
            key_to_check = (path_for_merging, sm_complexipy["symbol_name_complexipy"])
            if key_to_check in temp_symbol_metrics:
                update_symbol_metric(
                    path_for_merging,
                    sm_complexipy["symbol_name_complexipy"],
                    sm_complexipy,
                )
                found_match = True
            else:
                for (
                    existing_path,
                    existing_symbol,
                ), data in temp_symbol_metrics.items():
                    if (
                        os.path.basename(existing_path)
                        == sm_complexipy["file_name_complexipy"]
                        and existing_symbol == sm_complexipy["symbol_name_complexipy"]
                    ):
                        update_symbol_metric(
                            existing_path, existing_symbol, sm_complexipy
                        )
                        found_match = True
                        break
            if not found_match:
                update_symbol_metric(
                    path_for_merging,
                    sm_complexipy["symbol_name_complexipy"],
                    sm_complexipy,
                )

        if (
            "total_cognitive_complexity" in complexipy_data
            and complexipy_data["total_cognitive_complexity"] > 0
        ):
            parsed_data["overall_summary"]["total_cognitive_complexity"] = (
                complexipy_data["total_cognitive_complexity"]
            )
        elif "total_cognitive_complexity" not in parsed_data["overall_summary"]:
            overall_total_cg_match = COMPLEXIPY_TOTAL_RE.search(
                complexipy_section_content
            )
            if overall_total_cg_match:
                parsed_data["overall_summary"]["total_cognitive_complexity"] = int(
                    overall_total_cg_match.group(1)
                )

    # Sort file_level_metrics by mi_score in ascending order
    # Ensure 'mi_score' exists, provide a default (e.g., -1) for sorting if missing
    parsed_data["file_level_metrics"] = sorted(
        list(temp_file_metrics.values()),
        key=lambda x: x.get("mi_score", -1),
        reverse=False,
    )

    # Sort symbol_level_metrics by cc_score in descending order
    # Ensure 'cc_score' exists, provide a default (e.g., -1) for sorting if missing
    parsed_data["symbol_level_metrics"] = sorted(
        list(temp_symbol_metrics.values()),
        key=lambda x: x.get("cc_score", -1),
        reverse=True,
    )

    print("--- Parsed Data (List of Dicts) ---")
    print("\nOverall Summary:")
    print(json.dumps(parsed_data["overall_summary"], indent=2, ensure_ascii=False))
    print("\nFile Level Metrics (Sorted by MI Score Descending):")
    print(json.dumps(parsed_data["file_level_metrics"], indent=2, ensure_ascii=False))
    print("\nSymbol Level Metrics (Sorted by CC Score Descending):")
    print(json.dumps(parsed_data["symbol_level_metrics"], indent=2, ensure_ascii=False))

    if project_root_path and os.path.isdir(project_root_path):
        print("\n\n--- Project File Tree ---")
        tree_output = generate_file_tree(project_root_path)
        for line in tree_output:
            print(line)
    elif project_root_path:
        print(
            f"\nWarning: Project root path '{project_root_path}' is not a valid directory. Cannot generate tree."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse a code complexity analysis report."
    )
    parser.add_argument(
        "analysis_file", help="Path to the analysis.txt file to process."
    )
    args = parser.parse_args()

    if not os.path.exists(args.analysis_file):
        print(f"Error: The analysis file '{args.analysis_file}' was not found.")
    else:
        main(args.analysis_file)
