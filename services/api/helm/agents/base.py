"""Every agent is a module with one interface: run(input) -> typed output.

Agents are pure with respect to money: only code (Policy Engine, Executor) can authorise a payment.
"""
from typing import Protocol, TypeVar

from pydantic import BaseModel

In = TypeVar("In", bound=BaseModel, contravariant=True)
Out = TypeVar("Out", bound=BaseModel, covariant=True)


class Agent(Protocol[In, Out]):
    name: str

    def run(self, input: In) -> Out: ...
