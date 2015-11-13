import types
import sys
from contextlib import contextmanager
from copy import copy
import collections
import inspect
import operator
from functools import reduce

# TODO remove proj_int
# TODO raw, to add headers (only write_header_decl or whatever)

proj_init = []


def mark_constructor():
    (frame, filename, line_number, function_name, lines, index) = inspect.getouterframes(inspect.currentframe())[2]
    return (filename, line_number)


def gentemp_call():
    i = 0
    while True:
        yield 'temp{}'.format(i)
        i += 1
gentemp = gentemp_call()


class Context(object):
    def __init__(self, level=0):
        self.f = []
        self.level = level

    @contextmanager
    def indent(self):
        self.level += 1
        yield
        self.level -= 1

    @contextmanager
    def block(self, suffix=''):
        self.write('{')
        self.level += 1
        yield
        self.level -= 1
        self.write('}' + suffix)
    
    def free_indent(self):
        self.level += 1
    
    def free_unindent(self):
        self.level -= 1

    def write(self, text):
        def split(line):
            lines = line.splitlines() or ['']
            for line in lines:
                self.f.append('\t' * self.level + line)
        if isinstance(text, Context):
            lines = text.f
        if isinstance(text, str):
            split(text)
        else:
            for line in text:
                split(line)

    def dump(self):
        return '\n'.join(self.f)


def simpleinit(scalars, collections):
    def inner(cls):
        class Out(cls):
            def __init__(self, **kwargs):
                self.mark = mark_constructor()
                self.args_scalars = scalars
                self.args_collections = collections
                for arg in collections:
                    setattr(self, arg, [])
                super(Out, self).__init__()
                for arg in scalars:
                    setattr(self, arg, kwargs.pop(arg, None))
                for arg in collections:
                    for val in kwargs.pop(arg, []):
                        getattr(self, 'add_{}'.format(arg))(val)
                if kwargs:
                    raise AssertionError('Unknown constructor args: {}'.format(kwargs))
                if hasattr(self, 'init2'):
                    self.init2()

            def __repr__(self):
                return '{}{}'.format(cls.__name__, self.mark)

            def __getattr__(self, attr):
                try:
                    return super(Out, self).__getattr__(attr)
                except AttributeError:
                    raise AttributeError('\'{}\' object has no attribute \'{}\''.format(cls.__name__, attr))
        for arg in collections:
            name = 'add_{}'.format(arg)
            if hasattr(Out, name):
                continue
            def inner(self, val, arg=arg):
                getattr(self, arg).append(val)
            setattr(Out, name, inner)
        return Out
    return inner


@simpleinit(['name', 'type', 'private'], [])
class MVar(object):
    def format_move(self):
        return self.type.format_move(self.name)
    
    def format_read(self):
        return self.type.format_read(self.name)
    
    def format_copy(self):
        return self.type.format_copy(self.name)
    
    def format_decl(self):
        return self.type.format_decl(self.name)
    
    def write_impl(self):
        return self.type.write_impl(self.name)
    
    def write_var_decl(self):
        return self.type.write_var_decl(self.name)

    def write_method_decl(self, withdefs=False):
        return self.write_var_decl()
    
    def write_init_body(self):
        return self.type.write_init_body(self.name)

    def format_type(self):
        return self.type.format_type()

    # MClass only
    def format_call(self, method, *args):
        return self.type.format_call(self.name, method, *args)
    
    def write_call(self, method, *args):
        return self.type.write_call(self.name, method, *args)

    def format_access(self):
        return self.type.format_access(self.name)
    
    def format_bare_access(self):
        return self.type.format_bare_access(self.name)


@simpleinit(['name', 'type', 'private', 'pointer'], [])
class MRawVar(object):
    def get_type(self):
        return self.type
    
    def format_bare_access(self):
        if self.pointer:
            return '{}->'.format(self.name)
        else:
            return '{}.'.format(self.name)

    def format_access(self):
        if self.pointer:
            return '{}'.format(self.name)
        else:
            return '{}'.format(self.name)

    def format_move(self):
        return self.name
    
    def format_read(self):
        return self.name
    
    def format_copy(self):
        return self.name
    
    def format_decl(self):
        return '{} {}'.format(self.type, self.name)

    def format_type(self):
        return self.type

    def write_var_decl(self):
        return ['{};'.format(self.format_decl())]
    
    def write_method_decl(self, withdefs=False):
        return ['{};'.format(self.format_decl())]

void = MRawVar(name='out', type='void')

@simpleinit(['base', 'field'], [])
class MAccess(object):
    def get_type(self):
        return self.field.type

    def format_access(self):
        return self.base.format_bare_access() + self.field.name

    def format_bare_access(self):
        return self.base.format_bare_access() + self.field.format_bare_access()
    
    def format_call(self, *pargs):
        return '{}({})'.format(
            self.format_access(),
            ', '.join(parg.format_read() for parg in pargs)
        )
    
    def write_call(self, *pargs):
        return ['{};'.format(self.format_call(*pargs))]
        

