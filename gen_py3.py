from gen_base import *
from gen_py3 import *

# TODO placement_destroy
# TODO catch errors in wrapped functions
# TODO operator() -> __call__

def write_python_read(body, el):
    out = el.name
    if isinstance(el.type, MClass):
        # TODO check derived types as well
        body.write('if (!PyObject_IsInstance({}, pytype_{}_type))'.format(el.name, el.type.name))  # TODO use type name lookup in module
        with body.indent():
            body.write('throw GeneralError() << "Argument [{}] is not a [{}] instance.";'.format(el.name, el.type.oldname)) 
        out = next(gentemp)
        body.write('auto {} = {}->data'.format(out, el.name))  # TODO cast, see above note
    elif isinstance(el.type, TString):
        body.write('if (!PyUnicode_Check({}))'.format(el.name))
        with body.indent():
            body.write('throw GeneralError() << "Argument [{}] is not a string.";'.format(el.name)) 
        out = next(gentemp)
        body.write('auto {} = PyUnicode_AsUTF8({})'.format(out, el.name))
    elif isinstance(el.type, MFunction):
        body.write('if (!PyFunction_Check({}))'.format(el.name))
        with body.indent():
            body.write('throw GeneralError() << "Argument [{}] is not a function.";'.format(el.name)) 
        out = next(gentemp)
        body.write('{} {}{{{}}};'.format(
            'pyfunction<{}({})>'.format(
                el.type.ret.format_type(),
                ', '.join(arg.format_type() for arg in el.args),
            ),
            out,
            arg.name,
        ))
    elif isinstance(el.type, TArray):
        out = next(gentemp)
        body.write('if (PyList_Check({}))'.format(el.name))
        with body.block():
            body.write('size_t size = PyList_GetSize({});'.format(el.name))
            body.write(el.type.write_var_decl(out))
            body.write('{}.reserve(size);'.format(out))
            body.write('for (size_t index = 0; index < size; ++index)')
            with body.block():
                subel = MVar(name='subel', type=el.type.base)
                body.write('auto subel = PyList_GetItem({}, index);'.format(el.name))
                subout = write_python_read(body, subel)
                body.write('{}.emplace_back(std::move({}));'.format(out, subout))
        body.write('else if (PyTuple_Check({}))'.format(el.name))
        with body.block():
            body.write('size_t size = PyTuple_GetSize({});'.format(el.name))
            body.write(el.type.write_var_decl(out))
            body.write('{}.reserve(size);'.format(out))
            body.write('for (size_t index = 0; index < size; ++index)')
            with body.block():
                subel = MVar(name='subel', type=el.type.base)
                body.write('auto subel = PyTuple_GetItem({}, index);'.format(el.name))
                subout = write_python_read(body, subel)
                body.write('{}.emplace_back(std::move({}));'.format(out, subout))
        body.write('else')
        with body.indent():
            body.write('throw GeneralError() << "Argument [{}] is not a list or tuple.";'.format(el.name)) 
    elif isinstance(el.type, (TInt32, TInt64, TUInt64, TFloat, TString)):
        pass
    else:
        raise AssertionError('Cannot from-python element type {}'.format(el.type))
    return out


def write_python_write(body, el, recurse=None):
    if recurse is None:
        recurse = write_python_write
    out = next(gentemp)
    if isinstance(el.type, MClass):
        body.write('auto {} = raw_{n}_type->tp_new(raw_{n}_type, null, null);'.format(out, n=el.type.oldname))
        body.write('new (&{}->data){}({});'.format(out, el.type.format_type(), el.format_read()))
        out = '(PyObject *){}'.format(out)
    elif isinstance(el.type, TArray):
        # Unused I think
        index = next(gentemp)
        body.write('auto {} = PyTuple_New({}.size());'.format(out, el.format_read()))
        body.write('for (size_t {i} = 0; {i} < {}.size(); ++{i})'.format(el.format_read(), i=index))
        with body.block():
            subin = next(gentemp)
            body.write('auto &{} = {}[{}];'.format(subin, el.format_read(), index))
            subout = write_python_write(body, MVar(name=subin, type=el.type.base), recurse=recurse)
            body.write('PyTuple_SetItem({}, {}, {});'.format(out, index, subout))
    elif isinstance(el.type, (TInt32, TInt64)):
        body.write('auto {} = PyInt_FromLong({});'.format(out, el.name))
    elif isinstance(el.type, TUInt64):
        body.write('auto {} = PyInt_FromSize_t({});'.format(out, el.name))
    elif isinstance(el.type, TFloat):
        body.write('auto {} = PyFloat_FromDouble({});'.format(out, el.name))
    elif isinstance(el.type, TString):
        body.write('auto {} = PyUnicode_FromStringAndSize({n}.c_str(), {n}.length());'.format(out, n=el.name))
    elif isinstance(el.type, MFunction):
        raise AssertionError('Function to-python unimplemented.')
    return out


