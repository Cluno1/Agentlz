import typer

from ..agents.markdown_agent import ask


app = typer.Typer(help="Markdown conversion agent CLI")


@app.command()
def query(message: str):
    """Send input (URL, file path, or query) to the agent and print Markdown."""
    response = ask(message)
    print(response)


if __name__ == "__main__":
    app()