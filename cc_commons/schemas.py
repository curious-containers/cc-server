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
    'required': ['connector_type', 'connector_access', 'local_result_file'],
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

_auth = {
    'type': 'object',
    'properties': {
        'auth_type': {'enum': ['basic', 'digest']},
        'username': {'type': 'string'},
        'password': {'type': 'string'}
    },
    'required': ['auth_type', 'username', 'password'],
    'additionalProperties': False
}

_notification_connector_schema = {
    'type': 'object',
    'properties': {
        'connector_access': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string'},
                'json_data': {'type': 'object'},
                'ssl_verify': {'type': 'boolean'},
                'auth': _auth
            },
            'required': ['url'],
            'additionalProperties': False
        },
        'add_meta_data': {'type': 'boolean'}
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
        'tracing_file': {
            'anyOf': [
                _tracing_connector_schema,
                {'type': 'null'}
            ]
        }
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
                    'anyOf': [{
                        'type': 'object',
                        'properties': {
                            'username': {'type': 'string'},
                            'password': {'type': 'string'}
                        },
                        'required': ['username', 'password'],
                        'additionalProperties': False
                    }, {
                        'type': 'null'
                    }],
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

nodes_schema = {
    'type': 'object',
    'properties': {
        'nodes': {
            'type': 'array',
            'items': {
                'anyOf': [{
                    'type': 'object',
                    'properties': {
                        'cluster_node': {'type': 'string'}
                    },
                    'required': ['cluster_node'],
                    'additionalProperties': False
                }]
            }
        }
    },
    'required': ['nodes'],
    'additionalProperties': False
}

tasks_cancel_schema = {
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
        'aggregate': {
            'type': 'array',
            'items': {
                'anyOf': [{
                    'type': 'object',
                    'properties': {
                        '$match': {}
                    },
                    'required': ['$match'],
                    'additionalProperties': False
                }, {
                    'type': 'object',
                    'properties': {
                        '$project': {}
                    },
                    'required': ['$project'],
                    'additionalProperties': False
                }, {
                    'type': 'object',
                    'properties': {
                        '$limit': {}
                    },
                    'required': ['$limit'],
                    'additionalProperties': False
                }, {
                    'type': 'object',
                    'properties': {
                        '$skip': {}
                    },
                    'required': ['$skip'],
                    'additionalProperties': False
                }, {
                    'type': 'object',
                    'properties': {
                        '$count': {}
                    },
                    'required': ['$count'],
                    'additionalProperties': False
                }, {
                    'type': 'object',
                    'properties': {
                        '$sort': {}
                    },
                    'required': ['$sort'],
                    'additionalProperties': False
                }, {
                    'type': 'object',
                    'properties': {
                        '$unwind': {}
                    },
                    'required': ['$unwind'],
                    'additionalProperties': False
                }, {
                    'type': 'object',
                    'properties': {
                        '$group': {}
                    },
                    'required': ['$group'],
                    'additionalProperties': False
                }, {
                    'type': 'object',
                    'properties': {
                        '$sample': {}
                    },
                    'required': ['$sample'],
                    'additionalProperties': False
                }, {
                    'type': 'object',
                    'properties': {
                        '$replaceRoot': {}
                    },
                    'required': ['$replaceRoot'],
                    'additionalProperties': False
                }, {
                    'type': 'object',
                    'properties': {
                        '$addFields': {}
                    },
                    'required': ['$addFields'],
                    'additionalProperties': False
                }]
            }
        }
    },
    'required': ['aggregate'],
    'additionalProperties': False
}

