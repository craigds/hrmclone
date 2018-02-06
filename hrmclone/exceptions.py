
class ParseError(Exception):
    """
    Base of compile errors
    """


class NoSuchInstruction(ParseError):
    pass


class InvalidJumpTarget(ParseError):
    pass


class InvalidFloorIndex(ParseError):
    pass


class RunError(Exception):
    """
    Base of runtime errors.
    """


class EmptyInbox(RunError):
    """
    The inbox became empty during execution of an INBOX
    instruction.
    This can either mean the program is finished, or there was an error
    (if the level's goal state isn't reached yet.)
    """


class EmptyHands(RunError):
    pass


class EmptyFloorTile(RunError):
    pass


class Overflow(RunError):
    pass


class MathDomainError(RunError):
    pass
