"""Run all generators end-to-end: ground truth → logos → Excel → PDF → emails."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import seed_data
import generate_logos
import generate_excel
import generate_pdf
import generate_emails


def main() -> None:
    print("\n=== [1/5] Writing ground-truth JSON (expected output) ===")
    seed_data.write_expected_outputs()

    print("\n=== [2/5] Generating broker logos ===")
    generate_logos.main()

    print("\n=== [3/5] Generating Excel SOVs (variants 1, 2, 3, 6) ===")
    generate_excel.main()

    print("\n=== [4/5] Generating PDF SOVs (variants 4, 5) ===")
    generate_pdf.main()

    print("\n=== [5/5] Generating broker submission emails ===")
    generate_emails.main()

    print("\nAll demo assets generated successfully.")


if __name__ == "__main__":
    main()
