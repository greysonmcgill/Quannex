"""
Business Plan Builder Core

Main orchestrator for building business plans.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from business_plan_generator.models import BusinessPlan
from business_plan_generator.prompts import InteractivePrompter
from business_plan_generator.pdf_generator import PDFGenerator


class BusinessPlanBuilder:
    """
    Main class for building business plans.

    Supports:
    - Interactive prompting
    - Loading from JSON
    - PDF generation
    - Plan validation
    """

    def __init__(self):
        self.plan = BusinessPlan()
        self.output_dir = Path("./output")

    def build_interactive(self) -> BusinessPlan:
        """
        Build business plan through interactive prompts.

        Returns:
            Completed BusinessPlan object
        """
        prompter = InteractivePrompter()
        self.plan = prompter.build_plan()
        return self.plan

    def load_from_json(self, json_path: str) -> BusinessPlan:
        """
        Load business plan from JSON file.

        Args:
            json_path: Path to JSON file

        Returns:
            Loaded BusinessPlan object
        """
        with open(json_path, 'r') as f:
            data = json.load(f)

        # TODO: Deserialize to BusinessPlan
        # For now, return empty plan
        return self.plan

    def save_to_json(self, output_path: Optional[str] = None) -> str:
        """
        Save business plan to JSON file.

        Args:
            output_path: Optional output path

        Returns:
            Path to saved file
        """
        if not output_path:
            self.output_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            company_name = self.plan.company.name if self.plan.company else "plan"
            company_slug = company_name.lower().replace(" ", "_")
            output_path = self.output_dir / f"{company_slug}_{timestamp}.json"

        # Serialize plan
        data = self._serialize_plan()

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        return str(output_path)

    def generate_pdf(self, output_path: Optional[str] = None) -> str:
        """
        Generate PDF from current business plan.

        Args:
            output_path: Optional output path

        Returns:
            Path to generated PDF
        """
        if not output_path:
            self.output_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            company_name = self.plan.company.name if self.plan.company else "plan"
            company_slug = company_name.lower().replace(" ", "_")
            output_path = str(self.output_dir / f"{company_slug}_business_plan_{timestamp}.pdf")

        generator = PDFGenerator(self.plan)
        return generator.generate(output_path)

    def validate(self) -> Dict[str, Any]:
        """
        Validate business plan completeness and quality.

        Returns:
            Validation results dictionary
        """
        results = {
            "is_complete": self.plan.is_complete(),
            "sections": self.plan.get_completion_status(),
            "warnings": [],
            "errors": [],
        }

        # Check for common issues
        if self.plan.company:
            if not self.plan.company.founder_email:
                results["warnings"].append("Missing founder email")
            if not self.plan.company.tagline:
                results["warnings"].append("Missing company tagline")

        if self.plan.market:
            if self.plan.market.tam < self.plan.market.sam:
                results["errors"].append("TAM cannot be smaller than SAM")
            if self.plan.market.sam < self.plan.market.som:
                results["errors"].append("SAM cannot be smaller than SOM")

        if self.plan.financials and self.plan.financials.projections:
            # Check for realistic growth
            prev_revenue = None
            for proj in self.plan.financials.projections:
                if prev_revenue:
                    growth = float(proj.revenue) / float(prev_revenue) - 1
                    if growth > 10:  # 1000% growth
                        results["warnings"].append(
                            f"Year {proj.year} growth rate ({growth:.0%}) may be unrealistic"
                        )
                prev_revenue = proj.revenue

        return results

    def _serialize_plan(self) -> Dict:
        """Serialize plan to dictionary"""
        data = {
            "version": self.plan.version,
            "created_date": self.plan.created_date.isoformat(),
            "executive_summary": self.plan.executive_summary,
        }

        if self.plan.company:
            data["company"] = self.plan.company.to_dict()

        # Add other sections as needed
        # This is a simplified implementation

        return data


def main():
    """Main entry point for CLI"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Business Plan Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m business_plan_generator build          # Interactive build
  python -m business_plan_generator build --quick  # Quick mode
  python -m business_plan_generator pdf plan.json  # Generate PDF from JSON
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build a new business plan")
    build_parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Quick mode - skip optional sections"
    )
    build_parser.add_argument(
        "--output", "-o",
        help="Output directory"
    )

    # PDF command
    pdf_parser = subparsers.add_parser("pdf", help="Generate PDF from JSON")
    pdf_parser.add_argument("input", help="Input JSON file")
    pdf_parser.add_argument("--output", "-o", help="Output PDF path")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a business plan")
    validate_parser.add_argument("input", help="Input JSON file")

    args = parser.parse_args()

    if args.command == "build":
        builder = BusinessPlanBuilder()
        if args.output:
            builder.output_dir = Path(args.output)

        print("\n" + "=" * 60)
        print("  BUSINESS PLAN GENERATOR")
        print("=" * 60 + "\n")

        plan = builder.build_interactive()

        # Validate
        validation = builder.validate()
        print("\nValidation Results:")
        for section, complete in validation["sections"].items():
            icon = "✓" if complete else "○"
            print(f"  {icon} {section}")

        if validation["warnings"]:
            print("\nWarnings:")
            for warn in validation["warnings"]:
                print(f"  ⚠ {warn}")

        # Generate outputs
        print("\nGenerating outputs...")

        json_path = builder.save_to_json()
        print(f"  ✓ JSON saved: {json_path}")

        pdf_path = builder.generate_pdf()
        print(f"  ✓ PDF generated: {pdf_path}")

        print("\n" + "=" * 60)
        print("  BUSINESS PLAN COMPLETE")
        print("=" * 60 + "\n")

    elif args.command == "pdf":
        builder = BusinessPlanBuilder()
        builder.load_from_json(args.input)
        pdf_path = builder.generate_pdf(args.output)
        print(f"PDF generated: {pdf_path}")

    elif args.command == "validate":
        builder = BusinessPlanBuilder()
        builder.load_from_json(args.input)
        results = builder.validate()
        print(json.dumps(results, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
