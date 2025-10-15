#!/usr/bin/env python3
"""
Coverage metrics analysis and reporting script.

This script analyzes test coverage and provides detailed metrics and recommendations
for improving test coverage in the MLServer FastAPI wrapper project.
"""

import json
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass


@dataclass
class CoverageMetrics:
    """Coverage metrics data structure."""
    total_statements: int
    covered_statements: int
    missing_statements: int
    coverage_percent: float
    branch_coverage: float
    file_coverage: Dict[str, Dict[str, Any]]


class CoverageAnalyzer:
    """Analyze and report on test coverage."""

    def __init__(self, coverage_json_path: str = "coverage.json"):
        """Initialize with coverage JSON file path."""
        self.coverage_json_path = Path(coverage_json_path)
        self.coverage_data = None
        self.metrics = None

    def load_coverage_data(self) -> bool:
        """Load coverage data from JSON file."""
        if not self.coverage_json_path.exists():
            print(f"❌ Coverage file not found: {self.coverage_json_path}")
            print("Run 'make test-coverage' or 'pytest --cov=mlserver --cov-report=json' first")
            return False

        try:
            with open(self.coverage_json_path, 'r') as f:
                self.coverage_data = json.load(f)
            return True
        except json.JSONDecodeError as e:
            print(f"❌ Error reading coverage JSON: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error loading coverage data: {e}")
            return False

    def analyze_coverage(self) -> CoverageMetrics:
        """Analyze coverage data and return metrics."""
        if not self.coverage_data:
            raise ValueError("Coverage data not loaded. Call load_coverage_data() first.")

        totals = self.coverage_data.get('totals', {})
        files = self.coverage_data.get('files', {})

        # Filter to only mlserver files (exclude tests, examples, etc.)
        mlserver_files = {
            path: data for path, data in files.items()
            if 'mlserver/' in path and not any(exclude in path for exclude in [
                '/tests/', '/test_', '__pycache__', '/examples/', '/docs/', '.pyc'
            ])
        }

        # Calculate metrics
        total_statements = totals.get('num_statements', 0)
        covered_statements = totals.get('covered_lines', 0)
        missing_statements = totals.get('missing_lines', 0)
        coverage_percent = totals.get('percent_covered', 0.0)

        # Branch coverage (if available)
        branch_coverage = totals.get('percent_covered_display', '0%')
        if isinstance(branch_coverage, str):
            branch_coverage = float(branch_coverage.rstrip('%'))
        else:
            branch_coverage = coverage_percent

        self.metrics = CoverageMetrics(
            total_statements=total_statements,
            covered_statements=covered_statements,
            missing_statements=missing_statements,
            coverage_percent=coverage_percent,
            branch_coverage=branch_coverage,
            file_coverage=mlserver_files
        )

        return self.metrics

    def print_summary(self):
        """Print coverage summary."""
        if not self.metrics:
            print("❌ No metrics available. Run analyze_coverage() first.")
            return

        print("\n" + "=" * 60)
        print("📊 TEST COVERAGE SUMMARY")
        print("=" * 60)

        # Overall coverage
        print(f"📈 Overall Coverage: {self.metrics.coverage_percent:.1f}%")
        print(f"📊 Branch Coverage: {self.metrics.branch_coverage:.1f}%")
        print(f"📝 Total Statements: {self.metrics.total_statements:,}")
        print(f"✅ Covered: {self.metrics.covered_statements:,}")
        print(f"❌ Missing: {self.metrics.missing_statements:,}")

        # Coverage status
        if self.metrics.coverage_percent >= 90:
            status = "🟢 EXCELLENT"
        elif self.metrics.coverage_percent >= 80:
            status = "🟡 GOOD"
        elif self.metrics.coverage_percent >= 70:
            status = "🟠 FAIR"
        else:
            status = "🔴 NEEDS IMPROVEMENT"

        print(f"📋 Status: {status}")

    def print_file_breakdown(self, show_all: bool = False, min_coverage: float = 0.0):
        """Print per-file coverage breakdown."""
        if not self.metrics or not self.metrics.file_coverage:
            print("❌ No file coverage data available.")
            return

        print("\n" + "=" * 60)
        print("📁 FILE COVERAGE BREAKDOWN")
        print("=" * 60)

        # Sort files by coverage percentage (lowest first)
        sorted_files = sorted(
            self.metrics.file_coverage.items(),
            key=lambda x: x[1].get('summary', {}).get('percent_covered', 0)
        )

        printed_files = 0
        for file_path, file_data in sorted_files:
            summary = file_data.get('summary', {})
            coverage = summary.get('percent_covered', 0.0)

            # Skip files above minimum coverage threshold unless showing all
            if not show_all and coverage > min_coverage:
                continue

            # Clean up file path for display
            display_path = file_path.replace('/Users/peter/Desktop/enmacc/fastapi-mlserver-wrapper/', '')

            # Coverage status emoji
            if coverage >= 90:
                emoji = "🟢"
            elif coverage >= 80:
                emoji = "🟡"
            elif coverage >= 70:
                emoji = "🟠"
            else:
                emoji = "🔴"

            statements = summary.get('num_statements', 0)
            missing = summary.get('missing_lines', 0)
            covered = statements - missing

            print(f"{emoji} {coverage:5.1f}% | {covered:3d}/{statements:3d} | {display_path}")
            printed_files += 1

        if printed_files == 0:
            print(f"✅ All files have coverage above {min_coverage:.1f}%")

    def identify_coverage_gaps(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Identify files with low coverage that need attention."""
        if not self.metrics:
            return []

        gaps = []
        for file_path, file_data in self.metrics.file_coverage.items():
            summary = file_data.get('summary', {})
            coverage = summary.get('percent_covered', 0.0)

            if coverage < 80:  # Below 80% coverage
                gaps.append((file_path, {
                    'coverage': coverage,
                    'statements': summary.get('num_statements', 0),
                    'missing': summary.get('missing_lines', 0),
                    'missing_line_numbers': file_data.get('missing_lines', [])
                }))

        # Sort by coverage percentage (worst first)
        gaps.sort(key=lambda x: x[1]['coverage'])
        return gaps

    def generate_recommendations(self) -> List[str]:
        """Generate recommendations for improving coverage."""
        if not self.metrics:
            return ["No metrics available for recommendations."]

        recommendations = []
        coverage = self.metrics.coverage_percent

        # Overall coverage recommendations
        if coverage < 50:
            recommendations.append("🚨 CRITICAL: Coverage is very low. Focus on basic unit tests for core functionality.")
        elif coverage < 70:
            recommendations.append("⚠️  Coverage needs significant improvement. Add tests for main code paths.")
        elif coverage < 80:
            recommendations.append("📈 Coverage is approaching good levels. Focus on edge cases and error conditions.")
        elif coverage < 90:
            recommendations.append("✅ Good coverage! Add tests for remaining untested lines and branches.")
        else:
            recommendations.append("🎯 Excellent coverage! Focus on maintaining quality and testing edge cases.")

        # Specific file recommendations
        gaps = self.identify_coverage_gaps()
        if gaps:
            recommendations.append("\n📋 Priority files to improve:")
            for file_path, gap_data in gaps[:5]:  # Top 5 worst files
                clean_path = file_path.split('/')[-1]  # Just filename
                recommendations.append(
                    f"   • {clean_path}: {gap_data['coverage']:.1f}% "
                    f"({gap_data['missing']} uncovered lines)"
                )

        # Module-specific recommendations
        module_recommendations = self._get_module_recommendations()
        if module_recommendations:
            recommendations.extend(module_recommendations)

        return recommendations

    def _get_module_recommendations(self) -> List[str]:
        """Get module-specific testing recommendations."""
        if not self.metrics:
            return []

        recommendations = []
        files = self.metrics.file_coverage

        # Check CLI module
        cli_files = [f for f in files.keys() if 'cli.py' in f]
        if cli_files:
            cli_coverage = files[cli_files[0]].get('summary', {}).get('percent_covered', 0)
            if cli_coverage < 60:
                recommendations.append("\n🔧 CLI Module: Add tests for command parsing and error handling")

        # Check container module
        container_files = [f for f in files.keys() if 'container.py' in f]
        if container_files:
            container_coverage = files[container_files[0]].get('summary', {}).get('percent_covered', 0)
            if container_coverage < 60:
                recommendations.append("🐳 Container Module: Add tests for Docker build process and file detection")

        # Check version module
        version_files = [f for f in files.keys() if 'version.py' in f]
        if version_files:
            version_coverage = files[version_files[0]].get('summary', {}).get('percent_covered', 0)
            if version_coverage < 60:
                recommendations.append("🏷️  Version Module: Add tests for git info extraction and version validation")

        return recommendations

    def export_metrics(self, output_path: str = "coverage_metrics.json"):
        """Export coverage metrics to JSON file."""
        if not self.metrics:
            print("❌ No metrics to export. Run analyze_coverage() first.")
            return False

        export_data = {
            'timestamp': Path().cwd().name,  # Using cwd as timestamp placeholder
            'overall_coverage': self.metrics.coverage_percent,
            'branch_coverage': self.metrics.branch_coverage,
            'total_statements': self.metrics.total_statements,
            'covered_statements': self.metrics.covered_statements,
            'missing_statements': self.metrics.missing_statements,
            'coverage_gaps': [
                {
                    'file': gap[0].split('/')[-1],
                    'coverage': gap[1]['coverage'],
                    'missing_lines': gap[1]['missing']
                }
                for gap in self.identify_coverage_gaps()
            ],
            'recommendations': self.generate_recommendations()
        }

        try:
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            print(f"✅ Coverage metrics exported to {output_path}")
            return True
        except Exception as e:
            print(f"❌ Error exporting metrics: {e}")
            return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Analyze test coverage metrics")
    parser.add_argument(
        '--coverage-file',
        default='coverage.json',
        help='Path to coverage.json file (default: coverage.json)'
    )
    parser.add_argument(
        '--show-all-files',
        action='store_true',
        help='Show coverage for all files, not just low coverage ones'
    )
    parser.add_argument(
        '--min-coverage',
        type=float,
        default=80.0,
        help='Minimum coverage threshold for file display (default: 80.0)'
    )
    parser.add_argument(
        '--export',
        metavar='FILE',
        help='Export metrics to JSON file'
    )
    parser.add_argument(
        '--check-threshold',
        type=float,
        metavar='PERCENT',
        help='Exit with error code if coverage below threshold'
    )

    args = parser.parse_args()

    # Initialize analyzer
    analyzer = CoverageAnalyzer(args.coverage_file)

    # Load and analyze coverage data
    if not analyzer.load_coverage_data():
        sys.exit(1)

    metrics = analyzer.analyze_coverage()

    # Print summary and breakdown
    analyzer.print_summary()
    analyzer.print_file_breakdown(
        show_all=args.show_all_files,
        min_coverage=args.min_coverage
    )

    # Print recommendations
    print("\n" + "=" * 60)
    print("💡 RECOMMENDATIONS")
    print("=" * 60)
    recommendations = analyzer.generate_recommendations()
    for rec in recommendations:
        print(rec)

    # Export metrics if requested
    if args.export:
        analyzer.export_metrics(args.export)

    # Check threshold and exit with appropriate code
    if args.check_threshold:
        if metrics.coverage_percent < args.check_threshold:
            print(f"\n❌ Coverage {metrics.coverage_percent:.1f}% is below threshold {args.check_threshold:.1f}%")
            sys.exit(1)
        else:
            print(f"\n✅ Coverage {metrics.coverage_percent:.1f}% meets threshold {args.check_threshold:.1f}%")

    print(f"\n📊 Coverage analysis complete!")


if __name__ == "__main__":
    main()