def format_python_type(el):
    out = ''
    if isinstance(el.type, (MClass, TString, TArray)):
        out = 'PyObject *'.format(el.name)
    elif isinstance(el.type, (TInt32, TInt64, TUInt64)):
        out = 'int '
    elif isinstance(el.type, TFloat):
        out = 'float '
    else:
        raise AssertionError('Unimplemented type {}'.format(el.type))
    return out + el.name


def format_python_type_char(el):
    if isinstance(el.type, (MClass, TString, TArray)):
        return 'O'
    elif isinstance(el.type, TInt32):
        return 'i'
    elif isinstance(el.type, TInt64):
        return 'L'
    elif isinstance(el.type, TUInt64):
        return 'K'
    elif isinstance(el.type, TFloat):
        return 'f'
    else:
        raise AssertionError('Unimplemented type {}'.format(el.type))
    return out + el.name


def write_python_function_wrapper(mod, prefix, method):
    wrapper_name = ''
    wrapper_name = '{}_method_'.format(prefix)
    wrapper_name += method.name
    mod.write('static PyObject *{}({}PyObject *pargs)'.format(
        wrapper_name,
        'pyint_{} *self, '.format(method.parent.name) if method.parent is not None else '',
    ))
    with mod.block():
        for arg in method.args:
            mod.write('{};'.format(format_python_type(arg)))
        mod.write('if (!PyArg_ParseTuple(pargs, "{}", {}))'.format(
            ''.join([format_python_type_char(arg) for arg in method.args]),
            ', '.join([arg.name for arg in method.args]),
        ))
        with mod.indent():
            mod.write('throw GeneralError() << "Arguments invalid.";')  # TODO get real error?
        vals = [write_python_read(mod, arg) for arg in method.args]
        if method.parent is not None:
            access = MAccess(base=MVar(name='self->data', type=method.parent), field=method)
        else:
            access = method
        call = access.format_call(*[MVar(name=val, type=arg.type) for val, arg in zip(vals, method.args)])
        if method.ret is not None and method.ret != void:
            mod.write('auto {} = {};'.format(method.ret.name, call))
            out = write_python_write(mod, method.ret)
            mod.write('return {};'.format(out))
        else:
            mod.write('{};'.format(call))
    mod.write('')
    return wrapper_name


@simpleinit(['base', 'parent'], [])
class MPyFunction:
    def format_meta(self):
        return (
            '{' + 
            '"{}", (PyCFunction){}, {}METH_VARARGS, nullptr'.format(
                self.base.name, self.name, 'METH_STATIC | ' if self.base.static else '') + 
            '},'
        )

    def write_method_decl(self, withdefs):
        mod = Context()
        self.name = write_python_function_wrapper(mod, self.parent.prefix(), self.base)
        return mod.f


