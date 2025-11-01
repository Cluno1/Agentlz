import typer

from ..agents.simple_agent import ask


app = typer.Typer(help="Simple LangChain agent demo CLI")


@app.command()
def query(message: str):
    """Send a prompt to the agent and print the response."""
    response = ask(message)
    print(response)


if __name__ == "__main__":
    app()