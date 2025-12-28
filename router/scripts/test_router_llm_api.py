#!/usr/bin/env python3
"""
Test script demonstrating router as OpenAI-compatible LLM API.

This script shows how to:
1. Use router as drop-in replacement for OpenAI API
2. Compare router-enhanced vs baseline LLM calls
3. A/B test routing effectiveness
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
import json
from typing import List, Dict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def test_drop_in_replacement():
    """
    Test 1: Router as drop-in replacement for OpenAI API.

    Shows that you can just change base_url to use the router.
    """
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("Test 1: Router as Drop-In Replacement", style="bold cyan")
    console.print("=" * 80 + "\n", style="bold cyan")

    # Setup clients
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key:
        console.print("[red]Error: DEEPSEEK_API_KEY not found in environment[/red]")
        return

    # Client 1: Direct DeepSeek API (baseline)
    baseline_client = OpenAI(
        api_key=deepseek_key,
        base_url="https://api.deepseek.com"
    )

    # Client 2: Router (just change base_url!)
    router_client = OpenAI(
        api_key=deepseek_key,
        base_url="http://localhost:8000"  # Point to router
    )

    # Test question
    question = "什么是糖尿病？"

    console.print(f"Question: [yellow]{question}[/yellow]\n")

    # Call baseline
    console.print("[cyan]Calling baseline DeepSeek API...[/cyan]")
    baseline_response = baseline_client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "user", "content": question}
        ],
        max_tokens=500
    )
    baseline_answer = baseline_response.choices[0].message.content
    console.print(f"\n[green]Baseline Answer:[/green]\n{baseline_answer[:300]}...\n")

    # Call router
    console.print("[cyan]Calling router API (same interface!)...[/cyan]")
    router_response = router_client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "user", "content": question}
        ],
        max_tokens=500
    )
    router_answer = router_response.choices[0].message.content

    # Show routing decision (custom field)
    if hasattr(router_response, 'x_routing_decision') and router_response.x_routing_decision:
        decision = router_response.x_routing_decision
        console.print(f"\n[magenta]Routing Decision:[/magenta]")
        console.print(f"  - Use Patterns: {decision['use_patterns']}")
        console.print(f"  - Confidence: {decision['rag_confidence']:.2f}")
        console.print(f"  - Weaknesses found: {len(decision['weakness_patterns'])}")

    console.print(f"\n[green]Router Answer:[/green]\n{router_answer[:300]}...\n")

    # Comparison
    console.print("[yellow]✓ Same interface, enhanced with routing![/yellow]\n")


def test_a_b_comparison():
    """
    Test 2: A/B comparison - Router vs Baseline on multiple questions.
    """
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("Test 2: A/B Comparison - Router vs Baseline", style="bold cyan")
    console.print("=" * 80 + "\n", style="bold cyan")

    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key:
        console.print("[red]Error: DEEPSEEK_API_KEY not found[/red]")
        return

    # Setup clients
    baseline_client = OpenAI(
        api_key=deepseek_key,
        base_url="https://api.deepseek.com"
    )

    router_client = OpenAI(
        api_key=deepseek_key,
        base_url="http://localhost:8000"
    )

    # Test questions
    test_questions = [
        "什么是糖尿病？",
        "高血压有哪些症状？",
        "如何预防心脏病？",
    ]

    results = []

    for i, question in enumerate(test_questions, 1):
        console.print(f"\n[cyan]Question {i}:[/cyan] {question}")

        # Baseline call
        baseline_resp = baseline_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": question}],
            max_tokens=300
        )

        # Router call
        router_resp = router_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": question}],
            max_tokens=300
        )

        # Extract routing info
        use_patterns = False
        weaknesses = 0
        if hasattr(router_resp, 'x_routing_decision') and router_resp.x_routing_decision:
            decision = router_resp.x_routing_decision
            use_patterns = decision['use_patterns']
            weaknesses = len(decision['weakness_patterns'])

        results.append({
            "question": question,
            "baseline_tokens": baseline_resp.usage.total_tokens,
            "router_tokens": router_resp.usage.total_tokens,
            "use_patterns": use_patterns,
            "weaknesses": weaknesses,
            "baseline_answer": baseline_resp.choices[0].message.content[:100],
            "router_answer": router_resp.choices[0].message.content[:100]
        })

    # Show results table
    table = Table(title="A/B Comparison Results")
    table.add_column("Question", style="cyan")
    table.add_column("Patterns", justify="center")
    table.add_column("Weaknesses", justify="center")
    table.add_column("Baseline Tokens", justify="right")
    table.add_column("Router Tokens", justify="right")

    for r in results:
        table.add_row(
            r['question'][:30] + "...",
            "✓" if r['use_patterns'] else "✗",
            str(r['weaknesses']),
            str(r['baseline_tokens']),
            str(r['router_tokens'])
        )

    console.print("\n")
    console.print(table)
    console.print("\n[yellow]Router adds routing intelligence while maintaining API compatibility![/yellow]\n")


def test_router_specific_features():
    """
    Test 3: Router-specific features (x_ parameters).
    """
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("Test 3: Router-Specific Features", style="bold cyan")
    console.print("=" * 80 + "\n", style="bold cyan")

    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key:
        console.print("[red]Error: DEEPSEEK_API_KEY not found[/red]")
        return

    router_client = OpenAI(
        api_key=deepseek_key,
        base_url="http://localhost:8000"
    )

    question = "什么是糖尿病？"

    # Test 3a: Entity type hint
    console.print("\n[cyan]Test 3a: Using entity type hint (x_entity_type)[/cyan]")
    response = router_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": question}],
        extra_body={"x_entity_type": "diseases"},  # Hint for better routing
        max_tokens=300
    )
    console.print(f"Answer (first 150 chars): {response.choices[0].message.content[:150]}...")

    # Test 3b: Disable routing
    console.print("\n[cyan]Test 3b: Disabling routing (x_disable_routing)[/cyan]")
    response = router_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": question}],
        extra_body={"x_disable_routing": True},  # Skip routing, direct LLM call
        max_tokens=300
    )
    console.print(f"Answer (first 150 chars): {response.choices[0].message.content[:150]}...")

    # Test 3c: Disable weaknesses only
    console.print("\n[cyan]Test 3c: Disabling weakness patterns only (x_disable_weaknesses)[/cyan]")
    response = router_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": question}],
        extra_body={"x_disable_weaknesses": True},  # Keep routing, skip weaknesses
        max_tokens=300
    )
    console.print(f"Answer (first 150 chars): {response.choices[0].message.content[:150]}...")

    console.print("\n[yellow]✓ Router provides flexible controls via x_ parameters![/yellow]\n")


def test_streaming():
    """
    Test 4: Streaming support.
    """
    console.print("\n" + "=" * 80, style="bold cyan")
    console.print("Test 4: Streaming Support", style="bold cyan")
    console.print("=" * 80 + "\n", style="bold cyan")

    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key:
        console.print("[red]Error: DEEPSEEK_API_KEY not found[/red]")
        return

    router_client = OpenAI(
        api_key=deepseek_key,
        base_url="http://localhost:8000"
    )

    question = "什么是糖尿病？"

    console.print(f"[cyan]Question:[/cyan] {question}")
    console.print("\n[cyan]Streaming response:[/cyan]\n")

    stream = router_client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": question}],
        stream=True,
        max_tokens=200
    )

    full_response = ""
    for chunk in stream:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            full_response += content
            console.print(content, end="", style="green")

    console.print("\n\n[yellow]✓ Streaming works with router![/yellow]\n")


def main():
    """Run all tests"""
    console.print("\n[bold magenta]Smart Router LLM API Tests[/bold magenta]")
    console.print("[dim]Testing router as OpenAI-compatible drop-in replacement[/dim]\n")

    try:
        # Check if router is running
        import requests
        try:
            health = requests.get("http://localhost:8000/api/v1/health", timeout=2)
            if health.status_code != 200:
                console.print("[red]Error: Router is not healthy. Please start it first:[/red]")
                console.print("[yellow]  python scripts/serve_router.py[/yellow]\n")
                return
        except:
            console.print("[red]Error: Router is not running. Please start it first:[/red]")
            console.print("[yellow]  python scripts/serve_router.py[/yellow]\n")
            return

        # Run tests
        test_drop_in_replacement()
        test_a_b_comparison()
        test_router_specific_features()
        test_streaming()

        # Summary
        console.print("\n" + "=" * 80, style="bold green")
        console.print("All Tests Completed!", style="bold green")
        console.print("=" * 80, style="bold green")
        console.print("""
Key Takeaways:
1. ✓ Router is a drop-in replacement (just change base_url)
2. ✓ Same OpenAI SDK interface
3. ✓ Adds intelligent routing + weakness patterns
4. ✓ Supports streaming
5. ✓ Router-specific features via x_ parameters
6. ✓ Easy to A/B test router vs baseline

Usage in your code:
  # Before: Direct LLM
  client = OpenAI(api_key=key, base_url="https://api.deepseek.com")

  # After: With router
  client = OpenAI(api_key=key, base_url="http://localhost:8000")

  # That's it! Same code, smarter routing.
""", style="dim")

    except Exception as e:
        console.print(f"\n[red]Error during testing: {e}[/red]")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
