import re
import string
import sys

from . import exceptions


FLOOR_TILES = 20


def is_int(x):
    try:
        int(x)
        return True
    except ValueError:
        return False


class InstructionRegistry(type):
    """
    A nice little thingy that registers instructions automatically.
    """
    instructions = {}

    def __new__(meta, name, bases, classdict):
        klass = super().__new__(meta, name, bases, classdict)
        if not name.startswith('_'):
            command_text = name.lower().replace('_', ' ')
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

        instance = klass(*arguments)
        instance.text = line
        return instance

    def __str__(self):
        return self.text

    def parse_extra_lines(self, program, lines_iter):
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
        self.pointer = False
        if floor_index.startswith('['):
            self.pointer = True
            floor_index = floor_index[1:-1]

        self.floor_index = int(floor_index)

    def resolve_floor_index(self, program):
        if self.pointer:
            # Resolve the pointer!
            floor_index = program.floor[self.floor_index]
            if floor_index is None:
                # null pointer!
                raise exceptions.EmptyFloorTile

            # pointer values must be numeric
            try:
                floor_index = int(floor_index)
            except ValueError:
                raise exceptions.MathDomainError

            # and point to a valid floor tile
            if floor_index >= FLOOR_TILES or floor_index < 0:
                raise exceptions.InvalidFloorIndex

            # s'cool. cool cool cool.
            return floor_index
        else:
            return self.floor_index

    def validate(self, program):
        if self.floor_index >= FLOOR_TILES or self.floor_index < 0:
            raise exceptions.InvalidFloorIndex


class CopyFrom(_FloorInstruction):
    def execute(self, program):
        program.hands = None
        floor_index = self.resolve_floor_index(program)
        if not program.floor[floor_index]:
            raise exceptions.EmptyFloorTile
        program.hands = program.floor[floor_index]


class CopyTo(_FloorInstruction):
    def execute(self, program):
        if not program.hands:
            raise exceptions.EmptyHands
        floor_index = self.resolve_floor_index(program)
        program.floor[floor_index] = program.hands


class _MathInstruction(_FloorInstruction):
    def execute(self, program):
        if program.hands is None:
            raise exceptions.EmptyHands

        floor_index = self.resolve_floor_index(program)

        if not program.floor[floor_index]:
            raise exceptions.EmptyFloorTile

        operand = program.floor[floor_index]

        program.hands = self._do_math(program.hands, operand)


class Add(_MathInstruction):
    def _do_math(self, a, b):
        # You can't ADD when either operand is a letter
        try:
            a, b = int(a), int(b)
        except ValueError:
            raise exceptions.MathDomainError(
                f"Can't ADD '{a}' and '{b}'"
            )

        # try:
        #     int(a)
        # except ValueError:
        #     # 'A' + '1' == 'B'
        #     result = chr(ord(a) + b_int)
        #     if (
        #         (a in string.ascii_lowercase and result not in string.ascii_lowercase)
        #         or (a in string.ascii_uppercase and result not in string.ascii_uppercase)
        #     ):
        #         raise exceptions.Overflow

        #     return result
        # else:
        # '1' + '1' == '2'
        return str(a + b)


class Sub(Add):
    def _do_math(self, a, b):
        # You can SUB when a and b are *both* numbers, or *both* letters.
        if (is_int(a), is_int(b)) == (True, True):
            return str(int(a) - int(b))
        elif (is_int(a), is_int(b)) == (False, False):
            # Convert both to integers, sum them, and convert back to chars.

            if b.upper() < a.upper():
                # You can't get a negative letter, sorry
                raise exceptions.Overflow

            return chr(ord(a.upper()) - ord(b.upper()) + ord('A'))
        else:
            raise exceptions.MathDomainError(
                f"Can't SUB '{a}' and '{b}'"
            )


class _Noop(Instruction):
    def execute(self, program):
        # Do nothing.
        # Don't count this as an executed instruction
        program.runtime -= 1


class Comment(_Noop):
    def __init__(self, comment_key):
        # This is a key into program.comment_data,
        # But that dict will be empty until validate() time.
        self.comment_key = int(comment_key)

    def validate(self, program):
        if self.comment_key not in program.comment_data:
            raise exceptions.InvalidArgument


class _ExtraLines(_Noop):
    def _parse_extra_lines(self, program, lines_iter):
        line = ''
        data = ''
        while True:
            line = next(lines_iter)
            if not line:
                # EOF !?
                raise exceptions.ParseError(
                    "Reached EOF while processing DEFINE COMMENT. Should end with a ';'"
                )
            line = line.strip()
            data += line
            if line.endswith(';'):
                data = data[:-1]
                break
        return data


class Define_Comment(_ExtraLines):
    def __init__(self, comment_index):
        self.comment_index = int(comment_index)

    def parse_extra_lines(self, program, lines_iter):
        data = self._parse_extra_lines(program, lines_iter)
        program.comment_data[self.comment_index] = data


class Define_Label(_FloorInstruction, _ExtraLines):
    def parse_extra_lines(self, program, lines_iter):
        data = self._parse_extra_lines(program, lines_iter)
        program.label_data[self.floor_index] = data


class BumpUp(_FloorInstruction):
    amount = 1

    def execute(self, program):
        floor_index = self.resolve_floor_index(program)

        if not program.floor[floor_index]:
            raise exceptions.EmptyFloorTile
        try:
            val = int(program.floor[floor_index])
        except ValueError:
            raise exceptions.MathDomainError
        program.floor[floor_index] = str(val + self.amount)
        program.hands = program.floor[floor_index]


class BumpDn(BumpUp):
    amount = -1


class Program:
    """
    Represents a sequence of instructions which can be run, but has no associated state.
    """
    def _parse(self, text):
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
            instruction.parse_extra_lines(self, line_iterator)
            instructions.append(instruction)
        return instructions, jump_targets

    def __init__(self, text):
        self.comment_data = {}
        self.label_data = {}
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
            finally:
                print(
                    f"{instruction}:\n\tinbox={self.inbox}\n\tfloor={self.floor}\n\toutbox={self.outbox}",
                    file=sys.stderr
                )

            self.program_pointer += 1
            self.runtime += 1

        # Makes it easier for test assertions if this returns self.
        # (no other reason really)
        return self