class MBase(object):
    def format_move(self, varname):
        return 'std::move({})'.format(varname)
    
    def format_read(self, varname):
        return varname
    
    def format_copy(self, varname):
        return varname

    def format_decl(self, varname):
        return '{} {}'.format(self.format_type(), varname)
    
    def write_var_decl(self, varname):
        return ['{};'.format(self.format_decl(varname))]
    
    def write_init_body(self, varname):
        return []

    def write_proto(self):
        return []

    def write_method_decl(self, withdefs=False):
        return []

    def write_impl(self):
        return []

    def format_type(self):
        return self.name

    def get_type(self):
        return self


class TPrimitive(MBase):
    def write_proto(self):
        if self.name == self.base:
            return []
        return ['using {} = {};'.format(self.name, self.base)]


@simpleinit(['name', 'base'], [])
class TInt32(TPrimitive):
    def init2(self):
        self.base = self.base or 'int32_t'
        if self.name:
            self.name += '_t'
        else:
            self.name = self.base


@simpleinit(['name', 'base'], [])
class TInt64(TPrimitive):
    def init2(self):
        self.base = self.base or 'int64_t'
        if self.name:
            self.name += '_t'
        else:
            self.name = self.base
integer = TInt64()


@simpleinit(['name', 'base'], [])
class TUInt64(TPrimitive):
    def init2(self):
        self.base = self.base or 'uint64_t'
        if self.name:
            self.name += '_t'
        else:
            self.name = self.base


@simpleinit(['name'], [])
class TFloat(TPrimitive):
    def init2(self):
        self.name = self.name or 'float'
floating = TFloat()


@simpleinit(['name'], [])
class TBool(TPrimitive):
    def init2(self):
        self.name = self.name or 'bool'


@simpleinit(['name'], [])
class TString(TPrimitive):
    def init2(self):
        self.name = self.name or 'std::string'
string = TString()


@simpleinit(['base'], [])
class TArray(MBase):
    def format_type(self):
        return 'fixed_vector<{}>'.format(self.base.format_type())

    def write_init_body(self, varname):
        return []
    
        
@simpleinit(['key', 'value'], [])
class TMap(MBase):
    def format_type(self):
        return 'std::map<{}, {}>'.format(self.key.format_type(), self.base.format_type())

    def write_init_body(self, varname):
        return []
    

@simpleinit(['name', 'private', 'parent', 'ret', 'body', 'virtual', 'static'], ['args'])
class MFunction(MBase):
    def write_method_decl(self, withdefs=False):
        #if self.private and not self.parent:
        #    return []
        #if self.body is None:
        #    return []
        body = Context()
        preamble1 = '{s}{v}{r}'.format(
            s=('static ' if self.static else ''),
            v=('virtual ' if self.virtual else ''),
            r=(self.ret.format_type() + ' ') if self.ret else '', 
        )
        preamble2 = '{n}({a}){b}'.format(
            n=self.name,
            a=', '.join(arg.format_decl() for arg in self.args),
            b=' = 0' if self.virtual and self.body is None else '',
        )
        if withdefs:
            body.write('{}{}'.format(preamble1, preamble2))
            with body.block():
                if isinstance(self.body, types.FunctionType):
                    body.write(self.body())
                else:
                    body.write(self.body)
        else:
            body.write('{:<40}{};'.format(preamble1, preamble2))
        return body.f

    def write_impl(self):
        if self.virtual and self.body is None:
            return []
        body = Context()
        body.write('{}{}{}({})'.format(
            (self.ret.format_type() + ' ') if self.ret else '', 
            self.parent.format_qualifier() if self.parent else '',
            self.name,
            ', '.join(arg.format_decl() for arg in self.args),
        ))
        with body.block():
            if isinstance(self.body, types.FunctionType):
                body.write(self.body())
            else:
                body.write(self.body)
        body.write('')
        return body.f

    def format_call(self, *pargs):
        return '{}{}({})'.format(
            (
                (self.parent.name + '::' if self.static else '{}->'.format(self.name))
                if self.parent else ''
            ),
            self.name, 
            ', '.join(parg.format_read() for parg in pargs)
        )
    
    def write_proto(self):
        return []


