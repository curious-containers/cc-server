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
        }
    },
    'required': ['enabled'],
    'additionalProperties': False
}

_syscall_filter_condition_one_parameter_schema = {
    'type': 'object',
    'properties': {
        'argument': {'type': 'integer'},
        'operation': {'enum': ['==', '!=', '<=', '<', '>=', '>']},
        'datum_a': {'type': 'integer'}
    },
    'required': ['argument', 'operation', 'datum_a']
}

_syscall_filter_condition_two_parameter_schema = {
    'type': 'object',
    'properties': {
        'argument': {'type': 'integer', 'minimum': 0, 'maximum': 6},
        'operation': {'enum': ['&=']},
        'datum_a': {'type': 'integer'},
        'datum_b': {'type': 'integer'}
    },
    'required': ['argument', 'operation', 'datum_a', 'datum_b']
}

_syscall_filter_schema = {
    'type': 'object',
    'properties': {
        'syscall': {'type': ['string', 'integer']},
        'conditions': {
            'type': 'array',
            'minItems': 0,
            'maxItems': 6,
            'items': {
                'type': 'object',
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

_sandbox_schema = {
    'type': 'object',
    'properties': {
        'mode': {
            'enum': ['disabled', 'whitelist', 'blacklist']
        },
        'filter_items': {
            'type': 'array',
            'items': {
                'type': 'object',
                'anyOf': [
                    _syscall_filter_schema
                ]
            }
        }
    },
    'required': ['mode'],
    'additionalProperties': False
}

_tracing_telemetry_process_schema = {
    'type': 'object',
    'properties': {
        'pid': {'type': 'integer'},
        'start': {'type': 'number'},
        'end': {'type': 'number'},
        'exit_code': {'type': 'integer'},
        'signal': {'type': ['integer', 'null']}
    },
    'required': ['pid', 'start', 'end', 'exit_code', 'signal'],
    'additionalProperties': False
}

_tracing_telemetry_file_access_short_schema = {
    'type': 'object',
    'properties': {
        'filename': {'type': 'string'},
        'is_directory': {'type': 'boolean'},
        'exists': {'type': 'boolean'},
    },
    'required': ['filename', 'is_directory', 'exists'],
    'additionalProperties': False
}

_tracing_telemetry_file_access_full_schema = {
    'type': 'object',
    'properties': {
        'filename': {'type': 'string'},
        'is_directory': {'type': 'boolean'},
        'exists': {'type': 'boolean'},
        'syscall': {'type': 'string'},
        'access_time': {'type': 'number'},
        'pid': {'type': 'integer'},
        'syscall_result': {'type': 'integer'}
    },
    'required': ['filename', 'is_directory', 'exists', 'syscall', 'access_time', 'pid', 'syscall_result'],
    'additionalProperties': False
}

_tracing_telemetry_syscall_attribute_schema = {
    'type': 'object',
    'properties': {
        'name': {'type': 'string'},
        'type': {'type': 'string'},
        'value': {'type': ['number', 'string']},
        'text': {'type': ['string', 'null']}
    },
    'required': ['name', 'type', 'value'],
    'additionalProperties': False
}

_tracing_telemetry_syscall_short_schema = {
    'type': 'object',
    'properties': {
        'name': {'type': 'string'},
        'pid': {'type': 'integer'},
        'start': {'type': 'number'},
        'end': {'type': 'number'},
        'result': {'type': 'integer'}
    },
    'required': ['name', 'pid', 'start', 'end', 'result'],
    'additionalProperties': False
}

_tracing_telemetry_syscall_full_schema =  {
    'type': 'object',
    'properties': {
        'name': {'type': 'string'},
        'pid': {'type': 'integer'},
        'start': {'type': 'number'},
        'end': {'type': 'number'},
        'result': {'type': 'integer'},
        'attributes': {
            'type': 'array',
            'minItems': 0,
            'maxItems': 6,
            'items': {
                'type': 'object',
                'anyOf': [
                    _tracing_telemetry_syscall_attribute_schema
                ]
            }
        }
    },
    'required': ['name', 'pid', 'start', 'end', 'result', 'attributes'],
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
                'tracing': {
                    'type': 'object',
                    'anyOf': [
                        _tracing_schema
                    ]
                },
                'sandbox': {
                    'type': 'object',
                    'anyOf': [
                        _sandbox_schema
                    ]
                },
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
                        },
                        'wall_time': {'type': 'number'},
                        'tracing': {
                            'type': 'object',
                            'properties': {
                                'processes': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'object',
                                        'anyOf': [
                                            _tracing_telemetry_process_schema
                                        ]
                                    }
                                },
                                'file_access': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'object',
                                        'anyOf': [
                                            _tracing_telemetry_file_access_short_schema,
                                            _tracing_telemetry_file_access_full_schema
                                        ]
                                    }
                                },
                                'syscalls': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'object',
                                        'anyOf': [
                                            _tracing_telemetry_syscall_short_schema,
                                            _tracing_telemetry_syscall_full_schema
                                        ]
                                    }
                                }
                            },
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