_file_size = {
    'type': 'object',
    'properties': {
        'local_file_path': {'type': 'string'},
        'file_size': {'type': 'integer'}
    },
    'required': ['local_file_path', 'file_size'],
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
                'state': {'type': 'integer'},
                'description': {'type': 'string'},
                'exception': {'type': ['string', 'null']},
                'telemetry': {
                    'type': ['object', 'null'],
                    'properties': {
                        'max_vms_memory': {'type': 'number'},
                        'max_rss_memory': {'type': 'number'},
                        'input_file_sizes': {
                            'type': 'array',
                            'items': {
                                'anyOf': [
                                    {'type': 'null'},
                                    _file_size
                                ]
                            }
                        },
                        'result_file_sizes': {
                            'type': 'object',
                            'patternProperties': {
                                '^[a-zA-Z0-9_\-]+$': {
                                    'anyOf': [
                                        {'type': 'null'},
                                        _file_size
                                    ],
                                }
                            },
                            'additionalProperties': False
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

cc_server_config_schema = {
    'type': 'object',
    'properties': {
        'server_web': {
            'type': 'object',
            'properties': {
                'external_url': {'type': 'string'},
                'bind_host': {'type': 'string'},
                'bind_port': {'type': 'integer'},
                'num_workers': {'type': 'integer'}
            },
            'required': ['external_url', 'bind_host', 'bind_port'],
            'additionalProperties': False
        },
        'server_master': {
            'type': 'object',
            'properties': {
                'external_url': {'type': 'string'},
                'bind_host': {'type': 'string'},
                'bind_port': {'type': 'integer'},
                'scheduling_interval_seconds': {'type': 'integer'}
            },
            'required': ['external_url', 'bind_host', 'bind_port'],
            'additionalProperties': False
        },
        'server_log': {
            'type': 'object',
            'properties': {
                'external_url': {'type': 'string'},
                'bind_host': {'type': 'string'},
                'bind_port': {'type': 'integer'},
                'log_dir': {'type': 'string'},
                'suppress_stdout': {'type': 'boolean'}
            },
            'required': ['external_url', 'bind_host', 'bind_port'],
            'additionalProperties': False
        },
        'mongo': {
            'type': 'object',
            'properties': {
                'username': {'type': 'string'},
                'password': {'type': 'string'},
                'host': {'type': 'string'},
                'port': {'type': 'integer'},
                'db': {'type': 'string'}
            },
            'required': ['username', 'password', 'host', 'port', 'db'],
            'additionalProperties': False
        },
        'docker': {
            'type': 'object',
            'properties': {
                'thread_limit': {'type': 'integer'},
                'api_timeout': {'type': 'integer'},
                'net': {'type': 'string'},
                'machines_dir': {'type': 'string'},
                'nodes': {
                    'type': 'object',
                    'patternProperties': {
                        '^[a-zA-Z0-9_\-]+$': {
                            'type': 'object',
                            'properties': {
                                'base_url': {'type': 'string'},
                                'tls': {
                                    'type': 'object',
                                    'properties': {
                                        'verify': {'type': 'string'},
                                        'client_cert': {
                                            'type': 'array',
                                            'items': {'type': 'string'}
                                        },
                                        'assert_hostname': {'type': 'boolean'}
                                    },
                                    'additionalProperties': True
                                }
                            },
                            'required': ['base_url'],
                            'additionalProperties': False
                        }
                    }
                }
            },
            'required': ['thread_limit'],
            'additionalProperties': False
        },
        'defaults': {
            'type': 'object',
            'properties': {
                'application_container_description': {
                    'type': 'object',
                    'properties': {
                        'entry_point': {'type': 'string'}
                    },
                    'required': ['entry_point'],
                    'additionalProperties': False
                },
                'data_container_description': {
                    'type': 'object',
                    'properties': {
                        'image': {'type': 'string'},
                        'entry_point': {'type': 'string'},
                        'container_ram': {'type': 'integer'},
                        'registry_auth': {
                            'type': 'object',
                            'properties': {
                                'username': {'type': 'string'},
                                'password': {'type': 'string'}
                            },
                            'required': ['username', 'password'],
                            'additionalProperties': False
                        }
                    },
                    'required': ['image', 'entry_point', 'container_ram'],
                    'additionalProperties': False
                },
                'scheduling_strategies': {
                    'type': 'object',
                    'properties': {
                        'container_allocation': {'enum': ['spread', 'binpack']}
                    },
                    'required': ['container_allocation'],
                    'additionalProperties': False
                },
                'error_handling': {
                    'type': 'object',
                    'properties': {
                        'max_task_trials': {'type': 'integer'},
                        'dead_node_invalidation': {'type': 'boolean'},
                        'dead_node_notification': {
                            'type': 'object',
                            'properties': {
                                'url': {'type': 'string'},
                                'auth': _auth
                            },
                            'required': ['url'],
                            'additionalProperties': False
                        }
                    },
                    'required': ['max_task_trials'],
                    'additionalProperties': False
                },
                'authorization': {
                    'type': 'object',
                    'properties': {
                        'num_login_attempts': {'type': 'integer'},
                        'block_for_seconds': {'type': 'integer'},
                        'tokens_valid_for_seconds': {'type': 'integer'}
                    },
                    'required': ['num_login_attempts', 'block_for_seconds', 'tokens_valid_for_seconds']
                }
            }
        }
    },
    'required': ['server_web', 'server_master', 'server_log', 'mongo', 'docker', 'defaults'],
    'additionalProperties': True
}