@simpleinit(['name', 'identity', 'virtual', 'abstract', 'nodefaultconstructor'], ['implements', 'fields', 'implementations', 'notifications', 'enums'])
class MClass(MBase):
    def __init__(self):
        self.destructor_body = []
        constructor_ret = MVar(name='out', type=self)
        def write_constructor():
            return (
                constructor_ret.write_var_decl() +
                ['{}->{} = {};'.format(constructor_ret.name, data.name, data.format_move()) for data in self.constructor.args] +
                (proj_init if self.name == 'project_t' else ['']) +
                ['return {}'.format(constructor_ret.format_move())]
            )
        self.constructor = MFunction(
            name='create', 
            ret=constructor_ret,
            args=[],
            body=write_constructor,
            static=True,
        )
        self.add_field(self.constructor)

    def init2(self):
        self.oldname = self.name
        self.name += '_t'
        if self.abstract or self.nodefaultconstructor:
            try:
                self.fields.remove(self.constructor)
            except ValueError:
                pass
        self.add_field(MFunction(
            private=True,
            name=self.name,
            ret=None,
            args=[],
            body=[],
        ))
        def write_destructor():
            return self.destructor_body
        self.add_field(MFunction(
            name='~{}'.format(self.name),
            ret=None,
            args=[],
            body=write_destructor,
            virtual=self.virtual or self.abstract,
        ), 1 if self.constructor in self.fields else 0)

    def add_fields(self, body):
        self.add_field(body)

    def add_field(self, body, index=None):
        if isinstance(body, MClass) and body.identity:
            self.identity = True
        self.fields.insert(index if index is not None else len(self.fields), body)
        if isinstance(body, (MVar, MRawVar)):
            if not body.private:
                self.constructor.args.append(body)
        elif isinstance(body, MFunction):
            method = body
            method.parent = self
            if method.virtual:
                self.virtual = True
            if method.body is None:
                self.abstract = True
                try:
                    self.fields.remove(self.constructor)
                except ValueError:
                    pass

    def add_implements(self, base):
        base.implementations.append(self)
        self.implements.append(base)

    def get_field(self, name):
        for method in self.all_fields():
            if method.name == name:
                return method

    def all_fields(self):
        return reduce(operator.concat, (base.all_fields() for base in self.implements), []) + self.fields
    
    def all_methods(self):
        return [field for field in self.all_fields() if isinstance(field, MFunction)]
    
    def local_methods(self):
        return [field for field in self.fields if isinstance(field, MFunction)]

    def format_qualifier(self):
        return '{}::'.format(self.name)

    def write_proto(self):
        return ['struct {};'.format(self.name)]

    def write_method_decl(self, withdefs=False):  # methods = misnomer
        body = Context()
        body.write('struct {}'.format(self.name))
        if self.implements or self.identity:
            with body.indent():
                body.write(': {}'.format(', '.join(
                    [implements.name for implements in self.implements] + 
                    (['std::enable_shared_from_this'] if self.identity else [])
                )))
        body.write('{')
        with body.indent():
            for enum in self.enums:
                body.write(enum.write_method_decl(withdefs=withdefs))
            for el in self.fields:
                if el.private:
                    continue
                body.write(el.write_method_decl(withdefs=withdefs))
                if withdefs:
                    body.write('')
            body.write('protected:')
            with body.indent():
                for el in self.fields:
                    if not el.private:
                        continue
                    body.write(el.write_method_decl(withdefs=withdefs))
                    if withdefs:
                        body.write('')
        body.write('};')
        body.write('')
        return body.f

    def write_impl(self):
        body = Context()
        for method in self.local_methods():
            body.write(method.write_impl())
        body.write('')
        return body.f

    def format_type(self):
        if self.identity:
            return 'std::shared_ptr<{}>'.format(self.name)
        else:
            return self.name
    
    def format_decl(self, varname):
        return '{} {}'.format(self.format_type(), varname)

    def write_var_decl(self, varname):
        return ['{};'.format(self.format_decl(varname))]
    
    def write_init_body(self, varname):
        return []
    
    def format_bare_access(self, name):
        if self.identity:
            return '{}->'.format(name)
        else:
            return '{}.'.format(name)

    def format_access(self, name, field):
        if self.identity:
            return '{}->{}'.format(name, field.name)
        else:
            return '{}.{}'.format(name, field.name)


class MFunctionObject(MClass):
    def __init__(self, name, ret=void, args=[]):
        super(MFunctionObject, self).__init__(
            name=name,
            identity=True,
            fields=[
                MFunction(
                    name='operator()',
                    ret=ret,
                    args=args,
                    virtual=True,
                ),
            ],
        )


@simpleinit(['name'], ['values'])
class TEnum(MBase):
    def __init__(self):
        self.values = {}
    
    def init2(self):
        self.oldname = self.name
        self.name += '_t'

    def add_value(self, value):
        self.values[value] = value.upper()
    add_values = add_value

    def get_value(self, value):
        return self.values[value]

    def write_method_decl(self, withdefs=False):
        body = Context()
        body.write('enum {}'.format(self.name))
        body.write('{')
        with body.indent():
            body.write(',\n'.join(['_FIRST = 0'] + list(self.values.values()) + ['_LAST']))
        body.write('};')
        return body.f


