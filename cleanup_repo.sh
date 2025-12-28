#!/bin/bash
# Repository cleanup script - Remove temporary files before git commit

echo "🧹 Cleaning up repository..."

# Remove Python cache
echo "  Removing __pycache__ directories..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true

# Remove macOS files
echo "  Removing .DS_Store files..."
find . -name ".DS_Store" -delete 2>/dev/null || true

# Remove log files (except in outputs/logs/)
echo "  Removing temporary log files..."
find . -maxdepth 1 -name "*.log" -delete 2>/dev/null || true
rm -f debug_retrieval.log optimizer_test_run.log 2>/dev/null || true
rm -f router_test_with_category_fix.log optimizer_test_with_categories.log 2>/dev/null || true
rm -f expansion_evaluation.log pattern_analysis_results.log 2>/dev/null || true
rm -f ood_test_output.log ood_test_output_v2.log 2>/dev/null || true

# Remove temporary test outputs (keep cache and final reports)
echo "  Cleaning outputs directory..."
# Remove specific evaluation run directories (keep latest)
find outputs/reports -type d -name "eval_202*" | sort -r | tail -n +2 | xargs rm -rf 2>/dev/null || true

# Remove old comparison outputs
rm -rf outputs/comparisons 2>/dev/null || true

# Remove temporary JSON outputs in root of outputs/
rm -f outputs/ood_test_results.json 2>/dev/null || true

# Clean up Claude cache (optional - uncomment if needed)
# rm -rf .claude/plans/* 2>/dev/null || true

# Remove duplicate debug scripts
echo "  Removing temporary debug scripts..."
rm -f debug_pattern_retrieval.py 2>/dev/null || true
rm -f recategorize_patterns.py 2>/dev/null || true
rm -f test_router_ood.py 2>/dev/null || true

echo "✅ Cleanup complete!"
echo ""
echo "📊 Repository status:"
du -sh . 2>/dev/null | awk '{print "  Total size: " $1}'
echo "  Files to commit:"
git status --short 2>/dev/null | wc -l | awk '{print "    " $1 " files changed/untracked"}'
echo ""
echo "Ready for git commit! 🚀"
