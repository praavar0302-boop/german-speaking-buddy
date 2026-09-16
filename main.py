import os

from dotenv import load_dotenv

from rich.console import Console
from rich.prompt import Prompt

from providers import (
    stream_gemini_response,
    stream_openrouter_response
)


load_dotenv()

console = Console()

console.print()
console.print(
    "[bold cyan]German Speaking Buddy[/bold cyan]"
)
console.print()


selected_provider = Prompt.ask(
    "Select AI provider",
    choices=["gemini", "openrouter"]
)


if selected_provider == "gemini":
    api_key = os.getenv("GEMINI_API_KEY")

else:
    api_key = os.getenv("OPENROUTER_API_KEY")


if not api_key:
    console.print(
        "[bold red]API key was not found in .env[/bold red]"
    )

    raise ValueError(
        "Add the selected provider's API key to .env"
    )


selected_level = Prompt.ask(
    "Select your German level",
    choices=["A1", "A2"]
)


selected_mode = Prompt.ask(
    "Select conversation mode",
    choices=["roleplay", "free flow"]
)


with open(
    "prompts/system.md",
    encoding="utf-8"
) as file:
    base_system_prompt = file.read()


system_prompt = (
    base_system_prompt
    + "\n\n"
    + "Learner level: "
    + selected_level
    + "\n"
    + "Conversation mode: "
    + selected_mode
    + "\n"
    + "The selected level is the maximum difficulty. "
    + "Never use grammar or vocabulary above "
    + selected_level
    + "."
)


conversation_history = []


console.print()
console.print(
    "[green]Conversation started.[/green]"
)
console.print(
    "Type [bold]exit[/bold] to end the conversation."
)
console.print()


while True:

    user_message = Prompt.ask("[bold]User[/bold]")

    if user_message.lower() == "exit":
        console.print()
        console.print("[cyan]Conversation ended.[/cyan]")
        break

    conversation_history.append(
        {
            "role": "user",
            "content": user_message
        }
    )

    try:

        if selected_provider == "gemini":

            assistant_reply = stream_gemini_response(
                api_key,
                system_prompt,
                conversation_history
            )

        else:

            assistant_reply = stream_openrouter_response(
                api_key,
                system_prompt,
                conversation_history
            )

    except RuntimeError as error:

        console.print(
            "[bold red]Request failed:[/bold red]",
            error
        )

        conversation_history.pop()

        continue


    conversation_history.append(
        {
            "role": "assistant",
            "content": assistant_reply
        }
    )