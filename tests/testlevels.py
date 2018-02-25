"""
Runs actual solutions for the HRM levels as test cases against my
parser and runner, checking the outbox and inbox states.

I don't actually check the *goal* of the levels themselves here.
"""
import pytest

from hrmclone.core import Program
from hrmclone import exceptions


def test_invalid_instruction():
    with pytest.raises(exceptions.NoSuchInstruction):
        Program('FROGS')


def test_jump_parse_errors():
    with pytest.raises(exceptions.InvalidJumpTarget):
        Program('JUMP a')

    with pytest.raises(exceptions.InvalidJumpTarget):
        Program('''
            a:
            JUMP b
        ''')

    # ok
    Program('''
        a:
        JUMP a
    ''')


def test_empty_inbox_finishes_program():
    program = Program('INBOX')
    run = program.run(inbox='')
    assert run.runtime == 0
    assert run.inbox == []


def test_level_1_ok():
    program = Program('''
        -- HUMAN RESOURCE MACHINE PROGRAM --

        INBOX
        OUTBOX
        INBOX
        OUTBOX
        INBOX
        OUTBOX
    ''')

    run = program.run(inbox='ABCDEF')

    assert run.outbox == ['A', 'B', 'C']
    assert run.inbox == ['D', 'E', 'F']
    assert run.runtime == 6


def test_empty_hands_when_outboxing():
    program = Program('''
        INBOX
        OUTBOX
        OUTBOX
    ''')

    run = program.bind(inbox='AB')
    with pytest.raises(exceptions.EmptyHands):
        run.run()

    # Check it got through the first two instructions
    assert run.outbox == ['A']
    assert run.inbox == ['B']
    assert run.runtime == 2


def test_level_2_jump():
    program = Program('''
        -- HUMAN RESOURCE MACHINE PROGRAM --

        a:
            INBOX
            OUTBOX
            JUMP     a
    ''')
    run = program.bind(inbox='FAERIES')
    run.run()
    assert run.outbox == ['F', 'A', 'E', 'R', 'I', 'E', 'S']
    assert run.inbox == []
    assert run.runtime == 21


def test_jump_to_end():
    program = Program('''
        -- HUMAN RESOURCE MACHINE PROGRAM --
        JUMP     a
            INBOX
            OUTBOX
        a:
    ''')
    run = program.bind(inbox='DAWG')
    run.run()
    assert run.outbox == []
    assert run.inbox == ['D', 'A', 'W', 'G']
    assert run.runtime == 1
    assert run.program_pointer == 3


def test_level_3_copy_floor():
    program = Program('''
        COPYFROM 4
        OUTBOX
        COPYFROM 0
        OUTBOX
        COPYFROM 3
        OUTBOX
    ''')

    run = program.bind(floor={4: 'A', 0: 'B', 3: 'C'})
    assert run.floor == ['B', None, None, 'C', 'A'] + [None] * 15
    run.run()
    assert run.outbox == ['A', 'B', 'C']
    assert run.floor == ['B', None, None, 'C', 'A'] + [None] * 15
    assert run.runtime == 6
    assert run.program_pointer == 6


def test_copyto_errors():
    program = Program('COPYTO   0')
    with pytest.raises(exceptions.EmptyHands):
        program.run()

    with pytest.raises(exceptions.InvalidFloorIndex):
        program = Program('''
            INBOX
            COPYTO 999
        ''')


def test_level_4_scrambler_handler():
    program = Program('''
        a:
            INBOX
            COPYTO   0
            INBOX
            OUTBOX
            COPYFROM 0
            OUTBOX
            JUMP     a
    ''')
    run = program.run(inbox='badcfe')
    assert run.outbox == ['a', 'b', 'c', 'd', 'e', 'f']
    assert run.program_pointer == 0
    assert run.runtime == 21


def test_add():
    program = Program('ADD 1')
    with pytest.raises(exceptions.EmptyHands):
        program.run()

    program = Program('''
        COPYFROM 0
        ADD 1
    ''')

    # You can't ADD when either operand is a letter.
    assert program.run(floor={0: '1', 1: '3'}).hands == '4'
    assert program.run(floor={0: '5', 1: '-3'}).hands == '2'
    assert program.run(floor={0: '-3', 1: '5'}).hands == '2'
    assert program.run(floor={0: '-3', 1: '-5'}).hands == '-8'

    with pytest.raises(exceptions.MathDomainError):
        program.run(floor={0: 'A', 1: '3'})

    with pytest.raises(exceptions.MathDomainError):
        program.run(floor={0: '3', 1: 'A'})

    with pytest.raises(exceptions.EmptyFloorTile):
        program.run(floor={0: '0'})


