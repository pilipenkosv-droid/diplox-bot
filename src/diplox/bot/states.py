"""Bot FSM states."""

from aiogram.fsm.state import State, StatesGroup


class AskCommandState(StatesGroup):
    waiting_for_input = State()


class DoCommandState(StatesGroup):
    waiting_for_input = State()
    waiting_for_followup = State()