@simpleinit(['name', 'type', 'parent'], ['functions'])
class MPyType:
    def prefix(self):
        return '{}_type_{}'.format(self.parent.prefix(), self.name)

    def add_functions(self, function):
        function.parent = self
        self.functions.append(function)

    def write_method_decl(self, withdefs):
        mod = Context()
            
        mod.write('static struct {}'.format(self.prefix()))
        with mod.block():
            mod.write('PyObject_HEAD')
            mod.write(self.type.write_var_decl('data'))
        mod.write('')

        for function in self.functions:
            mod.write(function.write_method_decl(True))

        mod.write('static PyMethodDef {}_methods[] ='.format(self.prefix()))
        with mod.block(';'):
            for function in self.functions:
                mod.write(function.format_meta())
            mod.write('{nullptr}')
        mod.write('')

        mod.write('static void {n}_dealloc({n}_type *self'.format(n=self.prefix()))
        with mod.block():
            mod.write('placement_destroy(self->data);')
            mod.write('Py_TYPE(self)->tp_free(self);')
        mod.write('')

        mod.write('static PyTypeObject {}_type ='.format(self.prefix()))
        with mod.block(';'):
            mod.write('PyVarObject_HEAD_INIT(nullptr, 0)')
            mod.write('"{}.{}", /* tp_name */'.format(self.parent.name, self.name))
            mod.write('sizeof({}_type), /* tp_basicsize */'.format(self.prefix()))
            mod.write('nullptr, /* tp_itemsize */')
            mod.write('(destructor)pyint_{}_dealloc, /* tp_dealloc */'.format(self.prefix()))
            mod.write('nullptr, /* tp_print */')
            mod.write('nullptr, /* tp_getattr */')
            mod.write('nullptr, /* tp_setattr */')
            mod.write('nullptr, /* tp_reserved */')
            mod.write('nullptr, /* tp_repr */')
            mod.write('nullptr, /* tp_as_number */')
            mod.write('nullptr, /* tp_as_sequence */')
            mod.write('nullptr, /* tp_as_mapping */')
            mod.write('nullptr, /* tp_hash */')
            mod.write('nullptr, /* tp_call */')
            mod.write('nullptr, /* tp_str */')
            mod.write('nullptr, /* tp_getattro */')
            mod.write('nullptr, /* tp_setattro */')
            mod.write('nullptr, /* tp_as_buffer */')
            mod.write('Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /* tp_flags */')
            mod.write('"no class documentation", /* tp_doc */')
            mod.write('nullptr, /* tp_traverse */')
            mod.write('nullptr, /* tp_clear */')
            mod.write('nullptr, /* tp_richcompare */')
            mod.write('nullptr, /* tp_weaklistoffset */')
            mod.write('nullptr, /* tp_iter */')
            mod.write('nullptr, /* tp_iternext */')
            mod.write('{}_methods, /* tp_methods */'.format(self.prefix()))
            mod.write('nullptr, /* tp_members */')
            mod.write('nullptr, /* tp_getset */')
            mod.write('nullptr, /* tp_base */')
            mod.write('nullptr, /* tp_dict */')
            mod.write('nullptr, /* tp_descr_get */')
            mod.write('nullptr, /* tp_descr_set */')
            mod.write('nullptr, /* tp_dictoffset */')
            mod.write('nullptr, /* tp_init */')
            mod.write('nullptr, /* tp_alloc */')
            mod.write('nullptr, /* tp_new */')
        mod.write('')

        return mod.f


@simpleinit(['name'], ['functions', 'types'])
class MPyModule:
    def prefix(self):
        return 'pyint_{}'.format(self.name)

    def initname(self):
        return 'PyInit_{}'.format(self.name)

    def add_functions(self, function):
        function.parent = self
        self.functions.append(function)
    
    def add_types(self, pytype):
        pytype.parent = self
        self.types.append(pytype)

    def write_method_decl(self, withdefs):
        mod = Context()

        for pytype in self.types:
            mod.write('//' + '-' * 78)
            mod.write('// {}'.format(pytype.name))
            mod.write(pytype.write_method_decl(True))

        mod.write('//' + '-' * 78)
        for function in self.functions:
            mod.write(function.write_method_decl(True))

        mod.write('static PyMethodDef {}_methods[] ='.format(self.prefix()))
        with mod.block(';'):
            for function in self.functions:
                mod.write(function.format_meta())
            mod.write('{null, null}')
        mod.write('')

        mod.write('static struct PyModuleDef {}_module ='.format(self.prefix()))
        with mod.block(';'):
            mod.write('PyModuleDef_HEAD_INIT,')
            mod.write('"{}",'.format(self.name))
            mod.write('null,')
            mod.write('-1,')
            mod.write('{}_methods,'.format(self.prefix()))
            mod.write('nullptr,')
            mod.write('nullptr,')
            mod.write('nullptr,')
            mod.write('nullptr')
        mod.write('')

        mod.write('PyObject *{}(void)'.format(self.initname()))
        with mod.block():
            for pytype in self.types:
                mod.write('if (PyType_Ready(&{}_type) < 0) return nullptr;'.format(pytype.prefix()))
            mod.write('PyObject *module = PyModule_Create(&{}_module);'.format(self.prefix()))
            mod.write('if (module == null)')
            with mod.indent():
                mod.write('return null;')
            for pytype in self.types:
                mod.write('Py_INCREF(&{}_type);'.format(pytype.prefix()))
                mod.write('PyModule_AddObject(module, "{}", (PyObject *)&{});'.format(pytype.name, pytype.prefix()))
            mod.write('return module;')
        mod.write('')
        return mod.f


def apply(name, model):
    module = MPyModule(name=name)
    for el in model:
        if isinstance(el, MClass):
            pytype = MPyType(name=el.oldname, type=el)
            module.add_types(pytype)
            for data in el.all_methods():
                if data.ret is None:
                    continue
                pytype.add_functions(MPyFunction(base=data))
        elif isinstance(el, MFunction):
            if el.ret is None:
                continue
            module.add_functions(MPyFunction(base=el))
    return [module]
