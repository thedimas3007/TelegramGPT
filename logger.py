from rich.console import Console
from datetime import datetime


def get_date() -> str:
    return datetime.now().strftime('%d.%m.%Y %H:%M:%S')


class Logger:
    console: Console

    def __init__(self, console=Console(highlight=False)) -> None:
        self.console = console

    def debug(self, msg: str) -> None:
        self.console.print(f"[dim bold][{get_date()}][/] [cyan bold][-][/] {msg}")

    def info(self, msg: str) -> None:
        self.console.print(f"[dim bold][{get_date()}][/] [blue bold][*][/] {msg}")

    def success(self, msg: str) -> None:
        self.console.print(f"[dim bold][{get_date()}][/] [green bold][✔][/] {msg}")

    def warn(self, msg: str) -> None:
        self.console.print(f"[dim bold][{get_date()}][/] [yellow bold][!][/] {msg}")

    def error(self, msg: str) -> None:
        self.console.print(f"[dim bold][{get_date()}][/] [red bold][✘][/] {msg}")

    def fatal(self, msg: str) -> None:
        self.console.print(f"[dim bold][{get_date()}][/] [on red bold][✘][/] {msg}")

    def input(self, msg="") -> str:
        return self.console.input(f"[purple bold][→][/] {msg} > ")
