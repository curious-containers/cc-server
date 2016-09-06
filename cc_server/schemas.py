_basic_auth = {
    'type': 'object',
    'properties': {
        'basic_username': {'type': 'string'},
        'basic_password': {'type': 'string'}
    },
    'required': ['basic_username', 'basic_password'],
    'additionalProperties': False
}

_digest_auth = {
    'type': 'object',
    'properties': {
        'digest_username': {'type': 'string'},
        'digest_password': {'type': 'string'}
    },
    'required': ['digest_username', 'digest_password'],
    'additionalProperties': False
}

_input_result_ssh_schema = {
    'type': 'object',
    'properties': {
        'ssh_host': {'type': 'string'},
        'ssh_username': {'type': 'string'},
        'ssh_password': {'type': 'string'},
        'ssh_file_dir': {'type': 'string'},
        'ssh_file_name': {'type': 'string'},
    },
    'required': [
        'ssh_host',
        'ssh_username',
        'ssh_password',
        'ssh_file_dir',
        'ssh_file_name'
    ],
    'additionalProperties': False
}

_input_http_schema = {
    'type': 'object',
    'properties': {
        'http_url': {'type': 'string'},
        'http_data': {'type': 'string'},
        'http_auth': {
            'type': 'object',
            'oneOf': [
                _basic_auth,
                _digest_auth
            ]
        }
    },
    'required': ['http_url'],
    'additionalProperties': False
}

_result_http_schema = {
    'type': 'object',
    'properties': {
        'http_url': {'type': 'string'},
        'http_file_name': {'type': 'string'},
        'http_auth': {
            'type': 'object',
            'oneOf': [
                _basic_auth,
                _digest_auth
            ]
        }
    },
    'required': ['http_url'],
    'additionalProperties': False
}

_result_json_schema = {
    'type': 'object',
    'properties': {
        'json_url': {'type': 'string'},
        'json_data': {'type': 'object'},
        'json_auth': {
            'type': 'object',
            'oneOf': [
                _basic_auth,
                _digest_auth
            ]
        }
    },
    'required': ['json_url'],
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
                'parameters': {'type': 'object'}
            },
            'required': ['image', 'container_ram'],
            'additionalProperties': False
        },
        'input_files': {
            'type': 'array',
            'items': {
                'type': 'object',
                'anyOf': [
                    _input_result_ssh_schema,
                    _input_http_schema
                ]
            }
        },
        'result_files': {
            'type': 'array',
            'items': {
                'type': 'object',
                'anyOf': [
                    _input_result_ssh_schema,
                    _result_http_schema,
                    _result_json_schema
                ]
            }
        },
        'notifications': {
            'type': 'array',
            'items': {
                'type': 'object',
                'anyOf': [
                    _input_http_schema
                ]
            }
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
            'items': {
                'type': 'object',
                'anyOf': [
                    _task_schema
                ]
            }
        }
    },
    'required': ['tasks'],
    'additionalProperties': False
}

tasks_schema = {
    'type': 'object',
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
        'query': {'type': 'object'},
        'projection': {'type': 'object'}
    },
    'required': ['query'],
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
                'input_file_keys': {
                    'type': 'array',
                    'items': {'type': 'string'}
                },
                'telemetry': {
                    'type': ['object', 'null'],
                    'properties': {
                        'max_vms_memory': {'type': 'number'},
                        'max_rss_memory': {'type': 'number'},
                        'input_file_sizes': {
                            'type': 'array',
                            'items': {'type': 'number'}
                        },
                        'result_file_sizes': {
                            'type': 'array',
                            'items': {'type': 'number'}
                        }
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