@simpleinit(['name'], ['data'])
class TUnion(MBase):
    def init2(self):
        if self.name:
            self.oldname = self.name
            self.name += '_t'
    
    def format_type(self):
        body = Context()
        body.write('union{}'.format(' {}'.format(self.name) if self.name else ''))
        body.write('{')
        with body.indent():
            for data in self.data:
                body.write(data.write_var_decl())
        body.write('}')
        return '\n'.join(body.f)


class MVariant(MClass):
    def __init__(self, name, data=[]):
        data = data or []
        super(MVariant, self).__init__(name=name, nodefaultconstructor=True)
        
        self.vtypes = []
        self.checks = {}
        self.gets = {}

        enum = TEnum(name='type')
        enum.add_values('none')
        self.add_enums(enum)
        self.typevar = MVar(
            name='type',
            type=enum,
        )
        self.add_field(self.typevar)
        self.unionvar = MVar(
            name='data', 
            type=TUnion(),
            private=True,
        )
        self.add_field(self.unionvar)
        
        create_ret = MVar(name='out', type=self)
        function_create_none = MFunction(
            name='create_none',
            ret=create_ret,
            args=[],
            body=
                create_ret.write_var_decl() +
                [
                    'out->type = NONE;',
                    'return out;',
                ] +
                [],
            static=True,
        )
        self.add_field(function_create_none)

        function_is_set = MFunction(
            name='is_set',
            ret=MVar(name='out', type=TBool()),
            args=[],
            body=['return type != NONE;'],
        )
        self.add_field(function_is_set)

        function_set_none = MFunction(
            name='none_set',
            ret=void,
            args=[],
            body=[
                'destroy();',
                'type = NONE;',
            ],
        )
        self.add_field(function_set_none)

        self.destructor_body.append('destroy();')

        self.destroy_body = Context()
        def write_function_destroy():
            body = Context()
            body.write('switch (type)')
            body.write('{')
            with body.indent():
                body.write(self.destroy_body.f)
            body.write('}')
            return body.f
        function_destroy = MFunction(
            name='destroy',
            ret=void,
            args=[],
            body=write_function_destroy,
            private=True,
        )
        self.add_field(function_destroy)

        for val in data or []:
            self.add_val(val)

    def add_val(self, val):
        self.typevar.type.add_value(val.name)
        self.unionvar.type.add_data(MVar(name='{}_data'.format(val.name), type=val.type))
        self.vtypes.append(val)
        create_ret = MVar(name='out', type=self)
        create_arg = MVar(name='in', type=val.type)
        function_create = MFunction(
            name='create_{}'.format(val.name),
            ret=create_ret,
            args=[create_arg],
            body=
                create_ret.write_var_decl() +
                [
                    'out->type = {};'.format(self.typevar.type.get_value(val.name)),
                    'new (&out->data.{}_data) {}({});'.format(val.name, val.type.format_type(), create_arg.format_move()),
                    'return out;',
                ] +
                [],
            static=True,
        )
        self.add_field(function_create)

        function_is = MFunction(
            name='is_{}'.format(val.name),
            ret=MVar(name='out', type=TBool()),
            args=[],
            body=[
                'return {} == {};'.format(self.typevar.name, self.typevar.type.get_value(val.name)),
            ],
        )
        self.add_field(function_is)
        self.checks[val.type] = function_is
        
        function_get = MFunction(
            name='{}_get'.format(val.name),
            ret=MVar(name='out', type=val.type),
            args=[],
            body=[
                'if (!is_{}) throw GeneralError() << "Variant {} is the wrong type (wanted {}, is " << format_name() << ")");'.format(val.name, self.name, val.name),
                'return data.{};'.format(val.name),
            ],
        )
        self.add_field(function_get)
        self.gets[val.type] = function_get

        set_arg = MVar(name='in', type=val.type)
        function_set = MFunction(
            name='{}_set'.format(val.name),
            ret=void,
            args=[set_arg],
            body=[
                'if (type != NONE) destroy();',
                'new (&data.{}_data) {}({});'.format(val.name, val.type.format_type(), set_arg.format_move()),
                'type = {};'.format(self.typevar.type.get_value(val.name)),
            ],
        )
        self.add_field(function_set)

        self.destroy_body.write('case {}:'.format(self.typevar.type.get_value(val.name)))
        with self.destroy_body.indent():
            self.destroy_body.write('data.{}_data.~{}();'.format(val.name, val.type.name))
            self.destroy_body.write('break;')

    def get_check(self, vtype):
        return self.checks[vtype]
    
    def get_get(self, vtype):
        return self.gets[vtype]
