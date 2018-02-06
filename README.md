# Human Resource Machine clone

Ref: [Human Resource Machine on Steam](http://store.steampowered.com/app/375820/Human_Resource_Machine/)

This is a work in development. It's more of a random out-of-interest project,
and less of an actual game or anything useful at this stage.

Right now all it does is execute your saved games from HRM:

```python
    >>> program = Program('''
        a:
            INBOX
            COPYTO   0
            INBOX
            OUTBOX
            COPYFROM 0
            OUTBOX
            JUMP     a
    ''')
    >>> run = program.run(inbox='badcfe')
    
    >>> print(run.outbox)
    ['a', 'b', 'c', 'd', 'e', 'f']
    
    >>> print(run.runtime)
    21
```

And that's it. No output, no nothing. It might do more in future. Or it might not.

I actually vaguely intend to make it into a real clone of the game, but this is where I started.