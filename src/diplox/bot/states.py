"""Bot FSM states."""

from aiogram.fsm.state import State, StatesGroup


class AskCommandState(StatesGroup):
    waiting_for_input = State()


class DoCommandState(StatesGroup):
    waiting_for_input = State()
    waiting_for_followup = State()


# ── Tool states ──────────────────────────────────────────────

class OutlineState(StatesGroup):
    waiting_for_topic = State()


class GrammarState(StatesGroup):
    waiting_for_text = State()


class RewriteState(StatesGroup):
    waiting_for_text = State()


class SummarizeState(StatesGroup):
    waiting_for_text = State()


class SourcesState(StatesGroup):
    waiting_for_topic = State()


class ChatState(StatesGroup):
    chatting = State()
