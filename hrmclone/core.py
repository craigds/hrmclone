import re
import string

from . import exceptions


FLOOR_TILES = 20


class InstructionRegistry(type):
    """
    A nice little thingy that registers instructions automatically.
    """
    instructions = {}

    def __new__(meta, name, bases, classdict):
        klass = super().__new__(meta, name, bases, classdict)
        if not name.startswith('_'):
            command_text = name.lower()
            meta.instructions[command_text] = klass
        return klass


class Instruction(object, metaclass=InstructionRegistry):
    @staticmethod
    def get(line):
        """
        Given a line from the program, retrieves the correct Instruction subclass,
        then instantiates it with the right arguments.
        """
        # AFAICT the tokenization is simple - no quoted strings!
        # so we can just split on whitespace.
        command, *arguments = line.strip().split()
        command = command.lower()
        if command == 'define':
            command += ' %s' % arguments.pop(0).lower()

        try:
            klass = InstructionRegistry.instructions[command]
        except KeyError:
            raise exceptions.NoSuchInstruction(command.upper())

        return klass(*arguments)

    def parse_extra_lines(self, lines_iter):
        """
        For most instructions this does nothing.

        Some special instructions use this to consume extra lines from the program.
        """
        pass

    def validate(self, program):
        """
        Allows the instruction to check itself against the program.

        This is called after parsing is finished and before the program is
        bound to any state or executed.
        """

    def execute(self, program):
        raise NotImplementedError


class Inbox(Instruction):
    def execute(self, program):
        try:
            item = program.inbox.pop(0)
        except IndexError:
            raise exceptions.EmptyInbox
        program.hands = item


class Outbox(Instruction):
    def execute(self, program):
        if not program.hands:
            raise exceptions.EmptyHands
        program.outbox.append(program.hands)
        program.hands = None


class Jump(Instruction):
    def __init__(self, jump_target):
        self.jump_target = jump_target

    def validate(self, program):
        if self.jump_target not in program.jump_targets:
            raise exceptions.InvalidJumpTarget(self.jump_target)

    def execute(self, program):
        target = program.program.jump_targets[self.jump_target]

        # The program itself is about to increment the program pointer.
        # So change it to the instruction *before* the one we want
        program.program_pointer = target - 1


class JumpZ(Jump):
    def execute(self, program):
        if not program.hands:
            raise exceptions.EmptyHands
        if program.hands == '0':
            super().execute(program)


class JumpN(Jump):
    def execute(self, program):
        if not program.hands:
            raise exceptions.EmptyHands
        try:
            val = int(program.hands)
        except ValueError:
            # 'A' < 0? Ignore.
            pass
        else:
            if val < 0:
                super().execute(program)


class _FloorInstruction(Instruction):
    def __init__(self, floor_index):
        self.floor_index = int(floor_index)

    def validate(self, program):
        if self.floor_index >= FLOOR_TILES or self.floor_index < 0:
            raise exceptions.InvalidFloorIndex


class CopyFrom(_FloorInstruction):
    def execute(self, program):
        program.hands = None
        if not program.floor[self.floor_index]:
            raise exceptions.EmptyFloorTile
        program.hands = program.floor[self.floor_index]


class CopyTo(_FloorInstruction):
    def execute(self, program):
        if not program.hands:
            raise exceptions.EmptyHands
        program.floor[self.floor_index] = program.hands


class Add(_FloorInstruction):
    def _add(self, a, b_int):
        try:
            int(a)
        except ValueError:
            # 'A' + '1' == 'B'
            result = chr(ord(a) + b_int)
            if (
                (a in string.ascii_lowercase and result not in string.ascii_lowercase)
                or (a in string.ascii_uppercase and result not in string.ascii_uppercase)
            ):
                raise exceptions.Overflow

            return result
        else:
            # '1' + '1' == '2'
            return str(
                int(a) + b_int
            )

    def execute(self, program):
        if program.hands is None:
            raise exceptions.EmptyHands

        if not program.floor[self.floor_index]:
            raise exceptions.EmptyFloorTile

        operand = program.floor[self.floor_index]

        try:
            int(operand)
        except ValueError:
            raise exceptions.MathDomainError("Can't add '%s' and '%s'" % (program.hands, operand))

        program.hands = self._add(program.hands, int(operand))


class Sub(Add):
    def _add(self, a, b_int):
        return super()._add(a, -b_int)


class Program:
    """
    Represents a sequence of instructions which can be run, but has no associated state.
    """
    @classmethod
    def _parse(cls, text):
        line_iterator = iter(text.split('\n'))
        instructions = []
        jump_targets = {}
        for line in line_iterator:
            line = line.strip()
            if (not line) or line.startswith('--'):
                # empty or an actual comment, can discard.
                # there's one of these comments in the header of each program.
                continue

            match = re.match(r'([a-z]):$', line)
            if match:
                # This is a label for a jump target, not an instruction.
                jump_targets[match.group(1)] = len(instructions)
                continue

            instruction = Instruction.get(line)

            # For complex instructions ('DEFINE COMMENT') extra lines might be
            # required. Give the instruction parser access to the instruction stream
            # so it can fetch more lines if necessary.
            instruction.parse_extra_lines(line_iterator)
            instructions.append(instruction)
        return instructions, jump_targets

    def __init__(self, text):
        self.instructions, self.jump_targets = self._parse(text)
        for instruction in self.instructions:
            instruction.validate(self)

    def bind(self, *, inbox='', floor=None):
        """
        Binds this program to a particular state, ready to run.

        Returns a ProgramRun instance.
        """
        return ProgramRun(self, inbox=inbox, floor=floor)

    def run(self, *, inbox='', floor=None):
        """
        This is a shortcut for bind().run().

        This one looks nicer in tests, but self.bind() gives access to the ProgramRun object
        in case an exception happens later while running.
        """
        return self.bind(inbox=inbox, floor=floor).run()


class ProgramRun:
    """
    A particular instance of a program run, complete with state.
    """
    def __init__(self, program, *, inbox='', floor=None):
        self.program = program

        # Variables and stuff
        self.inbox = list(inbox)
        self.hands = None
        self.outbox = []

        if floor is None:
            self.floor = [None] * 20
        elif isinstance(floor, dict):
            self.floor = [None] * 20
            for i, v in floor.items():
                self.floor[i] = v
        else:
            self.floor = floor[:]

        # Where the current program is up to (int from 0 to len(program))
        self.program_pointer = 0

        # How many total instructions we've executed
        self.runtime = None

    def run(self):
        self.runtime = 0

        while True:
            # TODO: detect infinite loop for never-ending non-interactive programs.
            # maybe by just stopping if we reach runtime=100000 or something

            try:
                instruction = self.program.instructions[self.program_pointer]
            except IndexError:
                # program finished!
                break

            try:
                instruction.execute(self)
            except exceptions.EmptyInbox:
                # TODO: evaluate goal state here.
                # for now assume end of program.
                break

            self.program_pointer += 1
            self.runtime += 1

        # Makes it easier for test assertions if this returns self.
        # (no other reason really)
        return self
