_input_connector_schema = {
    'type': 'object',
    'properties': {
        'connector_type': {'type': 'string'},
        'connector_access': {'type': 'object'}
    },
    'required': ['connector_type', 'connector_access'],
    'additionalProperties': False
}

_result_connector_schema = {
    'type': 'object',
    'properties': {
        'local_result_file': {'type': 'string'},
        'connector_type': {'type': 'string'},
        'connector_access': {'type': 'object'},
        'add_meta_data': {'type': 'boolean'}
    },
    'required': ['connector_type', 'connector_access'],
    'additionalProperties': False
}

_tracing_connector_schema = {
    'type': 'object',
    'properties': {
        'connector_type': {'type': 'string'},
        'connector_access': {'type': 'object'},
        'add_meta_data': {'type': 'boolean'}
    },
    'required': ['connector_type', 'connector_access'],
    'additionalProperties': False
}

_notification_connector_schema = {
    'type': 'object',
    'properties': {
        'connector_type': {'type': 'string'},
        'connector_access': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string'},
                'method': {'enum': ['PUT', 'POST', 'put', 'post', 'Put', 'Post']},
                'json_data': {'type': 'object'},
                'ssl_verify': {'type': 'boolean'},
                'auth': {
                    'type': 'object',
                    'properties': {
                        'auth_type': {'enum': ['basic', 'digest']},
                        'username': {'type': 'string'},
                        'password': {'type': 'string'}
                    },
                    'required': ['auth_type', 'username', 'password'],
                    'additionalProperties': False
                }
            },
            'required': ['url', 'method'],
            'additionalProperties': False
        }
    },
    'required': ['connector_access'],
    'additionalProperties': False
}

_tracing_schema = {
    'type': 'object',
    'properties': {
        'enabled': {
            'type': 'boolean'
        },
        'file_access': {
            'enum': ['none', 'short', 'full']
        },
        'syscall': {
            'enum': ['none', 'short', 'full']
        },
        'tracing_file': _tracing_connector_schema
    },
    'required': ['enabled'],
    'additionalProperties': False
}

_syscall_filter_condition_one_parameter_schema = {
    'type': 'object',
    'properties': {
        'argument': {'type': 'integer', 'minimum': 0, 'maximum': 6},
        'operator': {'enum': ['==', '!=', '<=', '<', '>=', '>']},
        'datum_a': {'type': 'integer'}
    },
    'required': ['argument', 'operator', 'datum_a']
}

_syscall_filter_condition_two_parameter_schema = {
    'type': 'object',
    'properties': {
        'argument': {'type': 'integer', 'minimum': 0, 'maximum': 6},
        'operator': {'enum': ['&=']},
        'datum_a': {'type': 'integer'},
        'datum_b': {'type': 'integer'}
    },
    'required': ['argument', 'operator', 'datum_a', 'datum_b']
}

_syscall_seccomp_filter_schema = {
    'type': 'object',
    'properties': {
        'syscall': {'type': ['string', 'integer']},
        'conditions': {
            'type': 'array',
            'minItems': 0,
            'maxItems': 6,
            'items': {
                'anyOf': [
                    _syscall_filter_condition_one_parameter_schema,
                    _syscall_filter_condition_two_parameter_schema
                ]
            },
        },
    },
    'required': ['syscall'],
    'additionalProperties': False
}

_sandbox_limits_schema = {
    'type': 'object',
    'properties': {
        'cpu_usage': {'type': 'number', 'minimum': 0, 'maximum': 1},
        'create_file_size': {'type': 'integer', 'minimum': 0},
        'num_open_files': {'type': 'integer', 'minimum': 0},
        'heap_size': {'type': 'integer', 'minimum': 0},
        'stack_size': {'type': 'integer', 'minimum': 0},
        'rss_size': {'type': 'integer', 'minimum': 0},
        'child_processes': {'type': 'integer', 'minimum': 0}
    },
    'additionalProperties': False
}

