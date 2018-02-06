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
        INBOX
        ADD 1
    ''')
    assert program.run(inbox='1', floor={1: '3'}).hands == '4'
    assert program.run(inbox='5', floor={1: '3'}).hands == '8'
    assert program.run(inbox='A', floor={1: '3'}).hands == 'D'
    assert program.run(inbox='c', floor={1: '3'}).hands == 'f'

    with pytest.raises(exceptions.Overflow):
        # TODO: what's the max integer before overflow in HRM? Is it 9? 99?
        program.run(inbox='z', floor={1: '1'})

    with pytest.raises(exceptions.EmptyFloorTile):
        program.run(inbox='z')


def test_sub():
    program = Program('''
        INBOX
        SUB 1
    ''')
    assert program.run(inbox='1', floor={1: '3'}).hands == '-2'
    assert program.run(inbox='1', floor={1: '-3'}).hands == '4'
    assert program.run(inbox='1', floor={1: '0'}).hands == '1'
    with pytest.raises(exceptions.MathDomainError):
        assert program.run(inbox='1', floor={1: 'A'})


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
    todo?
