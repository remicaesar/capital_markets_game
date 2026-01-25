"""
Input validation and helper functions
"""

from typing import Optional
from rich.console import Console

console = Console()


def get_int_input(prompt: str, min_val: int = 0, max_val: Optional[int] = None) -> int:
    """Get integer input with validation"""
    while True:
        try:
            value = int(input(prompt))
            if value < min_val:
                console.print(f"[red]Please enter a value ≥ {min_val}[/red]")
                continue
            if max_val is not None and value > max_val:
                console.print(f"[red]Please enter a value ≤ {max_val}[/red]")
                continue
            return value
        except ValueError:
            console.print("[red]Please enter a valid number[/red]")
        except KeyboardInterrupt:
            return 0


def get_company_input(market) -> str:
    """Get company name input with validation"""
    while True:
        name = input("Company name: ").strip()
        if name in market.companies:
            return name
        for n in market.companies:
            if n.lower() == name.lower():
                return n
        console.print(f"[red]'{name}' not found. Available companies:[/red]")
        for i, n in enumerate(sorted(market.companies)):
            console.print(f"  {n}", end="  ")
            if (i + 1) % 4 == 0:
                console.print()
        console.print() 