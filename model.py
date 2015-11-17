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
    add(element)
    elements.append(element)

for pname, ptype in (
        ('int', integer), 
        ('float', floating),
        ('string', string),
        ):
    add_element(MClass(
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
    ))

action_function = MFunctionObject(
    name='action_function',
    ret=void,
)
add(action_function)
add_element(MClass(
    name='action',
    identity=True,
    fields=[
        MFunction(
            name='define',
            ret=void,
            args=[
                MVar(
                    name='definition',
                    type=action_function,
                ),
                # TODO allow async (new function?) w/ completion
            ],
            virtual=True,
        ),
    ],
))

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
        ),
        # TODO derived selection data (+ multiple selection configurations) (+ selection changes?)
    ]
)
add_element(group)

element_variant = MVariant(
    name='element',
    data=[MVar(name=element.name, type=element) for element in elements],
)
add(element_variant)

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
            name='add',
            ret=void,
            args=[MVar(name='group', type=group)],
            virtual=True,
        ),
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
            virtual=True,
        ),
    ] + [
        MFunction(
            name='create_' + element.oldname,
            ret=MVar(name='out', type=element),
            virtual=True,
        )
        for element in elements
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