_sandbox_seccomp_schema = {
    'type': 'object',
    'properties': {
        'mode': {
            'enum': ['disabled', 'whitelist', 'blacklist']
        },
        'filter_items': {
            'type': 'array',
            'items': _syscall_seccomp_filter_schema
        }
    },
    'required': ['mode'],
    'additionalProperties': False
}

_sandbox_schema = {
    'type': 'object',
    'properties': {
        'limits': _sandbox_limits_schema,
        'seccomp': _sandbox_seccomp_schema
    },
    'additionalProperties': False
}

_task_schema = {
    'type': 'object',
    'properties': {
        'tags': {
            'type': 'array',
            'items': {'type': 'string'}
        },
        'no_cache': {'type': 'boolean'},
        'application_container_description': {
            'type': 'object',
            'properties': {
                'image': {'type': 'string'},
                'entry_point': {'type': 'string'},
                'registry_auth': {
                    'type': 'object',
                    'properties': {
                        'username': {'type': 'string'},
                        'password': {'type': 'string'}
                    },
                    'required': ['username', 'password'],
                    'additionalProperties': False
                },
                'container_ram': {'type': 'number'},
                'tracing': _tracing_schema,
                'sandbox': _sandbox_schema,
                'parameters': {
                    'anyOf': [
                        {'type': 'object'},
                        {'type': 'array'}
                    ]
                }
            },
            'required': ['image', 'container_ram'],
            'additionalProperties': False
        },
        'input_files': {
            'type': 'array',
            'items': _input_connector_schema
        },
        'result_files': {
            'type': 'array',
            'items': {
                'anyOf': [
                    _result_connector_schema,
                    {'type': 'null'}
                ]
            }
        },
        'notifications': {
            'type': 'array',
            'items': _notification_connector_schema
        }
    },
    'required': [
        'application_container_description',
        'input_files',
        'result_files'
    ],
    'additionalProperties': False
}

_tasks_schema = {
    'type': 'object',
    'properties': {
        'tasks': {
            'type': 'array',
            'items': _task_schema
        }
    },
    'required': ['tasks'],
    'additionalProperties': False
}

tasks_schema = {
    'anyOf': [
        _task_schema,
        _tasks_schema
    ]
}

cancel_schema = {
    'type': 'object',
    'oneOf': [{
        'type': 'object',
        'properties': {
            '_id': {'type': 'string'}
        },
        'required': ['_id'],
        'additionalProperties': False
    }, {
        'type': 'object',
        'properties': {
            'tasks': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        '_id': {'type': 'string'}
                    },
                    'required': ['_id'],
                    'additionalProperties': False
                }
            }
        },
        'required': ['tasks'],
        'additionalProperties': False
    }]
}

query_schema = {
    'type': 'object',
    'properties': {
        'aggregate': {'type': 'array'}
    },
    'required': ['aggregate'],
    'additionalProperties': False
}

callback_schema = {
    'type': 'object',
    'properties': {
        'callback_key': {'type': 'string'},
        'callback_type': {'type': 'number'},
        'container_id': {'type': 'string'},
        'content': {
            'type': 'object',
            'properties': {
                'state': {'type': 'number'},
                'description': {'type': 'string'},
                'exception': {'type': ['string', 'null']},
                'telemetry': {
                    'type': ['object', 'null'],
                    'properties': {
                        'max_vms_memory': {'type': 'number'},
                        'max_rss_memory': {'type': 'number'},
                        'input_file_sizes': {
                            'type': 'array',
                            'items': {'type': ['number', 'null']}
                        },
                        'result_file_sizes': {
                            'type': 'array',
                            'items': {'type': ['number', 'null']}
                        },
                        'wall_time': {'type': 'number'},
                        'std_out': {'type': 'string'},
                        'std_err': {'type': 'string'},
                        'return_code': {'type': 'integer'}
                    },
                    'additionalProperties': False
                }
            },
            'required': ['state', 'description'],
            'additionalProperties': False
        }
    },
    'required': [
        'callback_key',
        'callback_type',
        'container_id',
        'content'
    ],
    'additionalProperties': False
}
