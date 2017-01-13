from time import time

STATES = [
    'created',
    'waiting',
    'processing',
    'success',          # end state
    'failed',           # end state
    'cancelled'         # end state
]


# public functions
def index_to_state(index):
    return STATES[index]


def end_states():
    return [
        state_to_index('success'),
        state_to_index('failed'),
        state_to_index('cancelled')
    ]


def state_to_index(state):
    for i, s in enumerate(STATES):
        if s == state:
            return i
    raise Exception('Invalid state: %s' % str(state))


def is_state(index, compare_state):
    compare_index = state_to_index(compare_state)
    return index == compare_index


def transition(state, description, exception, caused_by):
    return {
        'timestamp': time(),
        'state': state_to_index(state),
        'description': description,
        'exception': exception,  # optional
        'caused_by': caused_by  # optional
    }





