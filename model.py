from gen_base import *

model = [
    MPreRaw(
        hxx=[
            '#include <memory>',
            '#include <iostream>',
            '#include <vector>',
            '#include <map>',
            '',
            'namespace deepness',
            '{',
            '',
        ],
        cxx=[
            '#include "_deepness.hxx"',
            '#include "misc.hxx"',
            '',
            'namespace deepness',
            '{',
            '',
        ],
    )
]


def add(melement):
    model.append(melement)

elements = []
prime_elements = []

def add_element(element):
    element.add_field(MFunction(
        name='hint',
        ret=void,
        args=[
            MVar(name='key', type=string),
            MVar(name='value', type=string),
        ],
        virtual=True,
    ))
    element.add_field(MFunction(
        name='note',
        ret=void,
        args=[
            MVar(
                name='category',
                type=string,
            ),
            MVar(
                name='message',
                type=string,
            ),
            MVar(
                name='details',
                type=string,
            ),
        ],
        virtual=True,
    ))
    add(element)
    elements.append(element)

for pname, ptype in (
        ('int', integer), 
        ('float', floating),
        ('string', string),
        ):
    element = MClass(
        name=pname,
        identity=True,
        fields=[
            MFunction(
                name='set',
                ret=void,
                args=[MVar(name='value', type=ptype)],
                virtual=True,
            ),
            MFunction(
                name='get',
                ret=MVar(name='value', type=ptype),
                virtual=True,
            ),
            # TODO derived change elements
        ],
    )
    add_element(element)
    prime_elements.append(element)
    if pname == 'int':
        element_integer = element

action_function = MFunctionObject(
    name='action_function',
    ret=void,
)
add(action_function)
action = MClass(
    name='action',
    identity=True,
)
add_element(action)
prime_elements.append(action)

subgroup = MClass(
    name='subgroup',
    identity=True,
    fields=[
        MFunction(
            name='count',
            virtual=True,
            ret=MVar(name='out', type=integer),
        ),
        MFunction(
            name='get',
            virtual=True,
            ret=MVar(name='out', type=integer),
            args=[
                MVar(name='index', type=integer)
            ],
        ),
        MFunction(
            name='remove',
            virtual=True,
            ret=void,
            args=[MVar(name='value', type=integer)],
        ),
        MFunction(
            name='add',
            virtual=True,
            ret=void,
            args=[MVar(name='value', type=integer)],
        ),
    ]
)
add_element(subgroup)

group = MClass(
    name='group',
    identity=True,
    fields=[
        MFunction(
            name='count',
            virtual=True,
            ret=MVar(name='out', type=integer),
        ),
        MFunction(
            name='remove',
            ret=void,
            virtual=True,
            args=[MVar(name='position', type=integer)],
        ),
        MFunction(
            name='clear',
            ret=void,
            virtual=True,
        ),
        MFunction(
            name='select_one',
            virtual=True,
            ret=MVar(name='out', type=element_integer),
            args=[MVar(name='name', type=string)],
        ),
        MFunction(
            name='select_many',
            virtual=True,
            ret=MVar(name='out', type=subgroup),
            args=[MVar(name='name', type=string)],
        ),
    ]
)
add_element(group)
prime_elements.append(group)

element_variant = MVariant(
    name='element',
    data=[MVar(name=element.name, type=element) for element in elements],
)
add(element_variant)

group.add_field(MFunction(
    name='guide',
    virtual=True,
    ret=void,
    args=[
        MVar(name='element', type=element_variant)
    ],
))
group.add_field(MFunction(
    name='get',
    virtual=True,
    ret=MVar(name='out', type=element_variant),
    args=[
        MVar(name='element', type=integer)
    ],
))
group.add_field(MFunction(
    name='add',
    virtual=True,
    ret=MVar(name='out', type=integer),
    args=[
        MVar(name='element', type=element_variant)
    ],
))
group.add_field(MFunction(
    name='insert',
    virtual=True,
    ret=void,
    args=[
        MVar(name='position', type=integer),
        MVar(name='element', type=element_variant)
    ],
))

context = MClass(
    name='context',
    identity=True,
    fields=[
        MFunction(
            name='act',
            ret=void,
            args=[
                MVar(name='action', type=action_function),
            ],
            virtual=True,
        ),
        MFunction(
            name='start',
            ret=void,
            args=[MVar(name='group', type=group)],
            virtual=True,
        ),
    ] + [
        MFunction(
            name='create_' + element.oldname,
            ret=MVar(name='out', type=element),
            args=[
                MVar(name='name', type=string)
            ] + [
                MVar(
                    name='arg',
                    type=element_variant,
                ),
                MVar(
                    name='definition',
                    type=action_function,
                ),
            ] if element == action else [
            ],
            virtual=True,
        )
        for element in prime_elements
    ],
)
add(context)

open_sig = MFunction(
    name='open',
    ret=MVar(name='out', type=context),
    args=[MVar(name='args', type=TArray(base=string))],
    body=undefined,
)
add(open_sig)

add(MPostRaw(
    hxx=[
        '',
        '}',
        '',
    ],
    cxx=[
        '',
        '}',
        '',
    ],
))