def test_sub():
    program = Program('''
        COPYFROM 0
        SUB 1
    ''')

    # You can sub two letters, or two numbers (the result is always a number)
    # You can't sub a letter from a number, or vice versa.
    # Also, if you sub B from A you get an error (letters can't go negative)
    assert program.run(floor={0: '1', 1: '3'}).hands == '-2'
    assert program.run(floor={0: '1', 1: '-3'}).hands == '4'
    assert program.run(floor={0: '1', 1: '0'}).hands == '1'

    with pytest.raises(exceptions.MathDomainError):
        program.run(floor={0: 'A', 1: '1'})
        program.run(floor={0: '1', 1: 'A'})

    assert program.run(floor={0: 'B', 1: 'A'}).hands == '1'
    with pytest.raises(exceptions.Overflow):
        program.run(floor={0: 'A', 1: 'B'})


def test_level_6_add():
    program = Program('''
        -- HUMAN RESOURCE MACHINE PROGRAM --
        a:
            INBOX
            COPYTO   0
            INBOX
            ADD      0
            OUTBOX
            JUMP     a
    ''')

    run = program.run(inbox='121a5b3c')
    assert run.outbox == ['3', 'b', 'g', 'f']
    assert run.inbox == []
    assert run.floor[0] == '3'


def test_jump_if_zero_errors():
    program = Program('''
        JUMPZ a
        a:
    ''')
    with pytest.raises(exceptions.EmptyHands):
        program.run()


def test_level_7_jump_if_zero():
    program = Program('''
        a:
        b:
            INBOX
            JUMPZ    b
            OUTBOX
            JUMP     a
    ''')

    run = program.run(inbox='0abc08000A00')
    assert run.outbox == ['a', 'b', 'c', '8', 'A']


def test_level_11_sub_hallway():
    program = Program('''
        a:
        INBOX
        COPYTO   0
        INBOX
        COPYTO   1
        SUB      0
        OUTBOX
        COPYFROM 0
        SUB      1
        OUTBOX
        JUMP     a
    ''')
    run = program.run(inbox=['1', '2', '-4', '-4', '9', '-3', '5', '0'])
    assert run.outbox == ['1', '-1', '0', '0', '-12', '12', '-5', '5']
    assert run.floor[:2] == ['5', '0']


def test_level_14_maximization_room():
    program = Program('''
        JUMP     c
    a:
        COPYFROM 0
    b:
        OUTBOX
    c:
        INBOX
        COPYTO   0
        INBOX
        SUB      0
        JUMPN    a
        ADD      0
        JUMP     b
    ''')
    run = program.run(inbox=['1', '2', '-4', '-4', '9', '-3', '5', '0'])
    assert run.outbox == ['2', '-4', '9', '5']
    assert run.floor[0] == '5'


def test_comments():
    program = Program('''
        COMMENT 0
        DEFINE COMMENT 0
        aowiefj0
        baoiehwoinwef02fn+[]123n;
        DEFINE COMMENT 1
        OUTBOX
        INBOX
        OUTBOX;
    ''')
    assert program.comment_data == {
        0: 'aowiefj0baoiehwoinwef02fn+[]123n',
        1: 'OUTBOXINBOXOUTBOX',
    }

    run = program.run(inbox=['a'])
    assert run.runtime == 0
    assert run.inbox == ['a']


def test_labels():
    program = Program('''
        DEFINE LABEL 0
        aowiefj0
        baoiehwoinwef02fn+[]123n;
        DEFINE LABEL 1
        OUTBOX
        INBOX
        OUTBOX;
    ''')
    assert program.label_data == {
        0: 'aowiefj0baoiehwoinwef02fn+[]123n',
        1: 'OUTBOXINBOXOUTBOX',
    }

    run = program.run(inbox=['a'])
    assert run.runtime == 0
    assert run.inbox == ['a']


def test_level_19_countdown():
    program = Program('''
        a:
            INBOX
            COPYTO   0
            JUMP     c
        b:
            BUMPUP   0
        c:
        d:
            OUTBOX
            COPYFROM 0
            JUMPZ    a
            JUMPN    b
            BUMPDN   0
            JUMP     d
    ''')

    run = program.run(inbox=['8', '2', '0'])
    assert run.outbox == ['8', '7', '6', '5', '4', '3', '2', '1', '0', '2', '1', '0', '0']


def test_pointers():
    program = Program('COPYFROM [0]')
    assert program.run(floor={0: '8', 8: 'A'}).hands == 'A'

    with pytest.raises(exceptions.EmptyFloorTile):
        program.run()

    with pytest.raises(exceptions.EmptyFloorTile):
        program.run(floor={0: '1'})

    with pytest.raises(exceptions.MathDomainError):
        program.run(floor={0: 'A'})


def test_level_35_duplicate_removal():
    program = Program('''
            INBOX
            COPYTO   [14]
        a:
            COPYFROM [14]
            OUTBOX
            BUMPUP   14
        b:
            INBOX
            COPYTO   [14]
            COPYFROM 14
            COPYTO   13
        c:
            BUMPDN   13
            JUMPN    a
            COPYFROM [13]
            SUB      [14]
            JUMPZ    b
            JUMP     c
    ''')
    run = program.run(
        inbox=['A', 'B', 'C', 'B', 'B', 'A', 'D', 'E', 'D', 'A', 'A', 'C', 'Z', 'A'],
        floor={14: '0'},
    )
    assert run.outbox == ['A', 'B', 'C', 'D', 'E', 'Z']
